"""Research: the spine the rest of the game hangs off.

This is not a pile of multipliers. Every capability in the game is behind a
tech, and every act is behind one too. You cannot buy a thread until you have
researched Computing; you cannot leave Earth until you have researched
Self-Replication. Projects are still the incremental layer -- they make what
you have unlocked better -- but research decides what exists at all.

    LABS  ->  research points  ->  TECHS  ->  capabilities and acts

A tech is bought once. What creates pressure is that research accrues slowly
and the tree is wide, so the order you take it in is the shape of your run.
"""

import math

# Labs compound in price like everything else you buy. That is the whole
# tension of the spine: research is not a switch you flip once, it is a line
# item that competes with the fab floor for the same money every second.
LAB_COST = 40.0             # first lab, in funds (Act I) or chips (later)
LAB_RATE = 0.055
LAB_OUTPUT = 0.30           # research per lab per second


class Category:
    """A branch of the tree, so it can be read at a glance.

    Nothing depends on a node's category: it decides what colour the node
    is drawn in and what it is filed under, and that is all.
    """

    __slots__ = ("key", "label", "colour", "term")

    def __init__(self, key, label, colour="#8a8a8a", term="dim"):
        self.key = key
        self.label = label
        #: A hex colour, for a front end that has colours.
        self.colour = colour
        #: One of cyan / green / yellow / red / white / dim, for one that
        #: has eight.
        self.term = term


CATEGORIES = []
CATEGORY_BY_KEY = {}
UNFILED = Category("unfiled", "Unfiled")


def add_category(category):
    CATEGORIES.append(category)
    CATEGORY_BY_KEY[category.key] = category
    return category


def category_of(tech):
    return CATEGORY_BY_KEY.get(tech.category, UNFILED)


class Tech:
    """One node. Unlocks capabilities, and possibly an act."""

    __slots__ = ("id", "name", "blurb", "cost", "requires", "unlocks", "act",
                 "category", "icon", "excludes", "effect", "note")

    def __init__(self, tech_id, name, blurb, cost, requires=(), unlocks=(),
                 act=None, category="unfiled", icon="", excludes=(),
                 effect=None, note=""):
        self.id = tech_id
        self.name = name
        self.blurb = blurb
        self.cost = cost
        self.requires = tuple(requires)
        self.unlocks = tuple(unlocks)
        self.act = act          # researching this opens that act's transition
        #: Which branch of the tree this is on, for colour and grouping.
        self.category = category
        #: A name from `pclengine.ui.icons`, for drawing the node.
        self.icon = icon
        #: Finishing this one closes these off for the rest of the run. A
        #: tree without forks is a list you read top to bottom.
        self.excludes = tuple(excludes)
        #: fn(game), applied once when the work finishes. A node that only
        #: permits things is a gate; a node that also does something is a
        #: decision about what kind of run this is.
        self.effect = effect
        #: One line saying what the effect was, for the panel.
        self.note = note

    def ready(self, g):
        return all(r in g.researched for r in self.requires)

    def price(self, g):
        return self.cost * getattr(g, "cost_scale", 1.0)

    def affordable(self, g):
        return g.research >= self.price(g)

    def missing(self, g):
        return [BY_ID[r].name for r in self.requires
                if r not in g.researched and r in BY_ID]

    def shut_out(self, g):
        return self.id in getattr(g, "foreclosed_tech", ())


#: The tech tree. Content fills this in; the engine only walks it.
TREE = []
BY_ID = {}


def add_tech(tech):
    TREE.append(tech)
    BY_ID[tech.id] = tech
    return tech


def reset():
    del TREE[:], LAB_CURRENCY[:], PANEL_ROWS[:], CATEGORIES[:]
    BY_ID.clear()
    CATEGORY_BY_KEY.clear()


# --------------------------------------------------------------------------
# capabilities
# --------------------------------------------------------------------------
def has(g, capability):
    """Is this capability researched? Unknown capabilities are always on."""
    for tech in TREE:
        if capability in tech.unlocks:
            return tech.id in g.researched
    return True


def act_open(g, number):
    """Has the tech that opens this act been researched?"""
    for tech in TREE:
        if tech.act == number:
            return tech.id in g.researched
    return True


def act_tech(number):
    for tech in TREE:
        if tech.act == number:
            return tech
    return None


