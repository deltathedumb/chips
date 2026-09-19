"""A mod shipped as a .mpkg, to show the package form.

Build with:  python foundry.py --build-mod mod_src/deep_geology
"""

NAME = "Deep Geology"
DESCRIPTION = "A richer Earth, plus a mantle-tapping project."

from . import rules


def register(api):
    api.constant("EARTH_MATTER", rules.EARTH_MATTER)

    api.add_project(
        "mantle_tap", "Mantle Tap",
        "1,000x crust miner performance. The crust was the easy part.",
        api.mult("miner_perf", 1000.0),
        after="deep_crust_boring",
        data=36_000,
        req=api.requires("deep_crust_boring"),
        hint="needs Deep Crust Boring",
    )

    @api.on_new_game
    def announce(game):
        game.log(rules.GREETING)
