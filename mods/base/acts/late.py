"""Acts beyond the light cone.

Act III used to run all the way to the last atom. It now stops at the galaxy,
and these take over: first the stars themselves, then a race against the
expansion of space, which is the first thing in the game that can take
something away from you permanently.
"""

import math

from pclengine.core import acts
from pclengine.core.acts import Act, dial, dial_row, panel, row
from pclengine.fmt import big, small

from base import constants

# --------------------------------------------------------------------------
# Act IV - stellar lifting
# --------------------------------------------------------------------------
LIFTER_COST = 1e18
LIFTER_RATE = 1e-10
LIFTER_YIELD = 3.4e34   # grams/s per lifter, sized against lift_perf x40
HEAT_PER_LIFTER = 1.0
RADIATOR_COST = 1e17
RADIATOR_RATE = 1e-10
RADIATOR_CAP = 40.0        # heat one radiator can shed


def lifter_price(g):
    from pclengine.core.state import scaled_price
    try:
        base = LIFTER_COST * math.exp(g.lifters * math.log1p(LIFTER_RATE))
    except OverflowError:
        return float("inf")
    return scaled_price(base, g.hw_scale)


def radiator_price(g):
    from pclengine.core.state import scaled_price
    try:
        base = RADIATOR_COST * math.exp(g.radiators * math.log1p(RADIATOR_RATE))
    except OverflowError:
        return float("inf")
    return scaled_price(base, g.hw_scale)


def _buy(g, attr, price_fn, rate, count, budget=None):
    first = price_fn(g)
    purse = g.unsold if budget is None else min(budget, g.unsold)
    if first > purse or first == float("inf"):
        return 0
    if first <= 0:
        bought = int(min(count, 1e9))
    else:
        bought = int(min(count, math.floor(
            math.log1p(purse * rate / first) / math.log1p(rate))))
    if bought <= 0:
        return 0
    if first > 0:
        g.unsold = max(0.0, g.unsold - first
                       * math.expm1(bought * math.log1p(rate)) / rate)
    setattr(g, attr, getattr(g, attr) + bought)
    return bought


def self_fund(g, price, dt, rate=4e8):
    """Pay the act enough to keep buying at `rate` units per second.

    Acts IV and V inherit an absurd chip pile from the swarm, which would let
    them buy every rig in one step. Zeroing that on entry and paying out
    against the current price makes unit growth linear, so the act has a
    length that can be set rather than one that falls out of history.
    """
    if price == float("inf"):
        return
    payout = price * rate * dt
    g.unsold += payout
    g.chips += payout


def buy_lifters(g, count=1, budget=None):
    return _buy(g, "lifters", lifter_price, LIFTER_RATE, count, budget)


def buy_radiators(g, count=1, budget=None):
    return _buy(g, "radiators", radiator_price, RADIATOR_RATE, count, budget)


def overdrive_gain(g):
    """Each point is +40% mass but a squared rise in heat."""
    return 1.0 + 0.4 * dial(g, "overdrive")


def overdrive_heat(g):
    step = dial(g, "overdrive")
    return 1.0 + (step / 3.0) ** 2


def heat_load(g):
    return (g.lifters * HEAT_PER_LIFTER * g.lift_perf ** 0.25
            * overdrive_heat(g))


def heat_capacity(g):
    return g.radiators * RADIATOR_CAP * g.radiator_perf


def tick_stellar(g, dt):
    """Lifting rigs are the whole chain here.

    The swarm that got you this far still replicates, but it neither mines
    nor etches in this act -- if it did, its output would buy every rig in
    the first second and the act would be over before it started. Spendable
    chips come only from `self_fund`, so rig growth is paced.
    """
    load, capacity = heat_load(g), heat_capacity(g)
    g.heat_ratio = 1.0 if load <= capacity else capacity / max(load, 1e-9)

    # Run too hot and lifters cook themselves. This destroys hardware rather
    # than throttling it, which is what makes it different from power.
    if g.heat_ratio < 1.0:
        burned = min(g.lifters, g.lifters * (1.0 - g.heat_ratio) * 0.08 * dt)
        g.lifters -= burned
        g.lifters_burned += burned

    lifted = min(g.lifters * LIFTER_YIELD * g.lift_perf * g.heat_ratio
                 * overdrive_gain(g) * dt, g.available_matter)
    g.available_matter -= lifted
    g.acquired += lifted
    made = lifted / constants.GRAMS_PER_WAFER * g.effective_yield
    g.chips += made
    g.made_rate = made / dt if dt else 0.0

    self_fund(g, lifter_price(g), dt)


def stellar_panels(g):
    load, capacity = heat_load(g), heat_capacity(g)
    rigs = [
        row(f"Star Lifters  x{small(g.lifters)}",
            f"{small(lifter_price(g))} chips", key="h",
            hint="peels mass off a star; runs hot"),
        row(f"Radiators  x{small(g.radiators)}",
            f"{small(radiator_price(g))} chips", key="j",
            hint="sheds heat so lifters survive"),
        row("lifters lost to heat", small(g.lifters_burned),
            warn=g.lifters_burned > 0),
    ]
    thermal = [
        dial_row(g, "overdrive"),
        row("load / capacity", f"{small(load)} / {small(capacity)}"),
        row("running at", f"{g.heat_ratio * 100:.1f}%", bar=g.heat_ratio,
            warn=g.heat_ratio < 0.999,
            hint="below 100% your lifters are burning up"),
    ]
    return [panel("CHIP STOCK", [row("available to spend", small(g.unsold))]),
            panel("LIFTING RIGS", rigs),
            panel("THERMAL", thermal)]


