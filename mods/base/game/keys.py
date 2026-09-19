"""Which key does what, act by act.

The engine turns a keypress into a name and hands it to the act you are in.
What "h" means -- a crust miner in Act II, a star lifter in Act IV -- is
subject matter, so it lives here. Anything the engine handles itself (the
panel tabs, the batch size, quitting, and the number row, which is reserved
for projects everywhere) never reaches this.

Every branch returns True when it took the key. That is not decoration: the
engine's input stack stops at the first layer that claims a keypress, and a
handler that always returns None is a layer that never claims anything, so
its keys quietly fall through to whatever is underneath. This file used to
do exactly that.
"""

from pclengine.ui.actions import visible_firmware_rows

from base import constants
from base.acts import final as acts_final, late as acts_late

#: Which keys each act answers to. The handler checks this before doing
#: anything, so what an act claims and what it does cannot drift apart.
ACT_ONE = ("w", "a", "s", "m", "[", "]", "LEFT", "RIGHT")
ACT_TWO = {"h": "miner", "j": "puller", "f": "foundry",
           "d": "solar", "g": "battery"}
SWARM = ("UP", "DOWN", "LEFT", "RIGHT", "l")


def handle(g, key):
    """Returns True if this act took the key, so nothing below sees it."""
    if g.act == 1:
        return _fab(g, key)
    if g.act == 2:
        return _lithosphere(g, key)
    if g.act == 4:
        return _stellar(g, key)
    if g.act == 5:
        return _horizon(g, key)
    if g.act >= 6:
        return _rigs(g, key)
    if g.act >= 3:
        return _swarm(g, key)
    return False


def _fab(g, key):
    """Act I's keys.

    Every refusal says which refusal it is. A buy that can fail because you
    are poor or because you have not researched it, and reports only the
    first, sends you off to earn money you already had.
    """
    if key == "w":
        if not g.buy_wafers(g.batch):
            g.log(f"A lot of wafers costs {g.spot_price:,.2f}; "
                  f"you have {g.funds:,.2f}.")
    elif key == "a":
        if not g.buy_stepper(g.batch):
            g.log(f"A stepper costs {g.stepper_cost:,.2f}; "
                  f"you have {g.funds:,.2f}.")
    elif key == "s":
        if not g.scanners_unlocked:
            g.log("EUV Scanners need their project first.")
        elif not g.can("scanners"):
            g.log("EUV scanners need Photonics. Research it first.")
        elif not g.buy_scanner(g.batch):
            g.log(f"A scanner costs {g.scanner_cost:,.2f}; "
                  f"you have {g.funds:,.2f}.")
    elif key == "m":
        if not g.can("design_wins"):
            g.log("Design wins need Market Analysis. Research it first.")
        elif not g.buy_design_win():
            g.log(f"A design win costs {g.design_win_cost:,.2f}; "
                  f"you have {g.funds:,.2f}.")
    elif key in ("[", "LEFT"):
        g.adjust_price(-0.01)
    elif key in ("]", "RIGHT"):
        g.adjust_price(0.01)
    else:
        return False
    return True


def _lithosphere(g, key):
    kind = ACT_TWO.get(key)
    if kind is None:
        return False
    if not g.buy_units(kind, g.batch):
        g.log(f"Not enough chips for a {kind.replace('_', ' ')}.")
    return True


def _stellar(g, key):
    if key == "h":
        if not acts_late.buy_lifters(g, g.batch):
            g.log("Not enough chips for a star lifter.")
    elif key == "j":
        if not acts_late.buy_radiators(g, g.batch):
            g.log("Not enough chips for a radiator.")
    elif key == "l":
        if not g.launch_seed_fabs(g.batch):
            g.log("Not enough chips to launch a seed fab.")
    else:
        return False
    return True


def _horizon(g, key):
    if key == "h":
        if not acts_late.buy_fronts(g, g.batch):
            g.log("Not enough chips for an expansion front.")
    elif key == "l":
        if not g.launch_seed_fabs(g.batch):
            g.log("Not enough chips to launch a seed fab.")
    else:
        return False
    return True


def _rigs(g, key):
    if key == "k":
        g.fidelity = 1.0 if g.fidelity < 1.0 else 0.35
        g.log(f"Archive fidelity set to {g.fidelity * 100:.0f}%.")
        return True
    for rig in acts_final.rigs_for(g.act):
        if rig.key == key:
            if not rig.buy(g, g.batch):
                g.log(f"Not enough chips for {rig.label}.")
            return True
    return False


def _swarm(g, key):
    rows = visible_firmware_rows(g)
    if key in ("UP", "DOWN") and rows:
        pos = rows.index(g.fw_sel) if g.fw_sel in rows else 0
        g.fw_sel = rows[(pos + (1 if key == "DOWN" else -1)) % len(rows)]
    elif key in ("LEFT", "RIGHT") and rows:
        name = constants.FIRMWARE_SETTINGS[g.fw_sel][0]
        if not g.adjust_firmware(name, 1 if key == "RIGHT" else -1):
            g.log("No free firmware slots.")
    elif key == "l":
        if not g.launch_seed_fabs(g.batch):
            g.log("Not enough chips to launch a seed fab.")
    else:
        return False
    return True


def install(api):
    """Every act shares one handler; it already branches on the act."""
    from pclengine.core import acts
    for act in acts.ALL:
        act.on_key = handle
