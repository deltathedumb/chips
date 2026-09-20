"""Screen composition. Every function returns lines of an exact width so the
terminal can repaint without measuring anything."""

import re

from pclengine.core import acts, projects
from pclengine.store import summary
from pclengine.ui import panels, techtree
from pclengine.fmt import big, dur, money, rate, size, small
from pclengine import content

# Frame geometry. These are rewritten by layout() at the top of every
# render, so the HUD can follow the terminal or a width the player picked.
MIN_W, MAX_W = 80, 200
MIN_H = 24
W = MIN_W
LEFT = 35
RIGHT = W - LEFT - 3
PROJECT_KEYS = "12345678"


def layout(width):
    """Set this frame's column geometry, keeping the 80-column proportions."""
    global W, LEFT, RIGHT
    W = max(MIN_W, min(int(width), MAX_W))
    LEFT = round((W - 3) * 35 / 77)
    RIGHT = W - LEFT - 3
    return W


def frame_width(g, term_w):
    """The width to draw at: the terminal, or the player's chosen cap."""
    chosen = getattr(g, "hud_width", None)
    return term_w if not chosen else min(term_w, chosen)

RESET = "\x1b[0m"
DIM = "\x1b[2m"
BOLD = "\x1b[1m"
CYAN = "\x1b[36m"
GREEN = "\x1b[32m"
YELLOW = "\x1b[33m"
RED = "\x1b[31m"
WHITE = "\x1b[97m"

ACT_NAMES = {
    1: "ACT I  ·  THE FAB",
    2: "ACT II  ·  THE LITHOSPHERE",
    3: "ACT III  ·  THE LIGHT CONE",
}


def node_label(nm):
    return f"{nm:g}nm"


def _cost_note(g):
    """Flag a run whose settings have been altered, so it is never a mystery."""
    project = getattr(g, "cost_scale", 1.0)
    hardware = getattr(g, "hw_scale", 1.0)
    events = getattr(g, "event_scale", 1.0)
    extra = ""
    if abs(events - 1.0) > 1e-9:
        extra = "    events " + ("off" if events == 0 else f"x{events:g}")
    if abs(project - 1.0) < 1e-9 and abs(hardware - 1.0) < 1e-9:
        return extra.strip()
    if abs(project - hardware) < 1e-9:
        return f"costs x{project:g}{extra}"
    return f"costs p{project:g}/h{hardware:g}{extra}"


# --------------------------------------------------------------------------
# primitives
# --------------------------------------------------------------------------
_ANSI = re.compile("\x1b\\[[0-9;]*m")


def vlen(text):
    """Visible length, ignoring colour escapes."""
    return len(_ANSI.sub("", text))


def pad(text, width):
    """Pad or truncate to an exact *visible* width, keeping colour codes."""
    n = vlen(text)
    if n <= width:
        return text + " " * (width - n)
    if not _ANSI.search(text):
        return text[: max(0, width - 1)] + "…"
    out, seen = [], 0
    i = 0
    while i < len(text):
        m = _ANSI.match(text, i)
        if m:
            out.append(m.group())
            i = m.end()
            continue
        if seen >= width - 1:
            break
        out.append(text[i])
        seen += 1
        i += 1
    return "".join(out) + "…" + RESET


def kv(label, value, width, marker=" "):
    label, value = str(label), str(value)
    gap = width - 2 - len(label) - len(value) - len(marker)
    if gap < 1:
        label = label[: max(0, len(label) + gap - 1)] + "…"
        gap = width - 2 - len(label) - len(value) - len(marker)
        gap = max(gap, 1)
    return marker + " " + label + " " * gap + value + " "


def section(title, width):
    head = "─ " + title + " "
    return pad(head + "─" * max(0, width - len(head)), width)


def blank(width):
    return " " * width


def bar(frac, width, fill="█", empty="·"):
    frac = min(max(frac, 0.0), 1.0)
    n = int(round(frac * width))
    return fill * n + empty * (width - n)


def hrule(left, right, width=None, junction=None, at=None):
    width = W if width is None else width
    line = left + "─" * (width - 2) + right
    if junction and at is not None:
        line = line[:at] + junction + line[at + 1:]
    return line


