"""The menu loop: draw a page, take a key, do what it says."""


from pclengine import errors
from pclengine.core import prestige
from pclengine.core.state import Game
from pclengine.dev import tools
from pclengine.modding import loader
from pclengine.store import runconfig, save, summary
from pclengine.ui import screen
from pclengine.ui.term import Terminal
from pclengine.ui.menus.pages import (Context, page_dev, page_help,

                                      page_history, page_legacy, page_main,
                                      page_mods, page_new)
from pclengine.ui.menus.pages import PAGES, TITLES
from pclengine.ui.menus.widgets import Entry, Menu

def _act(menu, ctx, entry):
    action = entry.action
    if action is None:
        return None
    if action.startswith("page:"):
        ctx.page = action.split(":", 1)[1]
        menu.sel = 0
        menu.status = ""
        return None
    if action in ("play", "quit", "web", "editor"):
        ctx.result = action
        return "done"
    if action == "load":
        game, unknown = save.load(ctx.path)
        if game is None:
            menu.status = "No save file to load."
            return None
        ctx.game = game
        ctx.result = "play"
        return "done"
    if action == "knob":
        return None            # the arrows change it, not ENTER
    if action == "knobreset":
        ctx.setup = runconfig.default()
        menu.status = "settings reset to normal"
        return None
    if action == "applysetup":
        if ctx.game is not None:
            ctx.setup.apply(ctx.game)
            menu.status = "applied: " + ctx.setup.label()
        return None
    if action == "start":
        loader.load(ctx.mod_infos)
        game = ctx.setup.apply(Game())
        loader.run_new_game_hooks(game)
        game.log("Welcome. You have one lot of blank wafers, at 180nm.")
        game.log("Press SPACE to etch one. ESC for the menu.")
        ctx.game = game
        ctx.result = "play"
        return "done"
    if action == "toggle":
        for info in ctx.mod_infos:
            if info.key == entry.value:
                info.enabled = not info.enabled
                menu.status = f"{info.name} is now {'on' if info.enabled else 'off'}"
        return None
    if action == "applymods":
        enabled = {i.key for i in ctx.mod_infos if i.enabled}
        loader.write_config(enabled)
        ctx.mod_infos = loader.load(loader.discover())
        broken = [i.name for i in ctx.mod_infos if i.error]
        menu.status = (f"{len(loader.loaded_names())} mod(s) loaded"
                       + (f"; failed: {', '.join(broken)}" if broken else ""))
        return None
    if action == "legacy":
        if ctx.game is not None and prestige.buy(ctx.game, entry.value):
            menu.status = (f"bought {prestige.BY_KEY[entry.value].name}; "
                           f"{ctx.game.mask_credits:,.1f} credits left")
        else:
            menu.status = "not enough mask credits"
        return None
    if action == "console":
        if ctx.game is None:
            menu.status = "Start or load a run first."
            return None
        return "console"
    if action == "dev":
        if ctx.game is None:
            menu.status = "Start or load a run first."
            return None
        spec = tools.BY_KEY.get(entry.value)
        if spec is not None and spec.arg is not None and menu.prompt is None:
            menu.prompt = entry           # ask for the number first
            menu.typed = "" if spec.default is None else str(spec.default)
            return None
        value = menu.typed if menu.prompt is not None else None
        menu.prompt, menu.typed = None, ""
        message, lines = tools.run(ctx.game, entry.value, value)
        menu.status = message + ("  |  " + " / ".join(lines[:2]) if lines else "")
        ctx.dev_lines = lines
        return "devout"
    return None


def _step(menu, delta):
    """Move the cursor, stepping over group headers."""
    i = menu.sel
    for _ in range(len(menu.entries) + 1):
        i += delta
        if not 0 <= i < len(menu.entries):
            return menu.sel
        if not menu.entries[i].header:
            return i
    return menu.sel


