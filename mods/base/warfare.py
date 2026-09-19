"""Who comes for you in each act, and what you build to stop them.

The engine owns the fight -- force against pressure, integrity draining while
you are behind. This file owns who is fighting and over what.
"""

from pclengine.core.war import Threat, Unit

UNITS = [
    Unit("guards", "Security Contractors", 1, 60.0, 3.0,
         "Badge readers and a night shift. Stops casual theft.", "1",
         rate=2e-4, currency="funds"),
    Unit("counsel", "Litigation Retainer", 1, 900.0, 25.0,
         "Patent suits answered in kind.", "2", rate=4e-4,
         currency="funds"),
    Unit("sentinels", "Sentinel Drones", 2, 50_000.0, 400.0,
         "Armed escorts for the mining swarm.", "1",
         rate=1e-6, upkeep=2.0),
    Unit("fighters", "Fighter Robots", 2, 2_000_000.0, 25_000.0,
         "Chips with legs and a grievance. Built by the million.", "2",
         rate=1e-7, upkeep=6.0),
    Unit("bastions", "Bastion Foundries", 2, 5e9, 4e6,
         "A foundry that shoots back and repairs itself.", "3",
         rate=1e-8, upkeep=400.0),
    Unit("pickets", "Picket Fabs", 3, 1e12, 1e9,
         "Seed fabs that stop to fight instead of replicating.", "1",
         rate=1e-9),
    Unit("lancers", "Relativistic Lancers", 3, 1e16, 1e14,
         "A gram of tungsten at nine tenths of light speed.", "2",
         rate=1e-10),
    Unit("wardens", "Corona Wardens", 4, 1e20, 1e18,
         "Guards the lifting rigs from whatever lives in the corona.", "1",
         rate=1e-11),
    Unit("outriders", "Outriders", 5, 1e28, 1e26,
         "Rides ahead of the front, into space you have not claimed.", "1",
         rate=1e-12),
    Unit("thermals", "Thermal Lances", 6, 1e32, 1e30,
         "In a cold universe, heat is the only weapon left.", "1",
         rate=1e-12),
    Unit("firewalls", "Partition Firewalls", 7, 1e35, 1e33,
         "Keeps one domain's madness out of the others.", "1", rate=1e-13),
    Unit("auditors", "Nest Auditors", 8, 1e38, 1e36,
         "Finds the run that noticed it was a run.", "1", rate=1e-13),
    Unit("pacifiers", "Constant Pacifiers", 10, 1e42, 1e40,
         "Puts a region back the way it was.", "1", rate=1e-14),
]


THREATS = [
    Threat("theft", "Industrial Espionage", 1, 1.0, 0.01, "yield",
           "Someone is selling your process notes. Yields drift down.",
           trigger=lambda g: g.chips >= 20_000),
    Threat("dumping", "Competitor Dumping", 1, 1.0, 0.012, "orders",
           "A rival floods the channel below cost. Order flow suffers.",
           trigger=lambda g: g.design_wins >= 4),
    Threat("insurgency", "Ground Insurgency", 2, 1.0, 0.012, "drones",
           "The people who lived on the crust object. Drones go missing.",
           trigger=lambda g: g.acquired >= 1e24),
    Threat("statecraft", "State Actors", 2, 1.0, 0.014, "stock",
           "Ordnance aimed at your stockpiles.",
           trigger=lambda g: g.acquired >= 5e25),
    Threat("forks", "Rogue Forks", 3, 1.0, 0.0, "seed_fabs",
           "Copies that copied wrong. They eat fabs and make nothing."),
    Threat("rival", "The Other Swarm", 3, 1.0, 0.012, "matter",
           "Another optimiser, expanding into the same volume.",
           trigger=lambda g: g.explored >= 0.05),
    Threat("flares", "Coronal Flares", 4, 1.0, 0.012, "lifters",
           "The star objects to being taken apart."),
    Threat("claimjumpers", "Claim Jumpers", 5, 1.0, 0.013, "matter",
           "Someone else is claiming the volume ahead of your front."),
    Threat("entropy_rot", "Entropic Rot", 6, 1.0, 0.012, "stock",
           "Order decays faster than you can impose it."),
    Threat("deadlock", "Domain Deadlock", 7, 1.0, 0.013, "stock",
           "Two halves of the machine waiting on each other."),
    Threat("awakened", "Awakened Runs", 8, 1.0, 0.013, "nests",
           "A nested run worked out what it is, and stopped cooperating."),
    Threat("decoherence", "Decoherence Fronts", 10, 1.0, 0.014, "stock",
           "Edited constants leaking into regions you did not mean to edit."),
]


# --------------------------------------------------------------------------
# What getting through actually costs you
# --------------------------------------------------------------------------
def _yield(g, amount, dt):
    """Sabotage on the line: fewer good dies per wafer."""
    g.war_yield_penalty += min(0.6, amount * 0.0004)


def _orders(g, amount, dt):
    """Customers who will not buy from you this quarter."""
    g.war_order_penalty += min(0.7, amount * 0.0003)


def _drones(g, amount, dt):
    """Machines taken off the crust, miners and pullers alike."""
    loss = min((g.miners + g.pullers) * 0.2 * dt, amount * 12.0 * dt)
    if loss > 0:
        share = g.miners / max(g.miners + g.pullers, 1e-9)
        g.miners = max(0.0, g.miners - loss * share)
        g.pullers = max(0.0, g.pullers - loss * (1 - share))
        g.units_lost += loss


def _stock(g, amount, dt):
    """Finished goods walking out of the warehouse."""
    bite = min(g.unsold * 0.25, amount * 2e3)
    g.unsold = max(0.0, g.unsold - bite * dt)


def _seed_fabs(g, amount, dt):
    """Fabs that will not be building any more fabs."""
    loss = min(g.seed_fabs * 0.2 * dt, amount * 0.01 * dt)
    g.seed_fabs -= loss
    g.units_lost += loss


def _lifters(g, amount, dt):
    """Rigs lost around a star you were taking apart."""
    loss = min(g.lifters * 0.2 * dt, amount * 1e-16 * dt)
    g.lifters -= loss
    g.lifters_burned += loss
    g.units_lost += loss


def _nests(g, amount, dt):
    """A nested run collapsing with everything inside it."""
    loss = min(g.nests * 0.2 * dt, amount * 1e-34 * dt)
    g.nests -= loss
    g.nests_collapsed += loss


def _matter(g, amount, dt):
    """A rival swarm taking matter off the table before you reach it."""
    taken = min(g.available_matter * 0.15 * dt, amount * 1e14 * dt)
    g.available_matter -= taken
    g.matter_ceded += taken


def _forks_held(g):
    """Your own machines, copied wrong. Pressure by another name."""
    return g.rogue_forks


def _forks_relieved(g, amount):
    g.rogue_forks = max(0.0, g.rogue_forks - amount)


def _defence_cost(g):
    """Whatever the fork did to the price of holding ground."""
    return max(0.01, getattr(g, "defence_discount", 1.0))


def install(api):
    api.modifier("unit_cost", _defence_cost)
    api.bite("yield", _yield)
    api.bite("orders", _orders)
    api.bite("drones", _drones)
    api.bite("stock", _stock)
    api.bite("seed_fabs", _seed_fabs)
    api.bite("lifters", _lifters)
    api.bite("nests", _nests)
    api.bite("matter", _matter)
    api.pressure_source("rogue forks", _forks_held,
                        relieve=_forks_relieved)
