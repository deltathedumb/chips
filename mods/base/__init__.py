"""FOUNDRY: the base game, shipped as a mod.

Everything that makes pclengine a game about silicon is in this package, and
all of it arrives through the same `register(api)` a third-party mod uses.
Nothing here is privileged. Switch it off and you get the bare engine; write
your own package in its shape and you get a different game on the same
machinery.

    constants   the numbers the subject matter is measured in
    currencies  what projects are priced in: data, entropy, chips
    game/       what a game is: its fields, its verbs, its keys
    acts/       the eleven acts, and the dials the late ones ask you to set
    trees/      research and projects, the two things you spend on
    bench       the benchmark circuit: ops, placements, Brand Recognition
    crypt       the cipher lab: rigs, algorithms and things to break
    market      what those rigs mine, and the market to sell it into
    help        what `?` says about all of it
    warfare     who attacks you, and what you build to stop them
    upgrades    what taping out carries into the next run
    strategy    how the balance bot plays, act by act
    devtools    developer actions only this game understands
"""

from pclengine.fmt import big

#: Act -> (fastest, slowest) acceptable minutes, for `--balance`.
PACING = {
    1: (18, 35), 2: (8, 16), 3: (8, 16), 4: (8, 16), 5: (8, 16),
    6: (6, 14), 7: (6, 14), 8: (6, 14), 9: (6, 14), 10: (6, 14),
    11: (5, 12),
}

NAME = "FOUNDRY"
DESCRIPTION = "The base game: silicon, the lithosphere and the light cone."

from base import (bench, constants, crypt, currencies, devtools, help,
                  hud, market, saveedit, strategy, upgrades, warfare)
from base.acts import dials
from base.acts import early as acts_early
from base.acts import final as acts_final
from base.acts import late as acts_late
from base.game import fields, keys, mechanics
from base.trees import projects, techs


def register(api):
    # Order matters exactly once: fields and methods have to exist before
    # anything that reads them is built.
    currencies.install(api)
    fields.install(api)
    mechanics.install(api)
    for key, label, colour, term in techs.CATEGORIES:
        api.tech_category(key, label, colour, term)
    for tech in techs.TREE:
        api.add_tech(tech)
    acts_early.install(api)
    acts_late.install()
    acts_final.install()
    projects.install(api)
    for unit in warfare.UNITS:
        api.add_unit(unit)
    for threat in warfare.THREATS:
        api.add_threat(threat)
    warfare.install(api)
    for dial in dials.DIALS:
        api.add_dial(dial)
    for upgrade in upgrades.UPGRADES:
        api.add_upgrade(upgrade)
    bench.install(api)
    crypt.install(api)
    market.install(api)
    help.install(api)
    hud.install(api)
    saveedit.install(api)
    keys.install(api)
    strategy.install(api)
    devtools.install(api)
    # How long each of these ought to take. Act I carries the tutorial.
    for number, (low, high) in PACING.items():
        api.pacing(number, low, high)
    api.probe_seed(acts_final.seed_probe)
    api.headline(lambda g: ("chips", big(g.chips, 3)))
    api.era(lambda g: f"{g.node:g}nm node")
    api.end_check(_everything_is_spent)


def _everything_is_spent(g):
    """The run ends when every gram has been taken *and* run through.

    Not at a chip count: a die weighs well under a gram, so the two converge
    separately and the last act is not over until both have.
    """
    residue = g.matter + g.wafers * constants.GRAMS_PER_WAFER
    ceiling = g.act_target
    return (g.acquired >= ceiling * 0.99999 and residue <= ceiling * 1e-9)
