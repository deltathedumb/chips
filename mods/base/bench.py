"""The benchmark circuit: ops, open problems, and Brand Recognition.

The other branch of computing. Where the data buffer buys projects, **ops**
buy a reputation, and a reputation is worth customers.

You split your compute between the two with `ops_share`, bank ops against an
open problem, and submit when you think you have done enough. What you
actually get is a **placement** against everybody else working on it, and
the placement is decided by how far past par you went:

    committed / par     placement        what it does to the book
    -------------------------------------------------------------
    >= 2.5x             first            you take your rivals' customers
    >= 1.5x             second           customers come to you
    >= 1.0x             third            a modest gain
    >= 0.6x             mid-field        you hold what you have
    below               also-ran         customers leave

That number is **Brand Recognition**, and it does three things, all of them
for the rest of the run rather than only while there is an order book:

    order flow      x brand           customers, in Act I
    research        x brand ** 0.4    a name attracts people worth hiring
    defender cost   x brand ** -0.3   contractors want to be seen with you

The two exponents are there because brand compounds -- six firsts in a row
is a brand of fifteen -- and fifteen times the research would simply end the
game. Damped, it is worth roughly three times, which is a lot without being
the only thing that matters. It cuts both ways: a brand of 0.15 is research
at less than half speed and defenders half again as dear.

The decision is when to submit: hold out for first and you are spending
compute your project tree is not getting, submit early and you may hand the
win -- and your customers -- to somebody else.
"""

from pclengine.core import research
from pclengine.core.acts import panel, row
from pclengine.fmt import big, small

SHARE_STEP = 0.05       # how far one keypress moves the split
SHARE_MAX = 0.90        # you can never starve the buffer completely
BRAND_FLOOR = 0.15      # however badly it goes, somebody still buys
#: Brand compounds, so its knock-on effects are damped. See the module note.
RESEARCH_POWER = 0.4
UNIT_COST_POWER = -0.3


class Placement:
    """One rung of the result table, and what it does to your name."""

    __slots__ = ("name", "ratio", "brand", "note")

    def __init__(self, name, ratio, brand, note):
        self.name = name
        self.ratio = ratio        # committed/par needed to place here
        self.brand = brand        # what it multiplies Brand Recognition by
        self.note = note


PLACEMENTS = [
    Placement("FIRST", 2.5, 1.55,
              "the field's customers come to you"),
    Placement("SECOND", 1.5, 1.28, "customers come to you"),
    Placement("THIRD", 1.0, 1.12, "a modest gain"),
    Placement("MID-FIELD", 0.6, 1.0, "you hold what you have"),
    Placement("ALSO-RAN", 0.0, 0.72, "customers leave"),
]


def placement_for(ratio):
    for place in PLACEMENTS:
        if ratio >= place.ratio:
            return place
    return PLACEMENTS[-1]


class Problem:
    """Something hard enough that solving it is news."""

    __slots__ = ("key", "name", "par", "blurb", "weight")

    def __init__(self, key, name, par, blurb, weight=1.0):
        self.key = key
        self.name = name
        self.par = par            # ops the rest of the field will commit
        self.blurb = blurb
        #: How much the result moves your name, relative to a normal result.
        self.weight = weight


PROBLEMS = [
    Problem("folding", "The Protein Folding Set", 4.0e4,
            "Ten thousand structures nobody has resolved.", 0.8),
    Problem("climate", "A Global Climate Ensemble", 3.0e5,
            "Every initial condition anybody has ever argued about."),
    Problem("nbody", "N-Body: The Local Cluster", 2.2e6,
            "Two hundred billion stars, integrated honestly."),
    Problem("turbulence", "Turbulent Flow at Scale", 1.6e7,
            "The last unsolved problem in classical physics."),
    Problem("qcd", "Lattice QCD to Four Loops", 1.1e8,
            "The strong force, to a decimal place nobody has reached.", 1.2),
    Problem("connectome", "A Whole-Brain Emulation Pass", 9.0e8,
            "One cubic centimetre, every synapse, one second of it.", 1.2),
    Problem("riemann", "The Riemann Zeros", 7.0e9,
            "Ten trillion of them, all on the line so far.", 1.4),
    Problem("navier", "Navier-Stokes Existence", 6.0e10,
            "Not a simulation. A proof.", 1.6),
    Problem("rerun", "A Full Universe Rerun", 5.0e11,
            "From the first microsecond, at the resolution it happened.", 2.0),
]
BY_KEY = {p.key: p for p in PROBLEMS}


# --------------------------------------------------------------------------
# state
# --------------------------------------------------------------------------
def open_for_business(g):
    """The circuit appears once you have researched Numerical Analysis."""
    return research.has(g, "ops")


def problem_of(g):
    if g.solved >= len(PROBLEMS):
        return None
    return PROBLEMS[int(g.solved)]


def ratio(g):
    problem = problem_of(g)
    if problem is None or problem.par <= 0:
        return 0.0
    return g.ops / problem.par


def projected(g):
    """Where you would place if you submitted right now."""
    return placement_for(ratio(g))


def adjust_share(g, direction):
    g.ops_share = max(0.0, min(SHARE_MAX, round(
        g.ops_share + direction * SHARE_STEP, 4)))
    return True


