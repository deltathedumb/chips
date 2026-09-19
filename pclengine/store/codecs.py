"""Save formats, as a registry.

The engine knows how to turn a game into a dict and back. It does not know
what bytes that should become on disk -- that is a format, and a format is
something you might want to replace without touching the game.

So there is one built-in codec, JSON, which is always there and always
readable; and content may register better ones. The `fsf` mod registers a
binary container and claims the default, and switching that mod off leaves
you with JSON and a game that still loads every save it ever wrote.

A codec is four functions:

    detect(blob)          is this one of mine?
    pack(data, header)    a dict and a header -> bytes
    unpack(blob)          bytes -> a dict, or raise
    describe(blob)        what the file says about itself, without unpacking

Reading tries every codec's `detect` against the file's actual bytes, so a
save that has been renamed still loads.
"""

import json


class BadSave(Exception):
    """The file is not in this format, or is damaged."""


class Codec:
    __slots__ = ("name", "extension", "detect", "pack", "unpack", "describe")

    def __init__(self, name, extension, detect, pack, unpack, describe=None):
        self.name = name
        #: No dot. The default codec's extension names the default save file.
        self.extension = extension
        self.detect = detect
        self.pack = pack
        self.unpack = unpack
        self.describe = describe


# --------------------------------------------------------------------------
# the one that is always here
# --------------------------------------------------------------------------
def _json_detect(blob):
    head = blob.lstrip()[:1]
    return head == b"{"


def _json_pack(data, header=None):
    return json.dumps(data).encode("utf-8")


def _json_unpack(blob):
    try:
        data = json.loads(blob.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise BadSave("not readable as JSON: " + str(exc))
    if not isinstance(data, dict):
        raise BadSave("the file is JSON, but not a save")
    return data


def _json_describe(blob):
    try:
        data = _json_unpack(blob)
    except BadSave:
        return None
    return {"game": "FOUNDRY", "act": data.get("act", 1),
            "elapsed": data.get("elapsed", 0.0),
            "generation": data.get("generation", 0),
            "_format": "json", "_bytes": len(blob)}


JSON = Codec("json", "json", _json_detect, _json_pack, _json_unpack,
             _json_describe)

CODECS = [JSON]
#: The one new saves are written with. Content may claim it.
_DEFAULT = [JSON]


def add(codec, default=True):
    CODECS.append(codec)
    if default:
        _DEFAULT[0] = codec
    return codec


def reset():
    """Back to JSON alone. Called whenever content is reloaded."""
    del CODECS[:]
    CODECS.append(JSON)
    _DEFAULT[0] = JSON


def default():
    return _DEFAULT[0]


def for_blob(blob):
    """Whichever codec recognises these bytes, newest first.

    By content, never by file name: a renamed save is still the format it
    was written in.
    """
    for codec in reversed(CODECS):
        try:
            if codec.detect(blob):
                return codec
        except Exception:            # a broken codec must not hide the rest
            continue
    return None


def for_path(path, as_json=False):
    """Which codec to write with, given where it is going."""
    if as_json or str(path).lower().endswith(".json"):
        return JSON
    return default()


def extensions():
    return [c.extension for c in CODECS]