def stellar_material(g):
    frac = g.acquired / constants.LOCAL_GROUP_MATTER
    return panel("STELLAR MASS", [
        row("unlifted", f"{small(g.available_matter)} g"),
        row("lifted", f"{small(g.matter)} g"),
        row("blank wafers", small(g.wafers)),
        row("local group taken", f"{frac * 100:.4f}%", bar=frac),
    ])


# --------------------------------------------------------------------------
# Act V - the receding horizon
# --------------------------------------------------------------------------
FRONT_COST = 1e26
FRONT_RATE = 1e-11
HORIZON_DECAY = 0.0009      # fraction of the remaining universe lost per second
FRONT_HOLD = 4e-14          # how much one expansion front slows that


def front_price(g):
    from pclengine.core.state import scaled_price
    try:
        base = FRONT_COST * math.exp(g.fronts * math.log1p(FRONT_RATE))
    except OverflowError:
        return float("inf")
    return scaled_price(base, g.hw_scale)


def buy_fronts(g, count=1, budget=None):
    return _buy(g, "fronts", front_price, FRONT_RATE, count, budget)


def decay_rate(g):
    """How fast the reachable universe is shrinking, after your fronts."""
    hold = 1.0 / (1.0 + g.fronts * FRONT_HOLD * g.front_hold)
    return HORIZON_DECAY * hold


def tick_horizon(g, dt):
    """Expansion fronts are the whole chain here, for the same reason."""
    before = g.horizon * constants.UNIVERSE_MATTER
    g.horizon = max(0.0, g.horizon - decay_rate(g) * dt)
    reachable = g.horizon * constants.UNIVERSE_MATTER
    g.matter_receded += max(0.0, before - reachable)

    frontier = max(0.0, reachable - g.acquired)
    claim = min(g.fronts * 0.60e41 * g.front_perf * dt, frontier)
    g.acquired += claim
    made = claim / constants.GRAMS_PER_WAFER * g.effective_yield
    g.chips += made
    g.made_rate = made / dt if dt else 0.0

    self_fund(g, front_price(g), dt)


def horizon_panels(g):
    reachable = g.horizon * constants.UNIVERSE_MATTER
    frontier = max(0.0, reachable - g.acquired)
    rows = [
        row(f"Expansion Fronts  x{small(g.fronts)}",
            f"{small(front_price(g))} chips", key="h",
            hint="claims matter, and slows the horizon closing"),
    ]
    clock = [
        row("still reachable", f"{small(reachable)} g", bar=g.horizon,
            warn=g.horizon < 0.5),
        row("not yet claimed", f"{small(frontier)} g",
            warn=frontier <= 0),
        row("receding at", f"{decay_rate(g) * 100:.4f}%/s",
            warn=decay_rate(g) > 0.0005),
        row("lost for good", f"{small(g.matter_receded)} g",
            warn=g.matter_receded > 0),
    ]
    return [panel("CHIP STOCK", [row("available to spend", small(g.unsold))]),
            panel("THE FRONT", rows),
            panel("THE HORIZON", clock)]


def horizon_material(g):
    frac = g.acquired / constants.UNIVERSE_MATTER
    return panel("THE UNIVERSE", [
        row("claimed", f"{small(g.acquired)} g"),
        row("mined", f"{small(g.matter)} g"),
        row("blank wafers", small(g.wafers)),
        row("universe taken", f"{frac * 100:.6f}%", bar=frac),
        row("receded", f"{small(g.matter_receded)} g",
            warn=g.matter_receded > 0),
    ])


# --------------------------------------------------------------------------
def install():
    acts.get(3).target = constants.GALAXY_MATTER
    acts.register(Act(4, "stellar", "ACT IV  ·  STELLAR LIFTING",
                      "Stop collecting rubble. Take the stars apart.",
                      tick_stellar, stellar_panels, stellar_material,
                      keys="h lifters  j radiators  ←→ overdrive  x batch"))
    acts.get(4).target = constants.LOCAL_GROUP_MATTER
    acts.register(Act(5, "horizon", "ACT V  ·  THE RECEDING HORIZON",
                      "Space is expanding. Claim it before it leaves.",
                      tick_horizon, horizon_panels, horizon_material,
                      keys="h fronts  x batch"))
    acts.get(5).target = constants.UNIVERSE_MATTER
    # You cannot take what has already left. The act is over when everything
    # still inside the horizon is yours, however much got away.
    acts.get(5).complete = lambda g: (
        g.horizon * constants.UNIVERSE_MATTER - g.acquired <= constants.UNIVERSE_MATTER * 1e-9)
