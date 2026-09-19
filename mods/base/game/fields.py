"""What a FOUNDRY game starts with.

The engine's Game knows about acts, research and war. Everything else -- how
many blank wafers you begin with, how much lithosphere there is to take --
is content, and arrives through `api.field`. Dicts and sets are given as
factories so two games never share one.

So is anything derived from a constant, and for a sharper reason: a mod
that raises EARTH_MATTER expects a game to start with that much of it. A
value read at import time is read before any mod has run, so the game would
start with the old figure and be measured against the new one -- and the
act it gates could never be finished.
"""

from base import constants

FIELDS = {
    # --- Act I: the fab ----------------------------------------------
    "chips": 0.0,
    "unsold": 0.0,
    "funds": 0.0,
    "wafers": lambda: constants.LOT,
    "spot_price": 20.0,
    "die_yield": 1.0,
    "price": 0.15,
    "design_wins": 1,
    "design_eff": 1.0,
    "order_mult": 1.0,
    "steppers": 0,
    "stepper_perf": 1.0,
    "scanners": 0,
    "scanner_perf": 1.0,
    "scanners_unlocked": False,
    "auto_procurement": False,
    "autoprice": False,
    # What a defender costs, relative. Lean Fabs cuts it; nothing else
    # touches it yet, which is what makes that fork worth taking.
    "defence_discount": 1.0,
    "revenue": 0.0,
    "sold_rate": 0.0,

    # --- the system you run on ---------------------------------------
    "bandwidth": 2,
    "threads": 1,
    "buffer": 1,
    "data": 0.0,
    "entropy": 0.0,
    "entropy_on": False,
    "entropy_mult": 1.0,
    "accelerators": 0,
    "next_bandwidth": 3000.0,
    "bandwidth_from_chips": 0,

    # --- Act II: the lithosphere -------------------------------------
    "available_matter": lambda: constants.EARTH_MATTER,
    "matter": 0.0,   # mined, not yet pulled into ingots
    "acquired": 0.0,
    "miners": 0.0,
    "pullers": 0.0,
    "foundries": 0.0,
    "solar": 0.0,
    "batteries": 0.0,
    "stored_power": 0.0,
    "miner_perf": 1.0,
    "puller_perf": 1.0,
    "foundry_perf": 1.0,
    "power_ratio": 1.0,
    "solar_perf": 1.0,
    "power_eff": 1.0,
    "telemetry": False,
    "buffer_expansions": 0,
    # Buffer is bought from a supplier who only has so many, and makes
    # more slowly. See `game/floor.py`.
    "buffer_stock": 2.0,
    "buffer_stock_max": 4.0,
    "buffer_restock_secs": 55.0,

    # --- Act III: the light cone -------------------------------------
    "seed_fabs": 0.0,
    "seed_perf": 1.0,
    "firmware": 0,
    "firmware_bought": 0,
    "fw": lambda: {key: 0 for key, _, _ in constants.FIRMWARE_SETTINGS},
    "fw_sel": 0,
    "rogue_forks": 0.0,
    "explored": 0.0,
    "counter_unlocked": False,
    "forks_reclaimed": 0.0,

    # --- warfare, present in every act -------------------------------
    # Losing ground for long enough ends the run. Integrity falls while
    # pressure exceeds your force and recovers while it does not.
    # One dial per act that needs a verb of its own.

    # --- the research line -------------------------------------------
    # Research is the spine: every capability and every act sits behind
    # a tech in `research.TREE`.
    "thread_perf": 1.0,

    # --- the manual compute burst ------------------------------------
    "burst_level": 0,
    "burst_cd": 0.0,
    "bursts_fired": 0,

    # --- Act IV: stellar lifting -------------------------------------
    "lifters": 0.0,
    "radiators": 0.0,
    "lift_perf": 1.0,
    "radiator_perf": 1.0,
    "heat_ratio": 1.0,
    "lifters_burned": 0.0,

    # --- Act V: the receding horizon ---------------------------------
    "fronts": 0.0,
    "front_perf": 1.0,
    "front_hold": 1.0,
    "horizon": 1.0,
    "matter_receded": 0.0,

    # --- Acts VI to XIV ----------------------------------------------
    "shells": 0.0,   # VI   heat death
    "sinks": 0.0,
    "negentropy": 0.0,
    "temperature": 2.7,
    "lattices": 0.0,   # VII  the universal wafer
    "domains": 0.0,
    "compute": 0.0,
    "substrates": 0.0,   # VIII nested foundries
    "nests": 0.0,
    "depth": 0.0,
    "instability": 0.0,
    "nests_collapsed": 0.0,
    "warfabs": 0.0,   # IX   the other swarm
    "screens": 0.0,
    "rival_volume": 0.35,
    "rival_strength": 1e38,
    "editors": 0.0,   # X    below planck
    "anchors": 0.0,
    "stability": 1.0,
    "constants_edited": 0.0,
    "regions_lost": 0.0,
    "capability": 0.0,   # XI   successor
    "verification": 0.0,
    "successor": 0.0,
    "alignment": 0.0,
    "archivists": 0.0,   # XII  the archive
    "vaults": 0.0,
    "archived": 0.0,
    "fidelity": 1.0,
    "watchers": 0.0,   # XIII boltzmann
    "aeons": 0.0,
    "fluctuation": 0.0,
    "masks": 0.0,   # XIV  tape-out
    "tapeout": 0.0,
}


def install(api):
    for name, default in FIELDS.items():
        api.field(name, default)
