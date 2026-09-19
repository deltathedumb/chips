"""Multipliers content hangs off the engine's own numbers.

The engine works out how much research a lab floor makes and what a defender
costs. It has no opinion about whether being famous should make either of
those go further -- that is a claim about a particular game. So content
registers a multiplier by name and the engine applies whatever is there.

    api.modifier("research_output", lambda g: g.brand ** 0.4)

Several mods may modify the same number; they multiply together, which is
the only combining rule that does not depend on load order.
"""

#: name -> [fn(game) -> float]
MODIFIERS = {}


def add(name, fn):
    MODIFIERS.setdefault(name, []).append(fn)
    return fn


def of(g, name):
    """The product of every multiplier registered under `name`."""
    total = 1.0
    for fn in MODIFIERS.get(name, ()):
        try:
            value = float(fn(g))
        except Exception:            # a broken mod must not stop the tick
            continue
        if value == value and value >= 0.0:      # no nan, no negative prices
            total *= value
    return total


def reset():
    MODIFIERS.clear()
