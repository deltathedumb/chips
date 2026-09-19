"""Which panels the right-hand column is showing.

TAB cycles between the act's own controls, warfare, the research line and
whatever else content has added, so the HUD stays the same size however many
systems a game has.

A tab is a key, a label, a builder that returns panels and an optional key
handler. Content adds one with `api.panel_view`; the three here are the ones
every game on this engine gets, because every game has acts, a war model and
a tech tree.
"""

from pclengine.core import acts, research, war


class View:
    __slots__ = ("key", "label", "build", "on_key", "shown", "keys")

    def __init__(self, key, label, build, on_key=None, shown=None, keys=""):
        self.key = key
        self.label = label
        self.build = build            # fn(game) -> [panel, ...]
        self.on_key = on_key          # fn(game, key) -> True if it took it
        self.shown = shown            # fn(game) -> bool, or None for always
        self.keys = keys              # footer hint while this tab is up

    def visible(self, g):
        return self.shown is None or bool(self.shown(g))


BUILTIN = [
    View("ops", "OPS", lambda g: acts.get(g.act).panels(g)),
    View("war", "WAR", war.war_panel,
         keys="↑↓ pick  ENTER build"),
    View("research", "R&D", research.research_panel,
         keys="r labs  ↑↓ pick  ENTER start/stop  u overclock"),
]
VIEWS = list(BUILTIN)
BY_KEY = {v.key: v for v in VIEWS}


def add_view(view):
    VIEWS.append(view)
    BY_KEY[view.key] = view
    return view


def visible(g):
    return [v for v in VIEWS if v.visible(g)]


def current(g):
    return BY_KEY.get(getattr(g, "panel_view", "ops"), VIEWS[0])


def cycle(g):
    """TAB to the next tab that has anything to show."""
    shown = visible(g)
    if not shown:
        return getattr(g, "panel_view", "ops")
    keys = [v.key for v in shown]
    try:
        i = keys.index(getattr(g, "panel_view", "ops"))
    except ValueError:
        i = -1
    g.panel_view = keys[(i + 1) % len(keys)]
    return g.panel_view


def right(g):
    view = current(g)
    if not view.visible(g):
        view = visible(g)[0] if visible(g) else VIEWS[0]
        g.panel_view = view.key
    return view.build(g)


#: Builders for the left-hand column, in the order they are shown. Each is
#: fn(game) -> a panel, or None to leave it out this frame. The act's own
#: material panel is `material_panel`, which content usually puts in the
#: middle; with nothing registered, that is all you get.
LEFT_PANELS = []


def add_left_panel(fn):
    LEFT_PANELS.append(fn)
    return fn


def reset():
    del LEFT_PANELS[:]
    VIEWS[:] = list(BUILTIN)
    BY_KEY.clear()
    BY_KEY.update({v.key: v for v in VIEWS})


def material_panel(g):
    """Whatever the act says it is working with."""
    return acts.get(g.act).material(g)


def left(g):
    if not LEFT_PANELS:
        return [material_panel(g)]
    built = [build(g) for build in LEFT_PANELS]
    return [panel for panel in built if panel]


def integrity_row(g):
    """The one warfare row that belongs on the main HUD, not behind a tab.

    Integrity is how you lose, so it has to be visible without remembering
    to press TAB. Content decides where in its own panel it goes.
    """
    if g.integrity >= 0.999:
        return None
    countdown = war.time_to_defeat(g)
    return acts.row(
        "INTEGRITY", f"{g.integrity * 100:.0f}%"
        + (f"   losing in {countdown / 60:,.0f} min"
           if countdown is not None else "   holding"),
        bar=g.integrity, warn=True, key="TAB",
        hint="TAB to the WAR panel and build force, or you lose the run")


def research_row(g):
    """Research banked, for content that wants it on the main HUD."""
    from pclengine.fmt import small
    if not g.labs:
        return None
    return acts.row("research", small(g.research))


def tab_label(g):
    here = getattr(g, "panel_view", "ops")
    return "  ".join(("[" + v.label + "]") if v.key == here else v.label
                     for v in visible(g))
