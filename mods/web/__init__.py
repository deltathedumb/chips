"""The browser front end, as a mod.

FOUNDRY's own front end is the terminal, because a terminal is always
there. This is the other one, and there is no reason for it to sit inside
the engine: it registers itself with `api.front_end` and `--web` finds it
the same way the game finds an act.

With this running there is no terminal UI at all. The process takes no
keys, draws no frame and owns no screen -- it prints what a server prints
and does everything else over HTTP.

    python foundry.py --web
    python foundry.py --web --saves client

WHERE THE SAVE LIVES is a real choice here in a way it is not on a desktop:

    local    the server writes a save file, as the terminal build does.
             Two browsers pointed at it share one game, and the game
             survives the browser being closed.
    client   the server writes nothing at all. The browser keeps the save
             bytes and hands them back when it reconnects. Good for running
             this somewhere you would rather not leave files -- and it
             means clearing the site data throws the run away, which the
             client says out loud rather than leaving you to find out.

Either way the bytes are whatever save format is installed, so a run kept
in a browser can be exported and loaded by the terminal build.
"""

import os
import sys

NAME = "Web Front End"
DESCRIPTION = "Play in a browser. The process becomes a headless server."

# The mod is imported as a top-level package, so its own modules are too.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def register(api):
    from web.server import serve

    api.front_end("web", serve,
                  "serve the game to a browser; no terminal UI")