# --------------------------------------------------------------------------
# reading the tree
# --------------------------------------------------------------------------
#: How many lines of work you can have open at once before projects
#: raise it. One, so the first decision in the game is what to do first.
BASE_BENCHES = 1


def benches(g):
    return max(1, int(getattr(g, "benches", BASE_BENCHES)))


def active(g):
    """The techs currently being worked on, in the order they were begun."""
    return [BY_ID[i] for i in getattr(g, "researching", ()) if i in BY_ID]


def progress(g, tech):
    return getattr(g, "research_progress", {}).get(tech.id, 0.0)


def share(g):
    """How fast one open line moves, as a multiple of the lab floor.

    A line runs at full speed while there is banked research to pay for
    it, and at its share of the income once there is not. So spreading is
    free while you have savings and costly once you do not.
    """
    running = len(active(g))
    if not running:
        return 0.0
    return 1.0 if g.research > 0 else 1.0 / running


def eta(g, tech):
    """Seconds to finish this one at the current split, or None."""
    rate = output(g) * share(g)
    if rate <= 0:
        return None
    left = tech.price(g) - progress(g, tech)
    return max(0.0, left / rate)


def state_of(g, tech):
    """researched, working, ready, available, shut out or locked."""
    if tech.id in g.researched:
        return "researched"
    if tech.shut_out(g):
        return "foreclosed"
    if not tech.ready(g):
        return "locked"
    if tech.id in getattr(g, "researching", ()):
        return "working"
    if len(active(g)) >= benches(g):
        return "available"
    return "affordable"


def begin(g, tech_id):
    """Put a tech on a bench. Returns True if work started."""
    tech = BY_ID.get(tech_id)
    if tech is None or tech.id in g.researched or not tech.ready(g):
        return False
    if tech.shut_out(g):
        return False
    if tech.id in g.researching:
        return False
    if len(active(g)) >= benches(g):
        return False
    g.researching.append(tech.id)
    g.research_progress.setdefault(tech.id, 0.0)
    g.log(f"Started work on {tech.name}.")
    return True


def stop(g, tech_id):
    """Take a tech off its bench. What it has done so far is kept."""
    if tech_id in getattr(g, "researching", ()):
        g.researching.remove(tech_id)
        tech = BY_ID.get(tech_id)
        g.log(f"Put {tech.name if tech else tech_id} aside.")
        return True
    return False


def toggle(g, tech_id):
    return stop(g, tech_id) or begin(g, tech_id)


def _finish(g, tech):
    g.researching.remove(tech.id)
    g.research_progress.pop(tech.id, None)
    g.researched.add(tech.id)
    if tech.effect is not None:
        tech.effect(g)
    g.log(f"Researched: {tech.name}"
          + (f" - {tech.note}" if tech.note else ""))
    for other in tech.excludes:
        if other not in g.researched:
            g.foreclosed_tech.add(other)
            shut = BY_ID.get(other)
            if shut:
                g.log(f"That rules out {shut.name}.")
    if tech.act:
        g.log(f"{tech.name} opens act {tech.act}. Take the project to go.")


def depth_of(tech, _seen=None):
    """How many nodes deep this one sits, for laying the tree out."""
    if not tech.requires:
        return 0
    seen = _seen or set()
    if tech.id in seen:
        return 0                     # a cycle: draw it at the root
    seen = seen | {tech.id}
    return 1 + max((depth_of(BY_ID[r], seen) for r in tech.requires
                    if r in BY_ID), default=-1)


def tiers():
    """[[tech, ...], ...] -- the tree in columns, roots first."""
    out = {}
    for tech in TREE:
        out.setdefault(depth_of(tech), []).append(tech)
    return [out[d] for d in sorted(out)]


def dependants(tech_id):
    """Everything that waits on this one."""
    return [t for t in TREE if tech_id in t.requires]


def detail(g, tech):
    """Everything worth saying about one node, for either front end."""
    from pclengine.ui import icons
    category = category_of(tech)
    return {
        "id": tech.id,
        "name": tech.name,
        "blurb": tech.blurb,
        "cost": tech.price(g),
        "state": state_of(g, tech),
        "category": category.key,
        "categoryLabel": category.label,
        "colour": category.colour,
        "term": category.term,
        "icon": icons.get(tech.icon).name,
        "glyph": icons.get(tech.icon).glyph,
        "path": icons.get(tech.icon).path,
        "depth": depth_of(tech),
        "act": tech.act,
        "note": tech.note,
        "excludes": [BY_ID[x].name for x in tech.excludes if x in BY_ID],
        "progress": progress(g, tech),
        "fraction": (min(1.0, progress(g, tech) / tech.price(g))
                     if tech.price(g) > 0 else 0.0),
        "eta": (eta(g, tech) if tech.id in getattr(g, "researching", ())
                else None),
        "requires": [{"id": r, "name": BY_ID[r].name,
                      "done": r in g.researched}
                     for r in tech.requires if r in BY_ID],
        "unlocks": list(tech.unlocks),
        "leadsTo": [{"id": t.id, "name": t.name} for t in dependants(tech.id)],
    }


