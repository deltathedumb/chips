"""What each menu page offers.

Pages are data: a title, some entries and their hints. `Context` is the
state they read -- the save on disk, the run settings, whether developer
mode is on -- so a page never reaches for a global.
"""

import os

from pclengine.core import prestige
from pclengine.dev import tools
from pclengine.modding import loader
from pclengine.store import runconfig, save, summary
from pclengine.ui.menus.widgets import Entry, Menu

class Context:
    """What the menu is allowed to act on."""

    def __init__(self, game=None, developer=False, path=None):
        self.game = game
        self.developer = developer
        self.path = path or save.default_path()
        self.result = None          # "play" / "quit" / ("editor", path) / "web"
        self.page = "main"
        self.mod_infos = loader.discover()
        self.dev_value = ""
        self.setup = (runconfig.from_game(game) if game is not None
                      else runconfig.default())


def page_main(ctx):
    has_save = os.path.exists(ctx.path) or ctx.game is not None
    entries = []
    if ctx.game is not None:
        entries.append(Entry("resume", "Resume",
                             "Go back to the run in progress.",
                             action="play"))
    entries.append(Entry("continue", "Continue saved game",
                         f"Load {os.path.basename(ctx.path)} and play it.",
                         action="load", enabled=has_save,
                         note="" if has_save else "no save"))
    entries.append(Entry("new", "New run",
                         "Pick a mode and start over. The current run is lost "
                         "unless you saved it.", action="page:new"))
    entries.append(Entry("mods", "Mods",
                         "Turn mod files and .mpkg packages on and off. Takes "
                         "effect on the next new run.", action="page:mods",
                         note=f"{len(loader.loaded_names())} on"))
    entries.append(Entry("web", "Play in a browser",
                         "Serve the same game on localhost and open it in a "
                         "browser. The engine stays here.", action="web"))
    entries.append(Entry("legacy", "Legacy",
                         "Spend mask credits earned by finished runs on "
                         "permanent changes to how the next one starts.",
                         action="page:legacy",
                         note=(f"{ctx.game.mask_credits:,.0f} cr"
                               if ctx.game is not None
                               and ctx.game.mask_credits else "")))
    entries.append(Entry("history", "Past runs",
                         "Every finished run, and how it went.",
                         action="page:history"))
    entries.append(Entry("help", "How to play",
                         "The rules, act by act.", action="page:help"))
    if ctx.developer:
        entries.append(Entry("dev", "Developer options",
                             "Diagnostics, grants, jumps and the raw state "
                             "dump.", action="page:dev", note="dev"))
        entries.append(Entry("editor", "Save editor",
                             "Edit every field of the save file.",
                             action="editor", note="dev"))
    entries.append(Entry("quit", "Quit", "Leave. The run is saved first.",
                         action="quit"))
    return entries


def page_new(ctx):
    """Set the knobs, then start. No presets - you decide what you want."""
    setup = ctx.setup
    out = [Entry(knob.attr, knob.name,
                 knob.blurb + "  Use the left and right arrows to change it.",
                 action="knob", value=knob.attr,
                 note=knob.describe(getattr(setup, knob.attr)))
           for knob in runconfig.KNOBS]
    out.append(Entry("reset", "Reset to normal",
                     "Put every setting back to 1x.", action="knobreset"))
    out.append(Entry("start", "Start this run",
                     "Begin with the settings above. The run in progress is "
                     "lost unless you saved it.", action="start"))
    if ctx.game is not None:
        out.append(Entry("apply", "Apply to the run in progress",
                         "Re-stamp these settings onto the current game "
                         "instead of starting over.", action="applysetup"))
    return out


def page_mods(ctx):
    out = []
    for info in ctx.mod_infos:
        detail = info.error or info.description or "No description."
        if info.error:
            detail = "This mod failed to load: " + info.error
        out.append(Entry(info.key, info.name, detail, action="toggle",
                         value=info.key, enabled=not info.error,
                         note="on" if info.enabled else "off"))
    if not out:
        out.append(Entry("none", "No mods found",
                         "Put a .py file or a .mpkg package in the mods/ "
                         "folder and it will appear here.", enabled=False))
    out.append(Entry("apply", "Apply and reload",
                     "Write the choice to mods/enabled.json and reload.",
                     action="applymods"))
    return out


