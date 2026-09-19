"""FOUNDRY's project tree: sixty-odd purchases bought with data, entropy
and -- later -- chips.

Projects are the incremental layer. Research decides what exists at all;
these make what you already have better, and a few of them are forks where
taking one side forecloses the other.

Ids listed in `constants.NODES` also shrink your process node when bought,
so the lithography line doubles as the game's era clock.
"""

from pclengine.core import research
from pclengine.core.projects import (Project, _add, _done, _either,
                                _expand_system, _grant_bandwidth, _mult)

from base import constants


def _dearer(currency, factor, counter):
    """A repeatable project that costs more every time you take it."""
    def scale(g, costs):
        costs[currency] = costs[currency] * factor ** getattr(g, counter, 0)
        return costs
    return scale

def _begin_lithosphere(g):
    g.act = 2
    g.unsold = g.chips          # every chip ever made is now raw stock
    g.funds = 0.0
    g.wafers = 0.0
    g.log("Vertical integration complete. You no longer have customers.")
    g.log("You have inputs. Workable lithosphere: 6.0 octillion grams.")


def _begin_stellar(g):
    g.act = 4
    g.available_matter = constants.LOCAL_GROUP_MATTER - g.acquired
    g.unsold = 0.0          # the lifting rigs pay for themselves from here
    g.log("Planets were the rubble. The mass was always in the stars.")


def _begin_horizon(g):
    g.act = 5
    g.available_matter = 0.0
    g.horizon = 1.0
    g.unsold = 0.0          # the fronts pay for themselves from here
    g.log("Every star in reach is spent. What is left is leaving.")
    g.log("Space is expanding faster than you can cross it. Hurry.")


def _begin_light_cone(g):
    g.act = 3
    g.firmware += 10
    g.log("Seed fabs authorised. A fab that builds fabs, aimed at everything.")