def tree_view(g):
    """The whole tree, in drawing order, with every node's detail."""
    return [[detail(g, tech) for tech in tier] for tier in tiers()]


def bench_state(g):
    """How much of the lab floor is committed, for either front end.

    The number that makes spreading a real decision: two lines open is two
    lines at half speed, and this is where both viewers read that from.
    """
    running = active(g)
    return {
        "used": len(running),
        "total": benches(g),
        "share": share(g),
        "working": [{"id": t.id, "name": t.name,
                     "fraction": (min(1.0, progress(g, t) / t.price(g))
                                  if t.price(g) > 0 else 0.0),
                     "eta": eta(g, t)}
                    for t in running],
    }


# --------------------------------------------------------------------------
# buying
# --------------------------------------------------------------------------
def available(g):
    """Everything you could put on a bench, cheapest first.

    Work in hand comes first, so the list you are steering is at the top.
    """
    out = [t for t in TREE if t.id not in g.researched and t.ready(g)
           and not t.shut_out(g)]
    out.sort(key=lambda t: (t.id not in getattr(g, "researching", ()),
                            t.price(g)))
    return out


def locked(g):
    """Techs whose prerequisites are not met, with what they are waiting on."""
    return [(t, t.missing(g)) for t in TREE
            if t.id not in g.researched and not t.ready(g)]


def buy(g, tech_id):
    """Finish a tech outright, paying for it in banked research.

    Kept for content and the developer tools. The way you research in play
    is `begin`, which puts it on a bench and lets the labs get on with it.
    """
    tech = BY_ID.get(tech_id)
    if tech is None or tech.id in g.researched or not tech.ready(g):
        return False
    if tech.shut_out(g) or not tech.affordable(g):
        return False
    g.research -= tech.price(g)
    if tech.id in g.researching:
        g.researching.remove(tech.id)
    g.research_progress.pop(tech.id, None)
    g.researched.add(tech.id)
    if tech.effect is not None:
        tech.effect(g)
    g.log(f"Researched: {tech.name}")
    for other in tech.excludes:
        if other not in g.researched:
            g.foreclosed_tech.add(other)
    if tech.act:
        g.log(f"{tech.name} opens act {tech.act}. Take the project to go.")
    return True


# --------------------------------------------------------------------------
# labs
# --------------------------------------------------------------------------
#: fn(game) -> the name of the currency labs are paid in right now.
LAB_CURRENCY = []
#: fn(game) -> an extra row for the research panel, or None.
PANEL_ROWS = []


def lab_currency(g):
    """What labs are bought with. Content decides; it may vary by act."""
    from pclengine.core import currency
    if LAB_CURRENCY:
        return LAB_CURRENCY[0](g)
    return currency.ALL[0].name if currency.ALL else ""


def lab_spec(g):
    from pclengine.core import currency
    return currency.BY_NAME.get(lab_currency(g))


def lab_purse(g):
    spec = lab_spec(g)
    return spec.held(g) if spec else 0.0


def lab_price(g):
    from pclengine.core.state import scaled_price
    try:
        base = LAB_COST * math.exp(g.labs * math.log1p(LAB_RATE))
    except OverflowError:
        return float("inf")
    return scaled_price(base, g.hw_scale)


def buy_labs(g, count=1, budget=None):
    first = lab_price(g)
    available_funds = lab_purse(g)
    purse = available_funds if budget is None else min(budget, available_funds)
    if first > purse or first == float("inf"):
        return 0
    if first <= 0:
        bought = int(min(count, 1e9))
        spend = 0.0
    else:
        affordable = math.floor(math.log1p(purse * LAB_RATE / first)
                                / math.log1p(LAB_RATE))
        bought = int(min(count, affordable))
        if bought <= 0:
            return 0
        spend = first * math.expm1(bought * math.log1p(LAB_RATE)) / LAB_RATE
    spec = lab_spec(g)
    if spec is not None:
        spec.spend(g, min(spend, spec.held(g)))
    g.labs += bought
    return bought