def page_dev(ctx):
    out = [Entry("console", "Python Console",
                 "Run Python against the live game. `g` is the Game, and the "
                 "package modules are all in scope. There is no sandbox - it "
                 "is a debug REPL for your own machine.",
                 action="console", note="repl"),
           Entry("state", "Edit live state",
                 "Open the save editor on the run in progress.",
                 action="editor", note="editor")]
    for title, items in tools.action_groups():
        out.append(Entry(title, title, "", header=True))
        for a in items:
            out.append(Entry(a.key, a.name,
                             a.blurb + (f"  Takes {a.arg} (default "
                                        f"{a.default})." if a.arg else ""),
                             action="dev", value=a.key,
                             note="needs a run" if ctx.game is None else ""))
    return out


HELP_PAGES = [
    ("Act I - The Fab",
     "Buy lots of blank wafers and etch them; one wafer is worth 'dies per "
     "wafer' chips. The price you set drives order flow. Profit buys Steppers "
     "and Design Wins, and at 75 steppers, EUV Scanners at 500x each."),
    ("The system you run on",
     "Chip milestones earn bandwidth. Spend it on threads, which push bytes "
     "into the buffer, which caps how many you hold. That data buys projects. "
     "Let the buffer sit full and idle threads distil entropy."),
    ("Act II - The Lithosphere",
     "Crust miners dig feedstock, ingot pullers grow blanks, foundries etch "
     "them, and all of it needs power. Whichever stage is slowest sets your "
     "rate. Hardware gets dearer the more you own, so research is the real "
     "progression."),
    ("Act III - The Light Cone",
     "Seed fabs build seed fabs. Firmware slots are scarce: a slot on "
     "replication is a slot not on radiation hardening. Any setting left at "
     "zero starves everything downstream, Survey most of all."),
    ("Keys",
     "SPACE etch, w lot, a stepper, s scanner, m design win, t/b threads and "
     "buffer, x buy multiplier, 1-8 projects, h/j/f/d/g Act II hardware, "
     "l launch, arrows for price and firmware, - + 0 resize, S save, "
     "ESC menu, q quit."),
]


def page_help(ctx):
    return [Entry(str(i), title, body) for i, (title, body)
            in enumerate(HELP_PAGES)]


def page_legacy(ctx):
    """Mask credits buy permanent changes to how a run begins."""
    game = ctx.game
    if game is None:
        return [Entry("none", "No run loaded",
                      "Start or load a run to spend credits.", enabled=False)]
    out = [Entry("banked", f"{game.mask_credits:,.1f} mask credits banked",
                 "Earned by finishing runs and taping out. Deeper runs, "
                 "steadier integrity and a well-aligned successor all pay "
                 "more.", enabled=False, header=False,
                 note=f"gen {game.generation}")]
    for upgrade in prestige.UPGRADES:
        owned = upgrade.owned(game.legacy)
        if upgrade.maxed(game.legacy):
            note = "maxed"
        else:
            note = f"{upgrade.price(game.legacy):,.0f} cr"
        out.append(Entry(upgrade.key, upgrade.name,
                         upgrade.blurb
                         + (f"  You own {owned}." if owned else ""),
                         action="legacy", value=upgrade.key,
                         enabled=prestige.affordable(game, upgrade),
                         note=note))
    return out


def page_history(ctx):
    lines = summary.history_lines()
    return [Entry(str(i), line, "A finished run.", enabled=False)
            for i, line in enumerate(lines)]


PAGES = {"main": page_main, "new": page_new, "mods": page_mods,
         "dev": page_dev, "help": page_help, "legacy": page_legacy,
         "history": page_history}
TITLES = {"main": "menu", "new": "new run", "mods": "mods",
          "dev": "developer", "help": "how to play", "legacy": "legacy",
          "history": "past runs"}
