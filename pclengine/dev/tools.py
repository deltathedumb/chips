"""Developer options.

Everything here is gated behind --developer (or ?developer=1 on the web UI).
Each entry in ACTIONS is a name, a blurb, whether it takes a number, and a
function, so the terminal menu and the browser can both list them without
knowing what any particular one does.
"""

from pclengine.core import projects
from pclengine.store import runconfig
from pclengine.fmt import big, size, small
from pclengine import content


# ---------------------------------------------------------------- granting
def unlock_all_projects(g):
    before = len(g.completed)
    for p in projects.ALL:
        if not p.repeatable and p.id not in g.completed:
            g.completed.add(p.id)
            p.effect(g)
    return f"completed {len(g.completed) - before} projects (effects applied)"


def lock_all_projects(g):
    g.completed = set()
    return "all projects marked incomplete (effects stay applied)"


def fast_forward(g, seconds=300):
    """Run the simulation as fast as the CPU allows, with no UI."""
    seconds = float(seconds)
    step, done = 0.1, 0.0
    while done < seconds and not g.finished:
        g.tick(step)
        done += step
    return f"ran {done:,.0f} simulated seconds"


def set_cost_multiplier(g, value=1.0):
    """Scale every price in the game at once. 0.1 is ten times cheaper."""
    scale = max(0.0, float(value))
    g.cost_scale = scale
    g.hw_scale = scale
    return f"all costs x{scale:g} (projects and hardware)"


def set_project_cost(g, value=1.0):
    g.cost_scale = max(0.0, float(value))
    return f"project and research costs x{g.cost_scale:g}"


def set_hardware_cost(g, value=1.0):
    g.hw_scale = max(0.0, float(value))
    return f"machine, drone and rig costs x{g.hw_scale:g}"


def set_event_scale(g, value=1.0):
    g.event_scale = max(0.0, min(float(value), 10.0))
    return ("events are off" if g.event_scale == 0
            else f"event speed x{g.event_scale:g}")


def set_time_scale(g, value=1.0):
    g.time_scale = max(0.05, min(float(value), 100.0))
    return f"clock x{g.time_scale:g}"


def grant_forces(g, count=100000):
    """Fill out every unit the current act can field."""
    from pclengine.core import war
    made = []
    for unit in war.units_for(g.act):
        g.forces[unit.key] = g.forces.get(unit.key, 0) + int(float(count))
        made.append(unit.name)
    return ("+" + f"{int(float(count)):,} " + ", ".join(made)) if made         else "no units buildable in this act"


def clear_threats(g):
    g.pressure = {}
    g.rogue_forks = 0.0
    g.war_yield_penalty = g.war_order_penalty = 0.0
    return "all threat pressure cleared"


def grant_research(g, amount=1e6):
    g.research += float(amount)
    return f"+{big(float(amount))} research"


def max_research(g):
    """Research the whole tree, in dependency order."""
    from pclengine.core import research
    before = len(g.researched)
    for _ in range(len(research.TREE) + 1):
        for tech in research.available(g):
            g.researched.add(tech.id)
    return f"researched {len(g.researched) - before} techs"


def set_setup(g, value=1.0):
    """Set every multiplier at once, the way the setup screen would."""
    runconfig.Setup(time_scale=float(value), cost_scale=float(value),
                    hw_scale=float(value)).apply(g)
    return "all run settings x" + f"{float(value):g}"


# ---------------------------------------------------------------- reading
def locked_projects(g):
    """Every project you cannot see yet, and what it is waiting on."""
    out = []
    for p in projects.ALL:
        if p.id in g.completed:
            continue
        try:
            if p.req(g):
                continue
        except Exception:
            pass
        out.append(f"{p.title} - {p.unlock_hint(g)}")
    return out or ["nothing is locked"]


def state_dump(g):
    skip = {"messages", "completed", "fw"}
    return [f"{k} = {v!r}" for k, v in sorted(vars(g).items()) if k not in skip]


class Action:
    __slots__ = ("key", "name", "blurb", "arg", "default", "fn", "reads",
                 "cast")

    def __init__(self, key, name, blurb, fn, arg=None, default=None, reads=False):
        self.key = key
        self.name = name
        self.blurb = blurb
        self.fn = fn
        self.arg = arg            # label for the value it takes, if any
        self.default = default
        self.reads = reads        # True if it returns lines to display
        # Front ends hand values over as text. Numeric actions say so here so
        # they never receive a string they cannot add to.
        self.cast = str if isinstance(default, str) else float

    def parse(self, value):
        if value is None or value == "":
            return None
        return self.cast(value)


