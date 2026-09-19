"""The coin market: what the rigs make when they are not breaking things.

Hashes are worth something to somebody. Your rigs split between cracking
the cipher in front of you and mining one of a handful of coins, and the
coins can be sold.

    hashrate x mine share  ->  coins  ->  sold into a moving market

The coins are generated for each run from its seed, so two runs are not
the same market and nobody can look up the right answer. Each gets a
three-letter ticker and a volatility rating, and the rating is the whole
decision:

    STABLE   barely moves. You will not lose, and you will not win.
    STEADY   drifts.
    SWINGY   worth watching.
    FERAL    can double in a minute and has done the other thing too.

Prices mean-revert toward a base, so nothing runs away to zero or to
infinity and waiting is always a live option. Selling moves the price
against you in proportion to how much of the book you take at once, which
is what stops "mine, then dump everything" being the only strategy: a feral
coin sold in one go is a feral coin sold into a hole you dug.

What a coin is worth is tied to what rigs cost, the same way the late acts
tie their payouts to their own hardware. That is what keeps the market
worth using in Act I and still worth using in Act XI, without a table of
era-specific prices nobody would be able to balance.
"""

import math

from pclengine.core.acts import panel, row
from pclengine.fmt import big, money, small

from base import crypt

#: How many coins a run lists.
COUNT = 6
#: Mixed into the run's seed so the market is not the same shape as
#: whatever else that seed decides.
SALT = 0x4D41524B          # "MARK"

#: Per-tier: how hard it swings, how fast it returns to its base, and how
#: deep the book is relative to a holding.
TIERS = [
    ("STABLE", 0.006, 0.020, 90.0),
    ("STEADY", 0.020, 0.012, 55.0),
    ("SWINGY", 0.055, 0.008, 30.0),
    ("FERAL", 0.140, 0.005, 14.0),
]

#: Coins mined per hash, and what one coin at price 1.0 fetches relative to
#: what a rig costs. Both tuned against a run rather than guessed.
COINS_PER_HASH = 0.04
COIN_VALUE = 3.0e-4

LETTERS = "ABCDEFGHIJKLMNPQRSTUVWXYZ"
VOWELS = "AEIOU"


class Coin:
    """One listing: a name, how violently it moves, and what it is worth."""

    __slots__ = ("ticker", "tier", "sigma", "reversion", "depth", "base",
                 "difficulty")

    def __init__(self, ticker, tier, sigma, reversion, depth, base,
                 difficulty):
        self.ticker = ticker
        self.tier = tier
        self.sigma = sigma
        self.reversion = reversion
        self.depth = depth
        self.base = base
        #: Coins per hash, relative. Flat across tiers on purpose: if a
        #: violent coin also paid out less on average, nobody would ever
        #: touch one and the rating would be decoration. Every coin is
        #: worth the same in expectation; what differs is the spread, and
        #: how hard it is to get out of a big position.
        self.difficulty = difficulty


def _ticker(rng, taken):
    """A three-letter ticker that is not already listed."""
    for _ in range(200):
        letters = [rng.choice(LETTERS), rng.choice(VOWELS + LETTERS),
                   rng.choice(LETTERS)]
        ticker = "".join(letters)
        if ticker not in taken:
            return ticker
    return "X" + str(len(taken) + 10)[:2]


def listings(g):
    """The coins this run lists, built from its seed.

    Derived rather than stored: the seed is saved, so the market comes back
    the same on load without a table of it in the save file.
    """
    cached = getattr(g, "_coins", None)
    if cached is not None and cached[0] == g.seed:
        return cached[1]
    import random
    rng = random.Random((g.seed ^ SALT) & 0xFFFFFFFF)
    out, taken = [], set()
    # One of each tier, then the rest wherever the run puts them, so every
    # market has something calm and something dangerous in it.
    order = list(range(len(TIERS)))
    order += [rng.randrange(len(TIERS)) for _ in range(COUNT - len(TIERS))]
    for index in order:
        name, sigma, reversion, depth = TIERS[index]
        ticker = _ticker(rng, taken)
        taken.add(ticker)
        out.append(Coin(ticker, name, sigma, reversion, depth,
                        base=rng.uniform(8.0, 120.0),
                        difficulty=1.0))
    rng.shuffle(out)
    g._coins = (g.seed, out)
    return out


