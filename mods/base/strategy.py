"""How the balance bot plays FOUNDRY, act by act.

The engine's autoplay drives the clock, keeps research moving and garrisons
against whatever is attacking -- all of which is true of any game built on
it. What to *buy* is subject matter, so it lives here, registered per act
with `api.strategy`. A content mod that adds an act adds its strategy the
same way, and `--balance` can then time it.
"""

from pclengine.core import research, war
from pclengine.dev import autoplay
from pclengine.dev.autoplay import hand_etch, paced, spend

from base import bench, constants, crypt, market
from base.acts import final as acts_final, late as acts_late

FIRMWARE_PRIORITY = ["replication", "survey", "mining", "ingot",
                     "litho", "hardening", "thrust", "counter"]


def _price_target(g, rate):
    """Where the bot wants the price.

    The same solver the Autopricing Daemon uses, so the machine that plays
    the game is not better at pricing than the one you can buy in it. The
    `rate` argument lets the caller aim somewhere other than "clear
    everything" -- holding stock back to pay for buffer, mostly.
    """
    return g.clearing_price(rate * 1.2)


def _act_one(g, dt):
    """Keep blanks in stock, keep the market able to absorb the output, then
    spend what is left on capacity. In that order -- capacity you cannot sell
    is worth nothing."""
    hand_etch(g, dt)
    rate = max(g.chip_rate(), 1.0)

    if g.wafers < max(600.0, rate * 30):
        spend(g, g.buy_wafers, g.funds * 0.4, dt, per_second=100)

    # The order book has to keep up with the fab floor.
    if g.order_flow() < rate * 1.2 and g.funds > g.design_win_cost * 1.2:
        for _ in range(paced(g, "design", dt, 2.0)):
            g.buy_design_win()
    # The buffer is bought with finished chips, so a line that sells every
    # chip it makes can never afford one. When something on the list will
    # not fit, ease off the order book and let stock build.
    if autoplay._buffer_short(g) and g.unsold < g.buffer_chip_cost:
        rate = rate * 0.45
    target = _price_target(g, rate)
    for _ in range(paced(g, "price", dt, 4.0)):
        if abs(g.price - target) <= g.price_step * 0.5:
            break
        g.adjust_price(0.01 if target > g.price else -0.01)

    # Hold back enough to be able to afford the next design win.
    reserve = max(g.spot_price * 10, min(g.design_win_cost, g.funds * 0.5))
    if research.available(g):
        reserve = max(reserve, min(research.lab_price(g) * 1.2, g.funds * 0.5))
    if g.scanners_unlocked:
        spend(g, g.buy_scanner, reserve, dt)
        if g.steppers < 80:
            spend(g, g.buy_stepper, reserve, dt)
    else:
        spend(g, g.buy_stepper, reserve, dt)


def _act_two(g, dt):
    g.batch = float("inf")
    hand_etch(g, dt)                   # in case we are broke
    infinity = float("inf")

    # Power first, or everything throttles.
    if g.power_supply() < g.power_demand() * 1.3:
        g.buy_units("solar", infinity, budget=g.unsold * 0.35)
    if g.stored_power < g.power_demand() * 60:
        g.buy_units("battery", infinity, budget=g.unsold * 0.05)
    if g.foundries < 1 or g.wafers > 0:
        g.buy_units("foundry", infinity, budget=g.unsold * 0.3)
    g.buy_units("miner", infinity, budget=g.unsold * 0.4)
    g.buy_units("puller", infinity, budget=g.unsold * 0.5)


def _act_three(g, dt):
    g.launch_seed_fabs(float("inf"), budget=g.unsold * 0.5)
    names = {k for k, _, _ in constants.FIRMWARE_SETTINGS}
    for name in FIRMWARE_PRIORITY:
        if name not in names or g.firmware_free() <= 0:
            continue
        if name == "counter" and not g.counter_unlocked:
            continue
        if g.fw[name] < 6:
            g.adjust_firmware(name, 1)
    if g.rogue_forks > g.seed_fabs * 0.05 and g.counter_unlocked:
        g.adjust_firmware("counter", 1)


def _act_four(g, dt):
    """Lift stars, but keep the radiators ahead of the heat."""
    g.batch = float("inf")
    from base.acts.late import heat_capacity, heat_load
    if heat_capacity(g) < heat_load(g) * 1.3:
        acts_late.buy_radiators(g, float("inf"), budget=g.unsold * 0.5)
    acts_late.buy_lifters(g, float("inf"), budget=g.unsold * 0.4)
    _act_three(g, dt)