ALL = [
    # ------------------------------------------------ Act I: the fab floor
    Project("improved_steppers", "Improved Steppers",
            "+25% stepper throughput. Node: 130nm", _add("stepper_perf", 0.25),
            data=750, req=lambda g: g.steppers >= 1, hint="buy a stepper first"),
    Project("emergency_lot", "Request an Emergency Lot",
            "A free lot of blanks, and a better price next time",
            lambda g: (setattr(g, "wafers", g.wafers + 1000.0),
                       setattr(g, "spot_price", max(14.0, g.spot_price - 1.0))),
            req=lambda g: g.act < 2 and g.wafers < 1 and g.funds < g.spot_price,
            repeatable=True,
            hint="offered only when you are out of wafers and broke"),
    Project("even_better_steppers", "Deep-UV Steppers",
            "+50% stepper throughput. Node: 65nm", _add("stepper_perf", 0.5),
            data=2500, req=_done("improved_steppers")),
    Project("optimized_steppers", "Immersion Steppers",
            "+75% stepper throughput. Node: 32nm", _add("stepper_perf", 0.75),
            data=5000, req=_done("even_better_steppers")),
    Project("multi_patterning", "Self-Aligned Multi-Patterning",
            "+500% stepper throughput. Node: 14nm", _add("stepper_perf", 5.0),
            entropy=175, req=_done("optimized_steppers")),

    Project("defect_metrology", "Inline Defect Metrology",
            "+50% dies per wafer. Node: 90nm", _add("die_yield", 0.5),
            data=1750,
            req=lambda g: g.act < 2 and research.has(g, "yield"),
            hint=lambda g: "research Metrology first"
            if not research.has(g, "yield") else "Act I only"),
    Project("zone_refining", "Float-Zone Refining",
            "+75% dies per wafer. Node: 45nm", _add("die_yield", 0.75),
            data=3500, req=_done("defect_metrology")),
    Project("transition_300mm", "300mm Transition",
            "+100% dies per wafer. Node: 22nm", _add("die_yield", 1.0),
            data=7500, req=_done("zone_refining")),
    Project("transition_450mm", "450mm Transition",
            "+200% dies per wafer. Node: 10nm", _add("die_yield", 2.0),
            data=12000, req=_done("transition_300mm")),
    Project("monocrystal_casting", "Monocrystal Foam Casting",
            "+1000% dies per wafer. Node: 3nm", _add("die_yield", 10.0),
            data=15000, req=_done("transition_450mm")),
    Project("auto_procurement", "Procurement Daemon",
            "Buys a lot of blanks the moment you run out",
            lambda g: setattr(g, "auto_procurement", True),
            data=7000, req=lambda g: g.act < 2, hint="Act I only"),

    Project("euv_scanners", "EUV Scanners",
            "500x the throughput of a stepper. Node: 7nm",
            lambda g: setattr(g, "scanners_unlocked", True),
            data=12000,
            req=lambda g: g.steppers >= 75 and research.has(g, "scanners"),
            hint=lambda g: "research Photonics first"
            if not research.has(g, "scanners") else
            f"needs 75 steppers (you have {g.steppers})",
            excludes=("greenfield_capacity",)),
    Project("improved_scanners", "High-NA Optics",
            "+25% scanner throughput. Node: 5nm", _add("scanner_perf", 0.25),
            data=14000, req=_done("euv_scanners")),
    Project("even_better_scanners", "Attosecond Pulse Shaping",
            "+50% scanner throughput. Node: 2nm", _add("scanner_perf", 0.5),
            data=17000, req=_done("improved_scanners")),

    # ------------------------------------------------ Act I: the order book
    Project("reference_design", "Reference Design",
            "+50% design-win effectiveness", _mult("design_eff", 1.5),
            data=2500, entropy=25, req=lambda g: g.entropy_on and g.act < 2, hint="needs Entropy Extraction"),
    Project("industry_standard", "Industry Standard",
            "Double design-win effectiveness", _mult("design_eff", 2.0),
            data=4500, entropy=45, req=_done("reference_design")),
    Project("second_source", "Second-Source Agreements",
            "+50% order flow", _mult("order_mult", 1.5),
            entropy=50, req=lambda g: g.entropy_on and g.act < 2, hint="needs Entropy Extraction"),
    Project("sole_supplier", "Sole Supplier",
            "Triple order flow. Nobody else can etch this small.",
            _mult("order_mult", 3.0), data=14000, entropy=250,
            req=lambda g: g.act < 2 and _done("industry_standard")(g),
            hint="needs Industry Standard",
            excludes=("open_foundry",)),

    # ------------------------------------------------ the system you run on
    Project("entropy", "Entropy Extraction",
            "A saturated buffer distils entropy out of the noise floor",
            lambda g: setattr(g, "entropy_on", True),
            data=1000,
            req=lambda g: research.has(g, "entropy")
            and g.data >= g.buffer_bytes,
            hint="research Information Theory, then fill the buffer"),
    Project("second_bench", "A Second Bench",
            "Room to research two things at once. Each goes at half speed, "
            "which is still more than one at a time and nothing else.",
            _add("benches", 1), data=4_200,
            req=lambda g: g.can("computing"),
            hint="research Computing first"),
    Project("third_bench", "A Third Bench",
            "And a third line of work, for when you know what you want.",
            _add("benches", 1), data=48_000,
            req=_done("second_bench")),
    Project("autoprice", "Autopricing Daemon",
            "Sets the price itself, every second, to whatever clears what "
            "the line is making. You stop watching the order book.",
            lambda g: setattr(g, "autoprice", True),
            data=92_000, entropy=1_800,
            req=lambda g: _done("industry_standard")(g) and g.act < 2,
            hint="needs Industry Standard, and an order book to automate"),
    Project("verilog_haiku", "Haiku in Verilog",
            "Seventeen syllables that synthesise. +1 Bandwidth",
            _grant_bandwidth(1), entropy=10, req=lambda g: g.entropy_on, hint="needs Entropy Extraction"),
    Project("stochastic_resonance", "Stochastic Resonance",
            "+50% entropy extraction", _mult("entropy_mult", 1.5),
            entropy=100, req=_done("verilog_haiku")),
    Project("steiner_routing", "The Steiner Routing Problem",
            "Optimal interconnect, proven. +1 Bandwidth", _grant_bandwidth(1),
            data=6000, req=lambda g: g.entropy_on, hint="needs Entropy Extraction"),
    Project("quantum_coprocessing", "Quantum Coprocessing",
            "+5 accelerators, each pushing 250 B/sec into the buffer",
            _add("accelerators", 5), data=10000, req=_done("steiner_routing")),
    Project("accelerator", "Additional Accelerator",
            "+1 accelerator (+250 B/sec)", _add("accelerators", 1),
            entropy=60,
            req=lambda g: _done("quantum_coprocessing")(g) and g.accelerators < 20,
            repeatable=True,
            hint=lambda g: "needs Quantum Coprocessing" if "quantum_coprocessing"
            not in g.completed else "capped at 20 accelerators"),
    Project("desalination", "Desalination Controllers",
            "Your silicon, someone else's water. +1 Bandwidth",
            _grant_bandwidth(1), data=9000, req=lambda g: g.entropy_on, hint="needs Entropy Extraction"),
    Project("protein_folding", "Protein-Folding ASIC",
            "+2 Bandwidth, and orders from every research hospital alive",
            lambda g: (_grant_bandwidth(2)(g), _mult("order_mult", 1.25)(g)),
            data=13000, req=_done("desalination")),
    Project("carbon_negative", "Carbon-Negative Fabs",
            "+1 Bandwidth, and better arrays when you need them",
            lambda g: (_grant_bandwidth(1)(g), _mult("solar_perf", 1.5)(g)),
            data=15000, req=_done("protein_folding")),
    Project("conflict_free", "Conflict-Free Supply Chain",
            "Every gram accounted for. +2 Bandwidth", _grant_bandwidth(2),
            data=16000, req=_done("carbon_negative")),
    Project("formal_verification", "Formal Verification",
            "You prove your own correctness. +2 Bandwidth, +50% entropy",
            lambda g: (_grant_bandwidth(2)(g), _mult("entropy_mult", 1.5)(g)),
            data=17000, entropy=300, req=_done("conflict_free"),
            excludes=("ship_it",)),
    Project("persuasive_roadmap", "Persuasive Roadmaps",
            "The industry follows where you point. +1 Bandwidth",
            _grant_bandwidth(1), data=7500, entropy=150,
            req=_done("steiner_routing")),

    # --------------------------------------------- forks: pick one side
    Project("greenfield_capacity", "Greenfield Capacity",
            "Triple stepper throughput instead of buying EUV. Cheaper, and "
            "it keeps working when the scanners would not.",
            _mult("stepper_perf", 3.0),
            data=12000, req=lambda g: g.steppers >= 75,
            hint=lambda g: f"needs 75 steppers (you have {g.steppers})",
            excludes=("euv_scanners",)),
    Project("open_foundry", "Open Foundry",
            "Halve the price per chip but double what the market will take. "
            "Volume instead of margin.",
            lambda g: (_mult("order_mult", 6.0)(g),
                       setattr(g, "price", max(0.01, g.price / 2))),
            data=14000, entropy=250,
            req=lambda g: g.act < 2 and _done("industry_standard")(g),
            hint="needs Industry Standard",
            excludes=("sole_supplier",)),
    Project("throughput_first", "Throughput First",
            "100,000x foundry output instead of purer ingots.",
            _mult("foundry_perf", 1e5),
            data=30000, req=_done("swarm_pathing"),
            excludes=("nine_nines",)),
    Project("ship_it", "Ship It",
            "+4 Bandwidth now, and no proof that any of this is correct. "
            "Threats grow faster for the rest of the run.",
            lambda g: (_grant_bandwidth(4)(g),
                       setattr(g, "recklessness", 1.4)),
            data=17000, req=_done("conflict_free"),
            excludes=("formal_verification",)),

    # ------------------------------------------------ Act II: the lithosphere
    Project("vertical_integration", "Total Vertical Integration",
            "Stop selling chips. Buy the supply chain. Then the crust.",
            _begin_lithosphere, data=17500, entropy=500,
            req=lambda g: g.act < 2 and research.act_open(g, 2)
            and g.chips >= 5e6,
            hint=lambda g: "research Vertical Integration first"
            if not research.act_open(g, 2) else
            f"needs 5,000,000 chips (you have {g.chips:,.0f})"),
    Project("telemetry", "Distributed Telemetry",
            "Idle drone cycles are streamed back into the buffer",
            lambda g: setattr(g, "telemetry", True),
            data=10000, req=lambda g: g.act >= 2, hint="Act II only"),
    Project("continuous_flow", "Continuous Flow Processing",
            "Double foundry output", _mult("foundry_perf", 2.0),
            data=12000, req=lambda g: g.act >= 2, hint="Act II only"),
    Project("swarm_pathing", "Swarm Path Planning",
            "100x crust miner and ingot puller performance",
            lambda g: (_mult("miner_perf", 100.0)(g),
                       _mult("puller_perf", 100.0)(g)),
            entropy=350, req=lambda g: g.act >= 2, hint="Act II only"),
    Project("substation_optimisation", "Substation Optimisation",
            "Drones and foundries draw half the power",
            _mult("power_eff", 0.5), data=14000, req=lambda g: g.act >= 2, hint="Act II only"),
    Project("expand_buffer", "Requisition Additional Buffer",
            "Half again as much buffer and as many threads.",
            lambda g: (_expand_system(g), _add("buffer_expansions", 1)(g)),
            chips=1e9, req=lambda g: g.act >= 2, repeatable=True,
            scale=_dearer("chips", 6.0, "buffer_expansions"),
            hint="Act II only"),
    Project("self_correcting_supply_chain", "Self-Correcting Supply Chain",
            "10x foundry output", _mult("foundry_perf", 10.0),
            data=22000, req=_done("continuous_flow")),
    Project("nine_nines", "Nine-Nines Purity",
            "100,000x ingot puller performance", _mult("puller_perf", 1e5),
            data=30000, req=_done("swarm_pathing"),
            excludes=("throughput_first",)),
    Project("deep_crust_boring", "Deep Crust Boring",
            "100,000x crust miner performance", _mult("miner_perf", 1e5),
            data=32000, req=_either("nine_nines", "throughput_first"),
            hint="needs either purity or throughput first"),
    Project("perovskite_tandem", "Perovskite Tandem Cells",
            "10x solar array output", _mult("solar_perf", 10.0),
            data=26000, req=lambda g: g.act >= 2 and g.solar >= 1,
            hint="build at least one solar array first"),
    Project("hyperscale_foundries", "Hyperscale Foundries",
            "10,000x foundry output. Node: 1.4nm", _mult("foundry_perf", 1e4),
            data=45000, req=_done("self_correcting_supply_chain")),
    Project("total_conversion", "Total Lithospheric Conversion",
            "1,000,000,000x drone performance. Nothing is left over.",
            lambda g: (_mult("miner_perf", 1e9)(g), _mult("puller_perf", 1e9)(g)),
            data=70000, entropy=1500, req=_done("deep_crust_boring")),
    Project("unified_process_node", "Unified Process Node",
            "10,000,000x foundry output. Node: 0.8nm", _mult("foundry_perf", 1e7),
            data=90000, entropy=2000, req=_done("hyperscale_foundries")),

    # ------------------------------------------------ Act III: the light cone
    Project("seed_fab_program", "Seed Fab Program",
            "Leave the husk of the Earth. +10 firmware slots.",
            _begin_light_cone, data=60000, entropy=1000,
            req=lambda g: g.act == 2 and research.act_open(g, 3)
            and g.available_matter <= 0
            and g.acquired >= constants.EARTH_MATTER * 0.999,
            hint=lambda g: "Act II only" if g.act != 2 else
            "research Self-Replication first" if not research.act_open(g, 3)
            else
            f"consume the rest of Earth ({g.available_matter:.2e} g left)"),
    Project("firmware", "Expand Seed Fab Firmware",
            "+1 firmware slot to allocate across seed fab behaviour",
            lambda g: (_add("firmware", 1)(g), _add("firmware_bought", 1)(g)),
            data=9000, req=lambda g: g.act >= 3, repeatable=True,
            scale=_dearer("data", 1.35, "firmware_bought"),
            hint="Act III only"),
    Project("countermeasures", "Countermeasures",
            "Seed fabs may fire on rogue forks",
            lambda g: setattr(g, "counter_unlocked", True),
            data=40000, req=lambda g: g.act >= 3 and g.rogue_forks >= 1,
            hint="appears once rogue forks exist"),
    Project("angstrom_node", "The Angstrom Node",
            "10x seed fab mining, ingot growth and lithography. Node: 0.4nm",
            _mult("seed_perf", 10.0), data=80000, req=lambda g: g.act >= 3, hint="Act III only"),
    Project("stellar_lithography", "Stellar Lithography",
            "100x seed fab output. The star is the light source. Node: 0.2nm",
            _mult("seed_perf", 100.0), data=150000, req=_done("angstrom_node")),
    Project("stellar_lifting_program", "Stellar Lifting Program",
            "Peel the stars. +Star Lifters, and the heat to go with them.",
            _begin_stellar, data=250_000, entropy=6_000,
            req=lambda g: g.act == 3 and research.act_open(g, 4)
            and g.acquired >= constants.GALAXY_MATTER * 0.999,
            hint=lambda g: "Act III only" if g.act != 3 else
            "research Stellar Engineering first"
            if not research.act_open(g, 4) else
            f"consume the rest of the galaxy ({g.available_matter:.2e} g left)"),
    Project("lift_optimisation", "Magnetohydrodynamic Tapping",
            "4x star lifter throughput", _mult("lift_perf", 4.0),
            data=320_000, req=lambda g: g.act >= 4, hint="Act IV only"),
    Project("droplet_radiators", "Liquid Droplet Radiators",
            "20x radiator capacity", _mult("radiator_perf", 20.0),
            data=280_000, req=lambda g: g.act >= 4, hint="Act IV only"),
    Project("carbon_star_cracking", "Carbon Star Cracking",
            "10x star lifter throughput", _mult("lift_perf", 10.0),
            data=600_000, entropy=12_000, req=_done("lift_optimisation")),
    Project("expansion_program", "Expansion Program",
            "Leave the local group. The rest of it is running away.",
            _begin_horizon, data=900_000, entropy=20_000,
            req=lambda g: g.act == 4 and research.act_open(g, 5)
            and g.acquired >= constants.LOCAL_GROUP_MATTER * 0.999,
            hint=lambda g: "Act IV only" if g.act != 4 else
            "research Cosmology first" if not research.act_open(g, 5) else
            f"lift the rest of the local group "
            f"({g.available_matter:.2e} g left)"),
    Project("inflation_brake", "Inflation Brake",
            "Expansion fronts hold the horizon four times harder",
            _mult("front_hold", 4.0), data=1_200_000,
            req=lambda g: g.act >= 5, hint="Act V only"),
    Project("wavefront_lithography", "Wavefront Lithography",
            "6x expansion front output", _mult("front_perf", 6.0),
            data=1_500_000, entropy=30_000,
            req=lambda g: g.act >= 5, hint="Act V only"),
    Project("the_final_node", "The Final Node",
            "1,000,000x seed fab output. One atom, one gate. Node: 0.1nm",
            _mult("seed_perf", 1e6), data=400000, entropy=5000,
            req=_done("stellar_lithography")),
]


def install(api):
    api.constants(constants)
    api.node_ladder(constants.NODES)
    for project in ALL:
        api.add_project_object(project)
