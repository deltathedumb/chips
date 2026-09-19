"""Act IX: THE OTHER SWARM. Something else is converting the same volume."""


from pclengine.core.acts import dial, dial_row, panel, row
from pclengine.fmt import big, small

from base.acts.rigs import (RIGS, UNITS_PER_SECOND, Rig, rig_panel, self_fund,
                            stock_panel)


WARFABS = Rig("warfabs", "War Fabs", 1e38, "h",
              "a fab that makes nothing but the means to take a fab")
SCREENS = Rig("screens", "Screening Fleets", 1e37, "j",
              "holds the line while the war fabs build")
RIGS[9] = [WARFABS, SCREENS]


def tick_rival(g, dt):
    """A contest of shares, not of differences.

    Territory drifts toward whichever side holds the larger share of force.
    Using the ratio rather than the gap keeps the act the same length however
    large the numbers were when you arrived, and stops the early buy-up from
    pinning their volume at 100% and doubling the work.
    """
    from pclengine.core import war
    g.rival_strength *= (1.0 + 0.001 * dt)      # standing still loses ground
    mine = g.warfabs * 1e39 + g.screens * 4e38 + war.force(g)
    total = mine + g.rival_strength
    share = mine / total if total > 0 else 0.5
    g.rival_volume = min(0.95, max(0.0,
                                   g.rival_volume + (0.5 - share) * 3.2e-3 * dt))
    if share < 0.5:
        lost = min(g.screens, g.screens * (0.5 - share) * 0.04 * dt)
        g.screens -= lost
        g.units_lost += lost
    self_fund(g, WARFABS, dt)


def panels_rival(g):
    from pclengine.core import war
    mine = g.warfabs * 1e39 + g.screens * 4e38 + war.force(g)
    share = mine / max(mine + g.rival_strength, 1e-9)
    return [stock_panel(g), rig_panel("WAR PRODUCTION", RIGS[9], g),
            panel("THE OTHER SWARM", [
                row("their volume", f"{g.rival_volume * 100:.3f}%",
                    bar=g.rival_volume, warn=g.rival_volume > 0.2),
                row("their strength", small(g.rival_strength), warn=True),
                row("your share of force", f"{share * 100:.1f}%", bar=share,
                    warn=share < 0.5,
                    hint="above half and their volume starts shrinking"),
            ])]


def material_rival(g):
    return panel("CONTESTED SPACE", [
        row("yours", f"{(1 - g.rival_volume) * 100:.3f}%",
            bar=1 - g.rival_volume),
        row("theirs", f"{g.rival_volume * 100:.3f}%"),
        row("units lost", small(g.units_lost), warn=g.units_lost > 0),
    ])