def submit(g):
    """Commit everything banked and take the result."""
    problem = problem_of(g)
    if problem is None:
        return False
    if g.ops <= 0:
        g.log("Nothing to submit. Put some compute into ops first.")
        return False
    place = placement_for(ratio(g))
    _apply(g, problem, place)
    return True


def _apply(g, problem, place):
    # A problem that matters moves your name further, in either direction.
    move = 1.0 + (place.brand - 1.0) * problem.weight
    before = g.brand
    g.brand = max(BRAND_FLOOR, g.brand * move)
    g.ops = 0.0
    g.solved += 1
    g.placements.append(place.name)
    del g.placements[:-12]
    if place.brand > 1.0:
        # Placing well takes share off the field, not just goodwill.
        g.order_mult *= 1.0 + 0.05 * problem.weight
    g.log(f"{problem.name}: {place.name} - {place.note}.")
    g.log(f"Brand Recognition {before:.2f} -> {g.brand:.2f}.")
    nxt = problem_of(g)
    if nxt is None:
        g.log("There is nothing left on the circuit worth entering.")
    else:
        g.log(f"Next on the circuit: {nxt.name}.")


def research_bonus(g):
    """What your name is worth to the research line."""
    return max(BRAND_FLOOR, g.brand) ** RESEARCH_POWER


def unit_discount(g):
    """What your name is worth when you are hiring people to defend you."""
    return max(BRAND_FLOOR, g.brand) ** UNIT_COST_POWER


def tick(g, dt):
    if not open_for_business(g):
        g.ops_share = 0.0
        return
    if problem_of(g) is None:
        # Nothing left to enter. Hand the compute back rather than quietly
        # spending it on a circuit that is over.
        if g.ops_share > 0.0:
            g.ops_share = 0.0
            g.log("The circuit is finished. Compute returns to the buffer.")
        return
    g.ops += g.ops_rate * dt


# --------------------------------------------------------------------------
# the panel
# --------------------------------------------------------------------------
def _problem_panel(g):
    problem = problem_of(g)
    if problem is None:
        return panel("THE CIRCUIT", [
            row("the circuit is finished", "-"),
            row("problems solved", str(int(g.solved))),
            row("Brand Recognition", f"{g.brand:.2f}x")])
    place = projected(g)
    fraction = min(1.0, ratio(g) / PLACEMENTS[0].ratio)
    return panel("OPEN PROBLEM", [
        row(problem.name, f"par {small(problem.par)} ops",
            hint=problem.blurb),
        row("committed", f"{small(g.ops)}   ({ratio(g):.2f}x par)",
            bar=fraction),
        row("would place", place.name, warn=place.brand < 1.0,
            hint=place.note + ".  " + _eta(g, problem)),
        row("submit now", "e", key="e",
            hint="takes the result you see, and puts up the next problem"),
    ])


def _eta(g, problem):
    if g.ops_rate <= 0:
        return "no compute is going into ops"
    for place in PLACEMENTS[:-1]:
        need = problem.par * place.ratio - g.ops
        if need > 0:
            return f"{place.name} in {need / g.ops_rate:,.0f}s at this split"
    return "first place is already yours"


def _split_panel(g):
    share = g.ops_share
    return panel("COMPUTE", [
        row("ops share", f"{share * 100:.0f}%", bar=share / SHARE_MAX,
            hint=", and . move the split; the rest goes to the buffer"),
        row("into ops", f"{small(g.ops_rate)}/s"),
        row("into data", f"{small(g.data_rate)}/s",
            warn=share >= SHARE_MAX - 1e-9),
    ])


def _brand_panel(g):
    rows = [row("Brand Recognition", f"{g.brand:.2f}x",
                warn=g.brand < 1.0,
                hint="worth customers, research and cheaper defenders, for "
                     "the rest of the run"),
            row("order flow", f"{big(g.order_flow(), 1)}/sec"),
            row("research", f"x{research_bonus(g):.2f}"),
            row("defender cost", f"x{unit_discount(g):.2f}",
                warn=unit_discount(g) > 1.0)]
    if g.placements:
        rows.append(row("recent results", ", ".join(g.placements[-4:])))
    return panel("BRAND", rows)


def panels(g):
    return [_problem_panel(g), _split_panel(g), _brand_panel(g)]


def on_key(g, key):
    if key == "e":
        submit(g)
        return True
    if key in (",", "<"):
        adjust_share(g, -1)
        return True
    if key in (".", ">"):
        adjust_share(g, 1)
        return True
    return False


# --------------------------------------------------------------------------
def install(api):
    api.field("ops", 0.0)
    api.field("ops_share", 0.0)
    api.field("solved", 0)
    api.field("brand", 1.0)
    api.field("placements", lambda: [])
    api.system_tick(tick)
    # A name is worth something long after the order book stops mattering.
    api.modifier("research_output", research_bonus)
    api.modifier("unit_cost", unit_discount)
    api.credit_bonus(lambda g: min(12.0, g.solved * 1.5))
    api.panel_view("bench", "BENCH", panels, on_key=on_key,
                   shown=open_for_business,
                   keys=", . ops split  e submit")
    api.editor_group("THE BENCHMARK CIRCUIT",
                     ["ops", "ops_share", "solved", "brand"])
