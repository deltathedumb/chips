"""Reading and writing the save file.

The game and the save editor both go through here, so a file the editor
writes is always a file the game can load.

What bytes a save turns into is a format, and formats live in
`codecs`. JSON is built in and always works; a mod may register something
better and claim the default. Reading looks at the file's own bytes rather
than at its name, so a renamed save still loads and switching a format mod
off never strands a file.
"""

import json
import os
import random

from pclengine import paths
from pclengine.core.state import Game
from pclengine.store import codecs

SAVE_VERSION = 1
#: The save file without an extension. The default codec supplies that.
SAVE_BASE = os.path.splitext(paths.SAVE_PATH)[0]
# Names this game shipped with earlier. If the current one is missing we read
# these, so an existing game survives the rename; the next save uses the new
# path and leaves the old file untouched.
LEGACY_PATHS = [paths.SAVE_PATH,
                os.path.join(paths.PROJECT, "chips.save.json")]


def default_path():
    """Where a save goes, given whichever format is installed.

    A function rather than a constant: the format comes from content, and
    content is not loaded when this module is imported.
    """
    return SAVE_BASE + "." + codecs.default().extension


def candidates():
    """Every path a save might be at, best first.

    Switching a format mod off must not lose your game, so loading looks
    for the file each installed format would have written, then for the
    names older versions used.
    """
    seen, out = set(), []
    for extension in [codecs.default().extension] + codecs.extensions():
        path = SAVE_BASE + "." + extension
        if path not in seen:
            seen.add(path)
            out.append(path)
    for path in LEGACY_PATHS:
        if path not in seen:
            seen.add(path)
            out.append(path)
    return out


# Fields held as sets in memory but written as sorted lists.
SET_FIELDS = ("completed", "foreclosed", "researched",
              "foreclosed_tech")
# Live objects that are rebuilt on load rather than written out. The random
# generator is restored from `seed`, so a reloaded run keeps rolling the
# same numbers it would have.
SKIP_FIELDS = ("rng",)


def to_dict(g):
    # Underscore names are scratch space -- the bot's carry counters and
    # the like -- and have no business in a file the editor will show.
    data = {k: v for k, v in g.__dict__.items()
            if k not in SKIP_FIELDS and not k.startswith("_")}
    for field in SET_FIELDS:
        data[field] = sorted(getattr(g, field, ()))
    data["act_log"] = [list(entry) for entry in g.act_log]
    data["batch"] = "MAX" if g.batch == float("inf") else g.batch
    data["_version"] = SAVE_VERSION
    return data


def apply_dict(g, data):
    """Copy a save dict onto a Game. Returns the keys it did not recognise."""
    unknown = []
    for key, value in data.items():
        if key.startswith("_"):
            continue
        if not hasattr(g, key):
            unknown.append(key)          # a save from a different version
            continue
        if key in SET_FIELDS:
            setattr(g, key, set(value))
        elif key == "act_log":
            g.act_log = [tuple(entry) for entry in value]
        elif key == "batch":
            g.batch = float("inf") if value == "MAX" else value
        elif key == "fw":
            g.fw.update({k: v for k, v in value.items() if k in g.fw})
        elif key in SKIP_FIELDS:
            continue
        else:
            setattr(g, key, value)
    g.rng = random.Random(g.seed)
    return unknown


def header_for(g):
    """What goes in the clear at the front of the file.

    Enough to describe a save without decoding it: which act, how far in,
    which generation, and what wrote it. A save that will not load can
    still say what it was.
    """
    from pclengine.core import acts
    return {
        "game": "FOUNDRY",
        "saveVersion": SAVE_VERSION,
        "act": int(g.act),
        "actName": acts.name_of(g.act),
        "elapsed": round(float(g.elapsed), 1),
        "generation": int(g.generation),
        "chips": float(g.chips) if g.chips == g.chips else 0.0,
        "projects": len(g.completed),
        "researched": len(g.researched),
        "mode": getattr(g, "mode", "standard"),
    }


def save(g, path=None, backup=False, as_json=False):
    """Write a save in whichever format is installed."""
    path = path or default_path()
    codec = codecs.for_path(path, as_json)
    try:
        blob = codec.pack(to_dict(g), header_for(g))
        if backup and os.path.exists(path) and not os.path.exists(path + ".bak"):
            with open(path, "rb") as src, open(path + ".bak", "wb") as dst:
                dst.write(src.read())
        with open(path, "wb") as fh:
            fh.write(blob)
        return True
    except (OSError, Exception):
        return False


def _bytes_at(path):
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except OSError:
        return None


def read_raw(path=None):
    """The save file as a plain dict, or None if it is missing or corrupt.

    The format is decided by what is in the file, not by the extension.
    """
    blob = _bytes_at(path or default_path())
    if blob is None:
        return None
    codec = codecs.for_blob(blob)
    if codec is None:
        return None
    try:
        data = codec.unpack(blob)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def describe(path=None):
    """What a save says about itself, without loading it into a Game.

    Returns a header dict, or None. For `--save-info`, the menu's save
    list, and for saying something useful about a file that will not load.
    """
    path = path or default_path()
    blob = _bytes_at(path)
    if blob is None:
        return None
    codec = codecs.for_blob(blob)
    if codec is None or codec.describe is None:
        return {"game": "FOUNDRY", "_format": "unknown", "_bytes": len(blob)}
    try:
        return codec.describe(blob)
    except Exception as exc:
        return {"game": "FOUNDRY", "error": str(exc), "_bytes": len(blob)}


def convert(source, target, as_json=None):
    """Rewrite a save in the other format. Returns True on success."""
    data = read_raw(source)
    if data is None:
        return False
    plain = (str(target).lower().endswith(".json") if as_json is None
             else as_json)
    try:
        if plain:
            with open(target, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=1)
        else:
            g = Game()
            apply_dict(g, data)
            codec = codecs.for_path(target, as_json=False)
            with open(target, "wb") as fh:
                fh.write(codec.pack(data, header_for(g)))
        return True
    except Exception:
        return False


def load(path=None):
    """Load into a Game, or None. Also hands back any unrecognised keys."""
    asked = path or default_path()
    data = read_raw(asked)
    if data is None and os.path.abspath(asked) == os.path.abspath(
            default_path()):
        for other in candidates():
            data = read_raw(other)
            if data is not None:
                break
    if data is None:
        return None, []
    g = Game()
    unknown = apply_dict(g, data)
    _clamp_act(g)
    return g, unknown


def _clamp_act(g):
    """A save may name an act this build no longer has.

    Acts were removed between versions, so a run parked on one of them would
    otherwise load pointing at nothing.
    """
    from pclengine.core import acts
    last = acts.last_number()
    if g.act > last:
        g.log(f"This save was on act {g.act}, which no longer exists. "
              f"Continuing at act {last}.")
        g.act = last
    elif g.act < 1:
        g.act = 1
