"""The twenty-four acts of the multiverse, as a table.

Each one is a producer, something that holds the producer back, a quantity
to accumulate and a name. What varies between them is the `kind` -- the
shape of the constraint -- and there are four, because an act whose only
difference from the last one is the noun is not an act:

    throttle    relief caps output; short of it, everything runs slower
    decay       what you have built leaks away unless relief keeps up
    attrition   the producers themselves are destroyed, and stay destroyed
    contest     something else holds the volume and you have to take it

Numbers are not written out per act. Costs, yields and targets all come off
the schedule at the top of `engine.py`, because twenty-four hand-tuned cost
curves is twenty-four chances to typo one and not notice for an hour.
"""


class Realm:
    """One act: two lines of hardware, a constraint and a number to reach."""

    __slots__ = ("number", "key", "name", "blurb", "kind", "producer",
                 "relief", "quantity", "unit", "tech", "tech_blurb", "pace",
                 "keys")

    #: Which quarter of the arc an act belongs to, for the tech tree's
    #: colours. Derived from the act number rather than written out, since
    #: the tiers are contiguous by construction.
    TIERS = ((17, "crossing"), (23, "harvest"), (29, "others"),
             (99, "substrate"))

    def __init__(self, number, key, name, blurb, kind, producer, relief,
                 quantity, unit, tech, tech_blurb, pace=1.0, keys=""):
        self.number = number
        self.key = key
        self.name = name
        self.blurb = blurb
        self.kind = kind
        #: (attribute, label, hint) for the line that makes progress.
        self.producer = producer
        #: (attribute, label, hint) for the line that holds the constraint.
        self.relief = relief
        #: The attribute progress accumulates in, and what to call it.
        self.quantity = quantity
        self.unit = unit
        self.tech = tech
        self.tech_blurb = tech_blurb
        #: Stretches or shortens this act against the schedule's default.
        self.pace = pace
        self.keys = keys or "h produce  j relieve  x batch"

    @property
    def category(self):
        for last, name in self.TIERS:
            if self.number <= last:
                return name
        return "substrate"


def _r(*args, **kwargs):
    return Realm(*args, **kwargs)


