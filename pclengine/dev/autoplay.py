"""A bot that plays the game with no UI attached.

It exists to sanity-check pacing: if the bot cannot get out of Act I in a
sensible number of minutes, the numbers are wrong. `--sim` runs it.

What it does every tick -- keep research moving, garrison against whatever
is attacking, spend the bandwidth, take the affordable projects -- is true
of any game on this engine. What to *buy* is not, so content registers a
strategy per act with `api.strategy` and this module dispatches to it.
"""

from pclengine import content
from pclengine.core import projects, research, war
from pclengine.fmt import big, dur
from pclengine.core.state import Game

#: act number -> fn(g, dt). The key None is the fallback for later acts.
STRATEGIES = {}


def add_strategy(act, fn):
    STRATEGIES[act] = fn
    return fn


def strategy_for(act):
    return STRATEGIES.get(act) or STRATEGIES.get(None)


def reset():
    STRATEGIES.clear()


def _spend_bandwidth(g):
    """Grow the compute floor, out of a slice of the purse rather than all
    of it.

    Threads and the buffer cost the same money the fab floor does, so a bot
    that buys them until it is broke has simply chosen compute over
    production. Half the purse, and never past the bandwidth ceiling --
    threads beyond it carry nothing.
    """
    purse = g.funds if g.act < 2 else g.unsold
    floor = purse * 0.5
    for _ in range(500):
        spendable = g.funds if g.act < 2 else g.unsold
        if g.free_bandwidth <= 0 or spendable <= floor or not g.buy_thread():
            break
    # The buffer exists to hold what you are about to buy. Grow it until
    # the cheapest thing that does not fit, fits -- a project priced above
    # your capacity can never be bought, and the bot used to stall on
    # exactly that without ever being told why.
    for _ in range(200):
        spendable = g.funds if g.act < 2 else g.unsold
        if spendable <= floor or not _buffer_short(g):
            break
        if getattr(g, "buffer_in_stock", 1) < 1 or not g.buy_buffer():
            break


def _buffer_short(g):
    """Is something on the list priced above what the buffer can hold?"""
    capacity = getattr(g, "buffer_bytes", 0)
    for project in projects.available(g):
        if project.ends_run:
            continue
        wanted = project.scaled_cost(g).get("data", 0.0)
        if wanted > capacity:
            return True
    return False


def _buy_projects(g, skip=()):
    for p in projects.available(g):
        if p.id in skip or p.ends_run:
            continue
        if p.affordable(g):
            p.buy(g)


def paced(g, name, dt, per_second):
    """How many times a keypress-shaped action should fire this step.

    Anything the bot does "once per step" -- take a design win, nudge the
    price -- is really a keypress, and a keypress happens at a rate in game
    seconds, not once per tick. Without this the harness runs faster at a
    fine step than a coarse one and its shortcut stops being honest.
    """
    key = "_pace_" + name
    carry = getattr(g, key, 0.0) + per_second * dt
    whole = int(carry)
    setattr(g, key, carry - whole)
    return whole


def hand_etch(g, dt, per_second=4.0):
    """Press SPACE at a steady rate, whatever the step size is."""
    g._bot_carry = getattr(g, "_bot_carry", 0.0) + per_second * dt
    whole = int(g._bot_carry)
    if whole:
        g._bot_carry -= whole
        g.make_chip(whole)


def spend(g, buy, floor, dt, per_second=2000, purse="funds"):
    """Buy one at a time until the purse would fall through `floor`.

    The ceiling is a rate, not a number of purchases per call. A cap of "a
    hundred at a time" quietly means a thousand a second at dt=0.1 and a
    hundred at dt=1.0, which is exactly the kind of drift that makes the
    balance harness disagree with itself.
    """
    bought = 0
    cap = max(1, int(per_second * dt)) if per_second else None
    while getattr(g, purse, 0.0) > floor and (cap is None or bought < cap):
        if not buy(1):
            break
        bought += 1
    return bought


