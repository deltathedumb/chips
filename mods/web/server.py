"""A local HTTP front end for the game.

The browser is a thin client: it never simulates anything, it posts keys and
renders the snapshot this server hands back. Same Game object, same tick, same
`handle_key` as the terminal, so the two front ends cannot drift apart.
"""

import base64
import http.server
import json
import os
import threading
import time
import webbrowser

from pclengine import content, errors
from pclengine.core import clock
from pclengine.core.state import Game
from pclengine.dev import console, tools
from pclengine.modding import loader
from pclengine.store import runconfig, save, summary
from pclengine.ui import actions, editor, menus as menu
from web import view

#: This mod's own files, wherever it happens to be installed.
WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

#: Where a save is kept.
#:   local   the server writes a file, as a desktop game does
#:   client  the server writes nothing; the browser holds the bytes and
#:           hands them back when it reconnects
SAVE_MODES = ("local", "client")
TICK = 1.0 / 20.0


class Session:
    """The running game, plus the lock that keeps the tick thread honest."""

    def __init__(self, game, developer=False, path=None, save_mode="local"):
        self.game = game
        self.developer = developer
        self.path = path or save.default_path()
        self.save_mode = save_mode if save_mode in SAVE_MODES else "local"
        self.lock = threading.Lock()
        self.alive = True
        self.frozen = None       # set if the tick thread hit a failure
        self.baseline = save.to_dict(game)
        #: Set when the game should be handed to the browser to keep. Only
        #: used in client mode, where the server is not allowed to write.
        self.handoff = None

    # -- where saves live ------------------------------------------------
    def keep(self, reason=""):        # noqa: D401
        """Persist however this session was told to.

        In client mode nothing touches the disk: the bytes are packed and
        left for the next snapshot to carry to the browser, which is the
        only thing holding them.
        """
        if self.save_mode == "client":
            self.handoff = self.packed()
            return True
        return save.save(self.game, self.path)

    def packed(self):
        """The game as the bytes a save file would contain, base64'd."""
        from pclengine.store import codecs
        codec = codecs.default()
        blob = codec.pack(save.to_dict(self.game), save.header_for(self.game))
        return base64.b64encode(blob).decode("ascii")

    def adopt(self, encoded):
        """Take a save the browser was holding. Returns a message."""
        try:
            blob = base64.b64decode(encoded.encode("ascii"), validate=True)
        except Exception:
            return "that does not look like a save"
        from pclengine.store import codecs
        codec = codecs.for_blob(blob)
        if codec is None:
            return "no installed format recognises that save"
        try:
            data = codec.unpack(blob)
        except Exception as exc:
            return "could not read it: " + str(exc)
        with self.lock:
            fresh = Game()
            unknown = save.apply_dict(fresh, data)
            self.game = fresh
            self.baseline = save.to_dict(fresh)
        return ("restored from your browser"
                + (f" ({len(unknown)} unknown fields dropped)"
                   if unknown else ""))

    def run(self):
        last = time.monotonic()
        pacer = clock.Pacer()
        while self.alive:
            now = time.monotonic()
            real_delta = now - last
            last = now
            if not self.frozen:
                with self.lock:
                    try:
                        pacer.frame(self.game, real_delta)
                    except Exception as exc:      # noqa: BLE001
                        self.frozen = errors.capture("simulation tick", exc)
                        self.keep("crash")
            time.sleep(TICK)

    # -- things the browser can ask for ---------------------------------
    def snapshot(self):
        with self.lock:
            try:
                state = view.snapshot(self.game, self.developer)
            except Exception as exc:              # noqa: BLE001
                failure = errors.capture("building the snapshot", exc)
                return {"fatal": failure.as_dict()}
        if self.frozen is not None:
            state["fatal"] = self.frozen.as_dict()
        state["saveMode"] = self.save_mode
        if self.handoff is not None:
            # Handed over once. If the browser drops it, it is gone -- which
            # is what "the client keeps the save" means, and the banner in
            # the client says so.
            state["saveBlob"] = self.handoff
            self.handoff = None
        return state

    def resume(self):
        self.frozen = None
        return {"ok": True}

    #: Keys the server handles itself rather than letting the engine's
    #: chrome layer run them. Saving is the one that matters: in client
    #: mode this process must not touch the disk, and the engine's own
    #: save key would.
    INTERCEPT = ("S",)

    def press(self, key):
        if key in self.INTERCEPT:
            written = self.keep("you asked")
            with self.lock:
                self.game.log("Saved to your browser." if
                              self.save_mode == "client" else
                              ("Game saved." if written
                               else "Could not write the save file."))
                return {"result": None,
                        "state": self.snapshot_locked()}
        with self.lock:
            result = actions.handle_key(key, self.game)
            return {"result": result, "state": self.snapshot_locked()}

    def snapshot_locked(self):
        """A snapshot from inside the lock, with the handoff attached."""
        state = view.snapshot(self.game, self.developer)
        state["saveMode"] = self.save_mode
        if self.handoff is not None:
            state["saveBlob"] = self.handoff
            self.handoff = None
        return state

    def set_price(self, value):
        with self.lock:
            self.game.set_price(value)

    def set_firmware(self, key, delta):
        with self.lock:
            self.game.adjust_firmware(key, int(delta))

    def set_dial(self, key, delta):
        from pclengine.core import acts
        with self.lock:
            acts.adjust_dial(self.game, key, int(delta))

    def new_game(self, settings):
        from pclengine.store import runconfig
        with self.lock:
            game = runconfig.Setup(**(settings or {})).apply(Game())
            loader.run_new_game_hooks(game)
            game.log("New run started in the browser.")
            self.game = game
            self.baseline = save.to_dict(game)

    def load(self, path=None):
        game, unknown = save.load(path or self.path)
        if game is None:
            return f"no save at {path or self.path}"
        with self.lock:
            self.game = game
        return f"loaded {path or self.path}" + (
            f" ({len(unknown)} unknown fields ignored)" if unknown else "")

    def store(self, path=None):
        with self.lock:
            ok = save.save(self.game, path or self.path)
        return f"saved to {path or self.path}" if ok else "could not write the save"

    def dev_panel(self):
        """Everything the developer screen needs to draw itself."""
        groups = [{"title": title,
                   "actions": [{"key": a.key, "name": a.name, "blurb": a.blurb,
                                "arg": a.arg,
                                "default": None if a.default is None
                                else str(a.default)}
                               for a in items]}
                  for title, items in tools.action_groups()]
        return {"actionGroups": groups,
                "consoleHelp": console.HELP,
                "history": console.history()}

    def console(self, source):
        if not self.developer:
            return {"ok": False, "error": "developer mode is off",
                    "output": "", "result": ""}
        with self.lock:
            return console.run(source, self.game)

    def dev(self, key, value):
        if not self.developer:
            return {"message": "developer mode is off", "lines": []}
        with self.lock:
            message, lines = tools.run(self.game, key, value)
        return {"message": message, "lines": lines}

    # -- save editor -----------------------------------------------------
    def editor_fields(self):
        with self.lock:
            g = self.game
            groups = []
            for title, names in editor.GROUPS:
                fields = []
                for name in names:
                    if not name.startswith("fw:") and not hasattr(g, name):
                        continue
                    fields.append({
                        "name": name,
                        "label": editor._label(name),
                        "kind": editor._kind(name),
                        "value": editor._shown(g, name),
                        "changed": self.baseline.get(name) != editor._get(g, name)
                        if not name.startswith("fw:") else False,
                    })
                if fields:
                    groups.append({"title": title, "fields": fields})
            return {"groups": groups,
                    "projects": [{"id": p.id, "title": p.title,
                                  "done": p.id in g.completed,
                                  "repeatable": p.repeatable}
                                 for p in __import__(
                                     "pclengine.core.projects", fromlist=["ALL"]).ALL]}

    def editor_set(self, name, raw):
        with self.lock:
            try:
                kind = editor._kind(name)
                editor._set(self.game, name,
                            editor._parse(kind, str(raw), editor._get(self.game, name)))
                return {"ok": True, "value": editor._shown(self.game, name)}
            except (ValueError, OverflowError, KeyError, AttributeError) as exc:
                return {"ok": False, "error": str(exc)}

    def editor_toggle_project(self, pid, on):
        with self.lock:
            if on:
                self.game.completed.add(pid)
            else:
                self.game.completed.discard(pid)
            return {"ok": True}


