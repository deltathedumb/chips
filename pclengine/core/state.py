"""The run, and nothing about what the run is made of.

`Game` owns what every paperclip-shaped game has: which act you are in, how
long it has gone on, what you have completed and researched, and the tick
that drives the act registry, the war model and the research tree. It owns
no silicon. Wafers, steppers, star lifters and the rest arrive from content
through `api.field` and `api.method`, so the engine can carry a game about
something else entirely without being edited.

    FIELDS   name -> default value (or a factory, for a dict or a set)
    METHODS  name -> function bound onto Game, so `g.chip_rate()` works
"""

import random

#: Content's starting values, applied to every new Game in order.
FIELDS = {}
#: Names of everything content bound onto Game, so it can be unbound again.
_CONTENT_METHODS = []
#: Content's own rule for "the run is over", checked in the last act.
END_CHECKS = []
#: Per-tick systems content wants run in every act, like a data buffer.
SYSTEM_TICKS = []
#: Filled in by `mods`, so `tick` can call mod hooks without importing it.
_MOD_TICK = []


def field(name, default):
    """Declare a game field and what it starts at."""
    FIELDS[name] = default


def method(name, fn):
    """Bind a function onto Game, so content can add verbs and properties.

    A plain function becomes a method and a `property` becomes a property,
    which is how content gets `g.buy_stepper()` and `g.node` alike without
    the engine knowing either exists.
    """
    setattr(Game, name, fn)
    _CONTENT_METHODS.append(name)
    return fn


def reset():
    """Forget every content field, method, system and end rule."""
    for name in _CONTENT_METHODS:
        if name in vars(Game):
            delattr(Game, name)
    del _CONTENT_METHODS[:]
    FIELDS.clear()
    del END_CHECKS[:]
    del SYSTEM_TICKS[:]


def scaled_price(base, scale):
    """Apply a price multiplier without ever producing a nan.

    `inf * 0` is nan, which is not a price and crashes every formatter that
    meets it. A zero multiplier means free, whatever the base was, and an
    overflowed base stays unaffordable.
    """
    if scale <= 0:
        return 0.0
    if base != base or base == float("inf"):
        return float("inf")
    result = base * scale
    return float("inf") if result != result else result


class Game:
    """Everything the simulation needs. Plain attributes so saving is trivial."""

    def __init__(self, mode="standard", seed=None):
        self.act = 1
        # A run has its own randomness. Anything in the game that wanders --
        # a spot price, a raid -- draws from here rather than the global
        # generator, so the same seed plays out the same way and the balance
        # harness is comparing step sizes rather than luck.
        self.seed = random.randrange(1 << 30) if seed is None else int(seed)
        self.rng = random.Random(self.seed)
        self.mode = mode
        # Run multipliers; runconfig.Setup.apply overwrites these.
        self.time_scale = 1.0
        self.cost_scale = 1.0
        self.hw_scale = 1.0
        # How fast things happen *to* you, measured against real time rather
        # than game time -- so a faster clock shortens the run instead of
        # making the world proportionally more dangerous.
        self.event_scale = 1.0
        self.elapsed = 0.0
        self.batch = 1
        self.hud_width = None     # None = fill the terminal
        self.panel_view = "ops"   # ops | war | research | content's own
        self.help_page = 0        # which page of `?` you are reading
        self.overlay = None       # None, or a full-body screen like "tech"
        self.tech_sel = 0         # where you are in the tech tree
        self.rnd_sel = 0          # where you are in the R&D list
        self.war_sel = 0          # where you are in the defender list
        self.messages = []
        self.finished = False
        self.completed = set()
        # Projects shut out by an exclusive choice you already made.
        self.foreclosed = set()
        # Research is the spine: every capability and every act is behind
        # a tech in the tree content registered.
        self.researched = set()
        # (act, elapsed when you entered it), for the run summary.
        self.act_log = [(1, 0.0)]
        # Carried between runs by taping out.
        self.mask_credits = 0.0
        self.legacy = {}
        self.generation = 0
        self.forks_open = False   # a legacy upgrade opens both sides

        # --- the research line ---------------------------------------------
        self.labs = 0.0
        self.research = 0.0
        self.research_spent = 0.0
        # What the labs are working on, and how far along each is. A tech
        # is started rather than bought: the deciding is in what to open,
        # and how many at once.
        self.researching = []
        self.research_progress = {}
        self.foreclosed_tech = set()
        self.benches = 1
        self.lab_perf = 1.0

        # --- warfare, present in every act ---------------------------------
        self.forces = {}               # unit key -> how many you own
        self.pressure = {}             # threat key -> accumulated pressure
        self.war_force = 0.0
        self.war_pressure = 0.0
        self.war_yield_penalty = 0.0   # fraction knocked off production
        self.war_order_penalty = 0.0   # fraction knocked off demand
        self.units_lost = 0.0
        self.matter_ceded = 0.0
        self.threats_repelled = 0.0
        self.force_mult = 1.0
        self.recklessness = 1.0        # some choices make threats grow faster
        # Losing ground for long enough ends the run. Integrity falls while
        # pressure exceeds your force and recovers while it does not.
        self.integrity = 1.0
        self.defeated = False
        self.lowest_integrity = 1.0
        self.war_grace = 0.0     # pressure below this cannot bite yet
        # One dial per act that needs a verb of its own.
        self.dials = {}

        # --- whatever the content is about ---------------------------------
        self.made_rate = 0.0
        for name, default in FIELDS.items():
            setattr(self, name, default() if callable(default) else default)

    # -- messaging ---------------------------------------------------------
    def log(self, text):
        if self.messages and self.messages[-1] == text:
            return
        self.messages.append(text)
        del self.messages[:-40]

    def can(self, capability):
        """Has the tech that unlocks this capability been researched?"""
        from pclengine.core import research
        return research.has(self, capability)

    # -- the clock ---------------------------------------------------------
    def tick(self, dt):
        from pclengine.core import acts, research, war
        dt *= getattr(self, "time_scale", 1.0)
        self.elapsed += dt
        self.made_rate = 0.0

        if not self.act_log or self.act_log[-1][0] != self.act:
            self.act_log.append((self.act, self.elapsed))
        acts.get(self.act).run(self, dt)

        # Systems that run in every act, whatever the act is doing.
        war.tick(self, dt)
        research.tick(self, dt)
        for hook in SYSTEM_TICKS:
            hook(self, dt)
        if _MOD_TICK:
            _MOD_TICK[0](self, dt)

        if self.defeated:
            self.finished = True
            return
        if not self.finished and acts.ALL and self.act >= acts.last_number():
            self._check_finished(acts.get(self.act))

    def _check_finished(self, act):
        """The last act decides. Its own rule wins; otherwise content's."""
        done = getattr(act, "complete", None)
        if done is not None:
            if done(self):
                self.finished = True
        elif END_CHECKS and all(check(self) for check in END_CHECKS):
            self.finished = True
