# Mods

A mod is a package with a `register(api)` function. It can be:

* a single `.py` file in this folder,
* a folder holding an `__init__.py`, or
* an `.mpkg` — an uncompressed zip with one importable package at its root,
  built with `python foundry.py --build-mod path/to/my_mod`.

They are found automatically; turn one on or off from the menu (Mods), which
writes `enabled.json`.

```python
NAME = "My Mod"
DESCRIPTION = "One line, shown in the menu."

def register(api):
    api.edit_project("improved_steppers", data=lambda old: old / 2)
```

## The base game is a mod

`mods/base` is FOUNDRY itself, and it registers through the same `api` your
mod gets — nothing about it is privileged. It is the reference for every
call below, and it is worth reading before writing anything substantial:

    base/constants.py     the numbers the subject matter is measured in
    base/game/            fields, verbs and keys: what a game *is*
    base/acts/            the eleven acts and their dials
    base/trees/           research and projects
    base/bench.py         the benchmark circuit and Brand Recognition
    base/crypt.py         the cipher lab: rigs, algorithms, ciphers
    base/help.py          what `?` says about all of it
    base/warfare.py       who attacks you, and what stops them
    base/strategy.py      how the balance bot plays each act

`--no-mods` starts with the base game and nothing on top of it.

## What `api` gives you

### The game object

| Call | Does |
| --- | --- |
| `api.field(name, default)` | Declare a game field. A callable default is a factory, for a dict or a set |
| `api.method(name, fn)` | Bind a verb or a `property` onto `Game`, so `g.<name>` works |
| `api.system_tick(fn)` | `fn(game, dt)` every tick, whatever act it is |
| `api.end_check(fn)` | Content's own "the run is over" rule |
| `api.constants(module)` | Expose a module's constants to `api.constant` |
| `api.node_ladder(list)` | Register the list `api.add_node` appends to |

### Content

| Call | Does |
| --- | --- |
| `api.add_act(api.Act(...))` | A new act. `panels`/`material` return plain rows, so both front ends render it |
| `api.add_dial(api.Dial(...))` | A 0–10 setting one act asks you to manage |
| `api.add_tech(api.Tech(...))` | A research node. `unlocks=` gates capabilities, `act=` gates an act |
| `api.add_unit(api.Unit(...))` | Something you build to defend yourself |
| `api.add_threat(api.Threat(...))` | Something that comes for you |
| `api.add_upgrade(api.Upgrade(...))` | Something taping out carries into the next run |
| `api.add_currency(api.Currency(name, field, render))` | Something projects can be priced in |
| `api.panel_view(key, label, build, on_key=, shown=, keys=)` | A HUD tab of your own, reached with TAB |
| `api.menu_button(id, after=, before=, **fields)` | Add a button along the top — or edit one that is there: `label=`, `hidden=True`, `screen=`, `action=` |
| `api.remove_menu_button(id)` | Take one away outright |
| `api.key_layer(name, priority, handle, ...)` | A level of the input stack. The engine's own sit at 1000 (overlays), 800 (chrome), 600 (tab), 400 (act), 200 (projects), 100 (system) |
| `api.front_end(name, run, blurb=)` | A way to play that is not the terminal. `--web` finds one this way |
| `api.save_codec(codec, default=True)` | A save format. JSON is built in and always readable; yours can claim the default |
| `api.left_panel(fn)` | A panel down the left of the HUD |
| `api.bite(target, fn)` / `api.pressure_source(...)` | What a threat costs you; pressure that is not an attacker |
| `api.headline(fn)` / `api.era(fn)` | The one number a run is measured in; the title-bar label |
| `api.editor_group(heading, fields)` | How the save editor groups your fields |
| `api.help_section(heading, lines)` | A section of the `?` screen, shown in both front ends |
| `api.modifier(name, fn)` | Scale one of the engine's numbers: `research_output`, `unit_cost` |
| `api.credit_bonus(fn)` | What else a finished run was worth, in mask credits |
| `api.dev_action(action)` | A developer-panel action of your own |
| `api.strategy(act, fn)` | How the balance bot plays that act. `None` is the fallback |
| `api.probe_seed(fn)` | How to stock a game dropped straight into an act, for `--balance` |

### Projects

| Call | Does |
| --- | --- |
| `api.add_project(id, title, desc, effect, after=None, **cost)` | New project. `data=`, `entropy=`, `chips=`, `req=`, `repeatable=`, `hint=`, `excludes=` |
| `api.edit_project(id, **fields)` | Change one. `data=`/`entropy=`/`chips=` accept a callable taking the old value |
| `api.remove_project(id)` | Drop one |
| `api.add_node(id, nm)` | Put a project on the process-node ladder |

### Everything else

| Call | Does |
| --- | --- |
| `api.constant(name, value)` | Overwrite a content constant (`EARTH_MATTER`, `GRAMS_PER_WAFER`, …) |
| `api.on_tick(fn)` / `api.on_new_game(fn)` | Hooks |
| `api.mult(attr, x)` / `api.add(attr, n)` / `api.grant_bandwidth(n)` | Ready-made effects |
| `api.requires("id", ...)` | A `req=` that waits on other projects |
| `api.row(...)` / `api.panel(...)` | Build the plain data a panel is made of |

A mod that raises is caught, skipped, and shown with its error in the menu —
it cannot take the game down with it.

## Front ends and formats

The browser front end used to be part of the engine. It is a mod now, and
it is the clearest example of how far the API reaches:

* `web/` — the **browser front end**. Registers itself with
  `api.front_end`, so `--web` finds it the way the game finds an act. With
  it running there is no terminal UI at all: the process is a headless
  server that prints what a server prints. `--saves client` makes it write
  nothing to disk and hand the save bytes to the browser instead.

## What ships here

* `web/` — the browser front end and headless server
* `multiverse/` — **twenty-four more acts**, in the directory form. The
  serious example: it adds acts, techs, transition projects, fields, help
  and pacing, builds on FOUNDRY's own hardware model, and edits nothing in
  the base game to do it. Roughly four hours on top of FOUNDRY's two.
* `deep_geology.mpkg` — the package form; edits a constant and a project
* `example_research.py` — a research node, and a project gated behind it
* `example_act.py` — a twelfth act, gated behind its own tech. Off by
  default: it collides with the Multiverse, which also numbers an act 12.

## Adding acts

An act needs five things, and `--balance` will tell you if you missed one:

1. `api.add_act(api.Act(...))` with `panels` and `material` returning rows
2. `act.complete` — a way to finish it, or the run stops there
3. `api.add_tech(api.Tech(..., act=N))` — research gates every act
4. `api.add_project(...)` with `req=` — the transition into it
5. `api.pacing(N, low, high)` — how long it ought to take

The bot's late-act fallback buys whatever is in `rigs_for(act)`, so an act
built on FOUNDRY's `Rig` is playable by `--balance` without writing a
strategy for it.

Two things that are easy to get wrong, both learned the hard way:

* **A field built from a constant must be a factory.** `api.field("matter",
  constants.EARTH_MATTER)` freezes the value at import time, before any mod
  has run. Pass `lambda: constants.EARTH_MATTER` instead.
* **Acts that fund themselves are coupled.** Whatever chip float one act
  finishes on bankrolls the next one's opening, so a long act makes the
  next instant and the pacing oscillates. Either clear the float on the way
  in, or price the next act so the carry-over does not matter.