def _act_five(g, dt):
    """Claim it before it recedes."""
    g.batch = float("inf")
    acts_late.buy_fronts(g, float("inf"), budget=g.unsold * 0.6)
    _act_three(g, dt)


def _act_late(g, dt):
    """Acts VI+ all look the same to a bot: keep both rigs growing."""
    g.batch = float("inf")
    rigs = acts_final.rigs_for(g.act)
    for rig in reversed(rigs):        # the constraint rig is always second
        rig.buy(g, float("inf"), budget=g.unsold * 0.45)


def _cipher_lab(g, dt):
    """Keep the best-matched algorithm running, and the rigs behind it.

    The bot always picks the highest multiplier it owns, which is the
    obvious play; what it does not do is over-invest, so the rig floor is
    sized against the work left rather than against the purse.
    """
    if not crypt.open_for_business(g):
        return
    cipher = crypt.cipher_of(g)
    if cipher is None:
        return
    owned = crypt.unlocked(g)
    if not owned:
        return
    best = max(owned, key=lambda a: a.effectiveness(cipher) * a.rate)
    if g.algorithm != best.key:
        g.algorithm = best.key
    # Enough rigs to finish this cipher in a few minutes. The lab grows
    # toward that rather than jumping to it, so a target that is currently
    # out of reach costs a steady slice of income instead of the fab floor.
    wanted = cipher.work / max(240.0 * crypt.RIG_HASHES * g.rig_perf
                               * best.rate * best.effectiveness(cipher), 1e-9)
    if g.rigs >= wanted or not paced(g, "rigs", dt, 2.0):
        return
    step = min(wanted - g.rigs, g.rigs * 0.5 + 4.0)
    share = 0.08 if g.act == 1 else 0.12
    crypt.buy_rigs(g, int(step) + 1, budget=_purse(g) * share)


def _purse(g):
    return g.funds if crypt.rig_currency(g) == "funds" else g.unsold


def _benchmark(g, dt):
    """Hold out for first place, then submit.

    Placing badly costs customers, so there is no reason to submit early
    unless the compute is needed elsewhere -- and the bot keeps the split
    small enough that it is not.
    """
    if not bench.open_for_business(g):
        return
    problem = bench.problem_of(g)
    if problem is None:
        g.ops_share = 0.0
        return
    # A fifth of the compute is enough to stay on the circuit without
    # stalling the project tree, which is what the buffer is actually for.
    if g.ops_share <= 0.0:
        g.ops_share = 0.20
    if bench.ratio(g) >= bench.PLACEMENTS[0].ratio:
        bench.submit(g)


#: What the bot leaves mining rather than cracking, and how far above a
#: coin's base it waits before taking some off the table.
MINE_SHARE = 0.35
TAKE_PROFIT = 1.15


def _market(g, dt):
    """Mine the most volatile coin and sell into its spikes.

    The patient play: every coin is worth the same on average, so the one
    worth holding is the one that sometimes trades far above its base. Sell
    a slice at a time, because the book does not take the whole position
    without giving way.
    """
    if not crypt.open_for_business(g) or g.rigs <= 0:
        return
    coins = market.listings(g)
    if not coins:
        return
    wildest = max(coins, key=lambda c: c.sigma)
    if g.mine_target != wildest.ticker:
        g.mine_target = wildest.ticker
    if g.mine_share <= 0:
        g.mine_share = MINE_SHARE
    if not paced(g, "market", dt, 0.5):
        return
    for coin in coins:
        if market.holding(g, coin) <= 0:
            continue
        if market.price(g, coin) >= coin.base * TAKE_PROFIT:
            market.sell(g, coin, 0.25)


def _with_lab(play):
    """Every act runs the two compute branches alongside its own work."""
    def step(g, dt):
        play(g, dt)
        _cipher_lab(g, dt)
        _benchmark(g, dt)
        _market(g, dt)
    return step


def install(api):
    api.strategy(1, _with_lab(_act_one))
    api.strategy(2, _with_lab(_act_two))
    api.strategy(3, _with_lab(_act_three))
    api.strategy(4, _with_lab(_act_four))
    api.strategy(5, _with_lab(_act_five))
    api.strategy(None, _with_lab(_act_late))      # every act from here on looks alike
