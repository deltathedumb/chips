"""The act registry.

An act is a number, a name, a tick and a panel builder that returns plain
data. Both front ends render that same data, so adding an act never means
writing layout twice.

Nothing in this file knows what the game is *about*. The acts themselves --
their names, their ticks, their panels -- arrive from content through
`api.add_act`, which is what makes the base game a mod like any other.
"""

from pclengine.fmt import small


# --------------------------------------------------------------------------
# panel helpers, shared by every act
# --------------------------------------------------------------------------
def row(label, value, key=None, hint=None, bar=None, warn=False):
    out = {"label": label, "value": value}
    if key:
        out["key"] = key
    if hint:
        out["hint"] = hint
    if bar is not None:
        out["bar"] = max(0.0, min(1.0, bar))
    if warn:
        out["warn"] = True
    return out


def panel(title, rows):
    return {"title": title, "rows": rows}


def converter_rows(g, stages):
    """One row per stage of a production chain, with the slowest flagged."""
    slowest = min(stages, key=lambda s: s[1]) if stages else None
    out = []
    for label, capacity, value, key, hint in stages:
        out.append(row(label, value, key=key, hint=hint,
                       warn=(slowest is not None and label == slowest[0]
                             and capacity > 0)))
    return out


def chain_rows(g, stages, unit="g/s"):
    """Rows for a production chain, warning on whichever stage is the limit."""
    slowest = min(stages, key=lambda s: s[1])[0] if stages else None
    return [row(name, f"{small(capacity)} {unit}", warn=(name == slowest),
                hint="this stage is the bottleneck" if name == slowest
                else None)
            for name, capacity in stages]


# --------------------------------------------------------------------------
# Dials
# --------------------------------------------------------------------------
class Dial:
    """A 0-10 setting an act asks you to manage.

    Every dial trades the same way: turn it up for more output now and more
    of some risk. It is what gives an act a decision rather than a purchase.
    """

    __slots__ = ("key", "act", "name", "blurb", "high_note")

    def __init__(self, key, act, name, blurb, high_note):
        self.key = key
        self.act = act
        self.name = name
        self.blurb = blurb
        self.high_note = high_note


DIALS = []
DIAL_BY_KEY = {}
DIAL_MAX = 10


def add_dial(spec):
    DIALS.append(spec)
    DIAL_BY_KEY[spec.key] = spec
    return spec


def dials_for(act):
    return [d for d in DIALS if d.act == act]


def dial(game, key):
    return game.dials.get(key, 0)


def adjust_dial(game, key, delta):
    spec = DIAL_BY_KEY.get(key)
    if spec is None or spec.act != game.act:
        return False
    game.dials[key] = max(0, min(DIAL_MAX, dial(game, key) + int(delta)))
    return True


def dial_row(game, key):
    spec = DIAL_BY_KEY[key]
    value = dial(game, key)
    entry = row(spec.name, f"{value} / {DIAL_MAX}",
                hint=spec.blurb + "  Higher: " + spec.high_note,
                bar=value / DIAL_MAX, warn=value >= 8)
    entry["dial"] = key
    return entry


# --------------------------------------------------------------------------
# the registry
# --------------------------------------------------------------------------
class Act:
    __slots__ = ("number", "key", "name", "blurb", "tick", "panels",
                 "material", "keys", "target", "complete", "on_key")

    def __init__(self, number, key, name, blurb, tick, panels, material,
                 keys=()):
        self.number = number
        self.key = key
        self.name = name
        self.blurb = blurb
        self.tick = tick              # a Game method name, or fn(g, dt)
        self.panels = panels          # fn(g) -> [panel, ...]
        self.material = material      # fn(g) -> panel for the left column
        self.keys = keys              # footer hint
        self.target = None            # how much of the act's stuff it works
        self.complete = None          # optional fn(g) -> bool, overrides target
        self.on_key = None            # optional fn(g, key), content's verbs

    def run(self, game, dt):
        if callable(self.tick):
            self.tick(game, dt)
        elif self.tick:
            getattr(game, self.tick)(dt)


def _nothing_panels(g):
    return [panel("NO CONTENT", [
        row("no acts are registered", "-",
            hint="enable a content mod, or the base game, and start again")])]


#: Stands in when no content has registered anything, so an engine with no
#: mods loaded still renders and still says why it is empty.
BLANK = Act(0, "blank", "NO CONTENT LOADED",
            "Nothing has registered an act.", None,
            _nothing_panels, lambda g: panel("NOTHING", []))

ALL = []
BY_NUMBER = {}


def get(number):
    if number in BY_NUMBER:
        return BY_NUMBER[number]
    return ALL[0] if ALL else BLANK


def register(act):
    """Used by content mods, including the base game."""
    ALL.append(act)
    ALL.sort(key=lambda a: a.number)
    BY_NUMBER[act.number] = act
    return act


def reset():
    """Forget every act. `loader.load` registers them all again."""
    del ALL[:]
    BY_NUMBER.clear()
    del DIALS[:]
    DIAL_BY_KEY.clear()


def last_number():
    return max((a.number for a in ALL), default=0)


def name_of(number):
    act = BY_NUMBER.get(number)
    return act.name if act else ""
