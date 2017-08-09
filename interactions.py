
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
