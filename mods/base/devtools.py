"""Developer actions that only make sense for FOUNDRY.

Granting chips, filling the data buffer, jumping to the lithosphere: none of
it means anything to an engine that does not know what a wafer is, so it is
registered like any other content.
"""

from pclengine import content
from pclengine.core import acts, projects, research
from pclengine.dev.tools import Action
from pclengine.fmt import big, size, small
from pclengine.store import runconfig

from base import constants


def grant_chips(g, amount=1e12):
    g.chips += amount
    g.unsold += amount
    return f"+{big(amount)} chips"


def grant_funds(g, amount=1e6):
    g.funds += amount
    return f"+${amount:,.0f}"


def grant_data(g, amount=None):
    g.data = g.buffer_bytes if amount is None else min(g.buffer_bytes, g.data + amount)
    return f"buffer filled to {size(g.data)}"


def grant_entropy(g, amount=10000):
    g.entropy += amount
    return f"+{big(amount)} entropy"


def grant_bandwidth(g, amount=100):
    g.bandwidth += int(amount)
    return f"+{int(amount)} bandwidth ({g.free_bandwidth} free)"


def grant_firmware(g, amount=10):
    g.firmware += int(amount)
    return f"+{int(amount)} firmware slots"


# ---------------------------------------------------------------- jumping


def diagnose(g):
    """Why the numbers are not moving. The thing you actually want at 2am."""
    out = [f"act {g.act}   node {g.node:g}nm   mode "
           f"{runconfig.label_of(g)}"]
    if g.act == 1:
        make, sell = g.chip_rate(), g.order_flow()
        out.append(f"production {make:,.1f}/s vs order flow {sell:,.1f}/s")
        if g.wafers < 1:
            out.append("STALLED: no blank wafers - buy a lot (w)")
        elif make == 0:
            out.append("STALLED: no steppers - buy one (a)")
        elif sell < make:
            out.append(f"OVERPRODUCING: lower the price, or buy a design win")
        else:
            out.append("balanced; the market takes everything you make")
        left = 5e6 - g.chips
        if left > 0 and make > 0:
            out.append(f"vertical integration needs {big(left)} more chips "
                       f"({left / make / 60:,.1f} min at this rate)")
        if g.steppers < 75:
            out.append(f"EUV Scanners unlock at 75 steppers (you have {g.steppers})")
    elif g.act == 2:
        stages = {
            "crust miners": g.miners * g.miner_perf,
            "ingot pullers": g.pullers * g.puller_perf,
            "foundries": (g.foundries * 1e6 * g.foundry_perf
                          / max(g.die_yield, 1e-9) * content.constant("GRAMS_PER_WAFER", 1.0)),
        }
        slowest = min(stages, key=stages.get)
        for name, cap in stages.items():
            mark = "  <-- bottleneck" if name == slowest else ""
            out.append(f"{name:<15}{cap:.3e} g/s{mark}")
        supply, demand = g.power_supply(), g.power_demand()
        out.append(f"power {supply:.2e} / {demand:.2e} MW"
                   + ("  <-- THROTTLED" if g.power_ratio < 0.999
                      else f"  ({supply / max(demand, 1e-9):,.0f}x spare)"))
        rest = g.available_matter + g.matter
        if stages[slowest] > 0:
            out.append(f"{rest:.3e} g of Earth left: "
                       f"{rest / stages[slowest] / 60:,.1f} min at this rate")
    else:
        s = g.fw
        zero = [label for key, label, _ in
                __import__("pclengine.core.state", fromlist=["x"]).FIRMWARE_SETTINGS
                if s.get(key, 0) == 0 and key != "counter"]
        if s.get("survey", 0) == 0:
            out.append("STALLED: survey is 0, so nothing is charted and there "
                       "is no matter to mine. Put one slot in Survey.")
        for label in zero:
            out.append(f"{label} is at zero - that stage produces nothing")
        out.append(f"seed fabs {small(g.seed_fabs)}   forks {small(g.rogue_forks)}"
                   f"   charted {g.explored * 100:.4f}%")
        out.append(f"firmware {g.firmware_allocated()}/{g.firmware} allocated, "
                   f"{g.firmware_free()} free")
        if g.rogue_forks > g.seed_fabs * 0.01 and not g.counter_unlocked:
            out.append("forks are growing and Countermeasures is not unlocked")
    return out


def force_win(g):
    g.acquired = content.constant("UNIVERSE_MATTER", 1.0)
    g.available_matter = 0.0
    g.matter = 0.0
    g.wafers = 0.0
    g.chips = max(g.chips, content.constant("UNIVERSE_MATTER", 1.0) * 1.525)
    g.finished = True
    return "ending triggered"


def jump_to_act(g, act=2):
    act = int(act)
    if act >= 2 and g.act < 2:
        projects.BY_ID["vertical_integration"].effect(g)
    if act >= 3:
        g.acquired = max(g.acquired, content.constant("EARTH_MATTER", 1.0))
        g.available_matter = 0.0
        if g.act < 3:
            projects.BY_ID["seed_fab_program"].effect(g)
    g.act = act
    return f"jumped to act {act}"


def finish_act(g):
    """Satisfy whatever the current act is waiting on."""
    from pclengine.core import acts
    act = acts.get(g.act)
    target = getattr(act, "target", None)
    if target:
        g.acquired = max(g.acquired, target)
        g.available_matter = 0.0
    for attr, value in (("negentropy", 1e60), ("compute", 1e90), ("depth", 1e3),
                        ("rival_volume", 0.0), ("constants_edited", 1e3),
                        ("successor", 1e3), ("archived", 1e15),
                        ("fluctuation", 1.0), ("tapeout", 1.0)):
        if hasattr(g, attr):
            current = getattr(g, attr)
            setattr(g, attr, value if attr != "rival_volume"
                    else min(current, 0.0))
    return f"act {g.act} goal satisfied; take the next project"


ACTIONS = [
    Action("diagnose", "Diagnose", "Why is nothing happening?", diagnose, reads=True),
    Action("chips", "Grant chips", "Add chips to the stock", grant_chips,
           arg="how many", default=1e12),
    Action("funds", "Grant funds", "Add money (Act I)", grant_funds,
           arg="how much", default=1e6),
    Action("data", "Fill the buffer", "Top the data buffer up", grant_data),
    Action("entropy", "Grant entropy", "Add entropy", grant_entropy,
           arg="how much", default=10000),
    Action("bandwidth", "Grant bandwidth", "Add unassigned bandwidth",
           grant_bandwidth, arg="how much", default=100),
    Action("firmware", "Grant firmware slots", "Add seed fab firmware slots",
           grant_firmware, arg="how many", default=10),
    Action("act", "Jump to act", "Skip straight to act 2 or 3", jump_to_act,
           arg="act number", default=2),
    Action("finishact", "Satisfy this act's goal", "Skip to the transition",
           finish_act),
    Action("win", "Trigger the ending", "Jump to the end screen", force_win),
]


def install(api):
    for action in ACTIONS:
        api.dev_action(action)
