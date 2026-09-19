"""Drones, foundries, arrays and seed fabs: hardware bought in bulk.

Every kind is priced on the same compounding curve and bought in one
closed-form step, so buying a billion costs the same arithmetic as buying
one and the act cannot be collapsed into three keypresses.
"""

import math

from pclengine.core.state import scaled_price


# The unit price curve: base price of the first unit, and how fast the price
# climbs per unit owned. It is what stops Act II collapsing into three
# keypresses: each purchase is cheap, but a swarm of them is not.


UNIT_COST = {
    "miner": 10.0,
    "puller": 10.0,
    "foundry": 100_000.0,
    "solar": 1_000.0,
    "battery": 500.0,
    "seed_fab": 1e11,
}


UNIT_RATE = {
    "miner": 1e-8,
    "puller": 1e-8,
    "foundry": 1e-6,
    "solar": 1e-9,
    "battery": 1e-9,
    "seed_fab": 1e-9,
}


UNIT_ATTR = {
    "miner": "miners",
    "puller": "pullers",
    "foundry": "foundries",
    "solar": "solar",
    "battery": "batteries",
    "seed_fab": "seed_fabs",
}


UNIT_LABEL = {
    "miner": "Crust Miners",
    "puller": "Ingot Pullers",
    "foundry": "Foundries",
    "solar": "Solar Arrays",
    "battery": "Grid Storage",
    "seed_fab": "Seed Fabs",
}


def unit_price(self, kind):
    """What the next unit of this kind costs."""
    owned = getattr(self, self.UNIT_ATTR[kind])
    try:
        base = self.UNIT_COST[kind] * math.exp(
            owned * math.log1p(self.UNIT_RATE[kind]))
    except OverflowError:
        return float("inf")
    return scaled_price(base, self.hw_scale)


UNIT_TECH = {"miner": "drones", "puller": "pullers",
             "foundry": "foundries", "solar": "power",
             "battery": "power", "seed_fab": "seed_fabs"}


def buy_units(self, kind, count, budget=None):
    """Buy up to `count` units, priced in chips, in one closed-form step.

    Prices form a geometric series, so the largest affordable run is
    solved for directly rather than looped over a billion times.
    `budget` caps the spend without capping the count.
    """
    if not self.can(self.UNIT_TECH.get(kind, kind)):
        return 0
    rate = self.UNIT_RATE[kind]
    first = self.unit_price(kind)
    purse = self.unsold if budget is None else min(budget, self.unsold)
    if first > purse or first == float("inf"):
        return 0
    if first <= 0:                      # sandbox mode: they cost nothing
        bought = int(min(count, 1e9))
        attr = self.UNIT_ATTR[kind]
        setattr(self, attr, getattr(self, attr) + bought)
        return bought
    affordable = math.floor(math.log1p(purse * rate / first) / math.log1p(rate))
    bought = int(min(count, affordable))
    if bought <= 0:
        return 0
    spend = first * math.expm1(bought * math.log1p(rate)) / rate
    self.unsold = max(0.0, self.unsold - spend)
    attr = self.UNIT_ATTR[kind]
    setattr(self, attr, getattr(self, attr) + bought)
    return bought


def launch_seed_fabs(self, count=1, budget=None):
    """Seed fabs are priced like Act II hardware: launching your way to a
    swarm is capped, so the swarm has to build itself."""
    return self.buy_units("seed_fab", count, budget=budget)
