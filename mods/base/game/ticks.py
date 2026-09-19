"""What each act does with a second.

One function per act, bound onto Game as `_tick_fab` and friends, plus the
two systems that run underneath every act whatever it is doing.
"""


import math

from base import constants


@property
def price_step(self):
    """How far one press moves the price.

    Proportional, because there is no ceiling any more and a cent at a
    time is no use at fifty dollars a chip. The floor stays at a cent:
    demand goes as a power of the price, and zero is not a price.
    """
    here = self.price
    if here < 1.0:
        return 0.01
    if here < 10.0:
        return 0.10
    if here < 100.0:
        return 1.0
    return round(here * 0.05, 2)


def adjust_price(self, delta):
    """Move the price. Only the sign of `delta` matters; the size comes
    from where the price already is."""
    step = self.price_step
    direction = 1.0 if delta > 0 else -1.0
    self.price = max(0.01, round(self.price + direction * step, 2))


#: Nobody sells at more than this. It is not a rule of the market -- you
#: may set any price you like by hand -- it is a guard on the solver, which
#: divides by the rate it is asked to clear and would otherwise answer
#: "infinity" the moment the line stops.
SOLVER_CEILING = 1_000.0


def clearing_price(self, target=None):
    """The price at which the book just absorbs `target` chips a second.

    An absolute rate, not a multiple of production: production is zero
    whenever the line is stalled, and a solver that multiplies by zero
    answers with a price nobody will ever pay, which is how the line stays
    stalled. Defaults to clearing a fifth more than you are making.

    `order_flow` is a closed form in price, so this inverts it rather than
    groping toward it a cent at a time. The autopricing daemon uses it and
    so does the balance bot, so the machine that plays the game is not
    better at pricing than the one you can buy in it.
    """
    here = max(self.price, 0.01)
    scale = self.order_flow() * (here / 0.80) ** 1.15    # flow at 0.80
    if target is None:
        target = self.chip_rate() * 1.2
    wanted = max(float(target), 1e-6)
    if scale <= 0:
        return here
    return max(0.01, min(SOLVER_CEILING,
                         0.80 * (scale / wanted) ** (1 / 1.15)))


def _tick_autoprice(self, dt):
    """Ease the price toward what clears the line, once automated.

    Eased rather than snapped: a price that teleports every tick makes the
    order book unreadable, and watching it converge is most of what tells
    you the daemon is working.
    """
    if not getattr(self, "autoprice", False) or self.act >= 2:
        return
    target = self.clearing_price()
    blend = min(1.0, dt * 0.6)
    self.price = max(0.01, round(self.price
                                 + (target - self.price) * blend, 2))


