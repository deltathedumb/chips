"""Player actions, shared by every front end.

The terminal loop and the web server both funnel input through `handle_key`,
so a key means the same thing in both. What a key means is decided by the
layer stack in `keymap`; this file is the six layers the engine always has.
"""

from pclengine import content
from pclengine.core import acts, projects, research, war
from pclengine.store import save
from pclengine.ui import keymap, panels, screen, techtree
from pclengine.ui.keymap import PASS, Bind

BATCHES = [1, 10, 100, 1_000, 10_000, 10**6, 10**9, 10**12, float("inf")]


def visible_firmware_rows(g):
    return [i for i, (key, _, _) in enumerate(content.firmware())
            if key != "counter" or g.counter_unlocked]


def cycle_batch(g):
    try:
        i = BATCHES.index(g.batch)
    except ValueError:
        i = 0
    g.batch = BATCHES[(i + 1) % len(BATCHES)]


# --------------------------------------------------------------------------
# 1000 -- an overlay owns the keyboard while it is open
# --------------------------------------------------------------------------
def _overlay_active(g):
    return bool(getattr(g, "overlay", None))


def _overlay(g, key):
    if getattr(g, "overlay", None) == "loan":
        # The one overlay the player did not open. A stray keypress must
        # not sign for a loan, so only ENTER accepts and only ESC leaves.
        from pclengine.core import rescue
        if key in ("ENTER", " "):
            if rescue.accept(g):
                g.overlay = None
                return "resize"
        elif key in ("ESC", "q", "n"):
            g.overlay = None
            return "resize"
        return True
    if getattr(g, "overlay", None) != "tech":
        # Any other overlay is read-only: anything closes it.
        g.overlay = None
        return "resize"
    if key in ("UP", "k"):
        techtree.move(g, -1)
    elif key in ("DOWN", "j"):
        techtree.move(g, 1)
    elif key in ("LEFT", "PGUP"):
        techtree.move(g, -8)
    elif key in ("RIGHT", "PGDN"):
        techtree.move(g, 8)
    elif key in ("ENTER", " "):
        techtree.take(g)
    elif key in ("T", "ESC", "q"):
        g.overlay = None
        return "resize"
    return True                      # nothing falls out of an overlay


def _overlay_binds(g):
    if getattr(g, "overlay", None) == "loan":
        return [Bind("ENTER", "take the loan"), Bind("ESC", "not yet")]
    return [Bind("UP", "up"), Bind("DOWN", "down"),
            Bind("LEFT", "back a page"), Bind("RIGHT", "on a page"),
            Bind("ENTER", "start / put aside"), Bind("T", "close")]


def _overlay_footer(g):
    if getattr(g, "overlay", None) == "loan":
        return "  ENTER take the loan   ESC look around first"
    return ("  ↑↓ move a node   ←→ jump a page"
            "   ENTER start work   T close")


# --------------------------------------------------------------------------
# 800 -- the frame around the game
# --------------------------------------------------------------------------
def _chrome(g, key):
    if key in ("q", "CTRL-C"):
        return "quit"
    if key == "ESC":
        return "menu"
    if key == "?":
        return "help"
    if key == "T":
        g.overlay = "tech"
        return "resize"
    if key == "x":
        cycle_batch(g)
        return True
    if key == "TAB":
        panels.cycle(g)
        return True
    if key == "S":
        if save.save(g):
            g.log("Game saved.")
        else:
            g.log("Could not write the save file. "
                  + (save.why_failed() or "No reason given."))
        return True
    if key in ("-", "_"):
        g.hud_width = max(screen.MIN_W, screen.W - 8)
        return "resize"
    if key in ("+", "="):
        g.hud_width = min(screen.MAX_W, screen.W + 8)
        return "resize"
    if key == "0":
        g.hud_width = None          # back to filling the terminal
        return "resize"
    return PASS


def _chrome_binds(g):
    return [Bind("TAB", "panel", "cycle OPS, WAR, R&D and the rest"),
            Bind("T", "tech tree", "the whole tree, and what each node needs"),
            Bind("x", "batch", "how many to buy at once"),
            Bind("?", "help"), Bind("S", "save"), Bind("ESC", "menu")]


# --------------------------------------------------------------------------
# 600 -- whichever HUD tab is up
# --------------------------------------------------------------------------
def _panel(g, key):
    view = getattr(g, "panel_view", "ops")
    tab = panels.BY_KEY.get(view)
    if tab is not None and tab.on_key is not None and tab.on_key(g, key):
        return True
    if view == "war":
        if key == "UP":
            return war.move_selection(g, -1)
        if key == "DOWN":
            return war.move_selection(g, 1)
        if key == "ENTER":
            return war.buy_selected(g)
    elif view == "research":
        if key == "r":
            if not research.buy_labs(g, g.batch):
                g.log("Not enough "
                      + ("funds" if research.lab_currency(g) == "funds"
                         else "chips") + " for a lab.")
            return True
        if key == "UP":
            return research.move_selection(g, -1)
        if key == "DOWN":
            return research.move_selection(g, 1)
        if key == "ENTER":
            return research.take_selected(g)
    return PASS


