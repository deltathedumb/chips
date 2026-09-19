"""Adding to the research tree.

Research is the spine: a capability you have not researched cannot be
bought, and an act you have not researched cannot be entered. A mod can hang
new nodes off the existing ones, and gate its own content behind them.
"""

NAME = "Applied Optics"
DESCRIPTION = "A research node that makes the lithography line cheaper."


def register(api):
    api.add_tech(api.Tech(
        "applied_optics", "Applied Optics",
        "Lenses you designed rather than bought. Halves the optics line.",
        cost=180, requires=("photonics",), unlocks=("cheap_optics",)))

    api.add_project(
        "in_house_lenses", "In-House Lens Grinding",
        "Double stepper throughput, once you know how the light behaves.",
        api.mult("stepper_perf", 2.0),
        after="euv_scanners", data=9_000,
        req=lambda g: g.can("cheap_optics"),
        hint="research Applied Optics first")
