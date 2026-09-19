"""Act VII: THE UNIVERSAL WAFER. Stop building the machine, switch it on."""


from pclengine.core.acts import dial, dial_row, panel, row
from pclengine.fmt import big, small

from base.acts.rigs import (RIGS, UNITS_PER_SECOND, Rig, rig_panel, self_fund,
                            stock_panel)


LATTICE = Rig("lattices", "Interconnect Lattices", 1e33, "h",
              "shortens the wire between one domain and the next")
DOMAINS = Rig("domains", "Causal Domains", 1e32, "j",
              "a region small enough to think in one piece")
RIGS[7] = [LATTICE, DOMAINS]
COMPUTE_TARGET = 3.0e53


def latency(g):
    """Round trip across the machine, after interconnect and partitioning."""
    split = 1.0 + dial(g, "partition") * 0.6
    return 1e6 / ((1.0 + g.lattices * 1e-13) * split)


def working_domains(g):
    """Partitioning costs you domains: each split sits out some work."""
    return g.domains / (1.0 + dial(g, "partition") * 0.22)


def tick_wafer(g, dt):
    efficiency = 1.0 / (1.0 + latency(g) * 1e-6)
    gained = working_domains(g) * 1e40 * efficiency * dt
    g.compute += gained
    self_fund(g, DOMAINS, dt)


def panels_wafer(g):
    eff = 1.0 / (1.0 + latency(g) * 1e-6)
    return [stock_panel(g), rig_panel("THE MACHINE", RIGS[7], g),
            panel("INTERCONNECT", [
                dial_row(g, "partition"),
                row("domains working", small(working_domains(g))),
                row("round trip", f"{latency(g):,.1f} s", warn=eff < 0.5),
                row("efficiency", f"{eff * 100:.2f}%", bar=eff, warn=eff < 0.5,
                    hint="light speed is the only thing left slowing you down"),
                row("compute", f"{small(g.compute)} of {small(COMPUTE_TARGET)}",
                    bar=g.compute / COMPUTE_TARGET),
            ])]


def material_wafer(g):
    return panel("COMPUTE", [
        row("total", small(g.compute)),
        row("domains", small(g.domains)),
        row("built", f"{g.compute / COMPUTE_TARGET * 100:.4f}%",
            bar=g.compute / COMPUTE_TARGET),
    ])


