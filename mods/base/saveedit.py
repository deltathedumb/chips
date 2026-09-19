"""How the save editor groups a FOUNDRY save.

Which fields a game has depends on what is loaded, so the grouping is
content's to supply. Anything not named here still appears, under
EVERYTHING ELSE -- a mod's own fields included.
"""

from base import constants

GROUPS = [
    ("PROGRESS", ["act", "elapsed", "chips", "unsold", "funds", "finished"]),
    ("THE FAB", ["wafers", "spot_price", "die_yield", "price", "design_wins",
                 "design_eff", "order_mult", "steppers", "stepper_perf",
                 "scanners", "scanner_perf", "scanners_unlocked",
                 "auto_procurement"]),
    ("SYSTEM", ["bandwidth", "threads", "buffer", "data", "entropy",
                "entropy_on", "entropy_mult", "accelerators",
                "next_bandwidth", "bandwidth_from_chips"]),
    ("THE LITHOSPHERE", ["available_matter", "matter", "acquired", "miners",
                         "pullers", "foundries", "solar", "batteries",
                         "stored_power", "miner_perf", "puller_perf",
                         "foundry_perf", "solar_perf", "power_eff",
                         "telemetry", "buffer_expansions"]),
    ("THE LIGHT CONE", ["seed_fabs", "seed_perf", "firmware", "firmware_bought",
                        "rogue_forks", "explored", "counter_unlocked",
                        "forks_reclaimed"]),
    ("FIRMWARE ALLOCATION", [f"fw:{key}" for key, _, _ in constants.FIRMWARE_SETTINGS]),
    ("PROJECTS", ["completed"]),
    ("DISPLAY", ["batch", "hud_width"]),
    ("RUN SETTINGS", ["time_scale", "cost_scale", "hw_scale"]),
]


def install(api):
    for heading, fields in GROUPS:
        api.editor_group(heading, fields)
