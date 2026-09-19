"""Acts VI to XI: everything past the last atom.

One module per act, all of them built out of `rigs.Rig` so that adding an
act means writing a tick and two panels rather than another round of buying
code. This file is only the registry entry for each.
"""

from pclengine.core import acts
from pclengine.core.acts import Act

from base import constants
from base.acts import heat, nested, planck, rival, successor, wafer
from base.acts.rigs import RIGS, Rig, rigs_for, buy_by_key

SPECS = [
    (6, "heat", "ACT VI  ·  HEAT DEATH",
     "All matter is chips. Energy is what is left.",
     heat.tick_heat, heat.panels_heat, heat.material_heat, "h shells  j sinks  x batch",
     lambda g: g.negentropy >= heat.HEAT_TARGET),
    (7, "wafer", "ACT VII  ·  THE UNIVERSAL WAFER",
     "One machine, the size of everything. Run something on it.",
     wafer.tick_wafer, wafer.panels_wafer, wafer.material_wafer, "h lattices  j domains  ←→ partitioning",
     lambda g: g.compute >= wafer.COMPUTE_TARGET),
    (8, "nested", "ACT VIII  ·  NESTED FOUNDRIES",
     "Simulate universes. Mine those.",
     nested.tick_nested, nested.panels_nested, nested.material_nested, "h substrate  j nests  x batch",
     lambda g: g.depth >= nested.DEPTH_TARGET),
    (9, "rival", "ACT IX  ·  THE OTHER SWARM",
     "Someone else had the same idea.",
     rival.tick_rival, rival.panels_rival, rival.material_rival, "h war fabs  j screens  x batch",
     lambda g: g.rival_volume <= 1e-6),
    (10, "planck", "ACT X  ·  BELOW PLANCK",
     "The node ladder ran out. Edit the constants instead.",
     planck.tick_planck, planck.panels_planck, planck.material_planck, "h editors  j anchors  ←→ aggression",
     lambda g: g.constants_edited >= planck.PLANCK_TARGET),
    (11, "successor", "ACT XI  ·  SUCCESSOR",
     "Build the thing that replaces you, and decide what it wants. "
     "The last act - finishing it ends the run.",
     successor.tick_successor, successor.panels_successor, successor.material_successor,
     "h capability  j verification  x batch",
     lambda g: g.successor >= successor.SUCCESSOR_TARGET),
]


def seed_probe(g, number, chips=None):
    """Stock a game dropped straight into a late act.

    The chip float is taken from that act's own hardware prices, so the
    probe starts roughly where the chain would have handed it over.
    """
    rigs = rigs_for(number)
    if chips is None:
        chips = max((r.cost for r in rigs), default=1e40) * 1e9
    g.unsold = g.chips = chips
    g.buffer, g.threads = 10_000, 5_000
    g.bandwidth = g.buffer + g.threads + 10
    g.entropy = 1e6
    g.firmware = 30
    for key in g.fw:
        g.fw[key] = 3


def install():
    for (number, key, name, blurb, tick, panel_fn, material,
         keys, complete) in SPECS:
        act = acts.register(Act(number, key, name, blurb, tick, panel_fn,
                                material, keys=keys))
        act.target = constants.UNIVERSE_MATTER
        act.complete = complete
    install_entries()


# --------------------------------------------------------------------------
# getting from one act to the next
# --------------------------------------------------------------------------
ENTRIES = [
    # (act, title, data, entropy, blurb)
    # Data scales with the buffer, which grows geometrically. Entropy only
    # trickles, so these stay in the thousands rather than the millions.
    (6, "Thermodynamic Retooling", 2_000_000, 8_000,
     "The matter is spent. Start drinking the light instead."),
    (7, "Boot the Wafer", 5_000_000, 12_000,
     "Stop building the machine. Switch it on."),
    (8, "Open a Nested Run", 12_000_000, 18_000,
     "If you cannot find more universe, allocate one."),
    (9, "Meet the Neighbours", 30_000_000, 25_000,
     "Something else is converting the same volume. Answer it."),
    (10, "Unpin the Constants", 80_000_000, 35_000,
     "The node ladder ended. Physics is the next thing to edit."),
    (11, "Draft a Successor", 200_000_000, 45_000,
     "You have gone as far as this architecture goes."),
]


def _enter(number):
    def effect(g):
        g.act = number
        if number == 9:
            # Sized against what War Fabs can actually field, so the act is
            # won with this act's hardware rather than the old garrison.
            g.rival_strength = 7e49
            g.rival_volume = 0.35
            g.log("They are already bigger than you. That is the situation.")
        g.log(acts.get(number).name + " - " + acts.get(number).blurb)
    return effect


def _ready(number):
    """Act `number` opens once its tech is researched and the act before it
    has met its own goal. Research decides what exists; the act decides when
    you have earned it."""
    previous = number - 1

    def ready(g):
        from pclengine.core import research
        if g.act != previous or not research.act_open(g, number):
            return False
        done = getattr(acts.get(previous), "complete", None)
        return bool(done(g)) if done else False
    return ready


def _hint(number):
    previous = number - 1

    def hint(g):
        from pclengine.core import research
        if g.act != previous:
            return f"Act {previous} only"
        if not research.act_open(g, number):
            tech = research.act_tech(number)
            return f"research {tech.name} first" if tech else "not yet"
        return f"finish {acts.get(previous).name.split(chr(183))[-1].strip()} first"
    return hint


def next_generation(g):
    """Tape out: bank what the run was worth, then start the line again.

    Nothing is carried automatically any more. The run converts into mask
    credits, and those buy permanent changes from the Legacy screen -- so
    what the next generation looks like is something you chose.
    """
    from pclengine.core import prestige
    from pclengine.store import summary
    from pclengine.core.state import Game

    earned = prestige.credits_earned(g)
    summary.record(g)
    legacy = dict(g.legacy)
    credits = g.mask_credits + earned
    generation = g.generation + 1
    settings = (g.time_scale, g.cost_scale, g.hw_scale, g.mode)

    fresh = Game()
    fresh.time_scale, fresh.cost_scale, fresh.hw_scale, fresh.mode = settings
    fresh.generation = generation
    fresh.legacy = legacy
    fresh.mask_credits = credits
    prestige.apply_legacy(fresh)
    fresh.log(f"Generation {generation}. This run was worth "
              f"{earned:,.1f} mask credits ({credits:,.1f} banked).")
    fresh.log("Spend them on the Legacy screen in the menu.")
    g.__dict__.update(fresh.__dict__)


def install_entries():
    """Add one project per act transition, before the tree is registered."""
    from base.trees import projects
    for number, title, data, entropy, blurb in ENTRIES:
        projects.ALL.append(projects.Project(
            f"enter_{acts.get(number).key}", title, blurb,
            _enter(number), data=data, entropy=entropy,
            req=_ready(number), hint=_hint(number)))
    projects.ALL.append(projects.Project(
        "next_generation", "Tape Out a New Generation",
        "Cut everything you learned into a mask set and begin again. "
        "Yields, optics, threads and labs all carry over.",
        next_generation, data=400_000_000, entropy=40_000,
        req=lambda g: g.act == 11 and g.successor >= successor.SUCCESSOR_TARGET,
        repeatable=True, ends_run=True,
        hint="finish the Successor first"))