def _garrison(g, dt):
    """Stay ahead of the pressure, rather than reacting once behind.

    Integrity only recovers while your force exceeds theirs, so the bot aims
    for half again as much and buys the heaviest unit it can afford. The
    buying is paced, because spending a share of the purse is a decision and
    a decision happens at a rate, not once per tick."""
    target = g.war_pressure * 1.5
    if war.force(g) >= target or target <= 0:
        return
    if not paced(g, "garrison", dt, 2.0):
        return
    # Heaviest first for value, but fall through to what is affordable --
    # a cheap unit bought now beats a good one you cannot pay for.
    for unit in reversed(war.units_for(g.act)):
        purse = war.purse_of(g, unit)
        if purse <= 0:
            continue
        war.buy_unit(g, unit.key, float("inf"), budget=purse * 0.7)
        if war.force(g) >= target:
            return


def _research(g, dt):
    """Keep the benches busy, and the lab floor sized to what is on them.

    Research gates every capability and every act, so a bot that neglects
    it simply stops. Labs compound, so buying them without a target is how
    you spend an act funding a node you did not need yet. The target is the
    work in hand: whatever a bench is chewing on is exactly the thing more
    labs would finish sooner. Sizing against only the *next* node instead
    meant that once the one available tech was on a bench, there was
    nothing pending, and the bot quietly stopped buying labs for the rest
    of the run.
    """
    for tech in research.available(g):
        if len(research.active(g)) >= research.benches(g):
            break
        research.begin(g, tech.id)

    # What is left to pay for: whatever is on a bench, or the cheapest
    # thing that could go on one. Not the dearest node in sight -- sizing
    # against that buys a lab floor for work three decisions away and
    # starves the fab that has to pay for it.
    in_hand = [max(0.0, t.price(g) - research.progress(g, t))
               for t in research.active(g)]
    if in_hand:
        owed = max(in_hand)
    else:
        nxt = [t.price(g) for t in research.available(g)]
        if not nxt:
            return
        owed = min(nxt)
    horizon = 180.0 * research.LAB_OUTPUT * max(g.lab_perf, 1e-9)
    want = owed / horizon
    if g.labs >= want:
        return
    share = 0.5 if g.act == 1 else 0.25
    research.buy_labs(g, int(want - g.labs) + 1,
                      budget=research.lab_purse(g) * share)


#: How often the bot re-decides, in game seconds. The simulation is
#: accurate at any step size, but a bot that re-decides ten times a second
#: simply plays better than one that decides once -- so the cadence is
#: pinned here, or `--check` measures the step size instead of the balance.
DECISIONS_PER_SECOND = 4.0
SLICE = 1.0 / DECISIONS_PER_SECOND


def decide(g, dt):
    """One pass of the bot's judgement.

    Research goes first. Every capability and every act is behind the tree,
    so spending the last of your money on another stepper while the tree is
    stalled is simply the wrong move.
    """
    _research(g, dt)
    play = strategy_for(g.act)
    if play is not None:
        play(g, dt)
    _garrison(g, dt)
    _research(g, dt)
    _spend_bandwidth(g)
    _buy_projects(g)


def step(g, dt):
    """The bot's decisions for this slice of game time, then one tick."""
    for _ in range(paced(g, "decide", dt, DECISIONS_PER_SECOND)):
        decide(g, SLICE)
    g.tick(dt)


def simulate(seconds, dt=0.1, report_every=60.0, out=print):
    g = Game()
    acts_seen = {1: 0.0}
    next_report = 0.0
    steps = int(seconds / dt)
    for _ in range(steps):
        step(g, dt)
        if g.act not in acts_seen:
            acts_seen[g.act] = g.elapsed
            out(f"[{dur(g.elapsed)}] --- ACT {g.act} ---")
        if g.elapsed >= next_report:
            next_report += report_every
            label, value = content.headline(g)
            out(f"[{dur(g.elapsed)}] act {g.act}  {label} {value:>28}  "
                f"{big(g.made_rate, 1):>22}/s  bandwidth {g.bandwidth:>3}  "
                f"data {int(g.data):>7}/{g.buffer_bytes:<7} projects {len(g.completed)}")
        if g.finished:
            out(f"[{dur(g.elapsed)}] FINISHED: "
                f"{content.headline(g)[1]} {content.headline(g)[0]}")
            break
    label, value = content.headline(g)
    out(f"end: act {g.act}, {label} {value}, "
        f"projects {len(g.completed)}/{len(projects.ALL)}")
    return g