class Handler(http.server.SimpleHTTPRequestHandler):
    session = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def log_message(self, *args):
        pass                                     # keep the console clean

    def end_headers(self):
        """The page and its script change between runs; never cache them.

        Without this the browser keeps an old app.js and boots it against a
        newer API, which fails silently and shows a blank page."""
        self.send_header("Cache-Control", "no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    # -- helpers ---------------------------------------------------------
    def _json(self, payload, code=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except ValueError:
            return {}

    # -- routes ----------------------------------------------------------
    def do_GET(self):
        try:
            return self._get()
        except Exception as exc:                  # noqa: BLE001
            failure = errors.capture("GET " + self.path, exc)
            return self._json({"error": failure.headline,
                               "trace": failure.trace}, 500)

    def _get(self):
        s = self.session
        if self.path.startswith("/api/state"):
            return self._json(s.snapshot())
        if self.path.startswith("/api/techtree"):
            with s.lock:
                return self._json(view.tech_tree(s.game))
        if self.path.startswith("/api/menu"):
            from pclengine.store import runconfig
            return self._json({
                "knobs": [{"attr": k.attr, "name": k.name, "blurb": k.blurb,
                           "low": k.low, "high": k.high,
                           "default": k.default}
                          for k in runconfig.KNOBS],
                "mods": [i.as_dict() for i in loader.discover()],
                "developer": s.developer,
                "devActions": [{"key": a.key, "name": a.name, "blurb": a.blurb,
                                "arg": a.arg, "default": a.default}
                               for a in tools.ACTIONS] if s.developer else [],
                "savePath": s.path,
                # The same help the terminal shows, from the same content,
                # so the two front ends cannot drift apart.
                "help": [[heading, lines]
                         for heading, lines in content.help_sections()],
            })
        if self.path.startswith("/api/dev/panel"):
            if not s.developer:
                return self._json({"error": "developer mode is off"}, 403)
            return self._json(s.dev_panel())
        if self.path.startswith("/api/editor"):
            if not s.developer:
                return self._json({"error": "developer mode is off"}, 403)
            return self._json(s.editor_fields())
        if self.path in ("/", ""):
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self):
        try:
            return self._post()
        except Exception as exc:                  # noqa: BLE001
            failure = errors.capture("POST " + self.path, exc)
            return self._json({"error": failure.headline,
                               "trace": failure.trace}, 500)

    def _post(self):
        s = self.session
        data = self._body()
        route = self.path.split("?")[0]
        if route == "/api/key":
            return self._json(s.press(data.get("key", "")))
        if route == "/api/save/import":
            return self._json({"message": s.adopt(data.get("blob", ""))})
        if route == "/api/save/export":
            return self._json({"blob": s.packed()})
        if route == "/api/research":
            with s.lock:
                from pclengine.core import research
                tech_id = data.get("id", "")
                tech = research.BY_ID.get(tech_id)
                was_running = tech_id in s.game.researching
                # The browser starts and stops work, the same as ENTER in
                # the terminal. Nothing is bought with banked research.
                ok = research.toggle(s.game, tech_id)
                name = tech.name if tech else tech_id
                if ok:
                    message = (f"put {name} aside" if was_running
                               else f"started work on {name}")
                elif tech is None:
                    message = "no such technology"
                elif tech_id in s.game.researched:
                    message = "already researched"
                elif tech.shut_out(s.game):
                    message = f"{name} was ruled out earlier this run"
                elif not tech.ready(s.game):
                    message = "needs " + ", ".join(tech.missing(s.game))
                else:
                    message = (f"all {research.benches(s.game)} benches are "
                               "busy -- put something aside first")
            return self._json({"ok": ok, "message": message,
                               "tree": view.tech_tree(s.game)})
        if route == "/api/price":
            s.set_price(data.get("value", 0.15))
            return self._json(s.snapshot())
        if route == "/api/firmware":
            s.set_firmware(data.get("setting", ""), data.get("delta", 0))
            return self._json(s.snapshot())
        if route == "/api/dial":
            s.set_dial(data.get("setting", ""), data.get("delta", 0))
            return self._json(s.snapshot())
        if route == "/api/new":
            s.new_game(data.get("setup"))
            return self._json(s.snapshot())
        if route == "/api/save":
            return self._json({"message": s.store(data.get("path"))})
        if route == "/api/load":
            return self._json({"message": s.load(data.get("path"))})
        if route == "/api/mods":
            infos = loader.discover()
            wanted = set(data.get("enabled", []))
            for info in infos:
                info.enabled = info.key in wanted
            loader.write_config(wanted)
            loader.load(infos)
            return self._json({"mods": [i.as_dict() for i in loader.discover()],
                               "message": "mods reloaded; start a new run to "
                                          "see project changes"})
        if route == "/api/dev":
            return self._json(s.dev(data.get("action", ""), data.get("value")))
        if route == "/api/resume":
            return self._json(s.resume())
        if route == "/api/dev/exec":
            return self._json(s.console(data.get("source", "")))
        if route == "/api/editor/set":
            if not s.developer:
                return self._json({"error": "developer mode is off"}, 403)
            return self._json(s.editor_set(data.get("name", ""), data.get("value")))
        if route == "/api/editor/project":
            if not s.developer:
                return self._json({"error": "developer mode is off"}, 403)
            return self._json(s.editor_toggle_project(data.get("id", ""),
                                                      bool(data.get("on"))))
        return self._json({"error": "unknown route"}, 404)


def serve(game, host="127.0.0.1", port=8000, developer=False, path=None,
          open_browser=True, save_mode="local", **_ignored):
    """Run headless and serve the game to a browser.

    No terminal UI at all: this process draws nothing, takes no keys and
    holds no screen. It prints what a server prints -- where it is, what it
    is doing, and what went wrong -- and everything else happens over HTTP.
    """
    session = Session(game, developer=developer, path=path,
                      save_mode=save_mode)
    Handler.session = session

    ticker = threading.Thread(target=session.run, daemon=True)
    ticker.start()

    httpd = http.server.ThreadingHTTPServer((host, port), Handler)
    url = f"http://{host}:{port}/"
    print("FOUNDRY, headless.")
    print(f"  listening   {url}")
    print(f"  run         {game.mode}, act {game.act}")
    print(f"  developer   {'on' if developer else 'off'}")
    if session.save_mode == "client":
        print("  saves       in your browser; this process writes nothing")
        print("              clear the site data and the run is gone")
    else:
        print(f"  saves       {session.path}")
    if loader.loaded_names():
        print("  mods        " + ", ".join(loader.loaded_names()))
    print("  Ctrl-C to stop.")
    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("")
    finally:
        session.alive = False
        httpd.server_close()
        if session.save_mode == "client":
            print("Stopped. The browser is holding the save.")
        else:
            written = save.save(session.game, session.path)
            print("Stopped. Saved to " + session.path if written
                  else "Stopped. Could not write " + session.path)
    return 0
