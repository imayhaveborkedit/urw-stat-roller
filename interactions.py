from functools import wraps
from collections import defaultdict

from prompt_toolkit.keys import Keys

import statinfo

class StatConstraintState:
    # Selection states
    NONE_SELECTED          = 0x0 # Nothing selected
    SINGLE_SELECTED        = 0x1 # Single number selected (enter pressed once and not moved)
    RANGE_SELECTED         = 0x2 # Range selected (enter, move, enter)
    RANGE_SELECTED_PENDING = 0x3 # Range partially selected (enter, move)

    _default_state = {'state': NONE_SELECTED, 'low': 0, 'high': 0, 'start': 0}

    def __init__(self):
        self._state = defaultdict(self._default_state.copy)

    def for_buffer(self, buffer):
        if buffer not in statinfo.names:
            raise NameError("No such stat")

        return {k:v for k,v in self._state[buffer].items() if k != 'state'}

    def get_cursor_bounds(self, buffer):
        stats1, stats2, numeric, phys = statinfo.groups
        stats = stats1 + stats2

        if buffer in stats:
            return range(18, 35+1)

        # These next two may need some sort of alternate entry method
        # like some slider bar at the bottom

        elif buffer in numeric:
            return range(15, 15+1) # TODO: allow alt entry (f'in")

        elif buffer in phys:
            return range(23, 31+1, 2)

    def listen(self, func):
        @wraps(func)
        def wrapped(event):
            current_buffer = event.current_buffer
            current_buffer_name = event.cli.current_buffer_name
            self._process_event_before(event)

            x = func(event)

            event.previous_buffer = current_buffer
            event.previous_buffer_name = current_buffer_name
            self._process_event_after(event)

            return x
        return wrapped

    def _process_event_before(self, event):
        buffer_name = event.current_buffer.text.split(':')[0]
        key = event.key_sequence[0].key.name # non-character keys are key objects in events
        cursor_pos = event.current_buffer.cursor_position - 17

        full_state = self._state[buffer_name]
        state = full_state['state']

        low, high = sorted((cursor_pos, full_state['start']))

        if key in (Keys.Up.name, Keys.Down.name):
            # Reset selection to single, other option was to set to range
            if state == self.RANGE_SELECTED_PENDING:
                full_state.update(state=self.SINGLE_SELECTED, low=cursor_pos, high=cursor_pos, start=cursor_pos)

        elif key in (Keys.Left.name, Keys.Right.name):
            if state == self.RANGE_SELECTED_PENDING:
                full_state.update(low=low, high=high)

            elif state == self.SINGLE_SELECTED:
                full_state.update(state=self.RANGE_SELECTED_PENDING, low=low, high=high)

        elif key == Keys.Enter.name:
            if state in (self.NONE_SELECTED, self.RANGE_SELECTED):
                full_state.update(state=self.SINGLE_SELECTED, low=cursor_pos, high=cursor_pos, start=cursor_pos)

            elif state == self.RANGE_SELECTED_PENDING:
                if low == high:
                    full_state.update(state=self.SINGLE_SELECTED, low=low, high=high)
                else:
                    full_state.update(state=self.RANGE_SELECTED, low=low, high=high)

    def _process_event_after(self, event):
        last_buffer_name = event.previous_buffer.text.split(':')[0]
        key = event.key_sequence[0].key.name # non-character keys are key objects in events
        last_cursor_pos = event.previous_buffer.cursor_position - 17

        full_state = self._state[last_buffer_name]
        state = full_state['state']

        if key in (Keys.Up.name, Keys.Down.name):
            if state == self.RANGE_SELECTED_PENDING:
                full_state.update(state=self.SINGLE_SELECTED)



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


class InteractiveStatSetup:
    """
    Will post instructions and guide through stat selection process.

    Clear stats and constraints
    Select first buffer
    (if we have race data, place cursor on top of bell curve value)
        (need to consider the no data/dont care button (space?))
    (stat info will be posted as usual)
    Constraints will be entered by the user
        (need to thing about how to do weight/height)

    focus will move to some "start button"
    press enter to begin etc

    """

    def __init__(self, ui):
        self.ui = ui
        self.process_events = True

    def on_event(self, event):
        if not self.process_events:
            return

    def start(self):
        ...
