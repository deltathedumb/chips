"""Where things live on disk.

Every path the engine needs is anchored here rather than counted out in
`os.path.dirname` calls, so moving a module between subpackages cannot
silently move the save file with it.
"""

import os

#: The pclengine package itself.
PACKAGE = os.path.dirname(os.path.abspath(__file__))
#: The project the engine was installed into: where mods/ and saves live.
PROJECT = os.path.dirname(PACKAGE)

MODS_DIR = os.path.join(PROJECT, "mods")
#: The base game. It is a mod like any other, it just always goes first.
BASE_DIR = os.path.join(MODS_DIR, "base")
MOD_CONFIG = os.path.join(MODS_DIR, "enabled.json")

SAVE_PATH = os.path.join(PROJECT, "foundry.save.json")
HISTORY_PATH = os.path.join(PROJECT, "foundry.runs.json")
CRASH_LOG = os.path.join(PROJECT, "foundry.crash.log")

#: A front end that ships as a mod keeps its own files beside itself.
