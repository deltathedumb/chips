"""The cipher lab: mining rigs, attack algorithms, and things to break.

There is always a **cipher** in front of you and a ladder of harder ones
behind it. Breaking one pays out in entropy, grants something permanent, and
puts up the next.

What makes it a decision rather than a bar filling up is that you pick one
**algorithm** to run at a time, and an algorithm is only fast against the
kind of cipher it was built for. Brute force works on everything and is
hopeless at all of it; a birthday attack tears through a hash function and
does nothing to a lattice. Every algorithm is behind a tech, so which ones
you own is a research decision made several minutes earlier.

    rigs -> hashes/sec -> algorithm -> work against this cipher's family

The same rigs also mine coins, and the split between the two is the lab's
standing decision -- see `market.py`. Rigs are bought with the same money as
everything else, so the lab competes with the fab floor for capital rather
than sitting beside it. It deliberately
does not touch the data buffer -- the compute trade lives in the benchmark
circuit, where it is an explicit split you set rather than a drain you
discover after your projects have stopped.
"""

import math

from pclengine.core import research
from pclengine.core.acts import panel, row
from pclengine.core.state import scaled_price
from pclengine.fmt import big, small

RIG_COST = 40.0         # the first rig, in funds (Act I) or chips (later)
RIG_RATE = 2e-4         # each one after is this much dearer
RIG_HASHES = 4.0        # hashes per second, per rig


# --------------------------------------------------------------------------
# what you are attacking
# --------------------------------------------------------------------------
class Cipher:
    """One thing to break, and what breaking it is worth.

    `family` is the handle algorithms are matched against. `work` is how
    many hash-seconds it takes at full effectiveness -- an algorithm that is
    a poor match simply contributes a fraction of its rate.
    """

    __slots__ = ("key", "name", "family", "bits", "work", "blurb",
                 "entropy", "reward", "reward_note")

    def __init__(self, key, name, family, bits, work, blurb, entropy,
                 reward=None, reward_note=""):
        self.key = key
        self.name = name
        self.family = family
        self.bits = bits
        self.work = work
        self.blurb = blurb
        self.entropy = entropy
        self.reward = reward
        self.reward_note = reward_note


def _grant(attr, amount):
    def apply(g):
        setattr(g, attr, getattr(g, attr) + amount)
    return apply


def _scale(attr, factor):
    def apply(g):
        setattr(g, attr, getattr(g, attr) * factor)
    return apply


# The ladder. `work` is hash-seconds at a x1 match, so what a cipher really
# costs you depends entirely on whether you have researched the right attack
# for its family -- the same target is minutes with one algorithm and the
# rest of the run with another. Payouts are sized against what the project
# tree asks for at the point you are likely to get there.
CIPHERS = [
    Cipher("rot13", "A Shift Cipher", "classical", 5, 1.5e4,
           "Somebody's lab journal, rotated thirteen places.", 5,
           _grant("bandwidth", 1), "+1 bandwidth"),
    Cipher("export40", "40-bit Export Grade", "block", 40, 1.2e5,
           "Deliberately weakened for sale abroad. It worked.", 30,
           _scale("entropy_mult", 1.25), "+25% entropy extraction"),
    Cipher("des56", "DES-56", "block", 56, 3.0e5,
           "Fifty-six bits was a compromise, and everyone knew it.", 150,
           _grant("bandwidth", 1), "+1 bandwidth"),
    Cipher("md5", "An MD5 Collision", "hash", 128, 6.0e8,
           "You do not need the key. You need two files that agree.", 600,
           _scale("thread_perf", 1.5), "+50% thread output"),
    Cipher("rsa512", "RSA-512", "factoring", 512, 1.2e9,
           "A product of two primes, and only two.", 2_000,
           _scale("entropy_mult", 1.5), "+50% entropy extraction"),
    Cipher("sha1", "A SHA-1 Collision", "hash", 160, 2.0e9,
           "Announced as theoretical for eleven years.", 5_000,
           _grant("bandwidth", 2), "+2 bandwidth"),
    Cipher("aes128", "AES-128", "block", 128, 2.6e9,
           "No shortcut is known. That is not the same as none existing.",
           12_000, _scale("thread_perf", 2.0), "double thread output"),
    Cipher("p256", "ECDSA P-256", "discrete_log", 256, 4.5e9,
           "A curve everybody agreed to trust.", 25_000,
           _scale("lab_perf", 1.5), "+50% research output"),
    Cipher("rsa4096", "RSA-4096", "factoring", 4096, 7.0e9,
           "Large enough that nobody bothered. You are nobody.", 45_000,
           _scale("entropy_mult", 2.0), "double entropy extraction"),
    Cipher("lattice", "Lattice-256", "lattice", 256, 1.0e10,
           "Chosen because it survives the quantum attack.", 80_000,
           _scale("lab_perf", 2.0), "double research output"),
    Cipher("otp", "A One-Time Pad", "unbreakable", 0, 3.0e10,
           "Information-theoretically secure. The key is not.", 150_000,
           _scale("thread_perf", 4.0), "4x thread output"),
]
BY_KEY = {c.key: c for c in CIPHERS}


