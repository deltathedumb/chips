"""What a mod is allowed to do.

`ModAPI` is the whole contract. A mod gets one, calls methods on it, and
never imports an engine module directly -- which is what lets the engine be
restructured underneath without breaking every mod on disk.

The base game uses exactly this and nothing more.
"""

from pclengine.core import (acts, currency, modifiers, prestige, projects,
                            research, state, war)
from pclengine.dev import autoplay

#: Whatever content registered as its process-node ladder, so add_node has
#: somewhere to put a node without the engine knowing what one is.
NODE_LADDER = []
#: fn(game) -> (label, value): the one number a run is measured in.
HEADLINE = []
#: fn(game) -> a short label for the title bar, like a process node.
ERA = []
#: [(heading, [field, ...])], how the save editor groups a game's fields.
EDITOR_GROUPS = []
#: [(heading, [line, ...])] for the in-game help, in the order shown.
HELP_SECTIONS = []
#: Modules whose constants a mod may reach with api.constant.
CONSTANT_HOSTS = {}

#: Constants a mod overwrote, with what they were, so a reset can undo them.
_CONSTANTS = {}
TICK_HOOKS = []
NEW_GAME_HOOKS = []


class ModAPI:
    """Everything a mod is allowed to touch."""

    def __init__(self, mod_name):
        self.mod_name = mod_name
        # Handy re-exports so a mod does not have to reach into internals.
        self.Project = projects.Project
        self.mult = projects._mult
        self.add = projects._add
        self.grant_bandwidth = projects._grant_bandwidth
        self.requires = projects._done
        self.state = state
        self.Act = acts.Act
        self.Dial = acts.Dial
        self.Tech = research.Tech
        self.Unit = war.Unit
        self.Threat = war.Threat
        self.Upgrade = prestige.Upgrade
        self.Currency = currency.Currency
        self.row = acts.row
        self.panel = acts.panel

    # -- the game object -----------------------------------------------
    def field(self, name, default):
        """Declare a game field and what a new game starts it at."""
        state.field(name, default)

    def method(self, name, fn):
        """Bind a verb or a property onto Game, so g.<name> works."""
        return state.method(name, fn)

    def system_tick(self, fn):
        """Run fn(game, dt) every tick, whatever act the game is in."""
        state.SYSTEM_TICKS.append(fn)
        return fn

    def end_check(self, fn):
        """Content's own rule for when the run is over."""
        state.END_CHECKS.append(fn)
        return fn

    def headline(self, fn):
        """The one number a run is measured in: fn(game) -> (label, value)."""
        del HEADLINE[:]
        HEADLINE.append(fn)
        return fn

    def era(self, fn):
        """A short label for the title bar: fn(game) -> text."""
        del ERA[:]
        ERA.append(fn)
        return fn

    def help_section(self, heading, lines):
        """One section of the `?` screen, in the order it should be read."""
        HELP_SECTIONS.append((heading, list(lines)))

    def editor_group(self, heading, fields):
        """One group of fields in the save editor, in the order shown."""
        EDITOR_GROUPS.append((heading, list(fields)))

    def node_ladder(self, ladder):
        """Register the list add_node appends to."""
        NODE_LADDER[:] = [ladder]
        return ladder

    def constants(self, module):
        """Expose a module's constants to api.constant."""
        CONSTANT_HOSTS[module.__name__.rsplit(".", 1)[-1]] = module
        return module

    # -- content registries --------------------------------------------
    def modifier(self, name, fn):
        """Scale one of the engine's numbers: fn(game) -> a multiplier.

        Known names: `research_output`, `unit_cost`. Several mods may scale
        the same number; they multiply together.
        """
        return modifiers.add(name, fn)

    def credit_bonus(self, fn):
        """What else a finished run was worth: fn(game) -> mask credits."""
        return prestige.add_credit_bonus(fn)

    def menu_button(self, button_id, after=None, before=None, **fields):
        """Add, edit or hide one of the buttons along the top.

        An id that is already there is edited rather than duplicated, so
        `api.menu_button("saves", hidden=True)` removes one and
        `api.menu_button("help", label="Manual")` renames one.
        """
        from pclengine.ui import menubar
        return menubar.add(button_id, after, before, **fields)

    def remove_menu_button(self, button_id):
        from pclengine.ui import menubar
        return menubar.remove(button_id)

    def front_end(self, name, run, blurb=""):
        """A way to play that is not the terminal. See `pclengine.frontends`."""
        from pclengine import frontends
        return frontends.add(name, run, blurb)

    def save_codec(self, codec, default=True):
        """A save format of your own. See `pclengine.store.codecs`."""
        from pclengine.store import codecs
        return codecs.add(codec, default)

    def add_currency(self, spec):
        """Something a project can be priced in. Order is display order."""
        return currency.add(spec)

    def add_act(self, act):
        return acts.register(act)

    def add_dial(self, dial):
        return acts.add_dial(dial)

    def add_tech(self, tech):
        return research.add_tech(tech)

    def tech_category(self, key, label, colour="#8a8a8a", term="dim"):
        """A branch of the tech tree, and what colour it is drawn in."""
        return research.add_category(
            research.Category(key, label, colour, term))

    def add_unit(self, unit):
        return war.add_unit(unit)

    def add_threat(self, threat):
        return war.add_threat(threat)

    def lab_currency(self, fn):
        """What labs are bought with: fn(game) -> a currency name."""
        del research.LAB_CURRENCY[:]
        research.LAB_CURRENCY.append(fn)
        return fn

    def key_layer(self, name, priority, handle, active=None, binds=None,
                  footer=None, exclusive=False):
        """A level of the input stack of your own.

        Higher priority sees a key first. The engine's own layers sit at
        1000 (overlays), 800 (chrome), 600 (the HUD tab), 400 (the act),
        200 (projects) and 100 (etch and bandwidth).
        """
        from pclengine.ui import keymap
        return keymap.add_layer(keymap.Layer(name, priority, handle, active,
                                             binds, footer, exclusive))

    def panel_view(self, key, label, build, on_key=None, shown=None,
                   keys=""):
        """A HUD tab of your own: TAB reaches it like any other.

        `build(game)` returns panels, `on_key(game, key)` returns True when
        it has taken a keypress, and `shown(game)` hides the tab until the
        game has something to put in it.
        """
        from pclengine.ui import panels
        return panels.add_view(
            panels.View(key, label, build, on_key, shown, keys))

    def left_panel(self, fn):
        """A panel down the left of the HUD: fn(game) -> panel or None."""
        from pclengine.ui import panels
        return panels.add_left_panel(fn)

    def research_row(self, fn):
        """An extra row on the research panel: fn(game) -> row or None."""
        research.PANEL_ROWS.append(fn)
        return fn

    def bite(self, target, fn):
        """What a threat getting past your force actually costs you."""
        return war.add_bite(target, fn)

    def pressure_source(self, name, amount, relieve=None, render=None):
        """Pressure nobody is applying on purpose. See `war.PressureSource`."""
        return war.add_pressure_source(
            war.PressureSource(name, amount, relieve, render))

    def add_upgrade(self, upgrade):
        return prestige.add_upgrade(upgrade)

    def dev_action(self, action):
        """A developer-panel action, for content only this mod understands."""
        from pclengine.dev import tools
        return tools.add_action(action)

    def pacing(self, number, low_minutes, high_minutes):
        """How long act `number` ought to take, for `--balance` to judge."""
        from pclengine.dev import balance
        balance.set_pacing(number, low_minutes, high_minutes)

    def probe_seed(self, fn):
        """How to stock a game dropped straight into an act, for --balance."""
        from pclengine.dev import balance
        return balance.seed_probe(fn)

    def progress_metric(self, fn):
        """Declare a number that ought to climb while the run is alive.

        If every declared metric holds still long enough, the engine calls
        the run stuck and asks for a rescue offer. Name the quantities that
        mean production, not every number that happens to move.
        """
        from pclengine.core import rescue
        rescue.add_metric(fn)

    def rescue_offer(self, fn):
        """Register `fn(g) -> rescue.Offer or None`, a way out of a corner.

        Returning None means "they are idle, not stuck", and no popup is
        shown -- so a game can decline to rescue states it considers fair.
        """
        from pclengine.core import rescue
        rescue.add_offer(fn)

    def strategy(self, act, fn):
        """How the balance bot plays an act. None is the fallback."""
        return autoplay.add_strategy(act, fn)

    def add_project_object(self, project):
        projects.ALL.append(project)
        projects.BY_ID[project.id] = project
        return project

    # -- projects ------------------------------------------------------
    def add_project(self, pid, title, desc, effect, after=None, **kwargs):
        if pid in projects.BY_ID:
            raise ValueError(f"project id already exists: {pid}")
        project = projects.Project(pid, title, desc, effect, **kwargs)
        if after and after in projects.BY_ID:
            index = projects.ALL.index(projects.BY_ID[after]) + 1
            projects.ALL.insert(index, project)
        else:
            projects.ALL.append(project)
        projects.BY_ID[pid] = project
        return project

    def edit_project(self, pid, **fields):
        """Set fields on an existing project. A callable takes the old value."""
        project = projects.BY_ID.get(pid)
        if project is None:
            raise KeyError(f"no such project: {pid}")
        for name, value in fields.items():
            if name in project.costs or name in currency.BY_NAME:
                old = project.costs.get(name, 0.0)
                project.costs[name] = value(old) if callable(value) else value
            elif hasattr(project, name):
                setattr(project, name, value)
            else:
                raise AttributeError(f"projects have no field {name!r}")
        return project

    def remove_project(self, pid):
        project = projects.BY_ID.pop(pid, None)
        if project is not None and project in projects.ALL:
            projects.ALL.remove(project)
        return project

    def add_node(self, pid, nanometres):
        """Put a project on the process-node ladder, if content has one."""
        if not NODE_LADDER:
            raise LookupError("no content has registered a node ladder")
        ladder = NODE_LADDER[0]
        ladder.append((pid, float(nanometres)))
        ladder.sort(key=lambda entry: -entry[1])

    # -- constants and hooks -------------------------------------------
    def constant(self, name, value):
        """Overwrite a content constant, remembering what it was."""
        for key, module in CONSTANT_HOSTS.items():
            if hasattr(module, name):
                _CONSTANTS.setdefault((key, name), getattr(module, name))
                setattr(module, name, value)
                return
        raise AttributeError(f"no loaded content has a constant {name!r}")

    def on_tick(self, fn):
        TICK_HOOKS.append(fn)
        return fn

    def on_new_game(self, fn):
        NEW_GAME_HOOKS.append(fn)
        return fn