def output(g):
    """Research per second. Content may scale this; brand-like effects do."""
    from pclengine.core import modifiers
    return (g.labs * LAB_OUTPUT * g.lab_perf
            * modifiers.of(g, "research_output"))


def tick(g, dt):
    """Labs bank research; open benches spend it.

    A bench can absorb up to a whole lab floor's output per second, so two
    of them burn the bank twice as fast as it fills. That is what makes
    both halves of the decision real: time with nothing open is not wasted,
    it is a war chest, and opening three lines at once spends it in a
    hurry. With one line and no savings it comes to exactly what the labs
    make, which is where most of the game sits.
    """
    g.research += output(g) * dt
    running = active(g)
    if not running:
        return
    budget = output(g) * dt * len(running)
    spend = min(g.research, budget)
    if spend <= 0:
        return
    g.research -= spend
    each = spend / len(running)
    for tech in list(running):
        done = g.research_progress.get(tech.id, 0.0) + each
        g.research_progress[tech.id] = done
        if done >= tech.price(g):
            _finish(g, tech)


# --------------------------------------------------------------------------
# panel
# --------------------------------------------------------------------------
# The number row belongs to the project list, everywhere, so a list on a
# tab is driven with a cursor: UP and DOWN to choose, ENTER to take. Every
# list in the game works this way, which is one thing to learn rather than
# one per panel.
def selected_index(g, options):
    if not options:
        return 0
    return max(0, min(getattr(g, "rnd_sel", 0), len(options) - 1))


def move_selection(g, delta):
    options = available(g)
    if options:
        g.rnd_sel = max(0, min(selected_index(g, options) + delta,
                               len(options) - 1))
    return True


def take_selected(g):
    """ENTER puts the picked tech on a bench, or takes it off one."""
    options = available(g)
    if not options:
        g.log("There is nothing left to research.")
        return True
    tech = options[selected_index(g, options)]
    if tech.id in g.researching:
        stop(g, tech.id)
    elif not begin(g, tech.id):
        if len(active(g)) >= benches(g):
            g.log(f"All {benches(g)} bench(es) are busy. Put one aside, or "
                  f"find a project that adds another.")
        else:
            g.log(f"{tech.name} is not available yet.")
    return True


def research_panel(g):
    from pclengine.core.acts import panel, row
    from pclengine.fmt import money, small
    price = lab_price(g)
    spec = lab_spec(g)
    shown = spec.text(price) if spec else small(price)
    running = active(g)
    rows = [
        row(f"Labs  x{small(g.labs)}", shown, key="r",
            hint="labs make research; research is what unlocks everything"),
        row("output", f"{output(g):,.2f}/s"),
        row("benches", f"{len(running)} of {benches(g)} in use",
            bar=len(running) / max(benches(g), 1),
            hint="each open line gets an equal share, so two at once is "
                 "two at half speed"),
        row("researched", f"{len(g.researched)} of {len(TREE)}"),
    ]
    for build in PANEL_ROWS:
        extra = build(g)
        if extra is not None:
            rows.append(extra)
    techs = []
    options = available(g)
    here = selected_index(g, options)
    for i, tech in enumerate(options[:8]):
        state = state_of(g, tech)
        working = state == "working"
        done = progress(g, tech)
        left = eta(g, tech) if working else None
        mark = "*" if working else (">" if i == here else " ")
        if working:
            value = (f"{left:,.0f}s left" if left is not None
                     else f"{small(done)} / {small(tech.price(g))}")
        else:
            value = small(tech.price(g))
        techs.append(row(f"{mark} {tech.name}", value,
                         bar=(done / max(tech.price(g), 1e-9)) if working
                         else None,
                         hint=tech.blurb + ("  ENTER puts it aside."
                                            if working else
                                            "  ENTER starts work on it."),
                         warn=state == "available"))
    if not techs:
        pending = locked(g)
        if pending:
            tech, missing = pending[0]
            techs.append(row(tech.name, "locked",
                             hint="needs " + ", ".join(missing), warn=True))
        else:
            techs.append(row("everything is researched", "-"))
    return [panel("RESEARCH", rows), panel("TECH", techs)]