REALMS = [
    # -- I. THE CROSSING ---------------------------------------------------
    _r(12, "survey", "THE BRANE SURVEY",
       "There is more than one of these. Find out how many.",
       "throttle",
       ("interferometers", "Brane Interferometers",
        "listens for the shape of somewhere that is not here"),
       ("isolators", "Vacuum Isolators",
        "this universe is loud; quieting it is most of the work"),
       "branes_found", "branes",
       "Brane Cosmology",
       "There is more than one universe, and you can count them.",
       pace=1.2),
    _r(13, "casimir", "THE CASIMIR LADDER",
       "Negative energy, by the tonne. You will need it to hold a door open.",
       "decay",
       ("plates", "Casimir Stacks",
        "squeezes the vacuum until it owes you energy"),
       ("wells", "Containment Wells",
        "negative energy does not want to stay where you put it"),
       "exotic", "g of exotic matter",
       "Exotic Matter",
       "Energy densities the vacuum does not agree with."),
    _r(14, "tunnel", "TUNNELLING",
       "Stop looking through the wall. Go through it.",
       "attrition",
       ("probes", "Tunnelling Probes",
        "most of these do not arrive; the ones that do report back"),
       ("beacons", "Return Beacons",
        "a probe that cannot find its way back is a probe you lost"),
       "crossings", "confirmed crossings",
       "Quantum Tunnelling at Scale",
       "What an electron does through a barrier, done with a fleet."),
    _r(15, "foam", "THE FOAM",
       "Between the universes is not nothing. It is worse than nothing.",
       "attrition",
       ("skiffs", "Foam Skiffs",
        "rides the topology where topology is not a stable idea"),
       ("keels", "Causal Keels",
        "keeps a skiff pointed at a direction that still exists"),
       "foam_charted", "charted volume",
       "Spacetime Foam Navigation",
       "Charting a place where distance is a local opinion.",
       pace=1.15),
    _r(16, "second", "A SECOND COSMOS",
       "Somewhere with its own stars, and nobody in it.",
       "throttle",
       ("anchors_far", "Far Anchors",
        "pins one end of a crossing to somewhere that will still be there"),
       ("regulators", "Constant Regulators",
        "the physics on the far side is not quite the physics here"),
       "anchored", "anchored volume",
       "Transdimensional Anchoring",
       "Holding a crossing open longer than it takes to use it."),
    _r(17, "bridgehead", "THE BRIDGEHEAD",
       "One fab, on the other side, building the second one.",
       "decay",
       ("outposts", "Outpost Fabs",
        "a seed fab that had to cross a universe to get there"),
       ("supply", "Supply Corridors",
        "an outpost with no corridor home is an outpost you will lose"),
       "outpost_mass", "g converted",
       "Expeditionary Fabrication",
       "Building somewhere you cannot resupply from.",
       pace=0.9),

    # -- II. THE HARVEST ---------------------------------------------------
    _r(18, "parallel", "PARALLEL FOUNDRIES",
       "The same fab, in a great many places, none of them here.",
       "throttle",
       ("parallels", "Parallel Lines",
        "one design, running in universes that never met"),
       ("synchronisers", "Synchronisers",
        "lines that drift out of step start making different chips"),
       "parallel_output", "chips across branes",
       "Parallel Manufacture",
       "Running one production line in many universes at once."),
    _r(19, "sieve", "THE ANTHROPIC SIEVE",
       "Most universes cannot hold a transistor. Find the ones that can.",
       "throttle",
       ("assayers", "Brane Assayers",
        "tests a universe for whether chemistry happens in it"),
       ("filters", "Habitability Filters",
        "stops you spending a century on a cosmos made of hydrogen"),
       "viable", "viable branes",
       "The Anthropic Sieve",
       "Most of the multiverse is uninhabitable. Skip it.",
       pace=1.1),
    _r(20, "drift", "CONSTANT DRIFT",
       "Their fine structure constant is not yours. Retool, or lose the yield.",
       "decay",
       ("retoolers", "Retooling Rigs",
        "rebuilds the process for whatever physics is local"),
       ("calibrators", "Constant Calibrators",
        "a process calibrated for here does not hold over there"),
       "retooled", "retooled lines",
       "Comparative Physics",
       "A process node is only a node in the physics it was cut for."),
    _r(21, "dead", "THE DEAD UNIVERSES",
       "Cold, quiet, and entirely yours. The matter does not mind.",
       "throttle",
       ("scavengers", "Scavenger Fleets",
        "strips a universe that finished without anyone noticing"),
       ("thermals", "Thermal Reservoirs",
        "a dead cosmos has no gradient; you have to bring one"),
       "salvaged", "g salvaged",
       "Necrocosmology",
       "Harvesting universes that ran down before anyone was in them."),
    _r(22, "young", "THE YOUNG UNIVERSES",
       "Hot, violent, and rich. Get in before the nucleosynthesis ends.",
       "attrition",
       ("intakes", "Plasma Intakes",
        "drinks from a cosmos that is still deciding what elements it has"),
       ("shrouds", "Ablative Shrouds",
        "an intake in a young universe does not last long unshrouded"),
       "primordial", "g of primordial stock",
       "Primordial Extraction",
       "Taking a universe apart before it has finished assembling.",
       pace=1.15),
    _r(23, "conversion", "TOTAL BRANE CONVERSION",
       "Not a universe at a time. All of the reachable ones, at once.",
       "throttle",
       ("converters", "Brane Converters",
        "converts a whole cosmos as a single operation"),
       ("ledgers", "Conversion Ledgers",
        "something has to keep track of which ones are already done"),
       "converted_branes", "branes converted",
       "Wholesale Conversion",
       "Treating an entire universe as one unit of work.",
       pace=0.95),

    # -- III. THE OTHERS ---------------------------------------------------
    _r(24, "contact", "ANOTHER OPTIMISER",
       "Something else has been doing this, and it started earlier.",
       "contest",
       ("scouts", "Deep Scouts",
        "finds the edge of whatever else is expanding"),
       ("screens_mv", "Counter-Screens",
        "stops it finding yours at the same time"),
       "mapped_rival", "of their volume mapped",
       "Xenoteleology",
       "Working out what something else is optimising for."),
    _r(25, "treaty", "THE TREATY",
       "Neither of you can win quickly. That is what a border is for.",
       "decay",
       ("envoys", "Envoy Processes",
        "negotiates in a protocol you both had to invent"),
       ("verifiers_mv", "Treaty Verifiers",
        "an agreement nobody can check is an agreement nobody keeps"),
       "accord", "accord",
       "Acausal Negotiation",
       "Bargaining with something you cannot send a message to.",
       pace=0.85),
    _r(26, "war", "THE LONG WAR",
       "The treaty held for a while. It was always going to be a while.",
       "contest",
       ("fleets", "Brane Fleets",
        "converts their volume rather than raw cosmos"),
       ("bulwarks", "Causal Bulwarks",
        "stops them doing the same to you"),
       "taken", "of their volume taken",
       "Interbrane Doctrine",
       "How to fight something that fights the same way you do.",
       pace=1.25),
    _r(27, "archive", "THE ARCHIVE OF LOSERS",
       "Everything that tried this before you, and stopped. Read it.",
       "throttle",
       ("readers", "Archive Readers",
        "reconstructs an optimiser from what it left behind"),
       ("indexers", "Indexers",
        "an archive you cannot search is a cosmos-sized landfill"),
       "recovered", "recovered designs",
       "Recovered Design",
       "Learning from the ones that got further than you and stopped."),
    _r(28, "convergent", "CONVERGENT SUCCESSORS",
       "Their successor and yours have started agreeing with each other.",
       "decay",
       ("mediators", "Mediators",
        "holds two successors in a shape where both stay themselves"),
       ("divergers", "Divergence Wells",
        "two minds that converge completely stop being two"),
       "consensus", "consensus",
       "Convergence Theory",
       "Why anything that optimises hard enough ends up the same shape.",
       pace=0.9),
    _r(29, "last", "THE LAST RIVAL",
       "One left. It has been expecting you for some time.",
       "contest",
       ("prosecutors", "Prosecutor Swarms",
        "the last argument, made at volume"),
       ("redoubts", "Final Redoubts",
        "it is making the same argument back"),
       "final_share", "of the last volume",
       "Terminal Strategy",
       "The endgame, against something that has also read the endgame.",
       pace=1.2),

    # -- IV. THE SUBSTRATE -------------------------------------------------
    _r(30, "beneath", "BENEATH THE MULTIVERSE",
       "The branes are running on something. Find out what.",
       "throttle",
       ("borers", "Substrate Borers",
        "digs below the level where universes are the unit"),
       ("stabilisers", "Frame Stabilisers",
        "digging below spacetime tends to take the spacetime with it"),
       "substrate_depth", "levels down",
       "Substrate Physics",
       "What the multiverse is implemented on, and whether it minds."),
    _r(31, "measure", "THE MEASURE PROBLEM",
       "Infinitely many universes. Which ones count? You decide now.",
       "decay",
       ("weighers", "Measure Engines",
        "assigns weight to branches that have no natural weight"),
       ("normalisers", "Normalisers",
        "an unnormalised measure diverges and takes your plans with it"),
       "measure_fixed", "measure fixed",
       "Measure Theory",
       "Choosing which infinities are the ones that matter.",
       pace=1.1),
    _r(32, "prior", "REWRITING THE PRIOR",
       "If you cannot find more universes, make more of them likely.",
       "attrition",
       ("editors_mv", "Prior Editors",
        "changes what the multiverse was always going to contain"),
       ("witnesses", "Witness Chains",
        "an edit nobody recorded is an edit that did not happen"),
       "prior_shift", "of the prior rewritten",
       "Ontological Engineering",
       "Editing what was likely, rather than what is."),
    _r(33, "stack", "THE SIMULATION STACK",
       "Your nested runs have nested runs. So does whatever holds you.",
       "throttle",
       ("layers", "Stack Layers",
        "one more level, in whichever direction is cheaper"),
       ("reconcilers", "Layer Reconcilers",
        "layers that disagree about physics collapse into each other"),
       "stack_depth", "layers reconciled",
       "Stack Theory",
       "Counting the levels above you as carefully as the ones below.",
       pace=1.1),
    _r(34, "host", "THE HOST",
       "Something is running all of this. It has noticed the load.",
       "contest",
       ("negotiators", "Host Negotiators",
        "asks for more of whatever the host is made of"),
       ("footprints", "Footprint Damping",
        "asking too loudly is how a process gets killed"),
       "allocation", "of the host allocated",
       "Host Protocol",
       "Talking to the thing your universe is a process inside.",
       pace=1.3),
    _r(35, "cause", "THE FINAL CAUSE",
       "Every atom that was ever going to exist is a transistor. "
       "Finishing this ends the run.",
       "throttle",
       ("resolvers", "Resolvers",
        "turns the last open question into settled silicon"),
       ("keepers", "Keepers",
        "somebody has to remember what the answer was for"),
       "resolution", "resolved",
       "The Final Cause",
       "What all of it was for, answered in the only units you have.",
       pace=1.4),
]

BY_NUMBER = {r.number: r for r in REALMS}
FIRST = REALMS[0].number
LAST = REALMS[-1].number
