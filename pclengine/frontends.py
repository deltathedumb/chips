"""Ways to play, registered by content.

The engine simulates a game and renders it as data. Turning that into
something a person can use is a front end, and there is no reason for the
engine to contain every one of them: the terminal ships with it because a
terminal is always there, and anything else is a mod.

    api.front_end("web", serve)

`serve(game, **options)` is called instead of the terminal loop and owns
the process until it returns. What options it takes is its own business;
the command line passes through whatever it was given.
"""

FRONT_ENDS = {}


def add(name, run, blurb=""):
    FRONT_ENDS[name] = (run, blurb)
    return run


def get(name):
    entry = FRONT_ENDS.get(name)
    return entry[0] if entry else None


def names():
    return sorted(FRONT_ENDS)


def blurb(name):
    entry = FRONT_ENDS.get(name)
    return entry[1] if entry else ""


def reset():
    FRONT_ENDS.clear()
