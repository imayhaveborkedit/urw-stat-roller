import re
import time
import textwrap
import threading

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
from prompt_toolkit.shortcuts import create_eventloop
from prompt_toolkit.token import Token

import statinfo
import memhook
import scroll


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
    def at(self):
        return self.order[self.position]

    def up(self):
        self.position = min(len(self.order) - 1, self.position + 1)
        return self.order[self.position]

    def down(self):
        self.position = max(0, self.position - 1)
        return self.order[self.position]

    def first(self):
        self.position = len(self.order) - 1
        return self.order[self.position]

    def last(self):
        self.position = 0
        return self.order[self.position]


class StatConstraint:
    def __init__(self, stat, *, lower, upper, min, max, value=None):
        if upper > max:
            raise ValueError(f"Upper bound cannot be greater than max value ({upper} > {max})")

        if lower < min:
            raise ValueError(f"Lower bound cannot be less than than min value ({lower} > {min})")

        if upper < lower:
            raise ValueError(f"Upper bound cannot be lower than lower bound ({upper} < {lower}")

        self.stat = stat
        self.lower = lower
        self.upper = upper
        self.min = min
        self.max = max
        self.value = None

        self.low_token = self.high_token = ' '
        self.mid_token = '-'
        self.mid_low_bound_token = '>'
        self.mid_high_bound_token = '<'
        self.mid_same_bound_token = 'O'
        self.valid_token = '@'
        self.invalid_token = 'x'

    def set(self, value):
        self.value = min(self.upper, max(self.lower, value))
        return self.value

    def is_in_bounds(self, value):
        return self.lower <= value <= self.upper

    def is_valid(self, value):
        return self.min <= value <= self.max

    def visualize(self, value=None):
        if value is not None:
            if not self.is_valid(value):
                raise ValueError(f"Value not within bounds ({self.min} <= {value} <= {self.max})")

            elif not self.is_in_bounds(value) and self.invalid_token is None:
                value = None

        total_range = self.max - self.min
        ok_range = self.upper - self.lower

        low = self.low_token * (self.lower - 1)
        high = self.high_token * (total_range - ok_range - len(low))

        if self.lower == self.upper:
            mid = self.mid_same_bound_token
        else:
            mid = (self.mid_token * (self.upper - self.lower - 1)).join(
                self.mid_low_bound_token + self.mid_high_bound_token)

        if value is not None:
            chars = list(f"[{low}{mid}{high}]")
            t = self.valid_token if self.is_in_bounds(value) else self.invalid_token
            chars[value - self.min + 1] = t

            return ''.join(chars)
        else:
            return f"[{low}{mid}{high}]"


