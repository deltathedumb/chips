"""Acts I to III: the fab, the lithosphere and the light cone.

The panels are plain data -- rows of label, value and an optional key -- so
the terminal and the browser render the same act without either knowing what
an act is made of.
"""

from pclengine.core.acts import Act, chain_rows, panel, row
from pclengine.fmt import big, money, rate, size, small

from base import constants


# --------------------------------------------------------------------------
# Act I - the fab
# --------------------------------------------------------------------------
def fab_panels(g):
    # The order book itself lives down the left now, where it is visible
    # whichever tab you are on. This is the part you press keys at.
    floor = [row(f"Steppers  x{g.steppers}", money(g.stepper_cost), key="a",
                 hint="one wafer pass per second")]
    if g.scanners_unlocked:
        floor.append(row(f"EUV Scanners  x{g.scanners}", money(g.scanner_cost),
                         key="s", hint="500x a stepper"))
    floor.append(row(f"Design Wins  lvl {g.design_wins}",
                     money(g.design_win_cost), key="m",
                     hint="doubles the order flow"))
    floor.append(row("wafer lot", money(g.spot_price), key="w",
                     hint=f"{constants.LOT:,.0f} blank wafers"))
    return [panel("FAB FLOOR", floor),
            panel("MARKET", [
                row("price per chip", money(g.price), key="price",
                    hint="← and → move it; cheap chips move fast "
                         "but earn little"),
                row("the book will take", rate(g.order_flow())),
                row("you are making", rate(g.chip_rate()),
                    warn=g.chip_rate() > g.order_flow() * 1.5,
                    hint="capacity you cannot sell is worth nothing"),
            ])]


def fab_material(g):
    return panel("WAFERS", [
        row("blank wafers", big(g.wafers)),
        row("dies per wafer", f"{g.die_yield:,.2f}"),
        row(f"lot of {constants.LOT:,.0f}", money(g.spot_price), key="w"),
    ])


# --------------------------------------------------------------------------
# Act II - the lithosphere
# --------------------------------------------------------------------------
def lithosphere_panels(g):
    hardware = []
    for kind, key in (("miner", "h"), ("puller", "j"), ("foundry", "f"),
                      ("solar", "d"), ("battery", "g")):
        owned = getattr(g, g.UNIT_ATTR[kind])
        hardware.append(row(f"{g.UNIT_LABEL[kind]}  x{small(owned)}",
                            f"{small(g.unit_price(kind))} chips", key=key))
    supply, demand = g.power_supply(), g.power_demand()
    power = [
        row("supply / demand", f"{small(supply)} / {small(demand)} MW"),
        row("stored", f"{small(g.stored_power)} MWs"),
        row("running at", f"{g.power_ratio * 100:.1f}%", bar=g.power_ratio,
            warn=g.power_ratio < 0.999,
            hint="a shortfall throttles every drone"),
    ]
    return [panel("CHIP STOCK", [row("available to spend", small(g.unsold))]),
            panel("HARDWARE", hardware),
            panel("POWER", power),
            panel("THROUGHPUT", _chain_rows(g))]


def _chain_rows(g):
    """Which stage of grams -> wafers -> chips is actually the limit."""
    mine = g.miners * g.miner_perf
    pull = g.pullers * g.puller_perf
    etch = (g.foundries * 1e6 * g.foundry_perf
            / max(g.die_yield, 1e-9) * constants.GRAMS_PER_WAFER)
    return chain_rows(g, [("crust miners", mine), ("ingot pullers", pull),
                          ("foundries", etch)])


def lithosphere_material(g):
    frac = g.acquired / max(constants.EARTH_MATTER, 1.0)
    return panel("FEEDSTOCK", [
        row("unmined", f"{small(g.available_matter)} g"),
        row("mined", f"{small(g.matter)} g"),
        row("blank wafers", small(g.wafers)),
        row("dies per wafer", f"{g.die_yield:,.2f}"),
        row("lithosphere used", f"{frac * 100:.4f}%", bar=frac),
    ])


# --------------------------------------------------------------------------
# Act III - the light cone
# --------------------------------------------------------------------------
def light_cone_panels(g):
    swarm = [
        row("seed fabs", small(g.seed_fabs)),
        row("rogue forks", small(g.rogue_forks),
            warn=g.rogue_forks > g.seed_fabs * 0.01),
        row("chips in stock", small(g.unsold)),
        row("launch a seed fab", f"{small(g.unit_price('seed_fab'))} chips",
            key="l"),
    ]
    fw = []
    for key, label, blurb in constants.FIRMWARE_SETTINGS:
        if key == "counter" and not g.counter_unlocked:
            continue
        value = g.fw[key]
        entry = row(label, str(value), hint=blurb,
                    bar=value / max(g.firmware, 1),
                    warn=(value == 0 and key != "counter"))
        entry["setting"] = key
        fw.append(entry)
    return [panel("THE SWARM", swarm),
            panel(f"FIRMWARE   {g.firmware_free()}/{g.firmware} slots free", fw)]


def light_cone_material(g):
    frac = g.acquired / constants.UNIVERSE_MATTER
    return panel("FEEDSTOCK", [
        row("unmined", f"{small(g.available_matter)} g"),
        row("mined", f"{small(g.matter)} g"),
        row("blank wafers", small(g.wafers)),
        row("charted", f"{g.explored * 100:.2f}%"),
        row("matter taken", f"{small(g.acquired)} of {small(constants.UNIVERSE_MATTER)} g",
            bar=frac),
    ])


ACTS = [
    Act(1, "fab", "ACT I  ·  THE FAB",
        "Buy wafers, etch them, sell the chips.",
        "_tick_fab", fab_panels, fab_material,
        keys="SPACE etch  w lot  a/s fabs  m design  ←→ price  t/b sys"),
    Act(2, "lithosphere", "ACT II  ·  THE LITHOSPHERE",
        "Stop selling. Take the planet apart.",
        "_tick_lithosphere", lithosphere_panels, lithosphere_material,
        keys="h/j drones  f foundry  d/g power  x batch"),
    Act(3, "light_cone", "ACT III  ·  THE LIGHT CONE",
        "Seed fabs that build seed fabs.",
        "_tick_light_cone", light_cone_panels, light_cone_material,
        keys="l launch  ↑↓ pick  ←→ allocate  x batch"),
]


def install(api):
    for act in ACTS:
        api.add_act(act)
