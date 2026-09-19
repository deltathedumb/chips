"""Mod loading.

A mod is either a single .py file in the `mods/` folder next to foundry.py,
or a `.mpkg` package -- an uncompressed zip holding a Python package. Either
way it needs a `register(api)` function. It can add, edit or remove projects, extend the
process-node ladder, change constants, and hook the tick.

    # mods/cheap_optics.py
    NAME = "Cheap Optics"
    DESCRIPTION = "Lithography projects cost half as much."

    def register(api):
        for pid in ("improved_steppers", "even_better_steppers"):
            api.edit_project(pid, data=lambda old: old / 2)

A `.mpkg` is a stored (uncompressed) zip whose root holds one importable
package, so it is an ordinary Python module that happens to live in one file:

    my_mod.mpkg
      my_mod/__init__.py      <- NAME, DESCRIPTION, register(api)
      my_mod/rules.py         <- anything else it wants to import

Build one with `python foundry.py --build-mod path/to/my_mod`.

Which mods are enabled is remembered in `mods/enabled.json`.
"""

import importlib
import json
import os
import sys

from pclengine import paths
from pclengine.core import (acts, currency, modifiers, prestige, projects,
                            research, state, war)
from pclengine.dev import autoplay
from pclengine.modding import api
from pclengine.modding.api import ModAPI
from pclengine.modding.package import (build_package, inspect_package)

MODS_DIR = paths.MODS_DIR
CONFIG = paths.MOD_CONFIG
BASE_DIR = paths.BASE_DIR

LOADED = []
# Constants a mod overwrote, with what they were, so reset() can undo them.
api._CONSTANTS = {}


class ModInfo:
    __slots__ = ("key", "name", "description", "path", "enabled", "error")

    def __init__(self, key, name, description, path, enabled):
        self.key = key
        self.name = name
        self.description = description
        self.path = path
        self.enabled = enabled
        self.error = None

    def as_dict(self):
        return {"key": self.key, "name": self.name, "enabled": self.enabled,
                "description": self.description, "error": self.error}


def _metadata(source, fallback):
    name, description = fallback, ""
    for line in source.splitlines():
        if line.startswith("NAME"):
            name = line.split("=", 1)[1].strip().strip('"\'')
        elif line.startswith("DESCRIPTION"):
            description = line.split("=", 1)[1].strip().strip('"\'')
    return name, description


def _read_config():
    try:
        with open(CONFIG, encoding="utf-8") as fh:
            data = json.load(fh)
        return set(data.get("enabled", []))
    except (OSError, ValueError):
        return None


def write_config(enabled):
    try:
        os.makedirs(MODS_DIR, exist_ok=True)
        with open(CONFIG, "w", encoding="utf-8") as fh:
            json.dump({"enabled": sorted(enabled)}, fh, indent=2)
        return True
    except OSError:
        return False


def discover():
    """Every mod file on disk, with whether it is switched on."""
    enabled = _read_config()
    found = []
    if not os.path.isdir(MODS_DIR):
        return found
    for entry in sorted(os.listdir(MODS_DIR)):
        path = os.path.join(MODS_DIR, entry)
        if entry.startswith((".", "_")) or entry == "__pycache__":
            continue
        # A mod is a .py file, a .mpkg, or a package directory. The base
        # game is a directory too, but it is loaded first by name and must
        # not appear again in the list.
        is_package = (os.path.isdir(path)
                      and os.path.isfile(os.path.join(path, "__init__.py")))
        if is_package:
            if os.path.abspath(path) == os.path.abspath(BASE_DIR):
                continue
        elif not entry.endswith((".py", ".mpkg")):
            continue
        key = entry.rsplit(".", 1)[0] if not is_package else entry
        problem = source = ""
        if is_package:
            try:
                with open(os.path.join(path, "__init__.py"),
                          encoding="utf-8") as fh:
                    source = fh.read(4000)
            except OSError:
                source = ""
        elif entry.endswith(".mpkg"):
            package, source, problem = inspect_package(path)
            if package is None:
                broken = ModInfo(key, key, "", path, False)
                broken.error = problem
                found.append(broken)
                continue
            key = package
        else:
            try:
                with open(path, encoding="utf-8") as fh:
                    source = fh.read(4000)
            except OSError:
                source = ""
        name, description = _metadata(source, key)
        # No config yet means every mod found is on.
        info = ModInfo(key, name, description, path,
                       key in enabled if enabled is not None else True)
        if problem:
            info.description = (description + "  [" + problem + "]").strip()
        found.append(info)
    return found