#: Actions the engine offers whatever the game is about.
ACTIONS = [
    Action("locked", "Show locked projects", "What each hidden project waits on",
           locked_projects, reads=True),
    Action("dump", "Dump raw state", "Every field on the Game object",
           state_dump, reads=True),
    Action("unlock", "Complete every project", "Apply the whole tree at once",
           unlock_all_projects),
    Action("relock", "Mark every project incomplete", "Leaves effects applied",
           lock_all_projects),
    Action("ff", "Fast-forward", "Run the sim with no UI", fast_forward,
           arg="seconds", default=300),
    Action("timescale", "Clock multiplier", "How fast game time runs",
           set_time_scale, arg="multiplier", default=1.0),
    Action("eventspeed", "Event speed", "How fast threats grow; 0 is off",
           set_event_scale, arg="multiplier", default=1.0),
    Action("forces", "Fill out this act's units", "Grant war units you can build",
           grant_forces, arg="how many", default=100000),
    Action("clearthreats", "Clear all threats", "Wipe accumulated pressure",
           clear_threats),
    Action("research", "Grant research", "Add research points", grant_research,
           arg="how much", default=1e6),
    Action("maxresearch", "Research everything", "Unlock the whole tree",
           max_research),
    Action("cost", "Cost multiplier", "Scale every price at once",
           set_cost_multiplier, arg="multiplier", default=1.0),
    Action("cost_projects", "Project cost multiplier",
           "Scale project and research prices only", set_project_cost,
           arg="multiplier", default=1.0),
    Action("cost_hardware", "Hardware cost multiplier",
           "Scale machines, drones and rigs only", set_hardware_cost,
           arg="multiplier", default=1.0),
    Action("setup", "Set every multiplier", "Clock and both cost scales",
           set_setup, arg="multiplier", default=1.0),
]


def add_action(action):
    """A developer action content contributes."""
    ACTIONS.append(action)
    BY_KEY[action.key] = action
    return action


def reset():
    del ACTIONS[len(_ENGINE_ACTIONS):]
    BY_KEY.clear()
    BY_KEY.update({a.key: a for a in ACTIONS})


_ENGINE_ACTIONS = list(ACTIONS)
BY_KEY = {a.key: a for a in ACTIONS}


def run(g, key, value=None):
    """Run a developer action. Returns (message, lines)."""
    from pclengine import errors
    action = BY_KEY.get(key)
    if action is None:
        return f"no such developer action: {key}", []
    try:
        parsed = action.parse(value) if action.arg is not None else None
    except (TypeError, ValueError):
        return f"{action.name} needs {action.arg or 'a value'}, not {value!r}", []
    try:
        result = action.fn(g) if parsed is None else action.fn(g, parsed)
    except Exception as exc:              # noqa: BLE001 - reported, not raised
        errors.capture(f"developer action {key}", exc)
        return f"{action.name} failed: {type(exc).__name__}: {exc}", []
    if action.reads:
        return action.name, list(result)
    return str(result), []


# --------------------------------------------------------------------------
# Panel layout. Both front ends render these groups rather than a flat list,
# and pair them with the live state fields from `editor.GROUPS`.
# --------------------------------------------------------------------------
ACTION_GROUPS = [
    ("Diagnostics", ["diagnose", "locked", "dump"]),
    ("Grants", ["chips", "funds", "data", "entropy", "bandwidth", "firmware",
                "research", "forces"]),
    ("Multipliers", ["cost", "cost_projects", "cost_hardware", "timescale",
                     "mode"]),
    ("Progression", ["act", "finishact", "unlock", "relock", "maxresearch",
                     "ff", "win"]),
    ("War", ["clearthreats"]),
]


def action_groups():
    """[(title, [Action, ...])], skipping anything not registered."""
    out = []
    for title, keys in ACTION_GROUPS:
        items = [BY_KEY[k] for k in keys if k in BY_KEY]
        if items:
            out.append((title, items))
    return out


def field_groups():
    """The live state fields, reusing the save editor's grouping."""
    from pclengine.ui import editor
    return editor.GROUPS
