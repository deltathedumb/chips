"""The balance harness.

Plays the whole game headlessly and reports how long each act took, so pacing
can be tuned against numbers instead of guesses.

    python foundry.py --balance
    python foundry.py --balance --dt 1.0 --budget 40000

`dt` is the simulation step. Bigger is faster but less exact, so `--check`
runs a slice at two step sizes and reports how far they diverge.
"""

import time

from pclengine import content
from pclengine.core import acts
from pclengine.dev import autoplay
from pclengine.modding import loader
from pclengine.fmt import big, dur
from pclengine.core.state import Game

# How long each act ought to take, in game-minutes. Content sets this with
# `api.pacing`, because how long an act should take is a claim about that
# act -- an engine that does not know what Act I is cannot know it carries
# the tutorial. Anything unclaimed falls back to DEFAULT_TARGET.
TARGETS = {}
DEFAULT_TARGET = (5, 15)


def set_pacing(number, low, high):
    TARGETS[number] = (low, high)


def reset_pacing():
    TARGETS.clear()
STALL_AFTER = 3600.0        # game-seconds in one act before we call it stuck


def run(dt=1.0, budget=60000.0, stall_after=STALL_AFTER, quiet=True,
        seed=None):
    """Play to the end (or until stuck). Returns (game, [(act, seconds)])."""
    g = Game(seed=seed)
    timeline = []
    act, entered, last_change = g.act, 0.0, 0.0
    steps = int(budget / dt)
    for _ in range(steps):
        autoplay.step(g, dt)
        if g.act != act:
            timeline.append((act, g.elapsed - entered))
            if g.act < act:            # tape-out restarted the run
                break
            act, entered, last_change = g.act, g.elapsed, g.elapsed
        if g.finished:
            timeline.append((act, g.elapsed - entered))
            break
        if g.elapsed - last_change > stall_after:
            timeline.append((act, -(g.elapsed - entered)))   # negative = stuck
            break
    else:
        timeline.append((act, -(g.elapsed - entered)))
    return g, timeline


def report(g, timeline, out=print):
    out(f"{'act':>4}  {'name':<26}{'took':>10}  {'target':>11}  verdict")
    total = 0.0
    for number, seconds in timeline:
        stuck = seconds < 0
        seconds = abs(seconds)
        total += seconds
        low, high = TARGETS.get(number, DEFAULT_TARGET)
        minutes = seconds / 60.0
        if stuck:
            verdict = "STUCK"
        elif minutes < low:
            verdict = f"too fast (x{low / max(minutes, 0.01):.1f})"
        elif minutes > high:
            verdict = f"too slow (x{minutes / high:.1f})"
        else:
            verdict = "ok"
        name = acts.name_of(number).split("·")[-1].strip()
        out(f"{number:>4}  {name:<26}{dur(seconds):>10}  "
            f"{str(low) + '-' + str(high) + 'm':>11}  {verdict}")
    out(f"{'':>4}  {'TOTAL':<26}{dur(total):>10}")
    label, value = content.headline(g)
    out(f"      {label} {value}   projects {len(g.completed)}   "
        f"finished {g.finished}")
    return total


def check_step_sizes(budget=30000.0, coarse=1.0, fine=0.25, seed=20240101,
                     out=print):
    """Does the shortcut change the answer? Play it twice and compare.

    Not on chips: a run crossing a 500x threshold a few seconds earlier ends
    up orders of magnitude ahead, so raw totals always look alarming and
    never mean anything. What the harness claims is how long each act takes,
    so that is what gets compared -- both runs on one seed, so the only
    difference left is the step size.
    """
    runs = {}
    for dt in (fine, coarse):
        _game, timeline = run(dt=dt, budget=budget, seed=seed)
        runs[dt] = dict(timeline)
    shared = sorted(set(runs[fine]) & set(runs[coarse]))
    out(f"act timings at dt={fine} against dt={coarse}:")
    if not shared:
        out("  neither run cleared an act -- nothing to compare")
        return 1.0
    drifts = {n: abs(runs[fine][n] - runs[coarse][n])
              / max(runs[fine][n], runs[coarse][n], 1.0) for n in shared}
    loudest = max(drifts, key=drifts.get)
    for number in shared:
        out(f"  act {number:>2}  {dur(runs[fine][number]):>8} / "
            f"{dur(runs[coarse][number]):>8}   {drifts[number] * 100:5.1f}%"
            + ("   <-- worst" if number == loudest else ""))
    out(f"  acts finished: {len(runs[fine])} / {len(runs[coarse])}, "
        f"deepest act {max(runs[fine], default=0)} / "
        f"{max(runs[coarse], default=0)}")
    worst = drifts[loudest]
    verdict = ("the shortcut holds" if worst <= 0.25
               else "step too coarse - act timings move")
    out(f"  worst is act {loudest} at {worst * 100:.1f}%: {verdict}")
    return 0.0 if worst <= 0.25 else 1.0


def main(dt=1.0, budget=60000.0, do_check=False, with_mods=True):
    """Time the game as it is actually configured.

    With the mods on, not just the base content: a mod that adds acts or
    moves a constant changes the pacing, and a harness that quietly tested
    something else would report that everything was fine.
    """
    if with_mods:
        loader.load()
    else:
        loader.reset()
    if do_check:
        check_step_sizes()
        print()
    started = time.perf_counter()
    g, timeline = run(dt=dt, budget=budget)
    wall = time.perf_counter() - started
    total = report(g, timeline)
    print(f"      simulated {dur(total)} of game in {wall:.1f}s wall "
          f"({total / max(wall, 1e-9):,.0f}x real time)")
    return g, timeline


#: How content wants a game set up when an act is probed on its own.
PROBE_SEEDS = []


def seed_probe(fn):
    PROBE_SEEDS.append(fn)
    return fn


def probe(number, seconds=1200.0, dt=1.0, chips=None, out=print):
    """Drop the bot straight into one act and see if its goal is reachable.

    The engine knows how to run an act in isolation but not what a game
    needs in its pockets to start there, so content seeds it.
    """
    g = Game()
    g.act = number
    for seed in PROBE_SEEDS:
        seed(g, number, chips)
    done = getattr(acts.get(number), "complete", None)
    reached = None
    for step_i in range(int(seconds / dt)):
        autoplay.step(g, dt)
        if done and done(g):
            reached = g.elapsed
            break
    name = acts.name_of(number).split("·")[-1].strip()
    if reached:
        out(f"{number:>4}  {name:<26}goal in {dur(reached):>8}")
    else:
        out(f"{number:>4}  {name:<26}NOT REACHED in {dur(seconds)}")
    return reached, g


def probe_all(first=6, last=14, seconds=1500.0, out=print):
    out(f"{'act':>4}  {'name':<26}result")
    results = {}
    for number in range(first, last + 1):
        results[number] = probe(number, seconds=seconds, out=out)[0]
    return results
