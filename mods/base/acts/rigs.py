"""The shared hardware descriptor the late acts are built out of.

Past the last atom every act keeps the same shape -- buy two lines of
hardware on a rising price curve, feed a converter, work against a
constraint -- so an act here is a tick, a couple of rigs and a limit rather
than another two hundred lines of buying code.
"""

import math

from pclengine.core.acts import panel, row
from pclengine.fmt import big, small


class Rig:
    """One buyable line of hardware, priced like everything else."""

    __slots__ = ("attr", "label", "cost", "rate", "key", "hint")

    def __init__(self, attr, label, cost, key, hint, rate=1e-10):
        self.attr = attr
        self.label = label
        self.cost = cost
        self.rate = rate
        self.key = key
        self.hint = hint

    def price(self, g):
        from pclengine.core.state import scaled_price
        try:
            base = self.cost * math.exp(getattr(g, self.attr)
                                        * math.log1p(self.rate))
        except OverflowError:
            return float("inf")
        return scaled_price(base, g.hw_scale)

    def buy(self, g, count=1, budget=None):
        first = self.price(g)
        purse = g.unsold if budget is None else min(budget, g.unsold)
        if first > purse or first == float("inf"):
            return 0
        if first <= 0:
            bought = int(min(count, 1e9))
        else:
            bought = int(min(count, math.floor(
                math.log1p(purse * self.rate / first) / math.log1p(self.rate))))
        if bought <= 0:
            return 0
        if first > 0:
            g.unsold = max(0.0, g.unsold - first * math.expm1(
                bought * math.log1p(self.rate)) / self.rate)
        setattr(g, self.attr, getattr(g, self.attr) + bought)
        return bought

    def as_row(self, g):
        return row(f"{self.label}  x{small(getattr(g, self.attr))}",
                   f"{small(self.price(g))} chips", key=self.key,
                   hint=self.hint)


def rig_panel(title, rigs, g, extra=()):
    return panel(title, [r.as_row(g) for r in rigs] + list(extra))


def stock_panel(g):
    return panel("CHIP STOCK", [row("available to spend", small(g.unsold))])


# Past Act V chips are a bookkeeping unit, not an economy: the only thing
# they buy is this act's own hardware. Each act therefore pays out at a rate
# tied to what its hardware currently costs, which makes unit growth roughly
# linear and the act's length something we can actually set.
UNITS_PER_SECOND = 6e8


def self_fund(g, rig, dt, rate=UNITS_PER_SECOND):
    """Pay the act enough to keep buying `rig` at `rate` units per second."""
    price = rig.price(g)
    if price == float("inf"):
        return
    payout = price * rate * dt
    g.unsold += payout
    g.chips += payout
    g.made_rate = payout / dt if dt else 0.0


RIGS = {}


def rigs_for(act):
    return RIGS.get(act, [])


def buy_by_key(g, key, count):
    for rig in rigs_for(g.act):
        if rig.key == key:
            return rig.buy(g, count)
    return 0