def row(content):
    return "│" + pad(content, W - 2) + "│"


def split_row(left_text, right_text):
    return "│" + pad(left_text, LEFT) + "│" + pad(right_text, RIGHT) + "│"


# --------------------------------------------------------------------------
# panels
# --------------------------------------------------------------------------
def batch_label(g):
    return "MAX" if g.batch == float("inf") else small(g.batch)


def render_panel(block, width):
    """Turn one panel dict into rows of exactly `width` visible columns."""
    out = [section(block["title"], width)]
    for entry in block["rows"]:
        marker = entry.get("key", " ")
        if marker == "price":
            marker = " "
        if entry.get("setting") or entry.get("dial"):
            marker = ">"
        text = kv(entry["label"], entry["value"], width, marker=marker[:1])
        if entry.get("warn"):
            text = RED + pad(text, width) + RESET
        out.append(text)
        if entry.get("bar") is not None:
            meter = bar(entry["bar"], width - 6)
            colour = RED if entry.get("warn") else DIM
            out.append(pad("   " + colour + meter + RESET, width))
    return out


def stack(blocks, width, height):
    out = []
    for block in blocks:
        if out:
            out.append(blank(width))
        out.extend(render_panel(block, width))
    return (out + [blank(width)] * height)[:height] if height else out


def left_panel(g, height=0):
    """The first panel content registered is shown as the headline.

    Its first row is the big number at the top of the HUD and the rest sit
    under it; everything after is drawn as an ordinary panel.
    """
    blocks = panels.left(g)
    if not blocks:
        return [blank(LEFT)]
    headline = blocks[0]
    rows = headline.get("rows", [])
    out = [blank(LEFT), pad("  " + spaced(headline["title"]), LEFT),
           blank(LEFT)]
    if rows:
        out.append(pad("  " + BOLD + WHITE + str(rows[0]["value"]) + RESET,
                       LEFT))
    for entry in rows[1:]:
        out.append(kv(entry["label"], str(entry["value"]), LEFT))
    for block in blocks[1:]:
        out.append(blank(LEFT))
        out.extend(render_panel(block, LEFT))
    return out


def spaced(title):
    """C H I P S -- a title letterspaced for the top of the column."""
    return " ".join(title)


def right_panel(g, height=0):
    out = [pad("  " + DIM + panels.tab_label(g) + RESET, RIGHT)]
    for block in panels.right(g):
        out.append(blank(RIGHT))
        out.extend(render_panel(block, RIGHT))
    return out


# --------------------------------------------------------------------------
# lower sections
# --------------------------------------------------------------------------
def locked_lines(g, count):
    """Projects you cannot see yet, and the one thing each is waiting on."""
    out = []
    for p in projects.ALL:
        if len(out) >= count:
            break
        if p.id in g.completed:
            continue
        try:
            if p.req(g):
                continue
        except Exception:
            continue
        hint = p.unlock_hint(g)
        text = pad(f" [-] {pad(p.title, 30 + max(0, (W - MIN_W) // 3))} "
                   f"{'locked':>20}  {hint}", W - 2)
        out.append("│" + DIM + text + RESET + "│")
    return out


