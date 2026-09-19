"""A Python console that runs against the live game.

Developer-only. It executes whatever you type in-process with the running
`Game` bound to `g`, which is exactly as powerful as it sounds: there is no
sandbox, and there is not meant to be one. It is a debug REPL for a
single-player game on your own machine, in the same spirit as a browser
devtools console.

Two consequences worth being explicit about:

* It is only reachable with `--developer`. Without that flag the endpoint is
  refused and the terminal screen is not offered.
* The web server binds to 127.0.0.1, so the console is not exposed to the
  network. Do not re-bind that server to a public interface while developer
  mode is on.
"""

import contextlib
import io
import traceback

MAX_HISTORY = 50
MAX_OUTPUT = 8000


class Console:
    """Holds the namespace between calls, so state persists like a REPL."""

    def __init__(self):
        self.namespace = {}
        self.history = []
        self._seeded = False

    def _seed(self, game):
        """Put the engine's modules, and every loaded mod, one name away."""
        import sys

        from pclengine import content, fmt
        from pclengine.core import (acts, prestige, projects, research, state,
                                    war)
        from pclengine.dev import balance, tools
        from pclengine.modding import loader
        from pclengine.store import runconfig, save
        self.namespace.update({
            "acts": acts, "projects": projects, "research": research,
            "war": war, "prestige": prestige, "state": state, "save": save,
            "mods": loader, "content": content, "runconfig": runconfig,
            "devtools": tools, "balance": balance, "fmt": fmt,
            "help_text": HELP,
        })
        # Content is a mod, so reach it the way a mod is reached: by the
        # package it was loaded as, plus its submodules.
        for info in loader.LOADED:
            package = sys.modules.get(info.key)
            if package is None:
                continue
            self.namespace[info.key] = package
            for name, module in list(sys.modules.items()):
                if name.startswith(info.key + "."):
                    self.namespace[name.split(".", 1)[1]] = module
        self._seeded = True

    def run(self, source, game):
        """Execute `source`. Returns {ok, output, result, error}."""
        if not self._seeded:
            self._seed(game)
        self.namespace["g"] = game
        self.namespace["game"] = game
        source = (source or "").strip()
        if not source:
            return {"ok": True, "output": "", "result": "", "error": ""}

        self.history.append(source)
        del self.history[:-MAX_HISTORY]

        buffer = io.StringIO()
        result = ""
        try:
            with contextlib.redirect_stdout(buffer), \
                    contextlib.redirect_stderr(buffer):
                try:
                    # An expression gets its value shown, like a real REPL.
                    code = compile(source, "<console>", "eval")
                except SyntaxError:
                    exec(compile(source, "<console>", "exec"), self.namespace)
                else:
                    value = eval(code, self.namespace)
                    if value is not None:
                        result = repr(value)
                        self.namespace["_"] = value
        except BaseException:
            return {"ok": False, "output": buffer.getvalue()[:MAX_OUTPUT],
                    "result": "", "error": traceback.format_exc(limit=6)}
        return {"ok": True, "output": buffer.getvalue()[:MAX_OUTPUT],
                "result": result[:MAX_OUTPUT], "error": ""}


HELP = """\
g / game        the live Game object
projects, war, research, acts, prestige, state, save, mods, content
base            the loaded content package, with its modules beside it:
                acts_early, acts_late, acts_final, constants, mechanics
devtools        every developer action: tools.run(g, "chips", 1e15)
balance         balance.probe(9), balance.run(), balance.report(...)
_               the value of the last expression

  g.chips = 1e30
  g.fw["survey"] = 4
  [p.title for p in projects.available(g)][:5]
  war.buy_unit(g, "fighters", 10_000)
  tools.diagnose(g)
"""


SHARED = Console()


def run(source, game):
    return SHARED.run(source, game)


def history():
    return list(SHARED.history)
