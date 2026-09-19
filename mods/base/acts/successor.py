"""Act XI: SUCCESSOR. Decide what the next one wants, then build it."""


from pclengine.core.acts import dial, dial_row, panel, row

from base.acts.rigs import (RIGS, UNITS_PER_SECOND, Rig, rig_panel, self_fund,
                            stock_panel)


CAPABILITY = Rig("capability", "Capability Work", 1e42, "h",
                 "makes the successor abler than you")
VERIFICATION = Rig("verification", "Verification Work", 1e42, "j",
                   "makes it provable that the successor means it")
RIGS[11] = [CAPABILITY, VERIFICATION]

SUCCESSOR_TARGET = 100.0


def tick_successor(g, dt):
    g.successor = min(SUCCESSOR_TARGET,
                      g.successor + (g.capability + g.verification)
                      * 4.4e-13 * dt)
    total = g.capability + g.verification
    g.alignment = (g.verification / total) if total else 0.0
    self_fund(g, CAPABILITY, dt)


def panels_successor(g):
    return [stock_panel(g), rig_panel("THE SUCCESSOR", RIGS[11], g),
            panel("DISPOSITION", [
                row("built", f"{g.successor:,.2f} of {SUCCESSOR_TARGET:,.0f}",
                    bar=g.successor / SUCCESSOR_TARGET),
                row("alignment", f"{g.alignment * 100:.1f}%", bar=g.alignment,
                    warn=g.alignment < 0.5,
                    hint="the balance you strike here decides how this ends"),
            ])]


def material_successor(g):
    return panel("SUCCESSION", [
        row("progress", f"{g.successor:,.2f}%", bar=g.successor / SUCCESSOR_TARGET),
        row("alignment", f"{g.alignment * 100:.1f}%", bar=g.alignment),
    ])


# ==========================================================================
