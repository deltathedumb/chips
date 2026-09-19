"""The input stack: what a key means depends on what is on top.

Every keypress from either front end is offered to each active layer in
priority order, and the first layer to take it wins. Nothing below sees it.

    overlay   1000   a full-screen thing owns every key while it is open
    chrome     800   quit, menu, help, save, resize, batch, panels
    panel      600   whichever HUD tab you are looking at
    act        400   what this act does with h, j, arrows
    projects   200   1-8, when nothing above wanted them
    system     100   etch, bandwidth, the compute burst

Written as an if/else chain this went wrong in ways that were invisible: `q`
quit out of the tech tree because it was tested before the overlay, and the
tree's own `q` was unreachable code. As a stack, precedence is data -- you
can print it, test it, and see what shadows what.

The same table decides which buttons the browser draws, so a button can
never offer a key the stack would not route. That is the point of building
it once rather than twice.
"""

#: What `handle` returns to mean "I did not want this key".
PASS = None


class Bind:
    """One key that does something right now, and what to call it."""

    __slots__ = ("key", "label", "hint", "layer")

    def __init__(self, key, label, hint="", layer=""):
        self.key = key
        self.label = label
        self.hint = hint
        self.layer = layer

    def as_dict(self):
        return {"key": self.key, "label": self.label, "hint": self.hint,
                "layer": self.layer}


class Layer:
    """One level of the stack."""

    __slots__ = ("name", "priority", "handle", "active", "binds", "footer",
                 "exclusive")

    def __init__(self, name, priority, handle, active=None, binds=None,
                 footer=None, exclusive=False):
        self.name = name
        self.priority = priority
        #: fn(game, key) -> an action, True, or PASS to let it fall through.
        self.handle = handle
        #: fn(game) -> bool. A layer that is not active is not offered keys.
        self.active = active
        #: fn(game) -> [Bind]. What this layer would take right now.
        self.binds = binds
        #: fn(game) -> str, for the one-line key hint along the bottom.
        self.footer = footer
        #: An exclusive layer hides everything below it. Not just from the
        #: keyboard -- from the key list and the buttons too, so the game
        #: never offers you something that would do nothing.
        self.exclusive = exclusive

    def is_active(self, g):
        return True if self.active is None else bool(self.active(g))


LAYERS = []


def add_layer(layer):
    LAYERS.append(layer)
    LAYERS.sort(key=lambda l: -l.priority)
    return layer


def reset():
    del LAYERS[:]


def active(g):
    """The live layers, cut off at the first exclusive one."""
    out = []
    for layer in LAYERS:
        if not layer.is_active(g):
            continue
        out.append(layer)
        if layer.exclusive:
            break
    return out


def dispatch(g, key):
    """Offer a key down the stack. Returns the first action produced."""
    for layer in active(g):
        result = layer.handle(g, key)
        if result is not PASS and result is not False:
            return None if result is True else result
    return None


def bindings(g):
    """Every key that does something right now, highest layer first.

    A key claimed by two layers belongs to the higher one, because that is
    what pressing it would do -- so this is the truth about the keyboard,
    not a wish list.
    """
    out, seen = [], set()
    for layer in active(g):
        if layer.binds is None:
            continue
        for bind in layer.binds(g):
            if not bind.key or bind.key in seen:
                continue
            seen.add(bind.key)
            bind.layer = layer.name
            out.append(bind)
    return out


def footer(g):
    """The bottom line: the topmost layer that has something to say."""
    for layer in active(g):
        if layer.footer is None:
            continue
        text = layer.footer(g)
        if text:
            return text
    return ""


def describe(g):
    """[(layer name, [keys])] -- what is on the stack and what it owns.

    For tests and for the developer panel: if a key is not doing what you
    expect, this says which layer ate it.
    """
    claimed, out = set(), []
    for layer in active(g):
        keys = []
        if layer.binds is not None:
            for bind in layer.binds(g):
                if bind.key and bind.key not in claimed:
                    claimed.add(bind.key)
                    keys.append(bind.key)
        out.append((layer.name, keys))
    return out
