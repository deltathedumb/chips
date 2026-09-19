"""A small set of vector icons, and a terminal glyph for each.

Content asks for an icon by name and gets two things: a path a browser can
draw, and a character a terminal can. Neither front end invents its own, so
a tech that is a lens is a lens in both.

The paths are drawn inside a 24x24 box with the origin at the top left, to
be stroked rather than filled -- that keeps them legible at sixteen pixels
and on a dark background, which is where they mostly live.

    icons.get("lens").path     -> SVG path data
    icons.get("lens").glyph    -> a single character

Unknown names fall back to a plain marker instead of raising, because an
icon is decoration and a typo in one should not take a screen down.
"""


class Icon:
    __slots__ = ("name", "path", "glyph")

    def __init__(self, name, path, glyph):
        self.name = name
        #: Stroked SVG path data in a 24x24 box.
        self.path = path
        #: One character, for the front end that cannot draw.
        self.glyph = glyph


#: Deliberately generic: a shape per kind of idea rather than per subject,
#: so content that is not about silicon can still find something that fits.
ICONS = [
    Icon("lens", "M2 12s4-6 10-6 10 6 10 6-4 6-10 6-10-6-10-6z "
                 "M12 9a3 3 0 100 6 3 3 0 000-6z", "◉"),
    Icon("chip", "M8 8h8v8H8z M4 10h4 M4 14h4 M16 10h4 M16 14h4 "
                 "M10 4v4 M14 4v4 M10 16v4 M14 16v4", "▣"),
    Icon("wave", "M2 12c2-6 4-6 6 0s4 6 6 0 4-6 6 0", "∿"),
    Icon("atom", "M12 12m-2 0a2 2 0 104 0 2 2 0 10-4 0 "
                 "M12 2c5 0 9 4.5 9 10s-4 10-9 10-9-4.5-9-10 4-10 9-10 "
                 "M3 7c2.5-4.3 8.5-5 13.5-2s7.5 8.2 5 12.5-8.5 5-13.5 2"
                 "-7.5-8.2-5-12.5z", "⚛"),
    Icon("bolt", "M13 2L5 14h6l-2 8 8-12h-6z", "⚡"),
    Icon("gear", "M12 8a4 4 0 100 8 4 4 0 100-8 M12 2v3 M12 19v3 "
                 "M2 12h3 M19 12h3 M5 5l2 2 M17 17l2 2 M19 5l-2 2 "
                 "M7 17l-2 2", "⚙"),
    Icon("shield", "M12 2l8 4v6c0 5-3.5 8.5-8 10-4.5-1.5-8-5-8-10V6z",
         "⛨"),
    Icon("network", "M12 3v6 M6 21v-4a2 2 0 012-2h8a2 2 0 012 2v4 "
                    "M12 9a3 3 0 100 6 3 3 0 100-6 M6 21h0 M18 21h0", "⌘"),
    Icon("crystal", "M12 2l7 7-7 13-7-13z M5 9h14 M12 2v20", "⬡"),
    Icon("star", "M12 2l3 7 7 .5-5.5 4.5 2 7-6.5-4-6.5 4 2-7L2 9.5 9 9z",
         "✹"),
    Icon("globe", "M12 2a10 10 0 100 20 10 10 0 100-20 M2 12h20 "
                  "M12 2c3 3 3 17 0 20 M12 2c-3 3-3 17 0 20", "◌"),
    Icon("flask", "M9 2v6L4 19a2 2 0 002 3h12a2 2 0 002-3L15 8V2 M8 2h8 "
                  "M7 14h10", "⚗"),
    Icon("key", "M14 4a5 5 0 105 5 M13 10L3 20v2h3v-2h2v-2h2l3-3", "⚷"),
    Icon("eye", "M2 12s4-7 10-7 10 7 10 7-4 7-10 7-10-7-10-7z "
                "M12 10a2 2 0 100 4 2 2 0 100-4", "◈"),
    Icon("clock", "M12 2a10 10 0 100 20 10 10 0 100-20 M12 6v6l4 3", "◴"),
    Icon("infinity", "M7 12a3 3 0 105 2.2c1.5-1.5 2.5-3 4-4.4A3 3 0 1117 12"
                     "a3 3 0 01-5-2.2C10.5 11.3 9.5 12.8 8 14.2A3 3 0 017 12z",
         "∞"),
    Icon("rift", "M12 2c-3 5 3 8 0 10s-3 5 0 10 M6 6c-2 4 2 6 0 8 "
                 "M18 6c2 4-2 6 0 8", "⌇"),
    Icon("branch", "M6 3v8a4 4 0 004 4h4 M18 11v10 M18 11l-4 4 4-4 4 4 "
                   "M6 3h0", "⑂"),
    Icon("cube", "M12 2l9 5v10l-9 5-9-5V7z M12 12l9-5 M12 12v10 M12 12L3 7",
         "⬚"),
    Icon("anvil", "M4 8h10a6 6 0 006 6h-2l-2 4H8l-2-4H4z M8 18h8v3H8z",
         "⚒"),
    Icon("beacon", "M12 2v4 M12 6l-5 14h10z M4 9l3 2 M20 9l-3 2", "⚑"),
    Icon("scales", "M12 3v18 M5 21h14 M12 6l-7 3 M12 6l7 3 "
                   "M2 9a3 3 0 006 0 M16 9a3 3 0 006 0", "⚖"),
]
BY_NAME = {i.name: i for i in ICONS}
FALLBACK = Icon("dot", "M12 8a4 4 0 100 8 4 4 0 100-8", "○")


def get(name):
    return BY_NAME.get(name or "", FALLBACK)


def names():
    return [i.name for i in ICONS]