def by_ticker(g, ticker):
    for coin in listings(g):
        if coin.ticker == ticker:
            return coin
    return None


# --------------------------------------------------------------------------
# prices
# --------------------------------------------------------------------------
def price(g, coin):
    return g.coin_prices.get(coin.ticker) or coin.base


def _set_price(g, coin, value):
    g.coin_prices[coin.ticker] = max(coin.base * 0.02, min(value,
                                                           coin.base * 30.0))


def change(g, coin):
    """How far from its base it is, as a fraction."""
    return price(g, coin) / max(coin.base, 1e-9) - 1.0


def tick_prices(g, dt):
    """A mean-reverting walk, scaled so the step size does not change it.

    The noise goes as the square root of dt for the same reason the wafer
    spot market's does: ten small steps have to end up as far from where
    they started as one large one.
    """
    if dt <= 0:
        return
    root = math.sqrt(dt)
    for coin in listings(g):
        here = price(g, coin)
        pull = (coin.base - here) * coin.reversion * dt
        shock = here * coin.sigma * root * g.rng.gauss(0.0, 1.0)
        _set_price(g, coin, here + pull + shock)


# --------------------------------------------------------------------------
# mining and selling
# --------------------------------------------------------------------------
def mined_target(g):
    return by_ticker(g, g.mine_target) or (listings(g) or [None])[0]


def mine_rate(g, coin=None):
    """Coins per second at the current split."""
    coin = coin or mined_target(g)
    if coin is None or g.mine_share <= 0:
        return 0.0
    return (crypt.hashrate(g) * g.mine_share * COINS_PER_HASH
            / coin.difficulty)


def tick_mining(g, dt):
    coin = mined_target(g)
    if coin is None:
        return
    gained = mine_rate(g, coin) * dt
    if gained > 0:
        g.coins[coin.ticker] = g.coins.get(coin.ticker, 0.0) + gained


def holding(g, coin):
    return g.coins.get(coin.ticker, 0.0)


def unit_value(g):
    """What one coin at price 1.0 is worth, in this act's currency.

    Tied to what a rig costs, so the market keeps pace with the game the
    same way the late acts' payouts do.
    """
    rig = crypt.rig_price(g)
    if rig == float("inf") or rig != rig:
        return 0.0
    return rig * COIN_VALUE


#: How much output a book absorbs without complaint, in seconds of your own
#: mining. Sell more than this at once and the price starts giving way.
BOOK_SECONDS = 240.0


def book_depth(g, coin):
    """How many coins this market takes before the price moves.

    Scaled to what your own rigs produce, so a book stays meaningful as the
    hash rate climbs by ten orders of magnitude over a run.
    """
    per_second = max(crypt.hashrate(g) * COINS_PER_HASH / coin.difficulty,
                     1e-9)
    return per_second * BOOK_SECONDS * coin.depth / 30.0


def quote(g, coin, amount):
    """What selling `amount` would fetch, after it moves the price.

    Taking more than the book comfortably holds fills at an average well
    under the screen price, and a thin book gives way sooner. That is what
    makes four quarters worth more than one whole, and what stops a feral
    position being free money to anyone patient enough to wait for a spike.
    """
    if amount <= 0:
        return 0.0, price(g, coin)
    here = price(g, coin)
    impact = amount / max(book_depth(g, coin), 1e-9)
    average = here / (1.0 + impact)
    return amount * average * unit_value(g), average


def sell(g, coin, fraction=1.0):
    """Sell a slice of what you hold. Returns what it fetched."""
    from pclengine.core import currency
    amount = holding(g, coin) * max(0.0, min(1.0, fraction))
    if amount <= 0:
        g.log(f"You hold no {coin.ticker}.")
        return 0.0
    gained, average = quote(g, coin, amount)
    spec = currency.BY_NAME.get(crypt.rig_currency(g))
    if spec is None or gained <= 0:
        return 0.0
    setattr(g, spec.field, spec.held(g) + gained)
    g.coins[coin.ticker] = holding(g, coin) - amount
    g.coins_sold = getattr(g, "coins_sold", 0.0) + amount
    # The sale leaves a mark. It recovers, at whatever rate the tier says.
    _set_price(g, coin, average)
    g.log(f"Sold {small(amount)} {coin.ticker} at {average:,.2f} "
          f"for {spec.text(gained)}.")
    return gained


