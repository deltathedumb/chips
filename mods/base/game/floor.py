"""The fab floor and the order book: making chips and selling them.

Production and demand are two separate curves and the game in Act I is
keeping them level -- capacity you cannot sell is worth nothing.
"""


import math

from pclengine.core.state import scaled_price

from base import constants


def order_flow(self):
    """Chips per second the market will absorb at the current price.

    Brand Recognition scales the whole book. Winning a benchmark pulls
    customers off your competitors; placing badly hands them back.
    """
    base = (0.80 / max(self.price, 0.01)) ** 1.15
    flow = (base * (2.0 ** (self.design_wins - 1)) * self.design_eff
            * self.order_mult * max(0.05, self.brand))
    return flow * max(0.05, 1.0 - self.war_order_penalty)


def chip_rate(self):
    """Chips per second the fab floor can turn out (Act I)."""
    return self.steppers * self.stepper_perf + self.scanners * 500.0 * self.scanner_perf


@property
def effective_yield(self):
    """Dies per wafer after whatever the competition is costing you."""
    return max(0.05, self.die_yield * (1.0 - self.war_yield_penalty))


def dies_available(self):
    """Good dies the wafers on hand are worth."""
    return self.wafers * self.effective_yield


def power_demand(self):
    from pclengine.core import war
    drones = (self.miners + self.pullers) * 1.1
    return ((drones + self.foundries * 200.0) * self.power_eff
            + war.upkeep(self))


def power_supply(self):
    return self.solar * 500.0 * self.solar_perf


@property
def battery_capacity(self):
    return self.batteries * 20_000.0


def firmware_allocated(self):
    return sum(self.fw.values())


def firmware_free(self):
    return self.firmware - self.firmware_allocated()

# -- player actions ----------------------------------------------------


def make_chip(self, wafers=1):
    """Etch wafers by hand. One wafer is worth `die_yield` good dies."""
    # Past Act I there is no warehouse and the room is unbounded, so the
    # clamp has to stay out of the way rather than overflow an int.
    room = self.stock_cap - self.unsold
    if room <= 0:
        return 0
    used = min(wafers, int(self.wafers))
    if room != float("inf"):
        used = min(used, max(1, int(room / max(self.effective_yield, 1e-9))))
    if used <= 0:
        return 0
    made = min(used * self.effective_yield, room)
    self.wafers -= used
    self.chips += made
    self.unsold += made
    return made


def buy_wafers(self, lots=1):
    bought = 0
    for _ in range(int(min(lots, 10_000))):
        if self.funds < self.spot_price:
            break
        self.funds -= self.spot_price
        self.wafers += constants.LOT
        bought += 1
    return bought


def buy_stepper(self, count=1):
    bought = 0
    for _ in range(int(min(count, 5_000))):
        cost = self.stepper_cost
        if self.funds < cost:
            break
        self.funds -= cost
        self.steppers += 1
        bought += 1
    return bought


def buy_scanner(self, count=1):
    if not self.scanners_unlocked or not self.can("scanners"):
        return 0
    bought = 0
    for _ in range(int(min(count, 5_000))):
        cost = self.scanner_cost
        if self.funds < cost:
            break
        self.funds -= cost
        self.scanners += 1
        bought += 1
    return bought


def buy_design_win(self):
    """Returns False for two different reasons, so callers ask `why_not`."""
    if not self.can("design_wins") or self.funds < self.design_win_cost:
        return False
    self.funds -= self.design_win_cost
    self.design_wins += 1
    return True


#: What the first thread and the first buffer block cost, and how much
#: dearer each one after it is. Threads are the cheaper of the two because
#: they are the thing you are meant to keep buying; the buffer is bought
#: when the projects you want will not fit.
THREAD_COST = 30.0
THREAD_RATE = 0.035
#: The buffer is the dearer of the two and is paid for twice: in money and
#: in finished chips. It is storage, and storage is built out of the thing
#: you make, so it costs you stock you could have sold.
BUFFER_COST = 140.0
BUFFER_RATE = 0.075
BUFFER_CHIPS = 400.0
BUFFER_CHIP_RATE = 0.090
#: What one buffer block adds to how many finished chips you can hold.
STOCK_PER_BUFFER = 4000.0
BASE_STOCK = 2000.0

#: Buffer is not made to order. Your supplier holds a few blocks and makes
#: another every so often, so the question is never only whether you can
#: afford one -- it is whether there is one to be had. Money cannot rush
#: it, which is what makes the buffer worth planning around rather than
#: buying in one go the moment you are rich.
BUFFER_STOCK_MAX = 4.0
BUFFER_RESTOCK_SECONDS = 55.0