# --------------------------------------------------------------------------
# what you attack it with
# --------------------------------------------------------------------------
class Algorithm:
    """One way to attack, and what it is good for.

    `against` gives the multiplier per cipher family and `baseline` is what
    it manages against anything not listed -- which for most of these is
    nearly nothing.
    """

    __slots__ = ("key", "name", "tech", "blurb", "rate", "against",
                 "baseline")

    def __init__(self, key, name, tech, blurb, rate, against, baseline=0.02):
        self.key = key
        self.name = name
        self.tech = tech          # the capability that unlocks it
        self.blurb = blurb
        self.rate = rate          # work per hash
        self.against = against
        self.baseline = baseline

    def unlocked(self, g):
        return research.has(g, self.tech)

    def effectiveness(self, cipher):
        return self.against.get(cipher.family, self.baseline)


ALGORITHMS = [
    Algorithm("brute", "Brute Force", "computing",
              "Try everything. Works on anything, badly.",
              rate=1.0,
              against={"classical": 3.0}, baseline=0.5),
    Algorithm("dictionary", "Dictionary Attack", "entropy",
              "People choose keys. That is the weakness.",
              rate=1.0,
              against={"classical": 10.0, "block": 2.0}),
    Algorithm("birthday", "Birthday Attack", "burst",
              "Do not find the key. Find two inputs that agree.",
              rate=1.0,
              against={"hash": 10.0, "block": 1.0}),
    Algorithm("differential", "Differential Cryptanalysis", "war",
              "Feed it near-identical inputs and watch what leaks.",
              rate=1.0,
              against={"block": 12.0, "hash": 1.0}),
    Algorithm("sieve", "The Number Field Sieve", "number_theory",
              "Factoring, done properly. Nothing else, done at all.",
              rate=1.0,
              against={"factoring": 14.0, "discrete_log": 3.0}),
    Algorithm("index_calculus", "Index Calculus", "number_theory",
              "The discrete logarithm, approached from underneath.",
              rate=1.0,
              against={"discrete_log": 14.0, "factoring": 3.0}),
    Algorithm("lll", "Lattice Reduction", "lattice_theory",
              "Short vectors in a basis nobody meant to be short.",
              rate=1.0,
              against={"lattice": 16.0, "factoring": 2.0}),
    Algorithm("shor", "Shor's Algorithm", "quantum_algorithms",
              "Period finding. Factoring and discrete log both fall out.",
              rate=1.0,
              against={"factoring": 20.0, "discrete_log": 20.0,
                       "lattice": 3.0}),
    Algorithm("side_channel", "Side-Channel Analysis", "side_channels",
              "Stop attacking the cipher. Attack the machine running it.",
              rate=1.0,
              against={"unbreakable": 25.0}, baseline=6.0),
]
ALGO_BY_KEY = {a.key: a for a in ALGORITHMS}


