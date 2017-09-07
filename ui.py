import os
import re
import time
import bisect
import textwrap
import threading
import traceback

from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.document import Document
from prompt_toolkit.enums import DEFAULT_BUFFER
from prompt_toolkit.filters import Condition
from prompt_toolkit.interface import CommandLineInterface
from prompt_toolkit.key_binding.registry import Registry
from prompt_toolkit.key_binding.bindings.named_commands import get_by_name
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout.containers import VSplit, HSplit, Window
from prompt_toolkit.layout.controls import BufferControl, FillControl
from prompt_toolkit.layout.dimension import LayoutDimension as D
from prompt_toolkit.layout.margins import ScrollbarMargin, ConditionalMargin
from prompt_toolkit.layout.utils import token_list_to_text
from prompt_toolkit.shortcuts import create_eventloop
from prompt_toolkit.token import Token

import scroll
import memhook
import statinfo
import interactions


help_text = textwrap.dedent(
    '''
    Hello this is the help text I will write the rest of this later.

    Use PageUp and PageDown to scroll this window when a scrollbar is present.

    ''')

stat_args = {
    'dont_extend_width': True,
    'dont_extend_height': True,
    'always_hide_cursor': True,
    'wrap_lines': True,
    'height': D.exact(1),
    'width': D.exact(38),
}

def hpad(height, ch=' ', token=Token.Padding):
    return Window(height=D.exact(height), content=FillControl(ch, token=token))

def vpad(width, ch=' ', token=Token.Padding):
    return Window(width=D.exact(width), content=FillControl(ch, token=token))

def make_stat_doc(name, value=4):
    return Document(statinfo.Stats.format(name, value))

def make_stat_window(name):
    name = statinfo.Stats.get(name).buffername
    return Window(content=BufferControl(buffer_name=name), **stat_args)

def _is_main_thread():
    return threading.current_thread() is threading.main_thread()


class BufferState:
    order = list(reversed(
        [stat.buffername for stat in statinfo.Stats.all()] + [DEFAULT_BUFFER]))

    def __init__(self, position=0):
        self.position = position

    @property
    def current(self):
        return self.order[self.position]

    @property
    def current_stat(self):
        b = statinfo.Stats.get_name(self.current)
        return b.name if b else None

    def up(self):
        self.position = min(len(self.order) - 1, self.position + 1)
        return self.order[self.position]

    def down(self):
        self.position = max(0, self.position - 1)
        return self.order[self.position]

    def goto(self, pos):
        if not 0 <= pos <= len(self.order):
            raise IndexError(f"Invalid buffer position {pos} (0 <= {pos} <= {len(self.order)})")

        self.position = pos
        return self.order[pos]

    def first(self):
        self.position = len(self.order) - 1
        return self.order[self.position]

    def last(self):
        self.position = 0
        return self.order[0]


class HelpItem:
    def __init__(self, name, *keys, info=''):
        self.name = name
        self.keys = keys
        self.info = info

    def _gen_keycode(self):
        return ', '.join(self.keys)

    # TODO: Textwrap
    def _format_info(self):
        return self.info

    def render_tokens(self):
        return [(Token.Space, ' '),
                (Token.HelpKeyCode, self._gen_keycode()),
                (Token.Space, ' '),
                (Token.HelpName, self.name),
                (Token.SpaceSep, ' - '),
                (Token.HelpInfo, self._format_info())]


