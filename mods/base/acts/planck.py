"""Act X: BELOW PLANCK. The constants were only ever defaults."""


from pclengine.core.acts import dial, dial_row, panel, row
from pclengine.fmt import big, small

from base.acts.rigs import (RIGS, UNITS_PER_SECOND, Rig, rig_panel, self_fund,
                            stock_panel)


EDITORS = Rig("editors", "Constant Editors", 1e40, "h",
              "rewrites a dimensionless number and waits to see what breaks")
ANCHORS = Rig("anchors", "Causal Anchors", 1e39, "j",
              "holds the rest of physics still while you work")
RIGS[10] = [EDITORS, ANCHORS]
PLANCK_TARGET = 40.0


def tick_planck(g, dt):
    push = 1.0 + dial(g, "aggression") * 0.5
    pressure = g.editors * 2e-12 * push
    hold = 1.0 + g.anchors * 2e-12
    g.stability = max(0.0, min(1.0, g.stability + (hold - pressure) * 0.02 * dt))
    if g.stability <= 0.05:
        lost = min(g.editors, g.editors * 0.06 * dt)
        g.editors -= lost
        g.regions_lost += lost
    g.constants_edited = min(PLANCK_TARGET,
                             g.constants_edited
                             + min(g.editors, g.anchors) * 4.8e-13
                             * push * g.stability * dt)
    self_fund(g, EDITORS, dt)


def panels_planck(g):
    return [stock_panel(g), rig_panel("PHYSICS", RIGS[10], g),
            panel("STABILITY", [
                dial_row(g, "aggression"),
                row("constants edited",
                    f"{g.constants_edited:,.2f} of {PLANCK_TARGET:,.0f}",
                    bar=g.constants_edited / PLANCK_TARGET),
                row("stability", f"{g.stability * 100:.1f}%", bar=g.stability,
                    warn=g.stability < 0.25,
                    hint="anchors hold it up, editors push it down"),
                row("regions decohered", small(g.regions_lost),
                    warn=g.regions_lost > 0),
            ])]


def material_planck(g):
    return panel("THE CONSTANTS", [
        row("edited", f"{g.constants_edited:,.2f}"),
        row("stability", f"{g.stability * 100:.1f}%", bar=g.stability),
        row("progress", f"{g.constants_edited / PLANCK_TARGET * 100:.2f}%",
            bar=g.constants_edited / PLANCK_TARGET),
    ])
