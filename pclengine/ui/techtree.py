"""The tech tree, drawn in a terminal.

Fifty nodes will not fit on a screen as a picture, so this is the other
honest way to show a tree: the nodes in dependency order down the left, the
one you are on explained in full on the right.

    > ◉ Photonics                  140   │  PHOTONICS
      ⚛ Quantum Algorithms       9,000   │  The Fab Floor · tier 2
                                         │  Shorter wavelengths...
                                         │  requires  Metrology ✓
                                         │            Computing ✓

Indentation is tier, so what depends on what is still visible; colour is
the branch; the glyph is the same icon the browser draws as a vector.
"""

from pclengine.core import research
from pclengine.fmt import dur, small

#: Category colour names, mapped onto what a terminal actually has.
TERM_COLOURS = {"cyan": "\x1b[36m", "green": "\x1b[32m",
                "yellow": "\x1b[33m", "red": "\x1b[31m",
                "white": "\x1b[97m", "dim": "\x1b[2m"}
#: What each state looks like at the start of a row.
MARKS = {"researched": "■", "working": "◐", "affordable": "◈",
         "available": "◇", "locked": "·", "foreclosed": "✕"}
#: How wide the little progress bar in the cost column is.
BAR = 6


def bar(fraction, width=BAR):
    """A fixed-width bar. One codepoint per cell, like every other glyph
    on this screen, so the exact-width renderer can still count it."""
    filled = max(0, min(width, int(round(fraction * width))))
    return "▰" * filled + "▱" * (width - filled)


def order(g):
    """Every node, roots first, each tier sorted by cost.

    Dependency order rather than alphabetical: reading down the list is
    reading the tree in the order you could actually take it.
    """
    out = []
    for tier in research.tiers():
        for tech in sorted(tier, key=lambda t: t.cost):
            out.append(tech)
    return out


def selected(g, nodes):
    if not nodes:
        return None
    index = max(0, min(getattr(g, "tech_sel", 0), len(nodes) - 1))
    return nodes[index]


def move(g, delta):
    nodes = order(g)
    if not nodes:
        return
    g.tech_sel = max(0, min(getattr(g, "tech_sel", 0) + delta, len(nodes) - 1))


def take(g):
    """Put the selected node on a bench, or take it off again.

    Research is not bought any more, so ENTER commits the labs rather than
    spending a balance. Work already done is kept when you put one aside,
    which is what makes trying something and changing your mind cheap.
    """
    nodes = order(g)
    tech = selected(g, nodes)
    if tech is None:
        return False
    if tech.id in g.researched:
        g.log(f"{tech.name} is already researched.")
        return False
    if tech.shut_out(g):
        g.log(f"{tech.name} was ruled out earlier this run.")
        return False
    if not tech.ready(g):
        g.log(f"{tech.name} needs " + ", ".join(tech.missing(g)) + ".")
        return False
    if research.toggle(g, tech.id):
        return True
    g.log(f"All {research.benches(g)} benches are busy. "
          "Put something aside first.")
    return False


def _colour(detail):
    return TERM_COLOURS.get(detail["term"], "")