def project_lines(g, count):
    avail = projects.available(g)
    lines = []
    title_w = 30 + max(0, (W - MIN_W) // 3)
    for i, p in enumerate(avail[:count]):
        key = PROJECT_KEYS[i]
        cost = p.cost_text(g)
        text = f" [{key}] {pad(p.title, title_w)} {cost:>20}  {p.desc}"
        text = pad(text, W - 2)
        colour = GREEN if p.affordable(g) else DIM
        lines.append("│" + colour + text + RESET + "│")
    # Spare rows show what is coming, so a stall is never a mystery.
    if len(lines) < count:
        lines.extend(locked_lines(g, count - len(lines)))
    while len(lines) < count:
        lines.append(row(""))
    return lines


def log_lines(g, count):
    msgs = g.messages[-count:]
    pad_count = count - len(msgs)
    out = [row("") for _ in range(pad_count)]
    for m in msgs:
        out.append("│" + DIM + pad("  " + m, W - 2) + RESET + "│")
    return out


def key_line(g):
    """The footer shows the keys for whichever tab you are looking at.

    An act's own keys do nothing while another panel is up, so printing
    them there would only be a lie with good formatting.
    """
    from pclengine.ui import keymap
    keys = keymap.footer(g).strip()
    if getattr(g, "overlay", None):
        return ("│" + CYAN + pad("  " + keys, W - 2) + RESET
                + "│")
    # The number row always means projects now, so it is always worth
    # saying -- unless the tab you are on has already said it.
    if (W >= 96 and "1-8" not in keys
            and dict(keymap.describe(g)).get("projects")):
        keys += "  1-8 projects"
    keys += "  TAB panels  x batch  ? help  q quit"
    return "\u2502" + CYAN + pad("  " + keys, W - 2) + RESET + "\u2502"


#: Shown when no content has said anything about how its game is played.
HELP_FALLBACK = [("HOW TO PLAY", [
    "  No content has registered any help. Whatever is loaded did not say",
    "  how it works, which is something a mod does with api.help_section.",
])]


def help_pagination(sections, rows):
    """Pack sections into pages, breaking between them where it can.

    A heading alone at the foot of a page is worse than a short page, so a
    section that will not fit in what is left starts the next one. A section
    longer than a whole page still has to split; there is nowhere else for
    it to go. Trailing blanks are trimmed rather than carried over, or a
    section that ends level with the boundary produces an empty page.
    """
    pages, page = [], []

    def flush():
        while page and not page[-1][0].strip():
            page.pop()
        if page:
            pages.append(list(page))
        del page[:]

    for heading, lines in sections:
        block = [("  " + heading, True), ("", False)]
        block += [(line, False) for line in lines]
        block.append(("", False))
        if page and len(page) + len(block) > rows:
            flush()
        while len(block) > rows:
            room = rows - len(page)
            if room <= 0:
                flush()
                room = rows
            # Never strand a line or two alone on the next page. Taking a
            # little less now gives the remainder something to sit with.
            remainder = len(block) - room
            if 0 < remainder < 4:
                room = max(1, room - (4 - remainder))
            page.extend(block[:room])
            block = block[room:]
            flush()
        page.extend(block)
    flush()
    return pages or [[]]


def help_body(g, rows):
    """The help, cut into pages that fit the space there is.

    The help is longer than a short terminal, so it is paged rather than
    quietly truncated at whatever row the frame happens to end on. `?`
    turns it on and moves to the next page; the last page closes it.
    """
    sections = content.help_sections() or HELP_FALLBACK
    rows = max(2, rows)
    body = rows - 1                       # the last row is the page marker
    pages = help_pagination(sections, body)
    index = max(0, min(getattr(g, "help_page", 0), len(pages) - 1))
    page = list(pages[index])
    page += [("", False)] * (body - len(page))
    marker = (f"  page {index + 1} of {len(pages)}   "
              + ("? for more" if index + 1 < len(pages) else "? to close"))
    page.append((marker, False))
    # Remembered so the key handler can page without re-deriving the layout.
    g._help_pages = len(pages)
    return page, len(pages)


def help_pages(g, term_h=0):
    """How many pages the help came to when it was last drawn."""
    return max(1, int(getattr(g, "_help_pages", 1)))




# --------------------------------------------------------------------------
# frame assembly
# --------------------------------------------------------------------------
def tech_lines(g, rows):
    """The tech tree, as a two-column body of exactly `rows` rows."""
    left = max(30, (W - 4) * 2 // 5)
    right = W - 2 - left - 3
    listing = techtree.rows(g, left, rows - 2)
    detail = techtree.detail_lines(g, right)
    out = []
    for index in range(rows - 2):
        text, colour = listing[index] if index < len(listing) else ("", "")
        note, note_colour = detail[index] if index < len(detail) else ("", "")
        out.append(colour + pad(text, left) + RESET + DIM + " \u2502 " + RESET
                   + note_colour + pad(note, right) + RESET)
    out.append(pad("", W - 2))
    out.append(DIM + pad(techtree.footer(g), W - 2) + RESET)
    return out


def loan_lines(g, rows):
    """The emergency loan, as a body of exactly `rows` rows.

    Centred and boxed rather than run along the top, because it is the one
    overlay the player did not ask for and it has to read as an event.
    """
    from pclengine.core import rescue
    offer = rescue.offer(g)
    if offer is None:                       # rescued between tick and draw
        return [pad("", W - 2) for _ in range(rows)]

    inner = min(W - 8, 72)
    pane = []
    pane.append(RED + BOLD + "THE LINE HAS STOPPED" + RESET)
    pane.append("")
    pane.append(offer.headline)
    pane.append("")
    for line in offer.detail:
        pane.append(DIM + line + RESET)
    if offer.detail:
        pane.append("")
    pane.append(YELLOW + offer.terms + RESET)
    if getattr(g, "rescue_taken", 0):
        pane.append(DIM + f"You have taken {g.rescue_taken} loan(s) already."
                    + RESET)
    pane.append("")
    pane.append(BOLD + "ENTER  take the loan" + RESET
                + DIM + "     ESC  look around first" + RESET)

    left = max(2, (W - 2 - inner) // 2)
    top = max(0, (rows - len(pane) - 2) // 2)
    out = [pad("", W - 2) for _ in range(top)]
    out.append(" " * left + DIM + "┌" + "─" * inner + "┐" + RESET)
    for text in pane:
        out.append(" " * left + DIM + "│" + RESET
                   + pad(" " + text, inner) + DIM + "│" + RESET)
    out.append(" " * left + DIM + "└" + "─" * inner + "┘" + RESET)
    while len(out) < rows:
        out.append(pad("", W - 2))
    return [pad(line, W - 2) for line in out[:rows]]


def render(g, term_w, term_h, help_on=False, overlay=None):
    if term_w < MIN_W or term_h < MIN_H:
        return [
            f"This game needs a terminal at least {MIN_W} columns x {MIN_H} rows.",
            f"Yours is {term_w} x {term_h}. Please resize and it will redraw.",
        ]
    layout(frame_width(g, term_w))

    left = left_panel(g)
    right = right_panel(g)
    # The body has to fit what is left after the header, projects, log and
    # footer, or the frame spills past the bottom of the terminal.
    # Below the body sit: a divider, the PROJECTS heading, at least two
    # project rows, a divider, at least one log row, a divider, the key line
    # and the bottom rule. With the three header rows that is twelve.
    chrome = 12
    room = max(4, (term_h - 1) - chrome)
    height = min(max(len(left), len(right)), room)
    # The overlay is game state, so the frame reads it rather than relying
    # on every caller to remember to pass it along.
    overlay = (overlay or getattr(g, "overlay", None)
               or ("help" if help_on else None))
    if overlay:
        # Reading takes the screen. The columns shrink to a glance -- the
        # game is still running and you can still see it -- so the overlay
        # gets the room instead of arriving three lines at a time.
        height = min(height, max(4, room // 4))
    left = (left + [blank(LEFT)] * height)[:height]
    right = (right + [blank(RIGHT)] * height)[:height]

    header_right = acts.name_of(g.act) or ACT_NAMES.get(g.act, "")
    node = content.era(g)
    scale = getattr(g, "time_scale", 1.0)
    if abs(scale - 1.0) > 1e-9:
        node += f"    clock x{scale:g}"
    costs = _cost_note(g)
    if costs:
        node += "    " + costs
    left_bit = f"  {dur(g.elapsed)}    {node}"
    title = pad(left_bit, W - 2 - len(header_right) - 2) + header_right + "  "

    lines = [hrule("┌", "┐"), "│" + BOLD + title + RESET + "│",
             hrule("├", "┤", junction="┬", at=LEFT + 1)]
    for l, r in zip(left, right):
        lines.append(split_row(l, r))

    # The projects moved onto a tab, so everything left over down here is
    # the log -- which used to get six rows however much space there was.
    overhead = len(lines) + 4
    room = (term_h - 1) - overhead
    n_log = max(1, min(room, 10))

    lines.append(hrule("├", "┤", junction="┴", at=LEFT + 1))
    if overlay == "tech":
        lines.extend(row(text) for text in tech_lines(g, max(4, room + 1)))
    elif overlay == "loan":
        lines.extend(row(text) for text in loan_lines(g, max(4, room + 1)))
    elif overlay:
        # An overlay takes every row going, not the strip the project list
        # would have used -- that strip is capped at fifteen however tall
        # the terminal is, which turned a long page into forty short ones.
        page, _count = help_body(g, max(4, room + 1))
        lines.extend(row((BOLD + pad(t, W - 2) + RESET) if bold
                         else pad(t, W - 2))
                     for t, bold in page)
    else:
        lines.extend(log_lines(g, n_log))
    lines.append(hrule("├", "┤"))
    lines.append(key_line(g))
    lines.append(hrule("└", "┘"))
    return lines


# --------------------------------------------------------------------------
# full-screen moments
# --------------------------------------------------------------------------
def centered(text_lines, term_w, term_h):
    out = [""] * max(0, (term_h - len(text_lines)) // 2)
    for t in text_lines:
        out.append(" " * max(0, (term_w - len(t)) // 2) + t)
    return out


TITLE_ART = [
    "",
    "  ██████ ██████ ██  ██ ██  ██ █████  █████  ██  ██",
    "  ██     ██  ██ ██  ██ ███ ██ ██  ██ ██  ██ ██  ██",
    "  █████  ██  ██ ██  ██ ██████ ██  ██ █████   ████ ",
    "  ██     ██  ██ ██  ██ ██ ███ ██  ██ ██ ██    ██  ",
    "  ██     ██████ ██████ ██  ██ █████  ██  ██   ██  ",
    "",
]


def intro(term_w, term_h, resumed=False):
    body = list(TITLE_ART) + [
        "",
        "a terminal idle game about a fab, and an optimiser",
        "that was never told when to stop",
        "",
        "",
        "resuming your saved game" if resumed else "you begin with one lot of blank wafers, at 180nm",
        "",
        "press any key to begin       (? for help at any time)",
        "",
    ]
    return centered(body, term_w, term_h)


def ending(g, term_w, term_h):
    """The run summary: what happened, act by act."""
    report = summary.as_dict(g)
    body = ["", report["title"], ""]
    for name, value in report["rows"]:
        body.append(f"{name:<24}{value}")
    if report["acts"]:
        body.append("")
        body.append("time in each act")
        for name, spent in report["acts"]:
            body.append(f"  {name:<28}{spent:>9}")
    body += ["", report["note"], "",
             "ESC for the menu       q to exit", ""]
    return centered(body, term_w, term_h)


def error_screen(failure, term_w, term_h, extra=""):
    """Show a failure inside the UI, with the terminal still intact."""
    from pclengine import errors
    width = max(MIN_W, min(term_w, MAX_W))
    layout(width)
    W = width
    out = [hrule('┌', '┐'),
           '│' + BOLD + RED + pad("  S O M E T H I N G   B R O K E", W - 2)
           + RESET + '│',
           hrule('├', '┤')]
    body = []
    if failure is not None:
        body.append("in " + failure.where
                    + (f"   (x{failure.count})" if failure.count > 1 else ""))
        body.append("")
        body.append(failure.headline)
        body.append("")
        body.extend(failure.trace.rstrip().splitlines()[-14:])
    else:
        body.append("No details were recorded.")
    room = max(4, (term_h - 1) - len(out) - 5)
    for i in range(room):
        text = body[i] if i < len(body) else ""
        colour = RED if text.startswith(("Traceback", "  File")) is False \
            and i == 2 else DIM
        out.append('│' + colour + pad("  " + text, W - 2) + RESET + '│')
    out.append(hrule('├', '┤'))
    note = extra or ("Your run has been saved. Full trace written to "
                     + errors.LOG_PATH)
    out.append('│' + pad("  " + note, W - 2) + '│')
    out.append(hrule('├', '┤'))
    out.append('│' + CYAN + pad(
        "  r resume    ESC menu    q quit and save", W - 2) + RESET + '│')
    out.append(hrule('└', '┘'))
    return out
