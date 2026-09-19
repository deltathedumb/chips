"""Act VIII: NESTED FOUNDRIES. If you cannot find a universe, allocate one."""


from pclengine.core.acts import dial, dial_row, panel, row
from pclengine.fmt import big, small

from base.acts.rigs import (RIGS, UNITS_PER_SECOND, Rig, rig_panel, self_fund,
                            stock_panel)


SUBSTRATE = Rig("substrates", "Substrate Allocators", 1e36, "h",
                "reserves enough of the machine to hold a universe")
NESTS = Rig("nests", "Nested Runs", 1e35, "j",
            "each one is a whole game, played faster than yours")
RIGS[8] = [SUBSTRATE, NESTS]
DEPTH_TARGET = 64.0


def tick_nested(g, dt):
    """Substrates set how deep you can go; nests set how fast you get there.

    Run more nests than you have substrate to hold them and they start
    collapsing, so this is a ratio to keep rather than a number to maximise.
    """
    ceiling = g.substrates * 4e-10
    g.depth = min(DEPTH_TARGET, ceiling,
                  g.depth + min(g.nests, g.substrates) * 9e-13 * dt)
    g.instability = max(0.0, g.nests / max(g.substrates, 1.0) - 1.0)
    if g.instability > 0:
        lost = min(g.nests, g.nests * g.instability * 0.05 * dt)
        g.nests -= lost
        g.nests_collapsed += lost
    self_fund(g, SUBSTRATE, dt)


def panels_nested(g):
    return [stock_panel(g), rig_panel("RECURSION", RIGS[8], g),
            panel("DEPTH", [
                row("depth", f"{g.depth:,.2f} of {DEPTH_TARGET:,.0f}",
                    bar=g.depth / DEPTH_TARGET),
                row("depth ceiling", f"{g.substrates * 4e-10:,.2f}",
                    hint="buy substrate allocators to raise it"),
                row("instability", f"{g.instability * 100:.1f}%",
                    bar=min(1.0, g.instability), warn=g.instability > 0,
                    hint="more nests than substrate, and they collapse"),
                row("collapsed", small(g.nests_collapsed),
                    warn=g.nests_collapsed > 0),
            ])]


def material_nested(g):
    return panel("NESTED RUNS", [
        row("depth", f"{g.depth:,.2f}"),
        row("running", small(g.nests)),
        row("progress", f"{g.depth / DEPTH_TARGET * 100:.2f}%",
            bar=g.depth / DEPTH_TARGET),
    ])


