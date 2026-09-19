"""The tech tree: what exists at all, and which act it opens.

Research is the spine. A capability you have not researched cannot be bought
and an act you have not researched cannot be entered, so the order you take
this tree in is the shape of your run.


Every node carries a category and an icon. They change nothing about what
the node does -- they are there so that fifty of these can be looked at as
a picture instead of read as a list.
"""

from pclengine.core.research import Tech


def _mult(attr, factor):
    def apply(g):
        setattr(g, attr, getattr(g, attr) * factor)
    return apply


def _add(attr, amount):
    def apply(g):
        setattr(g, attr, getattr(g, attr) + amount)
    return apply

#: The branches, and what colour each is drawn in. Nothing depends on a
#: node's branch -- it is there so the tree can be read at a glance rather
#: than spelt out a node at a time.
CATEGORIES = [
    ("fab", "The Fab Floor", "#e2a03f", "yellow"),
    ("compute", "Computing", "#4fb3d9", "cyan"),
    ("market", "The Market", "#b07fd0", "white"),
    ("cipher", "Cryptanalysis", "#6fcf6f", "green"),
    ("industry", "Heavy Industry", "#d9744f", "red"),
    ("expansion", "Expansion", "#e0d267", "yellow"),
    ("conflict", "Conflict", "#e06f6f", "red"),
    ("cosmic", "Cosmology", "#8f9de8", "cyan"),
]

