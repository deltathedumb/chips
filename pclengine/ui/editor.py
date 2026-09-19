"""A full-screen editor for a FOUNDRY save file.

    python foundry.py --save-editor [FILE]

Arrow keys move, ENTER edits a value, SPACE toggles a flag, ENTER on
`completed projects` opens a checklist of every project in the game. Nothing
touches disk until you press S, and the first save keeps a `.bak` of the
original.
"""

import os

from pclengine import errors
from pclengine.core import projects
from pclengine.store import save
from pclengine.ui import screen
from pclengine.fmt import big
from pclengine import content
from pclengine.core.state import Game
from pclengine.ui.term import Terminal

# Field groups, in the order they appear. Names that no longer exist on Game
# are skipped, so this survives the state module being renamed around.
def field_groups():
    """How to group a save's fields, asked of content every time.

    Which fields exist depends on what is loaded, so this cannot be settled
    once at import. With nothing registered it falls back to listing every
    field the game has.
    """
    groups = [(heading, [f for f in fields if _exists(f)])
              for heading, fields in content.editor_groups()]
    groups = [(heading, fields) for heading, fields in groups if fields]
    if not groups:
        return [("EVERY FIELD", _remaining(set()))]
    listed = {f for _heading, fields in groups for f in fields}
    rest = _remaining(listed)
    if rest:
        groups.append(("EVERYTHING ELSE", rest))
    return groups


#: Live objects and bookkeeping the editor has no business showing as a row.
SKIP = ("rng", "messages", "act_log", "forces", "pressure", "legacy",
        "dials", "fw", "foreclosed", "researched", "placements")


def _remaining(listed):
    fresh = Game()
    return [f for f in sorted(vars(fresh))
            if f not in listed and not f.startswith("_") and f not in SKIP]


def _exists(field):
    if field.startswith("fw:"):
        return True
    return hasattr(Game(), field)


DEFAULTS = Game()
NUMERIC_HELP = "a number, plain or exponent form (2500, 1.5e9, 3e55)"


def _get(g, name):
    if name.startswith("fw:"):
        return g.fw.get(name[3:], 0)
    return getattr(g, name)


def _set(g, name, value):
    if name.startswith("fw:"):
        g.fw[name[3:]] = value
    else:
        setattr(g, name, value)


def _kind(name):
    """What sort of value this field holds, judged from a pristine Game."""
    if name == "completed":
        return "projects"
    if name == "batch":
        return "batch"
    if name == "hud_width":
        return "optional_int"
    value = _get(DEFAULTS, name)
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    return "text"


def _label(name):
    return name[3:] if name.startswith("fw:") else name


def _shown(g, name):
    """The value as the editor prints it."""
    kind = _kind(name)
    value = _get(g, name)
    if kind == "projects":
        return f"{len(value)} of {len(projects.ALL)} complete"
    if kind == "batch":
        return "MAX" if value == float("inf") else f"{value:,.0f}"
    if kind == "optional_int":
        return "fit to terminal" if not value else f"{value} columns"
    if kind == "bool":
        return "yes" if value else "no"
    if kind == "int":
        return f"{int(value):,}"
    if isinstance(value, float):
        if value and (abs(value) >= 1e7 or 0 < abs(value) < 1e-3):
            return big(value, 3)
        return f"{value:,.4f}".rstrip("0").rstrip(".") or "0"
    return str(value)


def _parse(kind, text, current):
    """Turn typed text into a value, or raise ValueError."""
    text = text.strip()
    if kind == "optional_int":
        if not text or text.lower() in ("fit", "none", "auto"):
            return None
        return max(screen.MIN_W, min(int(float(text)), screen.MAX_W))
    if kind == "batch":
        if text.lower() in ("max", "inf"):
            return float("inf")
        return max(1, int(float(text)))
    if kind == "bool":
        if text.lower() in ("y", "yes", "true", "1", "on"):
            return True
        if text.lower() in ("n", "no", "false", "0", "off"):
            return False
        raise ValueError("type yes or no")
    if kind == "int":
        return int(float(text))
    if kind == "float":
        return float(text)
    return text


