"""Warfare.

Something always wants what you are building. Every act has its own threat and
its own thing to build against it, but the machinery is the same throughout:
you convert chips into FORCE, threats accumulate PRESSURE, and each tick the
two grind against each other. Losing does not end the run -- it costs you
output, stock, or the units themselves.

    force   = sum(units owned * their attack)
    pressure= sum(live threats * their strength)

If pressure exceeds force, the surplus bites whatever that threat targets.
"""

import math

from pclengine.core.acts import panel, row
from pclengine.fmt import big, money, small


# --------------------------------------------------------------------------
# things you can build
# --------------------------------------------------------------------------
class Unit:
    __slots__ = ("key", "name", "act", "cost", "rate", "attack", "upkeep",
                 "blurb", "hotkey", "currency")

    def __init__(self, key, name, act, cost, attack, blurb, hotkey,
                 rate=1e-8, upkeep=0.0, currency="chips"):
        self.currency = currency
        self.key = key
        self.name = name
        self.act = act            # earliest act it can be built in
        self.cost = cost          # chips for the first one
        self.rate = rate          # how fast the price climbs per unit owned
        self.attack = attack      # force contributed by one unit
        self.upkeep = upkeep      # MW each, in acts that have a grid
        self.blurb = blurb
        self.hotkey = hotkey


#: What you can build to defend yourself. Content fills this in.
UNITS = []
BY_KEY = {}


def add_unit(unit):
    UNITS.append(unit)
    BY_KEY[unit.key] = unit
    return unit


def units_for(act):
    return [u for u in UNITS if u.act == act]


# --------------------------------------------------------------------------
# things that want what you have
# --------------------------------------------------------------------------
class Threat:
    __slots__ = ("key", "name", "act", "strength", "growth", "target",
                 "blurb", "trigger")

    def __init__(self, key, name, act, strength, growth, target, blurb,
                 trigger=None):
        self.key = key
        self.name = name
        self.act = act
        self.strength = strength   # force per point of pressure
        self.growth = growth       # compounding rate per second
        self.target = target       # what it damages: see _bite
        self.blurb = blurb
        self.trigger = trigger or (lambda g: True)


#: What comes for you, and in which act. Content fills this in.
THREATS = []
THREAT_BY_KEY = {}


#: target name -> fn(game, amount, dt), what a threat getting through does.
BITES = {}
#: Pressure that is not an attacker. See `PressureSource`.
PRESSURE_SOURCES = []


class PressureSource:
    """Pressure that nobody is applying on purpose.

    Not everything pushing on you is an enemy. FOUNDRY's rogue forks are its
    own machines copied wrong -- pressure by another name -- so content says
    how much there is, how it is worn down when you push back, and how to
    show it, and the engine treats it like any other pressure.
    """

    __slots__ = ("name", "amount", "relieve", "render")

    def __init__(self, name, amount, relieve=None, render=None):
        self.name = name
        self.amount = amount            # fn(game) -> how much
        self.relieve = relieve          # fn(game, amount), optional
        self.render = render            # fn(game) -> text, optional

    def row(self, g):
        held = self.amount(g)
        if held <= 0:
            return None
        from pclengine.core.acts import row as make_row
        from pclengine.fmt import small
        shown = self.render(g) if self.render else small(held)
        return make_row(self.name, shown, warn=True)


def add_bite(target, fn):
    BITES[target] = fn
    return fn


def add_pressure_source(fn):
    PRESSURE_SOURCES.append(fn)
    return fn


def add_threat(threat):
    THREATS.append(threat)
    THREAT_BY_KEY[threat.key] = threat
    return threat


def reset():
    """Forget every unit, threat and target. `loader.load` registers them
    again; nothing here survives a content swap."""
    del UNITS[:], THREATS[:], PRESSURE_SOURCES[:]
    BY_KEY.clear()
    THREAT_BY_KEY.clear()
    BITES.clear()


def threats_for(act):
    return [t for t in THREATS if t.act == act]


# --------------------------------------------------------------------------
# state helpers
# --------------------------------------------------------------------------
def force(g):
    raw = sum(BY_KEY[k].attack * n for k, n in g.forces.items() if k in BY_KEY)
    return raw * getattr(g, "force_mult", 1.0)


def pressure(g):
    """Everything pushing on you: threats, plus whatever content adds.

    Some pressure is not an attacker. FOUNDRY's rogue forks are its own
    machines gone wrong, which is pressure by another name, so content adds
    them here rather than inventing a threat that does not exist.
    """
    total = 0.0
    for key, amount in g.pressure.items():
        threat = THREAT_BY_KEY.get(key)
        if threat:
            total += amount * threat.strength
    for source in PRESSURE_SOURCES:
        total += source.amount(g)
    return total