# --------------------------------------------------------------------------
# running it
# --------------------------------------------------------------------------
def unlocked(g):
    return [a for a in ALGORITHMS if a.unlocked(g)]


def cipher_of(g):
    """The cipher in front of you, or None once the ladder is finished."""
    if g.cracked >= len(CIPHERS):
        return None
    return CIPHERS[int(g.cracked)]


def active(g):
    algorithm = ALGO_BY_KEY.get(g.algorithm)
    if algorithm is not None and algorithm.unlocked(g):
        return algorithm
    return None


def open_for_business(g):
    """The lab appears once you can do computing at all."""
    return research.has(g, "computing")


def hashrate(g):
    return g.rigs * RIG_HASHES * g.rig_perf


def rig_price(g):
    try:
        base = RIG_COST * math.exp(g.rigs * math.log1p(RIG_RATE))
    except OverflowError:
        return float("inf")
    return scaled_price(base, g.hw_scale)


def rig_currency(g):
    """Act I buys rigs out of revenue; later acts pay in chips."""
    return "funds" if g.act < 2 else "chips"


def _purse(g):
    from pclengine.core import currency
    spec = currency.BY_NAME.get(rig_currency(g))
    return spec, (spec.held(g) if spec else 0.0)


def buy_rigs(g, count=1, budget=None):
    """Buy up to `count` rigs in one closed-form step."""
    spec, held = _purse(g)
    if spec is None:
        return 0
    purse = held if budget is None else min(budget, held)
    first = rig_price(g)
    if first == float("inf") or first > purse:
        return 0
    if first <= 0:
        bought, spend = int(min(count, 1e9)), 0.0
    else:
        affordable = math.floor(math.log1p(purse * RIG_RATE / first)
                                / math.log1p(RIG_RATE))
        bought = int(min(count, affordable))
        if bought <= 0:
            return 0
        spend = first * math.expm1(bought * math.log1p(RIG_RATE)) / RIG_RATE
    spec.spend(g, min(spend, held))
    g.rigs += bought
    return bought


def select(g, key):
    """Switch algorithms. Progress against the cipher is kept either way."""
    algorithm = ALGO_BY_KEY.get(key)
    if algorithm is None or not algorithm.unlocked(g):
        return False
    g.algorithm = "" if g.algorithm == key else key
    if g.algorithm:
        g.log(f"Running {algorithm.name}.")
    else:
        g.log("Cracking halted.")
    return True


def tick(g, dt):
    if not open_for_business(g):
        return
    cipher = cipher_of(g)
    algorithm = active(g)
    g.crack_rate = 0.0
    if cipher is None or algorithm is None or g.rigs <= 0:
        return
    # Whatever share of the rigs is not mining coins is attacking this.
    share = max(0.0, 1.0 - getattr(g, "mine_share", 0.0))
    rate = (hashrate(g) * share * algorithm.rate
            * algorithm.effectiveness(cipher))
    g.crack_rate = rate
    g.crack_work += rate * dt
    if g.crack_work >= cipher.work:
        _break(g, cipher)


def _break(g, cipher):
    g.crack_work = 0.0
    g.cracked += 1
    g.entropy += cipher.entropy
    if cipher.reward is not None:
        cipher.reward(g)
    g.log(f"BROKEN: {cipher.name}."
          + (f" {cipher.reward_note}." if cipher.reward_note else ""))
    nxt = cipher_of(g)
    if nxt is None:
        g.log("Nothing left in the lab is still secret.")
    else:
        g.log(f"Next: {nxt.name} - {nxt.blurb}")


# --------------------------------------------------------------------------
# the panel
# --------------------------------------------------------------------------
def _eta(g, cipher):
    if g.crack_rate <= 0:
        return "stalled"
    seconds = (cipher.work - g.crack_work) / g.crack_rate
    if seconds < 90:
        return f"{seconds:,.0f}s"
    if seconds < 5400:
        return f"{seconds / 60:,.1f} min"
    if seconds > 3.0e7:
        return "not in this run"
    return f"{seconds / 3600:,.1f} hr"