def rows(g, width, height):
    """[(text, colour)] for the list column, scrolled to the selection."""
    nodes = order(g)
    if not nodes:
        return [("  the tree is empty -- no content is loaded", "")]
    index = max(0, min(getattr(g, "tech_sel", 0), len(nodes) - 1))
    # Keep the selection in view without jumping the list about: scroll
    # only when it would otherwise leave the window.
    top = max(0, min(index - height // 2, len(nodes) - height))
    out = []
    for position in range(top, min(top + height, len(nodes))):
        tech = nodes[position]
        detail = research.detail(g, tech)
        mark = MARKS.get(detail["state"], "·")
        indent = "  " * min(detail["depth"], 4)
        head = ("> " if position == index else "  ")
        if detail["state"] == "researched":
            cost = "done"
        elif detail["state"] == "working":
            # What it costs stopped being the question the moment work
            # started; how far along it is, is.
            cost = bar(detail["fraction"])
        elif detail["state"] == "foreclosed":
            cost = "ruled out"
        else:
            cost = small(detail["cost"])
        label = f"{head}{mark} {detail['glyph']} {indent}{tech.name}"
        room = max(0, width - len(cost) - 2)
        if len(label) > room:
            label = label[:max(0, room - 1)] + "…"
        if detail["state"] in ("locked", "foreclosed"):
            tint = TERM_COLOURS["dim"]
        elif detail["state"] == "working":
            tint = TERM_COLOURS["yellow"]
        else:
            tint = _colour(detail)
        out.append((label.ljust(room) + " " + cost, tint))
    return out


def detail_lines(g, width):
    """The right-hand column: everything about the node you are on."""
    nodes = order(g)
    tech = selected(g, nodes)
    if tech is None:
        return [("nothing to show", "")]
    d = research.detail(g, tech)
    colour = _colour(d)
    out = [(f"{d['glyph']}  {d['name'].upper()}", colour), ("", "")]
    out.append((f"{d['categoryLabel']}  ·  tier {d['depth']}", ""))
    words = {
        "researched": "researched",
        "working": "on a bench",
        "affordable": "a bench is free -- ENTER to start",
        "available": f"all {research.benches(g)} benches are busy",
        "locked": "locked",
        "foreclosed": "ruled out by a choice earlier this run",
    }
    out.append((words.get(d["state"], d["state"]),
                TERM_COLOURS["dim"] if d["state"] in ("locked", "foreclosed")
                else TERM_COLOURS["yellow"] if d["state"] == "working"
                else colour))
    if d["state"] == "working":
        left = dur(d["eta"]) if d["eta"] is not None else "--"
        out.append((f"{bar(d['fraction'], 12)} {d['fraction'] * 100:.0f}%",
                    TERM_COLOURS["yellow"]))
        out.append((f"{small(d['progress'])} of {small(d['cost'])}  ·  "
                    f"{left} left at this split", TERM_COLOURS["dim"]))
    elif d["state"] not in ("researched", "foreclosed"):
        out.append((f"costs {small(d['cost'])} research", ""))
        if d["progress"] > 0:
            out.append((f"{small(d['progress'])} already done",
                        TERM_COLOURS["dim"]))
    out.append(("", ""))
    out.extend((line, "") for line in _wrap(d["blurb"], width))
    if d["note"]:
        out.append(("", ""))
        out.extend((line, TERM_COLOURS["green"])
                   for line in _wrap(d["note"], width))
    if d["excludes"] and d["state"] != "researched":
        # The one thing a player must not find out afterwards.
        out.append(("", ""))
        out.append(("TAKING THIS RULES OUT", TERM_COLOURS["red"]))
        for name in d["excludes"]:
            out.append((f"  {name}", TERM_COLOURS["red"]))
    if d["requires"]:
        out.append(("", ""))
        out.append(("REQUIRES", ""))
        for need in d["requires"]:
            tick = "✓" if need["done"] else "·"
            out.append((f"  {tick} {need['name']}",
                        TERM_COLOURS["green"] if need["done"]
                        else TERM_COLOURS["dim"]))
    if d["unlocks"]:
        out.append(("", ""))
        out.append(("UNLOCKS", ""))
        for name in d["unlocks"]:
            out.append((f"  {name.replace('_', ' ')}", ""))
    if d["act"]:
        out.append(("", ""))
        out.append((f"OPENS ACT {d['act']}", TERM_COLOURS["yellow"]))
    if d["leadsTo"]:
        out.append(("", ""))
        out.append(("LEADS TO", ""))
        for nxt in d["leadsTo"][:6]:
            out.append((f"  {nxt['name']}", TERM_COLOURS["dim"]))
    return out


def _wrap(text, width):
    words, line, out = text.split(), "", []
    for word in words:
        if line and len(line) + 1 + len(word) > width:
            out.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    if line:
        out.append(line)
    return out


def footer(g):
    """Benches first: it is the number that decides what ENTER can do."""
    nodes = order(g)
    index = min(getattr(g, "tech_sel", 0), max(0, len(nodes) - 1)) + 1
    bench = research.bench_state(g)
    split = (f" at {bench['share'] * 100:.0f}% each"
             if bench["used"] > 1 else "")
    tech = selected(g, nodes)
    verb = ("put aside" if tech is not None and tech.id in g.researching
            else "start")
    return (f"  {index} of {len(nodes)}   {len(g.researched)} researched   "
            f"benches {bench['used']}/{bench['total']}{split}   "
            f"{small(research.output(g))}/s"
            f"   ↑↓ move  ENTER {verb}  T close")
