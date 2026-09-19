"""What you set before a run starts.

This replaces the old fixed modes. Rather than picking "Brisk" or "Marathon"
and hoping it means what you want, you set the three multipliers yourself and
the menu tells you what each one does. A run keeps the settings it started
with, and they are saved with it.
"""

import math

#: Quarter steps where you actually play, widening once the numbers get
#: big enough that quarters would take a hundred presses. Every boundary is
#: a multiple of the step below it, so a value never lands off the grid.
STEPS = [(4.0, 0.25), (10.0, 0.5), (25.0, 1.0), (100.0, 5.0),
         (float("inf"), 25.0)]


def step_at(value):
    """The increment to use around `value`."""
    for ceiling, step in STEPS:
        if value < ceiling:
            return step
    return STEPS[-1][1]


class Knob:
    __slots__ = ("attr", "name", "blurb", "low", "high", "default")

    def __init__(self, attr, name, blurb, low, high, default):
        self.attr = attr
        self.name = name
        self.blurb = blurb
        self.low = low
        self.high = high
        self.default = default

    def clamp(self, value):
        try:
            value = float(value)
        except (TypeError, ValueError):
            return self.default
        return max(self.low, min(value, self.high))

    def nudge(self, value, direction):
        """Move to the next clean step, landing on a round number every time.

        A value that came in off the grid -- from a flag, or a save made
        before these bands -- is pulled onto it rather than pushed a whole
        step past, so 0.9 goes up to 1.0 and 1.2 comes down to it.
        """
        value = self.clamp(value)
        step = step_at(value if direction > 0 else max(value - 1e-9, 0.0))
        grid = value / step
        moved = (math.ceil(grid + 1e-9) if direction > 0
                 else math.floor(grid - 1e-9)) * step
        return self.clamp(round(moved, 4))

    def describe(self, value):
        if abs(value - 1.0) < 1e-9:
            return "normal"
        if self.attr == "time_scale":
            return (f"{value:g}x - one game second takes "
                    f"{1 / value:.2f} real ones")
        if self.attr == "event_scale" and value == 0:
            return "off - nothing will attack you"
        return f"{value:g}x"


KNOBS = [
    Knob("time_scale", "Clock speed",
         "How fast game time runs against real time.", 0.25, 20.0, 1.0),
    Knob("event_scale", "Event speed",
         "How fast threats grow and integrity falls, in real time. "
         "Zero switches warfare off entirely.", 0.0, 10.0, 1.0),
    Knob("cost_scale", "Project costs",
         "What projects and research cost.", 0.0, 1000.0, 1.0),
    Knob("hw_scale", "Hardware costs",
         "What machines, drones, rigs and units cost.", 0.0, 1000.0, 1.0),
]
BY_ATTR = {k.attr: k for k in KNOBS}


class Setup:
    """A set of knob values, ready to stamp onto a new game."""

    def __init__(self, **values):
        for knob in KNOBS:
            setattr(self, knob.attr, knob.clamp(values.get(knob.attr,
                                                           knob.default)))

    def apply(self, game):
        for knob in KNOBS:
            setattr(game, knob.attr, getattr(self, knob.attr))
        game.mode = self.label()
        return game

    def label(self):
        parts = [f"{k.name.split()[0].lower()} x{getattr(self, k.attr):g}"
                 for k in KNOBS if abs(getattr(self, k.attr) - 1.0) > 1e-9]
        return ", ".join(parts) if parts else "standard"

    def as_dict(self):
        return {k.attr: getattr(self, k.attr) for k in KNOBS}


def default():
    return Setup()


def from_game(game):
    return Setup(**{k.attr: getattr(game, k.attr, k.default) for k in KNOBS})


def label_of(game):
    """What to show in the HUD for a run already in progress."""
    return from_game(game).label()
