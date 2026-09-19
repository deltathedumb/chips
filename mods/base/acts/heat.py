"""Act VI: HEAT DEATH. The matter is spent; start drinking the light."""

import math

from pclengine.core.acts import dial, dial_row, panel, row
from pclengine.fmt import big, small

from base.acts.rigs import (RIGS, UNITS_PER_SECOND, Rig, rig_panel, self_fund,
                            stock_panel)


SHELLS = Rig("shells", "Matrioshka Shells", 1e30, "h",
             "wraps a star and drinks everything it emits")
SINKS = Rig("sinks", "Cold Sinks", 1e29, "j",
            "a colder reservoir means more work per joule")
RIGS[6] = [SHELLS, SINKS]
HEAT_TARGET = 1.2e55


def tick_heat(g, dt):
    # The universe cools on its own; what you can extract depends on how big
    # a temperature difference you can still find.
    g.temperature = max(1e-9, g.temperature * math.exp(-0.0006 * dt))
    cold = 1.0 / (1.0 + g.sinks * 1e-12)
    carnot = max(0.0, 1.0 - cold / max(g.temperature, 1e-9))
    gained = g.shells * 1e42 * carnot * dt
    g.negentropy += gained
    self_fund(g, SHELLS, dt)


def panels_heat(g):
    cold = 1.0 / (1.0 + g.sinks * 1e-12)
    carnot = max(0.0, 1.0 - cold / max(g.temperature, 1e-9))
    return [stock_panel(g), rig_panel("HARVEST", RIGS[6], g),
            panel("THERMODYNAMICS", [
                row("background", f"{g.temperature:.3e} K", bar=g.temperature,
                    warn=g.temperature < 0.2),
                row("carnot ceiling", f"{carnot * 100:.2f}%", bar=carnot,
                    warn=carnot < 0.3),
                row("negentropy", f"{small(g.negentropy)} of {small(HEAT_TARGET)}",
                    bar=g.negentropy / HEAT_TARGET),
            ])]


def material_heat(g):
    return panel("FREE ENERGY", [
        row("negentropy", small(g.negentropy)),
        row("background", f"{g.temperature:.3e} K"),
        row("harvested", f"{g.negentropy / HEAT_TARGET * 100:.4f}%",
            bar=g.negentropy / HEAT_TARGET),
    ])


