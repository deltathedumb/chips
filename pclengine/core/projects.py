"""The project registry.

A project is data plus two callables: `req` decides when it appears and
`effect` applies it. The engine owns what a project *is* and how one is
bought; which projects exist is content, registered with `api.add_project`.
"""

from pclengine.core import currency as currency_module


class Project:
    """One purchase: a cost, a condition and an effect.

    A project is priced in whatever currencies content registered, so this
    class never names one. `Project(..., data=1750)` works because the cost
    keywords are gathered rather than declared.
    """

    __slots__ = ("id", "title", "desc", "costs", "req", "effect",
                 "repeatable", "hint", "excludes", "scale", "ends_run")

    def __init__(self, pid, title, desc, effect, req=None, repeatable=False,
                 hint=None, excludes=(), scale=None, ends_run=False,
                 **costs):
        self.id = pid
        self.title = title
        self.desc = desc
        self.effect = effect
        self.req = req or (lambda g: True)
        self.repeatable = repeatable
        self.hint = hint
        # Taking this finishes the run rather than advancing it. The bot
        # leaves these alone: an autoplayer measuring how long a game takes
        # should not volunteer to stop playing it.
        self.ends_run = ends_run
        # Taking this project puts these permanently out of reach.
        self.excludes = tuple(excludes)
        self.costs = {name: float(amount) for name, amount in costs.items()
                      if amount}
        # Repeatable projects that get dearer supply their own curve, since
        # how fast is a balance question and balance is content's.
        self.scale = scale

    def unlock_hint(self, g):
        """Plain English for why this is not on the list yet."""
        if self.id in getattr(g, "foreclosed", ()):
            takers = [p.title for p in ALL if self.id in p.excludes
                      and p.id in g.completed]
            return ("ruled out by " + takers[0]) if takers else "ruled out"
        ids = getattr(self.req, "requires", None)
        if ids:
            missing = [BY_ID[i].title for i in ids
                       if i in BY_ID and i not in g.completed]
            if missing:
                return "needs " + ", ".join(missing)
        if callable(self.hint):
            return self.hint(g)
        return self.hint or "not available yet"

    def scaled_cost(self, g):
        """What it costs right now, in registered display order."""
        costs = dict(self.costs)
        if self.scale is not None:
            costs = self.scale(g, costs)
        factor = getattr(g, "cost_scale", 1.0)
        return {name: amount * factor for name, amount in costs.items()}

    def cost_text(self, g):
        costs = self.scaled_cost(g)
        parts = [currency.text(costs[currency.name])
                 for currency in currency_module.ALL
                 if costs.get(currency.name)]
        return " + ".join(parts) if parts else "free"

    def affordable(self, g):
        for name, amount in self.scaled_cost(g).items():
            currency = currency_module.BY_NAME.get(name)
            if currency is None or currency.held(g) < amount:
                return False
        return True

    def price(self, g):
        """One number to sort by: the first currency, then the rest, dearer."""
        costs = self.scaled_cost(g)
        total = 0.0
        for index, currency in enumerate(currency_module.ALL):
            total += costs.get(currency.name, 0.0) * (1.0 if index == 0 else 50.0)
        return total

    def buy(self, g):
        if not self.affordable(g):
            return False
        for name, amount in self.scaled_cost(g).items():
            currency_module.BY_NAME[name].spend(g, amount)
        if not self.repeatable:
            g.completed.add(self.id)
        if not getattr(g, "forks_open", False):
            for other in self.excludes:
                if other not in g.completed:
                    g.foreclosed.add(other)
        self.effect(g)
        g.log(f"Project complete: {self.title}")
        if self.excludes:
            shut = [BY_ID[o].title for o in self.excludes if o in BY_ID]
            g.log("That rules out: " + ", ".join(shut))
        return True


def _grant_bandwidth(n):
    def effect(g):
        g.bandwidth += n
    return effect


def _mult(attr, factor):
    def effect(g):
        setattr(g, attr, getattr(g, attr) * factor)
    return effect


def _add(attr, amount):
    def effect(g):
        setattr(g, attr, getattr(g, attr) + amount)
    return effect


def _expand_system(g):
    """Buffer and threads grow by half, so megabyte buffers stay reachable."""
    g.buffer = int(g.buffer * 1.5) + 10
    g.threads = int(g.threads * 1.5) + 5
    g.bandwidth = g.threads + g.buffer + 10


def _either(*ids):
    """Ready once any one of these is done.

    Downstream projects must not depend on one side of a fork, or taking the
    other side dead-ends the act."""
    def ready(g):
        return any(i in g.completed for i in ids)
    ready.requires = ids
    return ready


def _done(*ids):
    def ready(g):
        return all(i in g.completed for i in ids)
    ready.requires = ids
    return ready


#: Every project content registered.
ALL = []
BY_ID = {}


def available(g):
    """Projects the player can currently see, cheapest first."""
    out = []
    for p in ALL:
        if p.id in g.completed or p.id in getattr(g, "foreclosed", ()):
            continue
        try:
            if p.req(g):
                out.append(p)
        except Exception:
            continue
    out.sort(key=lambda p: (not p.affordable(g), p.price(g)))
    return out