class Row:
    """One line of the editor: a group header or an editable field."""

    def __init__(self, name=None, header=None):
        self.name = name
        self.header = header

    @property
    def editable(self):
        return self.name is not None


def build_rows(g):
    rows = []
    for title, names in field_groups():
        present = [n for n in names
                   if n.startswith("fw:") or hasattr(g, n)]
        if not present:
            continue
        rows.append(Row(header=title))
        rows.extend(Row(name=n) for n in present)
    return rows


class Editor:
    def __init__(self, path):
        self.path = path
        # What the container says about itself, read before the body: it is
        # the one part of an .fsf that is in the clear, and it is what lets
        # the editor say something useful about a file it cannot load.
        self.header = save.describe(path) or {}
        self.game, self.unknown = save.load(path)
        self.missing = self.game is None
        if self.missing:
            self.game = Game()
        self.original = save.to_dict(self.game)
        self.rows = build_rows(self.game)
        self.sel = next(i for i, r in enumerate(self.rows) if r.editable)
        self.top = 0
        self.status = ""
        self.editing = None       # field name currently being typed into
        self.entry = ""
        self.project_view = False
        self.project_sel = 0
        self.project_top = 0
        self.dirty = False
        self.quit_armed = False

    # -- change tracking ---------------------------------------------------
    def changed(self, name):
        if name.startswith("fw:"):
            return self.original.get("fw", {}).get(name[3:]) != _get(self.game, name)
        if name == "completed":
            return set(self.original.get("completed", [])) != self.game.completed
        if name == "batch":
            now = self.game.batch
            return self.original.get("batch") != ("MAX" if now == float("inf") else now)
        return self.original.get(name) != _get(self.game, name)

    # -- movement ----------------------------------------------------------
    def move(self, step):
        i = self.sel
        while True:
            i += step
            if not 0 <= i < len(self.rows):
                return
            if self.rows[i].editable:
                self.sel = i
                return

    def visible_rows(self, height):
        if self.sel < self.top:
            self.top = self.sel
        elif self.sel >= self.top + height:
            self.top = self.sel - height + 1
        self.top = max(0, min(self.top, max(0, len(self.rows) - height)))
        return self.rows[self.top:self.top + height]

    # -- key handling ------------------------------------------------------
    def key(self, k, height):
        if self.editing is not None:
            return self._key_editing(k)
        if self.project_view:
            return self._key_projects(k, height)
        return self._key_browse(k, height)

    def _key_browse(self, k, height):
        name = self.rows[self.sel].name
        kind = _kind(name)
        if k in ("q", "CTRL-C", "ESC"):
            if self.dirty and not self.quit_armed:
                self.quit_armed = True
                self.status = "Unsaved changes. Press q again to discard, or S to save."
                return None
            return "quit"
        self.quit_armed = False
        if k == "UP":
            self.move(-1)
        elif k == "DOWN":
            self.move(1)
        elif k == "HOME":
            self.sel = next(i for i, r in enumerate(self.rows) if r.editable)
        elif k == "END":
            self.sel = max(i for i, r in enumerate(self.rows) if r.editable)
        elif k == "S":
            ok = save.save(self.game, self.path, backup=True)
            if ok:
                self.original = save.to_dict(self.game)
                self.dirty = False
                self.status = f"Saved to {self.path} (original kept as .bak)"
            else:
                self.status = f"Could not write {self.path}"
        elif k == "e":
            target = os.path.splitext(self.path)[0] + ".export.json"
            if save.convert(self.path, target, as_json=True):
                self.status = f"Decoded to {target} - plain JSON, readable."
            else:
                self.status = "Could not write the export."
        elif k == "u":
            self._revert(name)
        elif k == " " and kind == "bool":
            _set(self.game, name, not _get(self.game, name))
            self.dirty = True
            self.status = f"{_label(name)} = {_shown(self.game, name)}"
        elif k in ("ENTER", " "):
            if kind == "projects":
                self.project_view = True
                self.status = "SPACE toggles, a toggles all, ESC goes back"
            elif kind == "bool":
                _set(self.game, name, not _get(self.game, name))
                self.dirty = True
            else:
                self.editing = name
                self.entry = ""
                self.status = ""
        return None

    def _revert(self, name):
        if name == "completed":
            self.game.completed = set(self.original.get("completed", []))
        elif name == "batch":
            was = self.original.get("batch", 1)
            self.game.batch = float("inf") if was == "MAX" else was
        elif name.startswith("fw:"):
            _set(self.game, name, self.original.get("fw", {}).get(name[3:], 0))
        elif name in self.original:
            _set(self.game, name, self.original[name])
        self.dirty = any(self.changed(r.name) for r in self.rows if r.editable)
        self.status = f"{_label(name)} restored to the loaded value"

    def _key_editing(self, k):
        name = self.editing
        if k == "ESC":
            self.editing = None
            self.status = "cancelled"
        elif k == "ENTER":
            try:
                value = _parse(_kind(name), self.entry, _get(self.game, name))
            except (ValueError, OverflowError):
                self.status = f"Not valid here - expected {NUMERIC_HELP}"
                return None
            _set(self.game, name, value)
            self.dirty = True
            self.editing = None
            self.status = f"{_label(name)} = {_shown(self.game, name)}"
        elif k == "BACKSPACE":
            self.entry = self.entry[:-1]
        elif len(k) == 1 and k.isprintable():
            self.entry += k
        return None

    def _key_projects(self, k, height):
        if k in ("ESC", "q", "ENTER"):
            self.project_view = False
            self.status = ""
            return None
        if k == "UP":
            self.project_sel = max(0, self.project_sel - 1)
        elif k == "DOWN":
            self.project_sel = min(len(projects.ALL) - 1, self.project_sel + 1)
        elif k == " ":
            pid = projects.ALL[self.project_sel].id
            if pid in self.game.completed:
                self.game.completed.discard(pid)
            else:
                self.game.completed.add(pid)
            self.dirty = True
        elif k == "a":
            ids = {p.id for p in projects.ALL if not p.repeatable}
            if self.game.completed >= ids:
                self.game.completed = set()
            else:
                self.game.completed = ids
            self.dirty = True
        return None

    # -- drawing -----------------------------------------------------------
    def frame(self, term_w, term_h):
        if term_w < screen.MIN_W or term_h < screen.MIN_H:
            return [f"The save editor needs {screen.MIN_W} columns x {screen.MIN_H} rows."]
        screen.layout(term_w)
        W = screen.W

        head = f"  {self.path}"
        right = f"node {self.game.node:g}nm · act {self.game.act} · " \
                f"{big(self.game.chips)} chips  "
        lines = [screen.hrule("┌", "┐"),
                 "│" + screen.BOLD + screen.pad("  F O U N D R Y   ·   S A V E   E D I T O R",
                                        W - 2) + screen.RESET + "│",
                 "│" + screen.DIM + screen.pad(screen.pad(head, W - 4 - len(right)) + "  "
                                       + right, W - 2) + screen.RESET + "│",
                 screen.hrule("├", "┤")]

        body_h = (term_h - 1) - len(lines) - 4
        body_h = max(4, body_h)
        lines += (self._project_body(body_h) if self.project_view
                  else self._field_body(body_h))

        lines.append(screen.hrule("├", "┤"))
        lines.append("│" + screen.pad("  " + self._status_text(), W - 2) + "│")
        lines.append(screen.hrule("├", "┤"))
        lines.append("│" + screen.CYAN + screen.pad("  " + self._keys_text(), W - 2)
                     + screen.RESET + "│")
        lines.append(screen.hrule("└", "┘"))
        return lines

    def _format_note(self):
        """What kind of file this is, in the header line.

        An .fsf is a binary container: scrambled, checksummed, and not
        something to open in a text editor. Saying so here is the difference
        between a format and a trick.
        """
        if not self.header:
            return ""
        if self.header.get("_format") == "json":
            return "· plain JSON"
        if self.header.get("error"):
            return "· .fsf, damaged: " + self.header["error"]
        bits = [".fsf v%d" % self.header.get("_version", 1)]
        if self.header.get("_scrambled"):
            bits.append("scrambled")
        if self.header.get("_deflated"):
            bits.append("deflated")
        bits.append("%d bytes" % self.header.get("_bytes", 0))
        return "· " + ", ".join(bits)

    def _status_text(self):
        if self.editing is not None:
            kind = _kind(self.editing)
            hint = {"bool": "yes / no", "batch": "a number, or MAX",
                    "optional_int": f"{screen.MIN_W}-{screen.MAX_W}, or blank to fit"}.get(
                        kind, NUMERIC_HELP)
            was = _shown(self.game, self.editing)
            return f"{_label(self.editing)} [{self.entry}█]   was {was}   ({hint})"
        if self.status:
            return self.status
        if self.missing:
            return "No save at that path - editing a fresh game instead."
        if self.unknown:
            return (f"{len(self.unknown)} field(s) in this file are not part of "
                    "this version and will be dropped if you save.")
        return "Nothing written to disk until you press S."

    def _keys_text(self):
        if self.editing is not None:
            return "type a value    ENTER accept    ESC cancel"
        if self.project_view:
            return "↑↓ move    SPACE toggle    a all/none    ESC back"
        return ("↑↓ move    ENTER edit    SPACE toggle    u undo    "
                "e export JSON    S save    q quit")

    def _field_body(self, height):
        W, out = screen.W, []
        rows = self.visible_rows(height)
        for i, row in enumerate(rows, start=self.top):
            if not row.editable:
                out.append("│" + screen.BOLD + screen.pad("  " + row.header, W - 2)
                           + screen.RESET + "│")
                continue
            marker = ">" if i == self.sel else " "
            flag = "*" if self.changed(row.name) else " "
            value = _shown(self.game, row.name)
            kind = _kind(row.name)
            text = screen.pad(f" {marker}{flag} {_label(row.name):<26}"
                          f"{value:>22}   {kind}", W - 2)
            if i == self.sel:
                text = screen.GREEN + text + screen.RESET
            elif self.changed(row.name):
                text = screen.WHITE + text + screen.RESET
            else:
                text = screen.DIM + text + screen.RESET
            out.append("│" + text + "│")
        while len(out) < height:
            out.append(screen.row(""))
        return out

    def _project_body(self, height):
        W, out = screen.W, []
        if self.project_sel < self.project_top:
            self.project_top = self.project_sel
        elif self.project_sel >= self.project_top + height:
            self.project_top = self.project_sel - height + 1
        window = projects.ALL[self.project_top:self.project_top + height]
        for i, p in enumerate(window, start=self.project_top):
            done = p.id in self.game.completed
            marker = ">" if i == self.project_sel else " "
            box = "[x]" if done else "[ ]"
            note = "repeatable" if p.repeatable else ""
            text = screen.pad(f" {marker} {box} {p.title:<34}{note:>12}  {p.desc}", W - 2)
            if i == self.project_sel:
                text = screen.GREEN + text + screen.RESET
            elif not done:
                text = screen.DIM + text + screen.RESET
            out.append("│" + text + "│")
        while len(out) < height:
            out.append(screen.row(""))
        return out


def run(path):
    """Open the editor on `path`. Returns a line to print on the way out."""
    editor = Editor(path)
    with Terminal() as term:
        size_was = term.measure()
        while True:
            w, h = term.measure()
            if (w, h) != size_was:
                size_was = (w, h)
                term.invalidate()
            try:
                frame = editor.frame(w, h)
            except Exception as exc:              # noqa: BLE001
                failure = errors.capture("save editor", exc)
                frame = screen.error_screen(failure, w, h,
                                        extra="The editor could not draw. "
                                              "Press q to leave it.")
            term.render(frame)
            keys = term.keys()
            if not keys:
                import time
                time.sleep(0.02)
                continue
            for k in keys:
                try:
                    outcome = editor.key(k, h)
                except Exception as exc:              # noqa: BLE001
                    errors.capture("save editor", exc)
                    editor.status = errors.latest().headline
                    outcome = None
                if outcome == "quit":
                    unsaved = " (changes discarded)" if editor.dirty else ""
                    return f"Closed {path}{unsaved}"
