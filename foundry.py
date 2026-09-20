#!/usr/bin/env python3
"""FOUNDRY - a terminal idle game about a chip fab that does not stop.

    python foundry.py                    menu, then play
    python foundry.py --play             skip the menu, straight into a run
    python foundry.py --web              serve it to a browser, same engine
    python foundry.py --developer        unlock the developer menu and editor
    python foundry.py --save-editor      open a save file and edit it
    python foundry.py --build-mod DIR    pack a package folder into a .mpkg
    python foundry.py --sim 600          600 game-seconds of autoplay, no UI
"""

import argparse
import os
import sys
import time

from pclengine import errors, frontends
from pclengine.core import clock, prestige
from pclengine.core.state import Game
from pclengine.modding import loader
from pclengine.store import runconfig, save, summary
from pclengine.ui import menus as menu
from pclengine.ui import screen
from pclengine.ui.actions import handle_key
from pclengine.ui.term import Terminal

TICK = 1.0 / 20.0


# --------------------------------------------------------------------------
# the playing loop
# --------------------------------------------------------------------------
def play(g, resumed, show_intro=True):
    """Run the game. Returns "menu" or "quit".

    Anything that goes wrong inside the loop is caught, saved, and shown on an
    error screen rather than escaping as a traceback -- the terminal is left
    in a usable state and the run is still on disk.
    """
    with Terminal() as term:
        width, height = term.measure()
        if show_intro:
            term.render(screen.intro(width, height, resumed))
            while not term.keys():
                time.sleep(0.03)

        term.invalidate()
        help_on = False
        size = (width, height)
        last = time.monotonic()
        pacer = clock.Pacer()
        frozen = None          # the failure we are currently showing

        while True:
            frame_start = time.monotonic()
            real_delta = frame_start - last
            last = frame_start

            if frozen is not None:
                for key in term.keys():
                    if key == "r":
                        frozen = None
                        term.invalidate()
                        last = time.monotonic()
                    elif key == "ESC":
                        save.save(g, save.default_path())
                        return "menu"
                    elif key in ("q", "CTRL-C"):
                        save.save(g, save.default_path())
                        return "quit"
                if frozen is not None:
                    term.render(screen.error_screen(frozen, *term.measure()))
                    time.sleep(TICK)
                    continue

            with errors.Guard("the game loop") as guard:
                for key in term.keys():
                    if g.finished:
                        if key in ("q", "CTRL-C"):
                            return "quit"
                        if key == "ESC":
                            return "menu"
                        continue
                    action = handle_key(key, g)
                    if action == "quit":
                        save.save(g, save.default_path())
                        return "quit"
                    if action == "menu":
                        save.save(g, save.default_path())
                        return "menu"
                    if action == "help":
                        # `?` opens the help and then walks through it,
                        # closing once there is nothing left to read.
                        pages = screen.help_pages(g, size[1])
                        if not help_on:
                            help_on, g.help_page = True, 0
                        elif g.help_page + 1 < pages:
                            g.help_page += 1
                        else:
                            help_on, g.help_page = False, 0
                        term.invalidate()
                    if action == "resize":
                        term.invalidate()

                pacer.frame(g, real_delta)

                now_size = term.measure()
                if now_size != size:
                    size = now_size
                    term.invalidate()

                if g.finished:
                    term.render(screen.ending(g, *size))
                else:
                    term.render(screen.render(g, size[0], size[1],
                                              help_on, g.overlay))

            if guard:
                frozen = guard.failure
                errors.capture("autosave after failure", RuntimeError("saved")) \
                    if not save.save(g, save.default_path()) else None
                term.invalidate()

            elapsed = time.monotonic() - frame_start
            time.sleep(max(0.0, TICK - elapsed))


def new_game(setup=None, legacy=None, credits=0.0, generation=0):
    setup = setup or runconfig.default()
    game = setup.apply(Game())
    game.legacy = dict(legacy or {})
    game.mask_credits = credits
    game.generation = generation
    prestige.apply_legacy(game)
    loader.run_new_game_hooks(game)
    game.log("Welcome. You have one lot of blank wafers, at 180nm.")
    game.log("Press SPACE to etch one. ESC for the menu, ? for help.")
    return game