def set_price(self, value):
    """Set it outright. No upper bound -- charge what you like, and find
    out what that does to the order book."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        return self.price
    if value != value:                       # nan is not a price
        return self.price
    self.price = max(0.01, round(value, 2))
    return self.price


def adjust_firmware(self, key, delta):
    if delta > 0 and self.firmware_free() <= 0:
        return False
    new = self.fw[key] + delta
    if new < 0 or new > self.firmware:
        return False
    self.fw[key] = new
    return True

# -- simulation --------------------------------------------------------


def _consume(self, chips_wanted):
    """Turn wafers into chips, limited by the dies on hand and by room.

    The warehouse fills. A line running into a full warehouse is a line
    making nothing, which is the point: sell it, or stop making it. The
    ceiling lifts once there is no order book left to sell into.
    """
    room = self.stock_cap - self.unsold
    made = min(chips_wanted, self.dies_available(), max(0.0, room))
    if made <= 0:
        if room <= 0 and self.act < 2:
            self.log("Warehouse full. Drop the price, or buy buffer.")
        return 0.0
    self.wafers -= made / self.effective_yield
    self.chips += made
    self.unsold += made
    return made


def _tick_fab(self, dt):
    made = self._consume(self.chip_rate() * dt)
    self.made_rate = made / dt if dt else 0.0

    if self.auto_procurement and self.wafers < 1 and self.funds >= self.spot_price:
        # Enough to keep the line fed for a minute, not one lot per tick: a
        # tick is not a unit of anything the fab cares about, and buying by
        # the tick quietly stocks ten times faster on a finer clock.
        per_second = self.chip_rate() / max(self.effective_yield, 1e-9)
        self.buy_wafers(max(1, int(per_second * 60.0 / constants.LOT) + 1))

    sold = min(self.unsold, self.order_flow() * dt)
    self.unsold -= sold
    gross = sold * self.price
    self.funds += gross
    self.sold_rate = sold / dt if dt else 0.0
    if dt:
        self.revenue += (gross / dt - self.revenue) * min(1.0, dt * 2)

    # The wafer spot market drifts; a random walk inside sane bounds.
    # The step scales with the square root of dt, not dt: a walk taken in
    # ten small steps has to end up as far from where it started as one
    # taken in a single large one, or the market is quietly ten times more
    # volatile whenever the clock happens to be coarse.
    self.spot_price = min(max(
        self.spot_price + self.rng.uniform(-0.6, 0.6) * math.sqrt(dt),
        14.0), 30.0)


def _tick_lithosphere(self, dt):
    demand, supply = self.power_demand(), self.power_supply()
    if demand <= supply:
        self.power_ratio = 1.0
        self.stored_power = min(self.battery_capacity,
                                self.stored_power + (supply - demand) * dt)
    else:
        drawn = min(self.stored_power, (demand - supply) * dt)
        self.stored_power -= drawn
        self.power_ratio = min(1.0, (supply * dt + drawn) / (demand * dt))

    p = self.power_ratio
    mined = min(self.miners * 0.42 * self.miner_perf * p * dt,
                self.available_matter)
    self.available_matter -= mined
    self.matter += mined
    self.acquired += mined

    pulled = min(self.pullers * 0.42 * self.puller_perf * p * dt, self.matter)
    self.matter -= pulled
    self.wafers += pulled / constants.GRAMS_PER_WAFER

    made = self._consume(self.foundries * 1_000_000.0 * self.foundry_perf * p * dt)
    self.made_rate = made / dt if dt else 0.0


@property
def act_target(self):
    """How much matter the current act is working through.

    Acts that do not consume matter leave `target` unset, so this must
    never hand back None -- the finish check multiplies it.
    """
    from pclengine.core import acts
    target = getattr(acts.get(self.act), "target", None)
    return target if target else constants.UNIVERSE_MATTER


def _tick_light_cone(self, dt):
    if self.seed_fabs <= 0:
        return
    s = self.fw

    # Survey charts fresh matter; mining draws it in.
    reach = self.seed_fabs * (1 + s["thrust"]) * s["survey"] * 1e-14 * dt
    self.explored = min(1.0, self.explored + reach)
    frontier = self.act_target * self.explored - self.acquired
    if frontier > 0:
        mined = min(self.seed_fabs * s["mining"] * 2.6e8 * self.seed_perf * dt,
                    frontier)
        self.acquired += mined
        self.matter += mined

    pulled = min(self.seed_fabs * s["ingot"] * 2.6e8 * self.seed_perf * dt,
                 self.matter)
    self.matter -= pulled
    self.wafers += pulled / constants.GRAMS_PER_WAFER

    made = self._consume(self.seed_fabs * s["litho"] * 2.6e8 * self.seed_perf * dt)
    if dt:
        self.made_rate += made / dt

    born = self.seed_fabs * s["replication"] * 0.009 * dt
    self.seed_fabs += born

    radiation = max(0.0, 5.0 - s["hardening"]) * 0.0006
    self.seed_fabs = max(0.0, self.seed_fabs - self.seed_fabs * radiation * dt)

    # Replication is where forks come from: copies that copied wrong.
    if s["replication"] > 0:
        self.rogue_forks += born * 0.0005 + s["replication"] * 0.01 * dt
    if self.counter_unlocked and self.rogue_forks > 0:
        killed = min(self.rogue_forks, self.seed_fabs * s["counter"] * 0.02 * dt)
        self.rogue_forks -= killed
        self.forks_reclaimed += killed
    if self.rogue_forks > 0:
        lost = min(self.seed_fabs, self.rogue_forks * 0.01 * dt)
        self.seed_fabs -= lost


def _tick_system(self, dt):
    if self.burst_cd > 0:
        self.burst_cd = max(0.0, self.burst_cd - dt)
    if not self.can("computing"):
        return
    self.data = min(self.buffer_bytes, self.data + self.data_rate * dt)
    if self.entropy_on and self.can("entropy") \
            and self.data >= self.buffer_bytes:
        self.entropy += (0.5 + self.threads * 0.25) * self.entropy_mult * dt


def _tick_bandwidth(self):
    while self.bandwidth_from_chips < 28 and self.chips >= self.next_bandwidth:
        self.bandwidth += 1
        self.bandwidth_from_chips += 1
        self.next_bandwidth *= 1.4
        self.log(f"Bandwidth raised to {self.bandwidth}. More silicon authorised.")


#: Tables `self.UNIT_*` reads, bound onto Game alongside the methods.
