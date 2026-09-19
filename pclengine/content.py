"""A read-only window onto whatever content is loaded.

The engine renders rows, edits saves and runs developer tools over a game
whose subject matter it does not know. Rather than import a constant that
may not exist, it asks for one by name and takes a default if nothing
defines it. That keeps the engine honest -- it never imports FOUNDRY -- while
letting the parts that really are presentation stay in one place.

Content opts in by handing its constants module to `api.constants`.
"""


def constant(name, default=None):
    """A named constant from any loaded content, or `default`."""
    from pclengine.modding import api
    for module in api.CONSTANT_HOSTS.values():
        if hasattr(module, name):
            return getattr(module, name)
    return default


def headline(g):
    """(label, value) for the one number a run is really measured in.

    The headless reports need something to print and the engine has no
    opinion about what. Content registers it with `api.headline`.
    """
    from pclengine.modding import api
    if api.HEADLINE:
        return api.HEADLINE[0](g)
    return ("elapsed", f"{g.elapsed:,.0f}s")


def help_sections():
    """[(heading, [line, ...])] for the `?` screen, as content wrote it.

    Kept as sections rather than flattened so the screen can page on a
    section boundary instead of orphaning a heading at the foot of a page.
    """
    from pclengine.modding import api
    return list(api.HELP_SECTIONS)


def era(g):
    """A short label for where the run is: a process node, a year, nothing.

    It sits in the title bar next to the clock. Content registers it with
    `api.era`; with nothing registered the bar just shows the time.
    """
    from pclengine.modding import api
    return api.ERA[0](g) if api.ERA else ""


def editor_groups():
    """[(heading, [field, ...])] for the save editor, as content grouped it.

    An engine that does not know what a wafer is cannot group the fields of
    a game about wafers, so content says how. With nothing registered the
    editor falls back to every field on the game, in one list.
    """
    from pclengine.modding import api
    return list(api.EDITOR_GROUPS)


def firmware():
    """[(key, label, blurb)] for whatever content calls firmware, or []."""
    return constant("FIRMWARE_SETTINGS", []) or []


def node_ladder():
    """[(project id, size)] for content's era clock, or []."""
    from pclengine.modding import api
    return api.NODE_LADDER[0] if api.NODE_LADDER else []