def clear():
    """Empty every registry. Nothing is left but the engine itself."""
    for (key, name), original in api._CONSTANTS.items():
        module = api.CONSTANT_HOSTS.get(key)
        if module is not None:
            setattr(module, name, original)
    api._CONSTANTS.clear()
    del projects.ALL[:]
    projects.BY_ID.clear()
    del api.NODE_LADDER[:], api.HEADLINE[:], api.ERA[:]
    del api.EDITOR_GROUPS[:], api.HELP_SECTIONS[:], api.ERA[:]
    del api.EDITOR_GROUPS[:]
    api.CONSTANT_HOSTS.clear()
    from pclengine.dev import balance, tools
    del balance.PROBE_SEEDS[:]
    balance.reset_pacing()
    tools.reset()
    from pclengine.ui import menubar, panels
    panels.reset()
    menubar.install_defaults()
    from pclengine import frontends
    from pclengine.store import codecs
    codecs.reset()
    frontends.reset()
    currency.reset()
    modifiers.reset()
    acts.reset()
    research.reset()
    war.reset()
    prestige.reset()
    autoplay.reset()
    state.reset()
    del api.TICK_HOOKS[:], api.NEW_GAME_HOOKS[:], LOADED[:]


def _load_one(info):
    if info.path.endswith(".mpkg"):
        module = _import_package(info)
    elif os.path.isdir(info.path):
        module = _import_directory(info)
    else:
        spec = importlib.util.spec_from_file_location(
            "foundry_mod_" + info.key, info.path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    register = getattr(module, "register", None)
    if register is None:
        raise AttributeError("no register(api) function")
    register(ModAPI(info.name))
    return module


def base_info():
    """The base game, described the way any other mod is."""
    return ModInfo("base", "FOUNDRY", "The base game.", BASE_DIR, True)


def reset(with_base=True):
    """Put the game back the way it ships: the base content and nothing else.

    Callers mean "forget the mods", not "forget the game", so this reloads
    the base content rather than leaving an engine with no acts in it.
    """
    return load([], with_base=with_base)


def load(infos=None, with_base=True):
    """Apply the enabled mods. Returns the ones that loaded, errors attached.

    The base game goes first and is not optional unless you ask for the bare
    engine: everything after it -- including which projects exist to edit --
    depends on it having run.
    """
    clear()
    if with_base and os.path.isdir(BASE_DIR):
        info = base_info()
        try:
            _load_one(info)
            LOADED.append(info)
        except Exception as exc:
            info.error = f"{type(exc).__name__}: {exc}"
            raise
    infos = discover() if infos is None else infos
    for info in infos:
        if not info.enabled:
            continue
        try:
            _load_one(info)
            LOADED.append(info)
        except Exception as exc:               # a bad mod must not kill the game
            info.error = f"{type(exc).__name__}: {exc}"
    return infos


def _import_directory(info):
    """Import a mod that is a plain package directory, like mods/base."""
    parent = os.path.dirname(os.path.abspath(info.path))
    if parent not in sys.path:
        sys.path.insert(0, parent)
    package = os.path.basename(os.path.abspath(info.path))
    importlib.invalidate_caches()
    for stale in [m for m in sys.modules
                  if m == package or m.startswith(package + ".")]:
        del sys.modules[stale]
    return importlib.import_module(package)


def _import_package(info):
    """Import the package inside a .mpkg straight out of the archive."""
    package, _source, _warning = inspect_package(info.path)
    if package is None:
        raise ImportError("no importable package in " + info.path)
    if info.path not in sys.path:
        sys.path.insert(0, info.path)
    importlib.invalidate_caches()
    for stale in [m for m in sys.modules
                  if m == package or m.startswith(package + ".")]:
        del sys.modules[stale]
    return importlib.import_module(package)


def run_tick_hooks(game, dt):
    for hook in api.TICK_HOOKS:
        try:
            hook(game, dt)
        except Exception:
            pass


# Let Game.tick call into here without importing this module.
state._MOD_TICK[:] = [run_tick_hooks]


def run_new_game_hooks(game):
    for hook in api.NEW_GAME_HOOKS:
        try:
            hook(game)
        except Exception:
            pass


def loaded_names():
    return [info.name for info in LOADED]


def ensure_loaded():
    """Load content once, on import, so the engine comes up as a game."""
    if not LOADED and not acts.ALL:
        load()
