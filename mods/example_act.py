"""Adding an act.

An act is a number, a tick and two panel builders that return plain data --
the terminal and the browser both render whatever comes back, so an act
never means writing layout twice. Gate it behind a tech and give the balance
bot a strategy, and `--balance` can time it like any other.
"""

NAME = "The Long Tail"
DESCRIPTION = "An extra act after the Successor: keep the lights on."

TARGET = 1e6


def register(api):
    api.field("upkeep_done", 0.0)
    api.add_tech(api.Tech(
        "stewardship", "Stewardship",
        "Someone has to stay behind. Opens THE LONG TAIL.",
        cost=760_000, requires=("alignment_theory",), act=12))

    def tick(g, dt):
        g.upkeep_done = min(TARGET, g.upkeep_done + g.seed_fabs * 1e-30 * dt)

    def panels(g):
        return [api.panel("UPKEEP", [
            api.row("maintained", f"{g.upkeep_done:,.0f} of {TARGET:,.0f}",
                    bar=g.upkeep_done / TARGET),
            api.row("seed fabs still running", f"{g.seed_fabs:.3e}")])]

    def material(g):
        return api.panel("THE TAIL", [
            api.row("progress", f"{g.upkeep_done / TARGET * 100:.2f}%",
                    bar=g.upkeep_done / TARGET)])

    act = api.add_act(api.Act(
        12, "long_tail", "ACT XII  ·  THE LONG TAIL",
        "Nothing left to build. Keep what you built running.",
        tick, panels, material, keys="x batch"))
    act.complete = lambda g: g.upkeep_done >= TARGET
    api.strategy(12, lambda g, dt: None)