def adjust_share(g, direction):
    g.mine_share = max(0.0, min(1.0, round(g.mine_share + direction * 0.05, 4)))
    return True


def select(g, index):
    coins = listings(g)
    if 0 <= index < len(coins):
        g.coin_sel = index
        return True
    return False


def selected(g):
    coins = listings(g)
    if not coins:
        return None
    return coins[max(0, min(getattr(g, "coin_sel", 0), len(coins) - 1))]


def tick(g, dt):
    if not crypt.open_for_business(g):
        return
    tick_prices(g, dt)
    tick_mining(g, dt)


# --------------------------------------------------------------------------
# the panel
# --------------------------------------------------------------------------
def open_for_business(g):
    """The market opens with the cipher lab; the rigs are the same rigs."""
    return crypt.open_for_business(g)


def _board(g):
    rows = []
    here = selected(g)
    mining = mined_target(g)
    for index, coin in enumerate(listings(g)):
        drift = change(g, coin)
        mark = ">" if coin is here else " "
        dug = "*" if coin is mining and g.mine_share > 0 else " "
        rows.append(row(f"{mark}{dug}{coin.ticker}  {coin.tier}",
                        f"{price(g, coin):,.2f}  {drift * 100:+.1f}%",

                        warn=drift < -0.15,
                        hint=f"you hold {small(holding(g, coin))}; "
                             f"{coin.tier.lower()}, so it moves "
                             f"{'a lot' if coin.sigma > 0.05 else 'slowly'}"))
    return panel("LISTINGS", rows)


def _position(g):
    coin = selected(g)
    if coin is None:
        return panel("POSITION", [row("nothing listed", "-")])
    from pclengine.core import currency
    spec = currency.BY_NAME.get(crypt.rig_currency(g))
    held = holding(g, coin)
    whole, _average = quote(g, coin, held)
    quarter, _avg = quote(g, coin, held * 0.25)
    return panel("POSITION", [
        row(f"holding {coin.ticker}", small(held)),
        row("sell a quarter", spec.text(quarter) if spec else small(quarter),
            key="o", hint="four quarters fetch more than one whole"),
        row("sell the lot", spec.text(whole) if spec else small(whole),
            key="p", hint="a big sale moves the price against you"),
        row("mine this one", "ENTER",
            hint=f"{small(mine_rate(g, coin))}/s at the current split"),
    ])


def _split(g):
    return panel("HASH SPLIT", [
        row("to mining", f"{g.mine_share * 100:.0f}%",
            bar=g.mine_share,
            hint=", and . move it; the rest goes to the cipher"),
        row("mining", (mined_target(g).ticker if mined_target(g) else "-")
            + f"   {small(mine_rate(g))}/s"),
        row("cracking", f"{small(crypt.hashrate(g) * (1 - g.mine_share))}/s",
            warn=g.mine_share >= 0.999),
    ])


def panels(g):
    return [_board(g), _position(g), _split(g)]


def on_key(g, key):
    coins = listings(g)
    if key in ("UP", "DOWN") and coins:
        here = max(0, min(getattr(g, "coin_sel", 0), len(coins) - 1))
        select(g, max(0, min(here + (1 if key == "DOWN" else -1),
                             len(coins) - 1)))
        return True
    coin = selected(g)
    if key == "ENTER" and coin:
        g.mine_target = coin.ticker
        if g.mine_share <= 0:
            g.mine_share = 0.5
        g.log(f"Rigs now mining {coin.ticker}.")
        return True
    if key == "p" and coin:
        sell(g, coin, 1.0)
        return True
    if key == "o" and coin:
        sell(g, coin, 0.25)
        return True
    if key in (",", "<"):
        adjust_share(g, -1)
        return True
    if key in (".", ">"):
        adjust_share(g, 1)
        return True
    return False


def install(api):
    api.field("coins", lambda: {})
    api.field("coin_prices", lambda: {})
    api.field("mine_share", 0.0)
    api.field("mine_target", "")
    api.field("coin_sel", 0)
    api.field("coins_sold", 0.0)
    api.system_tick(tick)
    api.panel_view("market", "MKT", panels, on_key=on_key,
                   shown=open_for_business,
                   keys="↑↓ pick  ENTER mine  o sell 25%  "
                        "p sell all  , . split")
    api.editor_group("THE COIN MARKET",
                     ["mine_share", "mine_target", "coins_sold"])