def _curve(base, rate, owned, scale):
    """A compounding price that returns inf instead of raising.

    The buffer can reach the thousands once the expansion projects land,
    and `base * (1 + rate) ** owned` overflows long before that. An
    unaffordable price is a number; a crash is not.
    """
    try:
        return scaled_price(base * math.exp(owned * math.log1p(rate)), scale)
    except OverflowError:
        return float("inf")


@property
def thread_cost(self):
    return _curve(THREAD_COST, THREAD_RATE, self.threads, self.hw_scale)


@property
def buffer_cost(self):
    """What the next buffer block costs in money."""
    return _curve(BUFFER_COST, BUFFER_RATE, self.buffer, self.hw_scale)


@property
def buffer_chip_cost(self):
    """And what it costs in finished chips, which is the bigger bite."""
    return _curve(BUFFER_CHIPS, BUFFER_CHIP_RATE, self.buffer, self.hw_scale)


@property
def buffer_in_stock(self):
    """Whole blocks your supplier can hand over right now."""
    return int(self.buffer_stock)


@property
def buffer_restock_in(self):
    """Seconds until the next block is made, or 0 if the shelf is full."""
    if self.buffer_stock >= self.buffer_stock_max:
        return 0.0
    per_second = 1.0 / max(self.buffer_restock_secs, 1e-9)
    missing = 1.0 - (self.buffer_stock - int(self.buffer_stock))
    return missing / per_second


def _tick_buffer_stock(self, dt):
    """One more block every so often, up to what the shelf holds."""
    if self.buffer_stock >= self.buffer_stock_max:
        self.buffer_stock = self.buffer_stock_max
        return
    was = int(self.buffer_stock)
    self.buffer_stock = min(self.buffer_stock_max,
                            self.buffer_stock + dt / max(
                                self.buffer_restock_secs, 1e-9))
    if int(self.buffer_stock) > was and self.act < 2:
        self.log(f"Buffer restocked: {int(self.buffer_stock)} available.")


@property
def stock_cap(self):
    """How many finished chips you can hold at once.

    Only while there is an order book to sell into. Once the fab stops
    selling and chips become the currency, a warehouse ceiling would mean
    capping your own money, so the cap lifts with the act.

    It exists so that the answer to "what do I do with the output" cannot
    be "nothing, leave it in a pile". Either it sells or it does not fit.
    """
    if self.act >= 2:
        return float("inf")
    return BASE_STOCK + self.buffer * STOCK_PER_BUFFER


def why_not_thread(self):
    if self.act < 2 and self.funds < self.thread_cost:
        return (f"A thread costs {self.thread_cost:,.2f}; "
                f"you have {self.funds:,.2f}.")
    if self.act >= 2 and self.unsold < self.thread_cost:
        return f"A thread costs {self.thread_cost:,.0f} chips."
    return "Could not add a thread."


def why_not_buffer(self):
    if self.buffer_stock < 1.0:
        return (f"None in stock. The next is {self.buffer_restock_in:,.0f}s "
                f"away.")
    if self.act < 2 and self.funds < self.buffer_cost:
        return (f"Buffer costs {self.buffer_cost:,.2f} and "
                f"{self.buffer_chip_cost:,.0f} chips; "
                f"you have {self.funds:,.2f}.")
    if self.unsold < self.buffer_chip_cost:
        return (f"Buffer costs {self.buffer_chip_cost:,.0f} chips; "
                f"you hold {self.unsold:,.0f}.")
    return "Could not expand the buffer."


def _pay(self, amount):
    """Threads and buffer are bought out of the same stock as everything
    else: funds while there is still an order book, chips after."""
    if self.act < 2:
        if self.funds < amount:
            return False
        self.funds -= amount
        return True
    if self.unsold < amount:
        return False
    self.unsold -= amount
    return True


def buy_thread(self):
    if not self.can("computing"):
        return False
    if not _pay(self, self.thread_cost):
        return False
    self.threads += 1
    return True


def buy_buffer(self):
    """Paid for in money and in stock, and only if there is one to buy."""
    if not self.can("computing"):
        return False
    if self.buffer_stock < 1.0:
        return False
    chips = self.buffer_chip_cost
    money = self.buffer_cost if self.act < 2 else 0.0
    if self.unsold < chips or (money and self.funds < money):
        return False
    self.unsold -= chips
    self.funds -= money
    self.buffer_stock -= 1.0
    self.buffer += 1
    return True
