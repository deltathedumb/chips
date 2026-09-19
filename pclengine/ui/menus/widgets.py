"""The panelled menu widget.

A menu is a list of entries in one or more panels. It knows how to draw
itself and which entry is selected; it knows nothing about what choosing one
does, which is what lets the same widget serve every page.
"""


from pclengine import errors
from pclengine.dev import tools
from pclengine.ui import screen

BAR = '│'
#: How wide the left-hand panel of a two-column menu page starts out.
LEFT_W = 34


class Entry:
    __slots__ = ("key", "label", "detail", "action", "value", "enabled",
                 "note", "header")

    def __init__(self, key, label, detail, action=None, value=None,
                 enabled=True, note="", header=False):
        self.header = header
        self.key = key
        self.label = label
        self.detail = detail
        self.action = action
        self.value = value
        self.enabled = enabled
        self.note = note


class Menu:
    """A panelled chooser. `pages` maps a name to a builder returning Entries."""

    def __init__(self, title, page, context):
        self.title = title
        self.page = page
        self.context = context
        self.sel = 0
        self.status = ""
        self.entries = []
        self.prompt = None      # the Entry we are collecting a value for
        self.typed = ""

    # -- drawing ---------------------------------------------------------
    def frame(self, term_w, term_h):
        if term_w < screen.MIN_W or term_h < screen.MIN_H:
            return [f"FOUNDRY needs {screen.MIN_W} columns x {screen.MIN_H} rows."]
        screen.layout(term_w)
        W = screen.W
        left_w = min(LEFT_W + max(0, (W - screen.MIN_W) // 3), W - 30)
        right_w = W - left_w - 3

        try:
            self.entries = self.page(self.context)
        except Exception as exc:              # noqa: BLE001
            errors.capture("menu page", exc)
            self.entries = [Entry("broken", "This page failed to build",
                                  errors.latest().headline, enabled=False)]
            self.status = "See " + errors.LOG_PATH
        if self.entries:
            self.sel = max(0, min(self.sel, len(self.entries) - 1))

        lines = [screen.hrule("┌", "┐"),
                 "│" + screen.BOLD + screen.pad("  F O U N D R Y", W - 2 - 24)
                 + screen.pad(self.title.upper() + "  ", 24) + screen.RESET + "│",
                 screen.hrule("├", "┤", junction="┬", at=left_w + 1)]

        body_h = (term_h - 1) - len(lines) - 4
        body_h = max(6, body_h)
        chosen = self.entries[self.sel] if self.entries else None
        detail = self._detail_lines(chosen, right_w, body_h)

        top = max(0, min(self.sel - body_h // 2,
                         max(0, len(self.entries) - body_h)))
        for row in range(body_h):
            index = top + row
            if index < len(self.entries):
                item = self.entries[index]
                if item.header:
                    right = detail[row] if row < len(detail) else screen.blank(right_w)
                    lines.append(BAR + screen.BOLD
                                 + screen.pad(screen.section(item.label, left_w), left_w)
                                 + screen.RESET + BAR + screen.pad(right, right_w) + BAR)
                    continue
                marker = ">" if index == self.sel else " "
                text = screen.pad(f" {marker} {item.label}", left_w - 13) + " "
                text += screen.pad(item.note, 12)
                if not item.enabled:
                    text = screen.DIM + screen.pad(text, left_w) + screen.RESET
                elif index == self.sel:
                    text = screen.GREEN + screen.pad(text, left_w) + screen.RESET
                else:
                    text = screen.pad(text, left_w)
            else:
                text = screen.blank(left_w)
            right = detail[row] if row < len(detail) else screen.blank(right_w)
            lines.append("│" + text + "│" + screen.pad(right, right_w)
                         + "│")

        lines.append(screen.hrule("├", "┤", junction="┴", at=left_w + 1))
        if self.prompt is not None:
            action = tools.BY_KEY.get(self.prompt.value)
            label = action.arg if action else "value"
            bar = (f"  {self.prompt.label} - {label}: [{self.typed}█]"
                   "   ENTER accept   ESC cancel")
        else:
            bar = "  " + (self.status or "")
        lines.append("│" + screen.pad(bar, W - 2) + "│")
        lines.append(screen.hrule("├", "┤"))
        lines.append("│" + screen.CYAN + screen.pad(
            "  ↑↓ move    ENTER choose    ESC back    q quit", W - 2)
            + screen.RESET + "│")
        lines.append(screen.hrule("└", "┘"))
        return lines

    def _detail_lines(self, entry, width, height):
        if entry is None:
            return []
        out = [screen.blank(width), screen.pad("  " + entry.label, width),
               screen.blank(width)]
        for line in _wrap(entry.detail, width - 4):
            out.append(screen.DIM + screen.pad("  " + line, width) + screen.RESET)
        if entry.note:
            out.append(screen.blank(width))
            out.append(screen.pad("  " + entry.note, width))
        return out[:height]


def _wrap(text, width):
    words, line, out = str(text).split(), "", []
    for word in words:
        if len(line) + len(word) + 1 > width:
            out.append(line)
            line = word
        else:
            line = (line + " " + word).strip()
    if line:
        out.append(line)
    return out


def _wrap(text, width):
    words, line, out = str(text).split(), "", []
    for word in words:
        if len(line) + len(word) + 1 > width:
            out.append(line)
            line = word
        else:
            line = (line + " " + word).strip()
    if line:
        out.append(line)
    return out
