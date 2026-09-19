"""What taping out buys you: the things a run leaves behind for the next."""

from pclengine.core import projects
from pclengine.core.prestige import Upgrade


def _hot_start(g):
    """Begin the run already through the Act II gate."""
    project = projects.BY_ID.get("vertical_integration")
    if project is not None:
        g.completed.add(project.id)
        project.effect(g)
        g.unsold = max(g.unsold, 5e6)


def _published(g, count):
    """Begin with the easy end of the cipher ladder already broken.

    The rewards apply as though you had broken them, because you did --
    in an earlier run, and the notes came with you.
    """
    from base import crypt
    for cipher in crypt.CIPHERS[int(g.cracked):int(g.cracked) + count]:
        g.cracked += 1
        g.entropy += cipher.entropy
        if cipher.reward is not None:
            cipher.reward(g)


UPGRADES = [
    Upgrade("grant", "Standing Research Grant",
            "Begin each run with research already banked.", 30,
            lambda g, n: setattr(g, "research", g.research + 140.0 * n),
            repeatable=True, cap=6),
    Upgrade("tenure", "Tenure",
            "Every lab is worth half again as much, permanently.", 80,
            lambda g, n: setattr(g, "lab_perf", g.lab_perf * (1.5 ** n)),
            repeatable=True, cap=4),
    Upgrade("seed_capital", "Seed Capital",
            "Begin with funds and a few steppers already running.", 25,
            lambda g, n: (setattr(g, "funds", g.funds + 2000.0 * n),
                          setattr(g, "steppers", g.steppers + 5 * n)),
            repeatable=True, cap=5),
    Upgrade("retained_yield", "Retained Process Knowledge",
            "Start at a higher dies-per-wafer.", 40,
            lambda g, n: setattr(g, "die_yield", g.die_yield * (1.4 ** n)),
            repeatable=True, cap=8),
    Upgrade("standing_army", "Standing Contracts",
            "Begin each run with a garrison already paid for.", 45,
            lambda g, n: g.forces.update({"guards": 40 * n}),
            repeatable=True, cap=4),
    Upgrade("wide_bus", "Wide Bus",
            "+6 bandwidth and a bigger buffer from the start.", 60,
            lambda g, n: (setattr(g, "bandwidth", g.bandwidth + 6 * n),
                          setattr(g, "buffer", g.buffer + 4 * n)),
            repeatable=True, cap=5),
    Upgrade("hot_start", "Hot Start",
            "Skip Act I: begin already integrated, with the planet waiting.",
            150, lambda g, n: _hot_start(g)),
    Upgrade("overclocked", "Overclocked Line",
            "Every thread is worth half again as much, permanently.", 120,
            lambda g, n: setattr(g, "thread_perf", g.thread_perf * 1.5)),
    Upgrade("reputation", "Reputation Precedes You",
            "Begin each run with a name already worth something: customers, "
            "research and cheaper defenders from the first second.", 55,
            lambda g, n: setattr(g, "brand", g.brand + 0.3 * n),
            repeatable=True, cap=5),
    Upgrade("rig_contract", "Standing Rig Contract",
            "Begin with mining rigs already racked and hashing.", 50,
            lambda g, n: setattr(g, "rigs", g.rigs + 30 * n),
            repeatable=True, cap=5),
    Upgrade("published", "Published Results",
            "Begin with the first cipher on the ladder already broken, and "
            "everything breaking it was worth.", 90,
            lambda g, n: _published(g, n), repeatable=True, cap=3),
    Upgrade("second_source", "Second Sourcing",
            "Forks no longer shut each other out - you may take both sides.",
            200, lambda g, n: setattr(g, "forks_open", True)),
]
