"""Noticing that a run cannot move, and offering a way out.

An idle game can be spent into a corner: buy the wrong thing with the last
of the purse and there is no action left that earns anything, so no action
left that could buy the thing that earns. Nothing crashes. The clock runs
and every number stays exactly where it is.

The engine cannot tell on its own -- "is the player making progress" is a
claim about a particular game -- so content declares what counts:

    api.progress_metric(lambda g: g.chips)      # this should go up
    api.rescue_offer(builder)                   # what to do when it doesn't

A metric is deliberately not "any number at all". Research keeps ticking up
in a fab with no power, and reading that as progress would be how the check
misses the one state it exists to catch. Content names the quantities whose
standing still means the run is over.

The watchdog is a stopwatch, not a predicate: rather than enumerate the
ways a game can deadlock, it waits for every declared metric to hold still
for `PATIENCE` game-seconds and takes that as its answer. That generalises
to acts nobody has written yet.
"""

#: fn(g) -> float. Something that ought to climb while the game is alive.
METRICS = []
#: fn(g) -> Offer or None. What a bailout would consist of, if one applies.
OFFERS = []

#: Game-seconds every metric must hold still before the run is called stuck.
#: Long enough that a slow patch is not mistaken for a dead one -- a fab
#: waiting on one last expensive wafer is not softlocked, it is just poor.
PATIENCE = 120.0


class Offer:
    """A way out of a corner, and what taking it costs.

    Content builds these, so the terms are the game's to set: the engine
    only promises to show it and to call `accept` if the player says yes.
    """

    __slots__ = ("headline", "terms", "accept", "detail")

    def __init__(self, headline, terms, accept, detail=()):
        #: One line naming what has gone wrong.
        self.headline = headline
        #: One line naming the price of getting out.
        self.terms = terms
        #: fn(g) -> None. Applies the bailout.
        self.accept = accept
        #: Extra lines of explanation, shown above the terms.
        self.detail = tuple(detail)


def add_metric(fn):
    METRICS.append(fn)


def add_offer(fn):
    OFFERS.append(fn)


def reset():
    del METRICS[:], OFFERS[:]


def sample(g):
    """The declared metrics, rounded so float noise is not movement.

    A list rather than a tuple because this is saved: JSON has one kind of
    sequence, and a mark that comes back as a different type to the one it
    went out as would read as movement on the first tick after a load.
    """
    out = []
    for fn in METRICS:
        try:
            value = float(fn(g))
        except Exception:                             # noqa: BLE001
            continue
        # A metric that has gone non-finite is broken, not moving.
        out.append(round(value, 6) if value == value else 0.0)
    return out


def watch(g, dt):
    """Run the stopwatch. Called once per tick, before anything asks."""
    if not METRICS:
        return
    now = sample(g)
    if now != getattr(g, "rescue_mark", None):
        g.rescue_mark = now
        g.rescue_still = 0.0
    else:
        g.rescue_still = getattr(g, "rescue_still", 0.0) + dt


def stalled(g):
    """True once nothing content cares about has moved for long enough."""
    return bool(METRICS) and getattr(g, "rescue_still", 0.0) >= PATIENCE


def offer(g):
    """The first bailout that applies, or None.

    An offer that declines to build itself is content saying "they are not
    actually stuck, they are only idle" -- waiting with the line switched
    off is not a softlock, and should not be interrupted by a bank.
    """
    for build in OFFERS:
        try:
            made = build(g)
        except Exception:                             # noqa: BLE001
            continue
        if made is not None:
            return made
    return None


def softlocked(g):
    """Stuck, and there is something we could do about it."""
    if g.finished or not stalled(g):
        return False
    return offer(g) is not None


def accept(g):
    """Take the offer on the table. Returns True if anything happened."""
    made = offer(g)
    if made is None:
        return False
    made.accept(g)
    # The stopwatch has to start over or the popup returns on the next
    # tick, before the bailout has had a chance to move anything.
    g.rescue_mark = None
    g.rescue_still = 0.0
    g.rescue_taken = getattr(g, "rescue_taken", 0) + 1
    return True