def unit_price(g, key):
    unit = BY_KEY[key]
    owned = g.forces.get(key, 0)
    from pclengine.core.state import scaled_price
    try:
        base = unit.cost * math.exp(owned * math.log1p(unit.rate))
    except OverflowError:
        return float("inf")
    from pclengine.core import modifiers
    return scaled_price(base, g.hw_scale * modifiers.of(g, "unit_cost"))


def currency_of(unit):
    """What this unit is bought with, as a registered currency."""
    from pclengine.core import currency
    return currency.BY_NAME.get(unit.currency)


def purse_of(g, unit):
    spec = currency_of(unit)
    return spec.held(g) if spec else 0.0


def spend(g, unit, amount):
    spec = currency_of(unit)
    if spec is not None:
        spec.spend(g, min(amount, spec.held(g)))


def buy_unit(g, key, count=1, budget=None):
    unit = BY_KEY.get(key)
    if unit is None or unit.act > g.act:
        return 0
    first = unit_price(g, key)
    available = purse_of(g, unit)
    purse = available if budget is None else min(budget, available)
    if first > purse or first == float("inf"):
        return 0
    if first <= 0:
        bought = int(min(count, 1e9))
    else:
        affordable = math.floor(math.log1p(purse * unit.rate / first)
                                / math.log1p(unit.rate))
        bought = int(min(count, affordable))
    if bought <= 0:
        return 0
    if first > 0:
        spend(g, unit, first * math.expm1(bought * math.log1p(unit.rate))
              / unit.rate)
    g.forces[key] = g.forces.get(key, 0) + bought
    return bought


def upkeep(g):
    return sum(BY_KEY[k].upkeep * n for k, n in g.forces.items() if k in BY_KEY)


# --------------------------------------------------------------------------
# the fight
# --------------------------------------------------------------------------
def tick(g, dt):
    """Grow threats, resolve the grind, apply what gets through."""
    g.war_yield_penalty = 0.0
    g.war_order_penalty = 0.0

    for threat in THREATS:
        if threat.act != g.act or threat.key == "forks":
            continue
        try:
            live = threat.trigger(g)
        except Exception:
            live = False
        if not live:
            continue
        if threat.key not in g.pressure:
            # Seeded from what you can already field, so a threat is never
            # trivially small in a late act nor impossible in an early one.
            g.pressure[threat.key] = max(1.0, force(g) * 0.3)
            g.log(f"{threat.name}: {threat.blurb}")
        g.pressure[threat.key] *= (
            1.0 + threat.growth * getattr(g, "recklessness", 1.0)
            * event_dt(g, dt))

    mine, theirs = force(g), pressure(g)
    g.war_force, g.war_pressure = mine, theirs
    _grind(g, mine, theirs, dt)
    if theirs <= 0:
        return

    # Your force wears the pressure down; whatever is left gets through.
    killed = min(theirs, mine * 0.35 * dt)
    _spend_pressure(g, killed)
    g.threats_repelled += killed
    leak = max(0.0, theirs - mine)
    if leak <= 0:
        return

    for key, amount in list(g.pressure.items()):
        threat = THREAT_BY_KEY.get(key)
        if threat is None or amount <= 0:
            continue
        share = leak * (amount * threat.strength) / max(theirs, 1e-9)
        _bite(g, threat, share, dt)


def _spend_pressure(g, amount):
    """Take `amount` of force-weighted pressure off the board."""
    total = pressure(g)
    if total <= 0:
        return
    for key, value in list(g.pressure.items()):
        threat = THREAT_BY_KEY.get(key)
        if threat is None or value <= 0:
            continue
        portion = amount * (value * threat.strength) / total
        g.pressure[key] = max(0.0, value - portion / max(threat.strength, 1e-9))
    for source in PRESSURE_SOURCES:
        held = source.amount(g)
        if held > 0 and source.relieve is not None:
            source.relieve(g, amount * (held / total))


def _bite(g, threat, amount, dt):
    """Apply damage that got past your force.

    What a threat actually damages is subject matter -- a drone swarm, a
    stock of finished goods, a star lifter -- so content registers one
    handler per target and the engine only dispatches to it.
    """
    handler = BITES.get(threat.target)
    if handler is not None:
        handler(g, amount, dt)


# --------------------------------------------------------------------------
# Losing
# --------------------------------------------------------------------------
INTEGRITY_LOSS = 0.004       # per real second at total overwhelm
INTEGRITY_REGAIN = 0.02      # per second while you are ahead
WARN_AT = (0.6, 0.35, 0.15)