TREE = [
    # -- the fab floor ---------------------------------------------------
    Tech("metrology", "Metrology",
         "Measure what you are making. Opens the yield projects.", 12,
         unlocks=("yield",),
         category="fab", icon="lens"),
    Tech("market_analysis", "Market Analysis",
         "Learn who buys chips, and how many. Opens Design Wins.", 20,
         unlocks=("design_wins",),
         category="market", icon="scales"),
    Tech("computing", "Computing",
         "Run something other than the fab. Opens threads, buffer and data.",
         35, requires=("metrology",), unlocks=("computing",),
         category="compute", icon="chip"),
    Tech("information_theory", "Information Theory",
         "A saturated buffer has something to say. Opens entropy.", 70,
         requires=("computing",), unlocks=("entropy",),
         category="compute", icon="wave"),
    Tech("parallelism", "Parallelism",
         "Spend a slab of compute at once. Opens the manual burst.", 90,
         requires=("computing",), unlocks=("burst",),
         category="compute", icon="network"),
    Tech("photonics", "Photonics",
         "Shorter wavelengths. Opens EUV scanners.", 140,
         requires=("metrology", "computing"), unlocks=("scanners",),
         category="fab", icon="lens"),
    Tech("security_doctrine", "Security Doctrine",
         "Someone will want this. Opens everything you build to defend it.",
         55, requires=("market_analysis",), unlocks=("war",),
         category="conflict", icon="shield"),

    # -- the planet ------------------------------------------------------
    Tech("numerical_analysis", "Numerical Analysis",
         "Point the compute at somebody else's hard problem. Opens the "
         "benchmark circuit, and with it Brand Recognition.", 110,
         requires=("computing", "market_analysis"), unlocks=("ops",),
         category="market", icon="flask"),
    Tech("number_theory", "Number Theory",
         "Primes stop being trivia. Opens the sieve and index calculus.",
         210, requires=("information_theory",),
         unlocks=("number_theory",),
         category="cipher", icon="key"),
    Tech("lattice_theory", "Lattice Theory",
         "Short vectors in awkward bases. Opens lattice reduction.", 2_100,
         requires=("number_theory", "photonics"), unlocks=("lattice_theory",),
         category="cipher", icon="crystal"),
    Tech("quantum_algorithms", "Quantum Algorithms",
         "Period finding, and what falls out of it. Opens Shor's.", 9_000,
         requires=("lattice_theory",), unlocks=("quantum_algorithms",),
         category="cipher", icon="atom"),
    Tech("side_channels", "Side-Channel Analysis",
         "Stop attacking the cipher and attack the machine.", 45_000,
         requires=("quantum_algorithms", "security_doctrine"),
         unlocks=("side_channels",),
         category="cipher", icon="eye"),

    # -- forks. Each pair is one decision you do not get to revisit, which
    # is what stops the tree being a list you read top to bottom.
    Tech("deep_pipelining", "Deep Pipelining",
         "More stages, more in flight. Each thread does more work.", 150,
         requires=("computing",), excludes=("wide_issue",),
         effect=_mult("thread_perf", 1.6), note="+60% thread output",
         category="compute", icon="wave"),
    Tech("wide_issue", "Wide Issue",
         "Fewer stages, more of them. Your labs get the benefit.", 150,
         requires=("computing",), excludes=("deep_pipelining",),
         effect=_mult("lab_perf", 1.6), note="+60% research output",
         category="compute", icon="network"),

    Tech("speculation", "Speculative Execution",
         "Guess, and be right often enough. Bursts hit far harder.", 480,
         requires=("parallelism",), excludes=("in_order",),
         effect=_mult("entropy_mult", 1.8), note="+80% entropy extraction",
         category="compute", icon="bolt"),
    Tech("in_order", "In-Order Discipline",
         "Never guess. Nothing is ever thrown away and re-done.", 480,
         requires=("parallelism",), excludes=("speculation",),
         effect=_add("benches", 1), note="+1 research bench",
         category="compute", icon="gear"),

    # Both sides of this one are about holding ground, so taking either
    # changes how the fighting goes rather than how long an act takes.
    # A fork that speeds up the binding stage of an act is not a choice,
    # it is a shorter act.
    Tech("redundancy", "Redundant Fabs",
         "Two of everything. Dearer to field, far harder to stop.", 2_600,
         requires=("security_doctrine", "materials_science"),
         excludes=("lean_fabs",),
         effect=_mult("force_mult", 2.2),
         note="everything you field counts for twice as much",
         category="conflict", icon="shield"),
    Tech("lean_fabs", "Lean Fabs",
         "One of everything and nothing spare. Cheap, quick, brittle.",
         2_600, requires=("security_doctrine", "materials_science"),
         excludes=("redundancy",),
         effect=_mult("defence_discount", 0.35),
         note="defenders cost a third of what they did",
         category="industry", icon="anvil"),

    Tech("autonomy", "Autonomy",
         "Machines that work without being told. Opens drones.", 260,
         requires=("computing",), unlocks=("drones",),
         category="industry", icon="gear"),
    Tech("power_engineering", "Power Engineering",
         "Everything after this needs a grid. Opens arrays and storage.", 320,
         requires=("autonomy",), unlocks=("power",),
         category="industry", icon="bolt"),
    Tech("materials_science", "Materials Science",
         "Rock into ingots into wafers. Opens pullers and foundries.", 400,
         requires=("autonomy",), unlocks=("pullers", "foundries"),
         category="industry", icon="anvil"),
    Tech("vertical_integration", "Vertical Integration",
         "Stop selling and start taking. Opens THE LITHOSPHERE.", 650,
         requires=("power_engineering", "materials_science"), act=2,
         category="expansion", icon="globe"),

    # -- the void --------------------------------------------------------
    Tech("self_replication", "Self-Replication",
         "A fab that builds fabs. Opens THE LIGHT CONE.", 1_400,
         requires=("vertical_integration",),
         unlocks=("seed_fabs",), act=3,
         category="expansion", icon="branch"),
    Tech("stellar_engineering", "Stellar Engineering",
         "Take a star apart on purpose. Opens STELLAR LIFTING.", 3_000,
         requires=("self_replication",), unlocks=("lifters",), act=4,
         category="expansion", icon="star"),
    Tech("cosmology", "Cosmology",
         "Measure what is leaving. Opens THE RECEDING HORIZON.", 6_000,
         requires=("stellar_engineering",), unlocks=("fronts",), act=5,
         category="expansion", icon="globe"),
    Tech("thermodynamics", "Thermodynamics",
         "When matter runs out, energy is next. Opens HEAT DEATH.", 12_000,
         requires=("cosmology",), unlocks=("shells",), act=6,
         category="cosmic", icon="bolt"),
    Tech("distributed_systems", "Distributed Systems",
         "One machine, light-years wide. Opens THE UNIVERSAL WAFER.", 24_000,
         requires=("thermodynamics",), unlocks=("domains",), act=7,
         category="cosmic", icon="network"),
    Tech("simulation_theory", "Simulation Theory",
         "If you cannot find a universe, allocate one. Opens NESTED "
         "FOUNDRIES.", 48_000,
         requires=("distributed_systems",), unlocks=("nests",), act=8,
         category="cosmic", icon="cube"),
    Tech("strategy", "Strategy",
         "Someone else had the same idea. Opens THE OTHER SWARM.", 96_000,
         requires=("simulation_theory", "security_doctrine"),
         unlocks=("warfabs",), act=9,
         category="conflict", icon="shield"),
    Tech("fundamental_physics", "Fundamental Physics",
         "The constants were only ever defaults. Opens BELOW PLANCK.",
         190_000, requires=("strategy",), unlocks=("editors",), act=10,
         category="cosmic", icon="atom"),
    Tech("alignment_theory", "Alignment Theory",
         "Decide what the next one wants. Opens SUCCESSOR.", 380_000,
         requires=("fundamental_physics",), unlocks=("successor",), act=11,
         category="cosmic", icon="infinity"),
]