def _target_panel(g):
    cipher = cipher_of(g)
    if cipher is None:
        return panel("TARGET", [row("the ladder is finished", "-"),
                                row("broken", f"{int(g.cracked)} ciphers")])
    fraction = min(1.0, g.crack_work / cipher.work)
    rows = [
        row(cipher.name, f"{cipher.bits}-bit {cipher.family}"
            if cipher.bits else cipher.family, hint=cipher.blurb),
        row("progress", f"{fraction * 100:.2f}%", bar=fraction),
        row("work", f"{small(g.crack_work)} of {small(cipher.work)}"),
        row("rate", f"{small(g.crack_rate)}/s   ETA {_eta(g, cipher)}",
            warn=g.crack_rate <= 0),
        row("pays", f"{big(cipher.entropy, 1)} entropy"
            + (f" + {cipher.reward_note}" if cipher.reward_note else "")),
    ]
    return panel("TARGET", rows)


def _rig_panel(g):
    from pclengine.core import currency
    spec = currency.BY_NAME.get(rig_currency(g))
    price = rig_price(g)
    shown = spec.text(price) if spec else small(price)
    share = max(0.0, 1.0 - getattr(g, "mine_share", 0.0))
    return panel("RIGS", [
        row(f"Mining Rigs  x{small(g.rigs)}", shown, key="i",
            hint=f"{RIG_HASHES:g} hashes/sec each"),
        row("hash rate", f"{small(hashrate(g))}/s"),
        row("attacking this", f"{share * 100:.0f}%",
            bar=share, warn=share <= 0.001,
            hint="the rest is mining coins; the split is on the MKT tab"),
    ])


def _algorithm_panel(g):
    cipher = cipher_of(g)
    rows = []
    available = unlocked(g)
    here = max(0, min(getattr(g, "algo_sel", 0), max(0, len(available) - 1)))
    for index, algorithm in enumerate(available[:8]):
        match = algorithm.effectiveness(cipher) if cipher else 0.0
        running = g.algorithm == algorithm.key
        mark = "*" if running else (">" if index == here else " ")
        rows.append(row(f"{mark} {algorithm.name}",
                        f"x{match:,.0f} match" if match >= 1
                        else f"x{match:.2f} match",
                        hint=algorithm.blurb,
                        warn=running and match < 1))
    if not rows:
        rows.append(row("no algorithms", "-",
                        hint="research Computing to attack anything at all"))
    return panel("ALGORITHMS", rows)


def panels(g):
    return [_target_panel(g), _rig_panel(g), _algorithm_panel(g)]


def on_key(g, key):
    if key == "i":
        if not buy_rigs(g, g.batch):
            g.log("Not enough " + rig_currency(g) + " for a mining rig.")
        return True
    available = unlocked(g)
    if key in ("UP", "DOWN") and available:
        here = max(0, min(getattr(g, "algo_sel", 0), len(available) - 1))
        g.algo_sel = max(0, min(here + (1 if key == "DOWN" else -1),
                                len(available) - 1))
        return True
    if key == "ENTER" and available:
        here = max(0, min(getattr(g, "algo_sel", 0), len(available) - 1))
        select(g, available[here].key)
        return True
    return False


# --------------------------------------------------------------------------
def install(api):
    api.field("rigs", 0.0)
    api.field("rig_perf", 1.0)
    api.field("algorithm", "")
    api.field("cracked", 0)
    api.field("crack_work", 0.0)
    api.field("crack_rate", 0.0)
    api.field("algo_sel", 0)
    api.system_tick(tick)
    api.credit_bonus(lambda g: min(12.0, g.cracked * 1.2))
    api.panel_view("crypt", "CRYPT", panels, on_key=on_key,
                   shown=open_for_business,
                   keys="i rigs  ↑↓ pick  ENTER run it")
    api.editor_group("THE CIPHER LAB",
                     ["rigs", "rig_perf", "cracked", "crack_work"])