def event_dt(g, dt):
    """Convert a simulation step into EVENT SPEED seconds.

    Threats and integrity run on this rather than on game time. Dividing out
    the clock means changing how fast you play does not change how dangerous
    the world is; `event_scale` is the separate dial for that.
    """
    return (dt / max(0.05, getattr(g, "time_scale", 1.0))
            * max(0.0, getattr(g, "event_scale", 1.0)))


def _grind(g, mine, theirs, dt):
    """Integrity is the clock on losing. Fall behind and it runs down.

    A threat that has only just appeared cannot hurt you yet: the deficit is
    measured against the pressure you have already been holding, so there is
    always time to notice and answer it.
    """
    if theirs <= 0:
        deficit = 0.0
    else:
        deficit = max(0.0, (theirs - mine) / theirs)
        if theirs < g.war_grace:
            deficit = 0.0           # still inside the grace threshold
    g.war_grace = max(g.war_grace, theirs * 0.15)

    before = g.integrity
    step = event_dt(g, dt)
    if deficit > 0:
        g.integrity = max(0.0, g.integrity - deficit * INTEGRITY_LOSS * step)
    else:
        g.integrity = min(1.0, g.integrity + INTEGRITY_REGAIN * step)
    g.lowest_integrity = min(g.lowest_integrity, g.integrity)

    for level in WARN_AT:
        if before > level >= g.integrity:
            g.log(f"Integrity at {g.integrity * 100:.0f}%. "
                  "Build force or you will lose this.")
    if g.integrity <= 0 and not g.defeated:
        g.defeated = True
        g.log("Integrity gone. What you built is being taken apart.")


def time_to_defeat(g):
    """Seconds left at the current rate, or None if you are holding."""
    theirs, mine = g.war_pressure, g.war_force
    if theirs <= 0 or mine >= theirs:
        return None
    deficit = (theirs - mine) / theirs
    rate = deficit * INTEGRITY_LOSS
    return g.integrity / rate if rate > 0 else None


# --------------------------------------------------------------------------
# panel
# --------------------------------------------------------------------------
# The number row belongs to projects, so the defender list is driven the
# way every other list in the game is: a cursor, and ENTER.
def selected_index(g):
    units = units_for(g.act)
    if not units:
        return 0
    return max(0, min(getattr(g, "war_sel", 0), len(units) - 1))


def selected_unit(g):
    units = units_for(g.act)
    return units[selected_index(g)] if units else None


def move_selection(g, delta):
    units = units_for(g.act)
    if units:
        g.war_sel = max(0, min(selected_index(g) + delta, len(units) - 1))
    return True


def buy_selected(g):
    unit = selected_unit(g)
    if unit is None:
        g.log("There is nothing to build in this act.")
        return True
    if not buy_unit(g, unit.key, g.batch):
        g.log(f"Not enough for {unit.name}.")
    return True


def war_panel(g):
    rows = []
    here_unit = selected_unit(g)
    for unit in units_for(g.act):
        owned = g.forces.get(unit.key, 0)
        price = unit_price(g, unit.key)
        spec = currency_of(unit)
        shown = spec.text(price) if spec else small(price)
        rows.append(row(("> " if unit is here_unit else "  ")
                        + f"{unit.name}  x{small(owned)}", shown,
                        hint=unit.blurb))
    live = [(THREAT_BY_KEY[k], v) for k, v in g.pressure.items()
            if k in THREAT_BY_KEY and v > 0]
    for source in PRESSURE_SOURCES:
        extra = source.row(g)
        if extra is not None:
            rows.append(extra)
    status = []
    mine, theirs = g.war_force, g.war_pressure
    countdown = time_to_defeat(g)
    status.append(row("integrity", f"{g.integrity * 100:.1f}%",
                      bar=g.integrity, warn=g.integrity < 0.6,
                      hint="at zero the run is over"))
    if countdown is not None:
        status.append(row("losing in", f"{countdown / 60:,.1f} min",
                          warn=True, hint="build force, or retreat a stage"))
    if mine or theirs:
        share = mine / max(mine + theirs, 1e-9)
        status.append(row("force / pressure", f"{small(mine)} / {small(theirs)}",
                          bar=share, warn=theirs > mine))
    for threat, value in live:
        status.append(row(threat.name, small(value), hint=threat.blurb,
                          warn=True))
    if not status:
        status.append(row("no active threats", "-"))
    return [panel("FORCES", rows or [row("nothing to build yet", "-")]),
            panel("THREATS", status)]


def summary(g):
    """One line for the diagnostics screen."""
    mine, theirs = g.war_force, g.war_pressure
    if not (mine or theirs):
        return "no threats active"
    verdict = "holding" if mine >= theirs else "LOSING GROUND"
    return (f"force {small(mine)} vs pressure {small(theirs)} - {verdict}"
            f"; {small(g.units_lost)} units lost, "
            f"{small(g.matter_ceded)} g ceded")