def run(ctx):
    """Show the menu until it produces a result. Returns the Context."""
    menu = Menu(TITLES["main"], PAGES["main"], ctx)
    with Terminal() as term:
        while True:
            menu.page = PAGES[ctx.page]
            menu.title = TITLES[ctx.page]
            w, h = term.measure()
            term.render(menu.frame(w, h))
            keys = term.keys()
            if not keys:
                import time
                time.sleep(0.03)
                continue
            for key in keys:
                if menu.prompt is not None:
                    if key == "ESC":
                        menu.prompt, menu.typed = None, ""
                        menu.status = "cancelled"
                    elif key == "ENTER":
                        outcome = _act(menu, ctx, menu.prompt)
                        if outcome == "devout":
                            _show_lines(term, "developer output",
                                        getattr(ctx, "dev_lines", []))
                        if outcome == "console":
                            _console(term, ctx)
                    elif key == "BACKSPACE":
                        menu.typed = menu.typed[:-1]
                    elif len(key) == 1 and key.isprintable():
                        menu.typed += key
                    continue
                if key == "UP":
                    menu.sel = _step(menu, -1)
                elif key == "DOWN":
                    menu.sel = _step(menu, 1)
                elif key in ("LEFT", "RIGHT") and menu.entries \
                        and menu.entries[menu.sel].action == "knob":
                    knob = runconfig.BY_ATTR[menu.entries[menu.sel].value]
                    current = getattr(ctx.setup, knob.attr)
                    setattr(ctx.setup, knob.attr,
                            knob.nudge(current, 1 if key == "RIGHT" else -1))
                elif key in ("ESC", "BACKSPACE"):
                    if ctx.page == "main":
                        if ctx.game is not None:
                            ctx.result = "play"
                            return ctx
                    else:
                        ctx.page = "main"
                        menu.sel = 0
                elif key in ("q", "CTRL-C"):
                    ctx.result = "quit"
                    return ctx
                elif key in ("ENTER", " "):
                    if menu.entries:
                        try:
                            outcome = _act(menu, ctx, menu.entries[menu.sel])
                        except Exception as exc:          # noqa: BLE001
                            failure = errors.capture("menu action", exc)
                            menu.status = failure.headline
                            outcome = None
                        if outcome == "done":
                            return ctx
                        if outcome == "devout":
                            _show_lines(term, "developer output",
                                        getattr(ctx, "dev_lines", []))
                        if outcome == "console":
                            _console(term, ctx)
                menu.sel = max(0, min(menu.sel, max(0, len(menu.entries) - 1)))


def _show_lines(term, title, lines):
    """A scrollable read-only panel, for diagnostics and dumps."""
    top = 0
    while True:
        w, h = term.measure()
        screen.layout(w)
        W = screen.W
        body_h = max(6, (h - 1) - 6)
        out = [screen.hrule("┌", "┐"),
               "│" + screen.BOLD + screen.pad("  " + title.upper(), W - 2)
               + screen.RESET + "│",
               screen.hrule("├", "┤")]
        window = lines[top:top + body_h]
        for i in range(body_h):
            out.append(screen.row("  " + (window[i] if i < len(window) else "")))
        out.append(screen.hrule("├", "┤"))
        out.append("│" + screen.CYAN + screen.pad(
            f"  ↑↓ scroll    {len(lines)} line(s)    ESC back", W - 2)
            + screen.RESET + "│")
        out.append(screen.hrule("└", "┘"))
        term.render(out)
        keys = term.keys()
        if not keys:
            import time
            time.sleep(0.03)
            continue
        for key in keys:
            if key in ("ESC", "ENTER", "q", " ", "BACKSPACE"):
                term.invalidate()
                return
            if key == "UP":
                top = max(0, top - 1)
            elif key == "DOWN":
                top = min(max(0, len(lines) - body_h), top + 1)


def _console(term, ctx):
    """A Python prompt over the running game, drawn like the rest of the UI."""
    from pclengine.dev import console
    lines, typed = [], ""
    while True:
        w, h = term.measure()
        screen.layout(w)
        W = screen.W
        body_h = max(6, (h - 1) - 7)
        out = [screen.hrule('┌', '┐'),
               '│' + screen.BOLD + screen.pad("  P Y T H O N   C O N S O L E", W - 2)
               + screen.RESET + '│',
               '│' + screen.DIM + screen.pad("  g is the live Game; projects, war, "
                                     "research, acts and devtools are in scope",
                                     W - 2) + screen.RESET + '│',
               screen.hrule('├', '┤')]
        window = lines[max(0, len(lines) - body_h):]
        for i in range(body_h):
            if i < len(window):
                text, kind = window[i]
                colour = {"echo": screen.BOLD, "err": screen.RED,
                          "val": screen.GREEN}.get(kind, screen.DIM)
                out.append('│' + colour + screen.pad("  " + text, W - 2)
                           + screen.RESET + '│')
            else:
                out.append(screen.row(""))
        out.append(screen.hrule('├', '┤'))
        out.append('│' + screen.pad("  >>> " + typed + "\u2588", W - 2) + '│')
        out.append(screen.hrule('├', '┤'))
        out.append('│' + screen.CYAN + screen.pad(
            "  ENTER run    ESC back    BACKSPACE edit", W - 2) + screen.RESET + '│')
        out.append(screen.hrule('└', '┘'))
        term.render(out)

        keys = term.keys()
        if not keys:
            import time
            time.sleep(0.03)
            continue
        for key in keys:
            if key == "ESC":
                term.invalidate()
                return
            if key == "ENTER":
                if not typed.strip():
                    continue
                lines.append((">>> " + typed, "echo"))
                result = console.run(typed, ctx.game)
                for chunk, kind in ((result["output"], ""),
                                    (result["result"], "val"),
                                    (result["error"], "err")):
                    for text in (chunk or "").rstrip("\n").splitlines():
                        lines.append((text, kind))
                typed = ""
                del lines[:-200]
            elif key == "BACKSPACE":
                typed = typed[:-1]
            elif len(key) == 1 and key.isprintable():
                typed += key