# --------------------------------------------------------------------------
# entry point
# --------------------------------------------------------------------------
def build_parser():
    parser = argparse.ArgumentParser(description="FOUNDRY, in your terminal.")
    parser.add_argument(
        "--play", action="store_true", help="skip the menu and resume or start a run"
    )
    parser.add_argument("--new", action="store_true", help="start a fresh game")
    for knob in runconfig.KNOBS:
        parser.add_argument(
            "--" + knob.attr.replace("_", "-"),
            type=float, default=None, metavar="X",
            help=knob.blurb + f" Default {knob.default:g}.",
        )
    parser.add_argument(
        "--web", action="store_true", help="serve the game to a browser on localhost"
    )
    parser.add_argument("--port", type=int, default=8000, help="port for --web")
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="with --web, do not open a browser window",
    )
    parser.add_argument(
        "--developer",
        action="store_true",
        help="unlock developer options and the save editor",
    )
    parser.add_argument(
        "--sim",
        type=float,
        metavar="SECONDS",
        help="headless autoplay, for balance checking",
    )
    parser.add_argument("--save", default=save.default_path(), help="path to the save file")
    parser.add_argument(
        "--save-editor",
        nargs="?",
        const=save.default_path(),
        metavar="FILE",
        dest="save_editor",
        help="open a save file in the editor instead of playing",
    )
    parser.add_argument(
        "--build-mod",
        metavar="DIR",
        dest="build_mod",
        help="pack a package directory into mods/<name>.mpkg",
    )
    parser.add_argument(
        "--saves", choices=("local", "client"), default="local",
        help="with --web: keep the save on this machine, or in the browser")
    parser.add_argument(
        "--save-info", nargs="?", const="", metavar="FILE",
        help="describe a save file without loading it, and exit")
    parser.add_argument(
        "--no-mods", action="store_true",
        help="start with every mod switched off (the base game still loads)"
    )
    parser.add_argument(
        "--test", action="store_true", help="run the regression suite and exit"
    )
    parser.add_argument(
        "--balance", action="store_true", help="play headlessly and report act pacing"
    )
    parser.add_argument("--dt", type=float, default=1.0, help="step size for --balance")
    parser.add_argument(
        "--budget", type=float, default=60000.0, help="game-seconds for --balance"
    )
    parser.add_argument(
        "--check", action="store_true", help="with --balance, verify the step size"
    )
    parser.add_argument(
        "--width",
        type=int,
        metavar="COLS",
        help=f"cap the HUD width ({screen.MIN_W}-{screen.MAX_W}); "
        "default is to fill the terminal",
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)

    if args.build_mod:
        try:
            out = loader.build_package(args.build_mod)
        except (OSError, ValueError) as exc:
            print(f"Could not build: {exc}")
            return 1
        print(f"Built {out}")
        return 0

    # The base game is content like any other mod, so it loads either way;
    # --no-mods means "nothing on top of it".
    loaded = loader.load([] if args.no_mods else None)
    if loader.loaded_names():
        print("Mods: " + ", ".join(loader.loaded_names()))
    for info in [i for i in loaded if i.error]:
        print(f"Mod {info.key} failed to load: {info.error}")

    if args.save_info is not None:
        path = args.save_info or args.save or save.default_path()
        header = save.describe(path)
        if header is None:
            print(f"No save at {path}")
            return 1
        print(path)
        for key in sorted(header):
            print(f"  {key.lstrip('_'):<14} {header[key]}")
        return 0

    if args.test:
        import unittest

        # `tests/__init__.py` points the default save at a sandbox as it is
        # imported, so nothing in here can land on the player's game.
        suite = unittest.TestLoader().discover("tests", top_level_dir=".")
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1

    if args.balance:
        from pclengine.dev.balance import main as run_balance

        run_balance(dt=args.dt, budget=args.budget,
                    do_check=args.check, with_mods=not args.no_mods)
        return 0

    if args.sim:
        from pclengine.dev.autoplay import simulate

        simulate(args.sim)
        return 0

    if args.save_editor:
        from pclengine.ui.editor import run as run_editor

        try:
            print(run_editor(args.save_editor))
        except KeyboardInterrupt:
            print("Editor closed, nothing written.")
        return 0

    game, stale = (None, [])
    if not args.new:
        game, stale = save.load(args.save)
    if stale:
        print(
            f"Note: {len(stale)} field(s) in {args.save} are from a different "
            "version and were ignored."
        )
    if game is None and (args.new or args.play or args.web):
        game = new_game(_setup_from(args))
    if game is not None and args.width:
        game.hud_width = max(screen.MIN_W, min(args.width, screen.MAX_W))

    if args.web:
        # The browser front end is a mod. If it is switched off, say so
        # rather than failing with an import error.
        serve = frontends.get("web")
        if serve is None:
            print("The web front end is a mod, and it is not enabled.")
            print("Turn on 'web' in the Mods menu, or in mods/enabled.json.")
            return 1
        return serve(
            game,
            port=args.port,
            developer=args.developer,
            path=args.save,
            open_browser=not args.no_browser,
            save_mode=args.saves,
        )

    try:
        if args.play or args.new:
            if play(game, resumed=not args.new) == "quit":
                return _bye(game, args.save)
        return _menu_loop(game, args)
    except KeyboardInterrupt:
        return _bye(game, args.save)
    except Exception as exc:          # noqa: BLE001 - last line of defence
        failure = errors.capture("startup", exc)
        print("\nFOUNDRY hit a problem it could not show in the UI:\n")
        print("  " + failure.headline)
        print("\nFull trace written to " + errors.LOG_PATH)
        _bye(game, args.save)
        return 1


def _setup_from(args):
    """Command-line overrides, falling back to the plain defaults."""
    chosen = {knob.attr: getattr(args, knob.attr)
              for knob in runconfig.KNOBS
              if getattr(args, knob.attr, None) is not None}
    return runconfig.Setup(**chosen)


def _menu_loop(game, args):
    """Menu, game, menu, game... until something says quit."""
    ctx = menu.Context(game, developer=args.developer, path=args.save)
    first = True
    while True:
        ctx = menu.run(ctx)
        if ctx.result == "quit":
            return _bye(ctx.game, args.save)
        if ctx.result == "play":
            if ctx.game is None:
                ctx.game = new_game(_setup_from(args))
            outcome = play(ctx.game, resumed=not first, show_intro=first)
            first = False
            if outcome == "quit":
                return _bye(ctx.game, args.save)
        elif ctx.result == "editor":
            from pclengine.ui.editor import run as run_editor

            run_editor(args.save)
        elif ctx.result == "web":
            serve = frontends.get("web")
            if serve is None:
                print("The web front end is a mod, and it is not enabled.")
            else:
                if ctx.game is None:
                    ctx.game = new_game(_setup_from(args))
                serve(
                    ctx.game,
                    port=args.port,
                    developer=args.developer,
                    path=args.save,
                    open_browser=True,
                    save_mode=args.saves,
                )
        ctx.result = None


def _bye(game, path):
    if game is not None:
        save.save(game, path)
        print(f"Chips made: {game.chips:,.0f}. Saved to {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
