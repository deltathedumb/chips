"""The numbers FOUNDRY is measured in.

Every one of these is subject matter, not mechanism: the engine has no
opinion about how many grams a wafer costs because the engine does not know
what a wafer is. Mods reach them through `api.constant`.
"""

LOT = 1000.0              # blank wafers in one purchased lot
GRAMS_PER_WAFER = 10.0    # silicon mass a single blank wafer costs you
EARTH_MATTER = 6.0e27       # grams of workable lithosphere
GALAXY_MATTER = 1.0e45      # the Milky Way, near enough
LOCAL_GROUP_MATTER = 1.0e50 # everything gravitationally bound to it
UNIVERSE_MATTER = 3.0e55    # grams of workable everything else

# Each firmware slot buys one point of one behaviour. Every point spent on
# replication is a point not spent on surviving the void.
FIRMWARE_SETTINGS = [
    ("thrust", "Delta-V", "how fast a seed fab crosses the void"),
    ("survey", "Survey", "rate at which new matter is charted"),
    ("replication", "Self-Replication", "seed fabs building seed fabs"),
    ("hardening", "Radiation Hardening", "surviving cosmic rays"),
    ("mining", "Mining", "matter drawn in per fab"),
    ("ingot", "Ingot Growth", "matter pulled into wafers"),
    ("litho", "Lithography", "wafers etched into chips"),
    ("counter", "Countermeasures", "defence against rogue forks"),
]

# The headline number. Completing a lithography project shrinks the node;
# nothing else reads it, it is the stat that tells you what era you are in.
NODES = [
    ("improved_steppers", 130.0),
    ("defect_metrology", 90.0),
    ("even_better_steppers", 65.0),
    ("zone_refining", 45.0),
    ("optimized_steppers", 32.0),
    ("transition_300mm", 22.0),
    ("multi_patterning", 14.0),
    ("transition_450mm", 10.0),
    ("euv_scanners", 7.0),
    ("improved_scanners", 5.0),
    ("monocrystal_casting", 3.0),
    ("even_better_scanners", 2.0),
    ("hyperscale_foundries", 1.4),
    ("unified_process_node", 0.8),
    ("angstrom_node", 0.4),
    ("stellar_lithography", 0.2),
    ("the_final_node", 0.1),
]
START_NODE = 180.0

# loader.py installs its hook runner here; empty in the base game.