class Ui:
    repeated_message_pattern = re.compile(r'[ ]\((?P<num>[0-9]+)x\)$')

    def __init__(self, hook):
        self.hook = hook

        self._built = False
        self._scroll_state = 1
        self._help_showing = False
        self._last_roll = None

        self.stat_state = {name: 0 for name in statinfo.names}
        self.stat_state['Rerolls'] = 0


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
            self.cli.eventloop.call_from_executor(lambda: self._print(*args, **kwargs))


    def prompt(self, message, end='>'):
        ...


    def _update_info_text(self, buff=None):
        buff = buff or self.stat_buffer_state.at
        buffer = statinfo.Stats.get_name(buff)

        if buffer:
            buffername = buffer.name
        else:
            return

        text = statinfo.extra_info.get(buffername, f'TODO: {buffername} text')

        if text:
            self.set_info_text(text)


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
                r = self.info_window.render_info
                return r.window_height < l
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

        registry.add_binding(Keys.Left)(get_by_name('backward-char'))
        registry.add_binding(Keys.Right)(get_by_name('forward-char'))

        @registry.add_binding(Keys.ControlC)
        def _(event):
            event.cli.set_return_value(None)

        @registry.add_binding('?')
        def _(event):
            if self._help_showing:
                self._help_showing = False
                self._update_info_text()
                return

            self.set_info_text(help_text)
            self._help_showing = True

        @registry.add_binding(Keys.Up)
        def _(event):
            self._focus(self.stat_buffer_state.up())

        @registry.add_binding(Keys.Down)
        def _(event):
            self._focus(self.stat_buffer_state.down())

        @registry.add_binding('t')
        def _(event):
            # self.print("Dispatching runner")

            def do():
                # self.print("ok running")
                # event.cli.eventloop.call_from_executor(lambda: self.print("still good"))

                t0 = time.time()
                for x in range(50):
                    # self.reroll(delay=0.017, warning="WARNING SAME STATS ROLLED")
                    self.reroll(delay=0.017)


                t1 = time.time()
                self.print(f'Rolled 100 times in {t1-t0:.4f}', 'sec')

            event.cli.eventloop.run_in_executor(do)
            # self.print("alrighty then")

        @registry.add_binding('r')
        def _(event):
            l = self.hook.reroll()
            self.set_stats(**self.hook.zip(l))

        @registry.add_binding('e')
        def _(event):
            self.set_stats(**self.hook.zip(self.hook.read_all()))

        @registry.add_binding('l')
        def _(event):
            self.print(f"testing executor in {__import__('threading').currentThread()}")

            def do():
                self.print(f'ok whatever {__import__("threading").currentThread()}')
                # event.cli.eventloop.call_from_executor(lambda: )

            event.cli.eventloop.run_in_executor(do)
            self.print("ok sure done")

        @registry.add_binding('o')
        def _(event):
            self.append_info_text('ok more text here')

        @registry.add_binding(Keys.PageUp)
        def _(event):
            self._scroll_up()

        @registry.add_binding(Keys.PageDown)
        def _(event):
            self._scroll_down()

        @registry.add_binding('-')
        def _(event):
            self.print("got random stats")
            self.set_stats(**memhook.get_random_stats())

        @Condition
        def _f(cli):
            return any(b == cli.current_buffer for n,b in self.buffers.items() if n.endswith("_STAT_BUFFER"))

        @registry.add_binding(Keys.Enter, filter=_f)
        def _(event):
            buf = event.cli.current_buffer
            self.set_info_text(f"Enter on buffer {buf} at {buf.cursor_position}")

        return registry


    def _add_events(self):
        def default_buffer_changed(_):
            self.buffers['INFO_BUFFER'].reset(self.buffers[DEFAULT_BUFFER].document)

        self.buffers[DEFAULT_BUFFER].on_text_changed += default_buffer_changed


    def build(self, alt=True):
        self.buffers = self._gen_buffers()
        self.layout = self._gen_layout()
        self.registry = self._gen_bindings()

        self._add_events()

        self.application = Application(
            layout=self.layout,
            buffers=self.buffers,
            key_bindings_registry=self.registry,
            mouse_support=True,
            use_alternate_screen=alt)

        self.cli = CommandLineInterface(
            application=self.application, eventloop=create_eventloop())

        self.set_info_text("TODO: Startup text")

        self.print("UnReal World Stat Roller v2.0")
        self.print("Press ? for help\n")

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

    def _redraw(self):
        if _is_main_thread():
            self.cli._redraw()
        else:
            self.cli.invalidate()

    def reroll(self, *, delay=None, ensure_change=True, warning=None):
        new_stats = self.hook.reroll(delay=delay)

        if self._last_roll and self._last_roll == new_stats:
            if warning:
                self.print(warning)

            # TODO: add brakout failsafe
            count = 0
            while new_stats == self._last_roll and count < 50:
                time.sleep(0.001)
                new_stats = self.hook.read_all()
                count += 1

                if count == 10:
                    self.print("Waited too long and gave up")

        self._last_roll = new_stats

        self.set_stats(**self.hook.zip(new_stats))
        self.stat_state['Rerolls'] += 1

        self._redraw()

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


# TODO:
#   Race info and stat bounds helpers/warnings
#   Cheat mode, turn all the text hacker green
#     Undo button (stat history)
#     Custom roll bounds and distribution (generate and set)