class Ui:
    repeated_message_pattern = re.compile(r'[ ]\((?P<num>[0-9]+)x\)$')

    def __init__(self, hook):
        self.hook = hook

        self._built = False
        self._scroll_state = 1
        self._help_showing = False
        self._last_roll = None
        self._help_items = []

        self.stat_state = {name: 0 for name in statinfo.names}
        self.stat_state['Rerolls'] = 0

        self.stat_constraints = interactions.StatConstraintState()


    @property
    def info_wb(self):
        return self.info_window, self.buffers['INFO_BUFFER']


    def _increment_repeated_msg(self, first=False):
        if first:
            return lambda line: line.rstrip(' ') + ' (2x)'
        else:
            incr = lambda match: f" ({str(int(match.group('num')) + 1)}x)"
            return lambda line: self.repeated_message_pattern.sub(incr, line)

    def _print(self, *args, sep=' ', pre='\n', **kwargs):
        new_msg = sep.join(str(x) for x in args)

        buffer = self.buffers['MSG_BUFFER']

        last_line = buffer.document.current_line
        line_parts = self.repeated_message_pattern.split(last_line)
        last_msg = line_parts[0]

        if last_msg != new_msg:
            buffer.insert_text(pre + new_msg)
        else:
            buffer.transform_current_line(self._increment_repeated_msg(first=len(line_parts) == 1))
            buffer.cursor_right(len(buffer.document.current_line))


    def print(self, *args, **kwargs):
        if _is_main_thread():
            self._print(*args, **kwargs)
        else:
            self.run_in_executor(self._print, *args, **kwargs)
            self.redraw()


    # TODO
    def prompt(self, message, end='>'):
        ...


    def _update_info_text(self, buff=None):
        buff = buff or self.stat_buffer_state.current
        buffer = statinfo.Stats.get_name(buff)

        if buffer:
            buffername = buffer.name
        else:
            return

        text = statinfo.extra_info.get(buffername, f'TODO: {buffername} text')

        if text:
            self.set_info_text(text)
            self._help_showing = False


    def _focus(self, buffer, cli=None):
        cli = cli or self.cli

        cli.focus(buffer)
        self._update_info_text()


    # Don't question these double half scrolls this is completely correct
    def _scroll_up(self):
        if self._scroll_state < 0:
            scroll.scroll_half_page_up(*self.info_wb)
            scroll.scroll_half_page_up(*self.info_wb)

        scroll.scroll_half_page_up(*self.info_wb)
        self._scroll_state = 1

    def _scroll_down(self):
        if self._scroll_state > 0:
            scroll.scroll_half_page_down(*self.info_wb)
            scroll.scroll_half_page_down(*self.info_wb)

        scroll.scroll_half_page_down(*self.info_wb)
        self._scroll_state = -1


    # Setup functions

    def _gen_buffers(self):
        self.stat_buffer_state = BufferState()

        return {
            DEFAULT_BUFFER: Buffer(
                initial_document=Document(""),
                is_multiline=False, read_only=False),

            'INFO_BUFFER': Buffer(
                initial_document=Document(),
                is_multiline=True),

            'REROLL_STAT_BUFFER': Buffer(
                initial_document=make_stat_doc('Rerolls', 0),
                is_multiline=False),

            'MSG_BUFFER': Buffer(
                initial_document=Document(),
                is_multiline=True),

            **{
               stat.buffername: Buffer(initial_document=make_stat_doc(stat.name))
               for stat in statinfo.Stats.all()
            }
        }


    # TODO: Lexers
    # from pygments.lexers import HtmlLexer
    # from prompt_toolkit.layout.lexers import PygmentsLexer
    # BufferControl(lexer=PygmentsLexer(HtmlLexer))

    def _gen_layout(self):
        stat_windows = []

        for stat_group in statinfo.groups:
            for stat in stat_group:
                stat_windows.append(make_stat_window(stat))

            stat_windows.append(vpad(1))

        stat_windows.append(Window(
            content=BufferControl(buffer_name='REROLL_STAT_BUFFER'), **stat_args))
        stat_windows.append(vpad(1))

        @Condition
        def scroll_cond(cli):
            if self.info_window.render_info is None:
                return True

            try:
                l = self.buffers['INFO_BUFFER'].document.line_count
                return self.info_window.render_info.window_height < l
            except:
                return True

        self.info_window = Window(
            content=BufferControl(buffer_name='INFO_BUFFER'),
            dont_extend_width=True, wrap_lines=True, always_hide_cursor=True,
            right_margins=[ConditionalMargin(
                ScrollbarMargin(display_arrows=True), scroll_cond)
            ])

        return HSplit([
            hpad(1),
            VSplit([
                vpad(1),
                HSplit(stat_windows),
                vpad(2), # idk why there's an extra space on the stats
                self.info_window,
                vpad(1)
            ]),
            hpad(1),
            Window(content=BufferControl(buffer_name='MSG_BUFFER'),
                   height=D.exact(3), wrap_lines=True),
            Window(content=BufferControl(buffer_name=DEFAULT_BUFFER),
                   height=D.exact(1), always_hide_cursor=True)
        ])


    def _gen_bindings(self):
        registry = Registry()
        bind = registry.add_binding

        def bind_with_help(*args, name, info='', **kwargs):
            def dec(func):
                _info = func.__doc__ or info
                self._help_items.append(HelpItem(name, *args, info=_info))

                return bind(*args, **kwargs)(func)
            return dec

        def ensure_cursor_bounds(buffer, pos, valids=None):
            buffer_stat = self.stat_buffer_state.current_stat

            if not buffer_stat:
                return

            if valids is None:
                valids = self.stat_constraints.get_cursor_bounds(buffer_stat)

            if pos not in valids:
                valids = sorted(valids)
                pos_index = bisect.bisect_left(valids, pos)
                requested_pos = pos
                pos = valids[min(pos_index, len(valids)-1)]

                # if we wind up at the same spot, check to see if there's a non-sequential spot
                if buffer.cursor_position == pos:
                    if requested_pos < pos and pos > valids[0]:
                        pos = valids[max(0, pos_index-1)]
                    elif pos < valids[-1]:
                        pos = valids[min(pos_index+1, len(valids)-1)]

            buffer.cursor_position = pos

        @bind(Keys.Left)
        @self.stat_constraints.listen
        def _(event):
            buff = event.current_buffer
            new_pos = buff.cursor_position + buff.document.get_cursor_left_position(count=event.arg)
            ensure_cursor_bounds(buff, new_pos)

        @bind(Keys.Right)
        @self.stat_constraints.listen
        def _(event):
            buff = event.current_buffer
            new_pos = buff.cursor_position + buff.document.get_cursor_right_position(count=event.arg)
            ensure_cursor_bounds(buff, new_pos)
        # TODO: set all stat buffers with no value set to have the same cursor_position

        @bind(Keys.Up)
        @self.stat_constraints.listen
        def _(event):
            self._focus(self.stat_buffer_state.up())
            buff = event.cli.current_buffer
            ensure_cursor_bounds(buff, buff.cursor_position)

        @bind(Keys.Down)
        @self.stat_constraints.listen
        def _(event):
            self._focus(self.stat_buffer_state.down())
            buff = event.cli.current_buffer
            ensure_cursor_bounds(buff, buff.cursor_position)


        @bind(Keys.ControlC)
        def _(event):
            event.cli.set_return_value(None)

        @bind_with_help('?', name='Help', info="Shows a help screen")
        def _(event):
            if self._help_showing:
                self._help_showing = False
                self._update_info_text()
                return

            self.set_info_text(help_text)
            self._help_showing = True

        @bind_with_help('t', name='Reroll test')
        def _(event):
            self.print("Dispatching runner")

            def do():
                self.print("ok running")

                num = 50
                t0 = time.time()

                for x in range(num):
                    # self.reroll(delay=0.017, warning="WARNING SAME STATS ROLLED")
                    self.reroll(delay=0.09, retry_delay=0.05, retry=1)
                    self.print("Rolled")


                t1 = time.time()
                self.print(f'Rolled {num} times in {t1-t0:.4f}', 'sec')

            event.cli.eventloop.run_in_executor(do)
            self.print("alrighty then")

        @bind_with_help('r', name='Reroll')
        def _(event):
            l = self.reroll()
            self.set_stats(**self.hook.zip(l))

        @bind_with_help('e', name='Update stats')
        def _(event):
            self.set_stats(**self.hook.zip(self.hook.read_all()))

        @bind('a')
        def _(event):
            self.print("Showing cursor")
            memhook.Cursor.show()

        @bind('s')
        def _(event):
            self.print("Hiding cursor")
            memhook.Cursor.hide()

        @bind_with_help('E', name='Embed IPython')
        def _(event):
            def do():
                self, event # behold the magic of closures and scope

                __import__('IPython').embed()
                os.system('cls')

            event.cli.run_in_terminal(do)

        @bind(Keys.PageUp)
        def _(event):
            self._scroll_up()

        @bind(Keys.PageDown)
        def _(event):
            self._scroll_down()

        @bind('-')
        def _(event):
            self.print("got random stats")
            self.set_stats(**memhook.get_random_stats())

        @Condition
        def _in_stat_buffer(cli):
            return any(b == cli.current_buffer for n,b in self.buffers.items() if n.endswith("_STAT_BUFFER"))

        @bind(Keys.Enter, filter=_in_stat_buffer)
        @self.stat_constraints.listen
        def _(event):
            buf = event.cli.current_buffer
            self.set_info_text(f"Enter on buffer {buf} at {buf.cursor_position}")

        return registry


    def _add_events(self):
        def default_buffer_changed(_):
            self.buffers['INFO_BUFFER'].reset(self.buffers[DEFAULT_BUFFER].document)

        self.buffers[DEFAULT_BUFFER].on_text_changed += default_buffer_changed

    def _finalize_build(self):
        self.set_info_text(help_text)

        self.print("UnReal World Stat Roller v2.0")
        self.print("Press ? for help\n")

        self._memreader = memhook.MemReader(self)
        self._memreader.start()

        memhook.Cursor.link(self.cli)


    def build(self):
        self.buffers = self._gen_buffers()
        self.layout = self._gen_layout()
        self.registry = self._gen_bindings()

        self._add_events()

        self.application = Application(
            layout=self.layout,
            buffers=self.buffers,
            key_bindings_registry=self.registry,
            mouse_support=True,
            use_alternate_screen=True)

        self.cli = CommandLineInterface(
            application=self.application, eventloop=create_eventloop())

        self._finalize_build()

        self._built = True
        return self


    def run(self, build=True):
        if build and not self._built:
            self.build()

        elif not self._built:
            raise RuntimeError("UI has not been built yet")

        try:
            self.cli.run()
        finally:
            self.cli.eventloop.close()

    def redraw(self):
        if _is_main_thread():
            self.cli._redraw()
        else:
            self.cli.invalidate()

    def run_in_executor(self, func, *args, **kwargs):
        self.cli.eventloop.call_from_executor(lambda: func(*args, **kwargs))

    def reroll(self, **kw):
        # noinspection PyArgumentList
        new_stats = self.hook.safe_reroll(**kw)

        self.set_stats(**self.hook.zip(new_stats))
        self.stat_state['Rerolls'] += 1

        self.redraw()

    def set_stat(self, stat, value):
        self.stat_state[stat] = value
        self.buffers[statinfo.Stats.get(stat).buffername].reset(
            make_stat_doc(stat, value))

    def set_stats(self, **stats):
        for stat, value in stats.items():
            self.set_stat(stat, value)

    def _make_info_text(self, text):
        parts = str(text).strip().split('\n\n')
        filled_parts = [textwrap.fill(t, 35) for t in parts]
        return '\n\n'.join(filled_parts)

    def set_info_text(self, text):
        text = self._make_info_text(text)
        self.buffers['INFO_BUFFER'].reset(Document(text, cursor_position=0))

    def append_info_text(self, text, sep='\n'):
        text = self._make_info_text(text)
        buffer = self.buffers['INFO_BUFFER']

        newdoc = Document(buffer.document.text + sep + text,
                          cursor_position=buffer.document.cursor_position)

        buffer.reset(newdoc)
        buffer.on_text_changed.fire()

    def _make_help_text(self):
        return help_text

    def on_error(self, *args):
        self.print(f"An error has occurred: {args[1]}")
        traceback.print_exception(*args)

# TODO:
#   Race info and stat bounds helpers/warnings
#   Cheat mode, turn all the text hacker green
#     Undo button (stat history)
#     Custom roll bounds and distribution (generate and set)