def _rows_of(blocks):
    for block in blocks or ():
        for row in block.get("rows", ()):
            yield row


def _panel_binds(g):
    """Whatever the current tab is showing a key for."""
    out = []
    try:
        blocks = panels.right(g)
    except Exception:                # a half-built tab must not kill input
        return out
    for row in _rows_of(blocks):
        key = row.get("key")
        if key and key != "price":
            out.append(Bind(key, row.get("label", ""), row.get("hint", "")))
    return out


def _panel_footer(g):
    tab = panels.current(g)
    return "  " + (tab.keys or "") if tab.key != "ops" and tab.keys else ""


def _project_footer(g):
    """Always worth saying: the number row does this from anywhere."""
    return ""


# --------------------------------------------------------------------------
# 400 -- what this act does
# --------------------------------------------------------------------------
def _act(g, key):
    # An act with a dial of its own claims the arrows for it.
    if key in ("LEFT", "RIGHT") and acts.dials_for(g.act):
        acts.adjust_dial(g, acts.dials_for(g.act)[0].key,
                         1 if key == "RIGHT" else -1)
        return True
    play = getattr(acts.get(g.act), "on_key", None)
    if play is not None and play(g, key):
        return True
    return PASS


def _act_binds(g):
    out = []
    try:
        blocks = acts.get(g.act).panels(g)
    except Exception:
        return out
    for row in _rows_of(blocks):
        key = row.get("key")
        if key and key != "price":
            out.append(Bind(key, row.get("label", ""), row.get("hint", "")))
    return out


def _act_footer(g):
    return "  " + (acts.get(g.act).keys or "")


# --------------------------------------------------------------------------
# 200 -- the project list
# --------------------------------------------------------------------------
def _projects(g, key):
    if key not in screen.PROJECT_KEYS:
        return PASS
    index = screen.PROJECT_KEYS.index(key)
    available = projects.available(g)
    if index < len(available):
        project = available[index]
        if not project.buy(g):
            g.log(f"Not enough resources for {project.title}.")
    return True


def _project_binds(g):
    out = []
    for index, project in enumerate(projects.available(g)):
        if index >= len(screen.PROJECT_KEYS):
            break
        out.append(Bind(screen.PROJECT_KEYS[index], project.title,
                        project.desc))
    return out


# --------------------------------------------------------------------------
# 100 -- things you can do in any act
# --------------------------------------------------------------------------
def _system(g, key):
    if key == " ":
        if not g.make_chip(1):
            g.log("Out of blank wafers.")
        return True
    if key == "t":
        if not g.buy_thread():
            g.log("No unassigned bandwidth.")
        return True
    if key == "b":
        if not g.buy_buffer():
            g.log("No unassigned bandwidth.")
        return True
    if key == "c":
        if not g.fire_burst():
            g.log(f"Burst is recharging: {g.burst_cd:,.0f}s left.")
        return True
    if key == "u":
        if not g.upgrade_burst():
            g.log("Not enough entropy to overclock the burst.")
        return True
    return PASS


def _system_binds(g):
    return [Bind(" ", "etch a wafer", "works in every act"),
            Bind("t", "thread"), Bind("b", "buffer"),
            Bind("c", "compute burst"), Bind("u", "overclock the burst")]


BUILTIN = [
    # An overlay is exclusive: it is a screen, not a mode, so nothing under
    # it is reachable or advertised while it is up.
    ("overlay", 1000, _overlay, _overlay_active, _overlay_binds,
     _overlay_footer, True),
    ("chrome", 800, _chrome, None, _chrome_binds, None, False),
    # The number row is reserved. It sits above every panel so that 1-8
    # means the same thing on every tab and in every act: take that
    # project. A list on a tab uses a cursor instead.
    ("projects", 700, _projects, None, _project_binds, None, False),
    ("panel", 600, _panel, None, _panel_binds, _panel_footer, False),
    ("act", 400, _act, None, _act_binds, _act_footer, False),
    ("system", 100, _system, None, _system_binds, None, False),
]


def install():
    """Put the engine's own layers on the stack. Content may add more."""
    keymap.reset()
    for name, priority, handle, active, binds, foot, only in BUILTIN:
        keymap.add_layer(keymap.Layer(name, priority, handle, active, binds,
                                      foot, only))


install()


def handle_key(key, g):
    """Apply one keypress. Returns 'quit', 'menu', 'help', 'resize' or None."""
    return keymap.dispatch(g, key)


def bindings(g):
    return keymap.bindings(g)
