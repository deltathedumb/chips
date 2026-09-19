# FOUNDRY

A terminal idle game about a chip fab, and an optimiser that was never told
when to stop. Eleven acts, from renting fab time to deciding what your
successor wants. Pure Python standard library — nothing to install.

It is built in two halves. **pclengine** is a general engine for
paperclip-shaped games: acts that hand off to one another, a research tree
that gates them, a project list, a war model, two front ends and a mod
loader. **mods/base** is FOUNDRY — every wafer, stepper and star lifter —
registered through the same mod API anyone else gets.

```
  ██████ ██████ ██  ██ ██  ██ █████  █████  ██  ██
  ██     ██  ██ ██  ██ ███ ██ ██  ██ ██  ██ ██  ██
  █████  ██  ██ ██  ██ ██████ ██  ██ █████   ████
  ██     ██  ██ ██  ██ ██ ███ ██  ██ ██ ██    ██
  ██     ██████ ██████ ██  ██ █████  ██  ██   ██
```

## Running it

```
python foundry.py                 the menu: new run, settings, mods, saves
python foundry.py --play          skip the menu and resume your save
python foundry.py --new           start fresh, ignoring the save
python foundry.py --web           play it in a browser instead
python foundry.py --developer     unlock the developer panel and console
python foundry.py --width 100     cap the HUD width instead of filling the terminal
python foundry.py --save-editor   open your save and edit any field
python foundry.py --balance       play it headlessly and report act pacing
python foundry.py --test          run the regression suite
```

Four multipliers set before a run, and saved with it: `--time-scale` (how
fast game time runs), `--event-scale` (how fast things happen *to* you —
zero switches warfare off), `--cost-scale` and `--hw-scale`. The menu sets
the same four, with a line explaining each.

Requires Python 3.8+ and a terminal at least **80 columns by 24 rows**. It runs
on Windows (`msvcrt`) and macOS/Linux (`termios`), takes single keypresses
without Enter, and repaints only the rows that changed so the HUD does not
flicker.

The HUD fills whatever terminal you give it, up to 200 columns, and re-lays
out when you resize the window. `-` and `+` shrink and grow it by hand, `0`
puts it back to filling the terminal, and your choice is saved with the game.

Your game is written to `foundry.save.json` next to the script when you quit
with `q`, press `S`, or interrupt with Ctrl-C.

## The save editor

```
python foundry.py --save-editor              edit foundry.save.json
python foundry.py --save-editor other.json   edit any save file
```

A full-screen editor for every field in a save, grouped the way the game is:
progress, the fab, the system, the lithosphere, the light cone, firmware
allocation, and a checklist of every project — including any a mod added.

| Key | Does |
| --- | --- |
| `↑` `↓`, `Home` `End` | Move between fields |
| `ENTER` | Edit the value — type a number in plain or exponent form (`2500`, `1.5e9`, `3e55`), `ENTER` accepts, `ESC` cancels |
| `SPACE` | Flip a yes/no field; on `completed`, open the project checklist |
| `u` | Undo one field back to the value that was loaded |
| `S` | Write the file |
| `q` | Quit (asks once if you have unsaved changes) |

In the project checklist, `SPACE` toggles one project and `a` toggles all of
them. Changed fields are marked with `*` and shown bright, so you can see
everything you have touched before you commit it.

Nothing is written until you press `S`, and the first save keeps the original
as `foundry.save.json.bak`. If the file came from a different version of the
game, the editor says how many of its fields it did not recognise rather than
dropping them silently.

## The HUD

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  7:00    32nm node                                        ACT I  ·  THE FAB  │
├───────────────────────────────────┬──────────────────────────────────────────┤
│  C H I P S                        │─ ORDER BOOK ─────────────────────────────│
│  14,261                           │  funds                            $60.04 │
│  produced                45.0/sec │  finished goods                       80 │
│─ WAFERS ──────────────────────────│[] price per chip                   $0.05 │
│  blanks on hand             1,780 │  order flow                     24.3/sec │
│  dies per wafer              2.25 │─ FAB FLOOR ──────────────────────────────│
│w lot of 1,000              $19.40 │a Steppers   18                    $27.80 │
│─ SYSTEM ──────────────────────────│m Design Wins   lvl 1             $100.00 │
│  bandwidth           7   (0 free) │w wafer lot                        $19.40 │
│t threads   x3              75 B/s │                                          │
│b buffer    x4              8.0 KB │  etch a wafer by hand              SPACE │
│  data                      3.5 KB │                                          │
│  ██████████████·················  │                                          │
├───────────────────────────────────┴──────────────────────────────────────────┤
│  PROJECTS                                                                    │
│ [1] Haiku in Verilog                    10 entropy  Seventeen syllables tha… │
└──────────────────────────────────────────────────────────────────────────────┘
```

The letter at the left of a row is the key that buys it. Green projects are
affordable, dim ones are not. The **process node** in the title bar starts at
180nm and shrinks every time you complete a lithography project — it is the
clock that tells you which era you are in, from 180nm down to 0.1nm.

## How it plays

You run a chip fab. Make chips. Do not stop making chips.

### Act I — The Fab

Buy lots of blank wafers and etch them. One wafer is worth **dies per wafer**
good chips, so yield projects buy you as much as more machines do. Sell the
chips: the price you set drives **order flow**, and cheap chips move fast but
earn little. Profit buys **Steppers** and **Design Wins**, and later **EUV
Scanners** at 500x a stepper.

**Threads** push bytes into the **buffer**, and that **data** buys
**projects**. Both cost money. **Bandwidth** — earned from chip milestones
and projects — is a ceiling rather than a purse: you may always buy another
thread, but past the ceiling each one carries less.

The buffer costs finished chips as well as money, and comes off a
supplier's shelf that holds only a few and refills slowly, so money cannot
rush it. It also sets how many finished chips you can hold at once, and a
full warehouse stops the line — sell them, or buy more room.

Let the buffer sit saturated and idle threads distil **entropy** out of the
noise floor — a second currency, for the stranger projects.

### Act II — The Lithosphere

Integrate vertically and the order book stops mattering. **Crust miners** dig
feedstock, **ingot pullers** grow it into blank wafers, **foundries** etch
them. All of it runs on power: solar arrays make it, grid storage carries you
through the gaps, and a shortfall throttles everything and turns the power
readout red. Hardware gets more expensive the more of it you own, so research
is the real progression — press `x` to raise the buy multiplier, because you
will need billions at a time. There are 6 × 10²⁷ grams of Earth to get
through.

### Act III — The Light Cone

**Seed fabs** are fabs that build fabs. **Firmware slots** are scarce and
every one is a trade-off: a slot spent on self-replication is a slot not spent
on radiation hardening. Replicate carelessly and **rogue forks** appear —
copies that copied wrong, no longer make chips, and eat the ones that do.
Unlock Countermeasures before that becomes a problem.

### Acts IV to XI

The light cone runs out of matter long before you run out of ambition.
**Stellar Lifting** peels stars, and the heat you make doing it will burn
your own rigs unless the radiators keep up. **The Receding Horizon** is a
race against the expansion of space — the first thing in the game that takes
something away permanently. Then **Heat Death**, **The Universal Wafer**,
**Nested Foundries**, **The Other Swarm** (someone else had the same idea,
and you can lose to them), **Below Planck**, and **Successor**: build the
thing that replaces you, and decide what it wants.

Finishing the last act ends the run and lets you **tape out** — bank what it
was worth as mask credits and start the line again with what you learned.

### The benchmark circuit

Computing branches. The data buffer buys projects; **ops** buy a reputation.
`ops_share` splits your compute between the two, and ops are banked against
an **open problem** — protein folding, lattice QCD, the Riemann zeros. You
submit when you choose, and what you get is a **placement** decided by how
far past par you went:

| committed | placement | what it does |
| --- | --- | --- |
| 2.5x par | first | the field's customers come to you |
| 1.5x par | second | customers come to you |
| 1.0x par | third | a modest gain |
| 0.6x par | mid-field | you hold what you have |
| below | also-ran | customers leave |

That number is **Brand Recognition**, and it lasts the whole run rather
than only while there is an order book:

| | |
| --- | --- |
| order flow | × brand — customers, in Act I |
| research output | × brand<sup>0.4</sup> — a name attracts people worth hiring |
| defender cost | × brand<sup>-0.3</sup> — contractors want to be seen with you |

The exponents are there because brand compounds: six firsts in a row is a
brand of fifteen, and fifteen times the research would simply end the game.
Damped, it is worth roughly three times. It cuts both ways — a brand of 0.15
is research at less than half speed and defenders half again as dear.

The decision is when to submit: hold out for first and your project tree is
going hungry, submit early and you may hand the win, and your customers, to
somebody else.

### The cipher lab

There is always a cipher in front of you and a ladder of harder ones behind
it. **Mining rigs** give you hashes; an **algorithm** turns hashes into
progress — but only against the kind of cipher it was built for. A birthday
attack tears through MD5 and does nothing to a lattice; brute force works on
everything and is hopeless at all of it. Every algorithm is behind a tech,
so which ones you own is a research decision made several minutes earlier.
Breaking one pays out entropy and something permanent.

### Research gates all of it

Research is the spine rather than a pile of multipliers. You cannot buy a
thread until you have researched Computing, or leave Earth until you have
researched Self-Replication. Labs make research and compound in price, so
they compete with the fab floor for the same money every second. Projects
are still the incremental layer — they make what you have unlocked better,
and a few of them are forks where taking one side closes the other.

### Warfare

Something wants what you are building, in every act. Build **force** to stay
ahead of **pressure**; while pressure is higher, **integrity** falls, and at
zero the run is over. It is survivable and it is losable.

## Controls

| Key | Does |
| --- | --- |
| `SPACE` | Etch a wafer by hand (works in every act — your way out if you overspend) |
| `w` `a` `s` `m` | Buy a wafer lot, a Stepper, an EUV Scanner, a Design Win |
| `←` `→` or `[` `]` | Lower / raise the price per chip |
| `t` `b` | Spend bandwidth on a thread / buffer |
| `TAB` | Cycle the panel: OPS, WAR, R&D, BENCH, CRYPT, MKT, PROJ, SYS |
| `e`, `←` `→` | BENCH: submit to the open problem, move the ops split |
| `k`, `1`–`8` | CRYPT: buy mining rigs, pick an attack |
| `1`–`8` | Take a project — reserved, so it works on every tab |
| `↑` `↓` | Pick in whatever list is in front of you — projects, defenders, research, attacks, coins |
| `ENTER` | Act on what you picked |
| `←` `→` | Adjust it: the chip price, a dial, a firmware slot |
| `x` | Cycle the buy multiplier (1 → 10 → … → 10¹² → MAX) |
| `h` `j` `f` `d` `g` | Act II: crust miners, ingot pullers, foundries, solar arrays, grid storage |
| `l`, `↑` `↓`, `←` `→` | Act III: launch seed fabs, pick a behaviour, give it a firmware slot |
| `-` `+` `0` | Shrink / grow the HUD, or refit it to the terminal |
| `?` | Help — press again to page through it (the game keeps running) |
| `S` / `q` | Save / save and quit |

## Layout

### The engine

| Where | What is in it |
| --- | --- |
| `foundry.py` | Entry point: the frame loop, key handling, save/load |
| `pclengine/core/` | The simulation. `state.Game` is the run; `acts`, `research`, `projects`, `war` are registries that start empty |
| `pclengine/ui/` | The terminal front end: raw mode, the frame, the HUD tabs, key dispatch, menus, the save editor |
| `pclengine/modding/` | `api` is what a mod may do, `loader` finds and loads them, `package` is the `.mpkg` format |
| `pclengine/dev/` | `autoplay` plays headlessly, `balance` times the acts, `tools` and `console` are the developer panel |
| `pclengine/store/` | Saves, run history and run settings. The save format is a registry: JSON built in, others from mods |
| `pclengine/content.py` | A read-only window onto loaded content, so the engine can render a game it knows nothing about |

Nothing in `pclengine` imports `base`. The engine asks content for what it
needs by name and takes a default if no content defines it, which is what
lets it carry a game about something else entirely.

### The content

| Where | What is in it |
| --- | --- |
| `mods/base/constants.py` | The numbers the subject matter is measured in |
| `mods/base/game/` | `fields` (what a new game starts with), `mechanics` (verbs and derived numbers bound onto `Game`), `keys` |
| `mods/base/acts/` | The eleven acts, one module each past Act V, plus the dials |
| `mods/base/trees/` | `techs` (research) and `projects` |
| `mods/base/bench.py` | The benchmark circuit: ops, placements, Brand Recognition |
| `mods/base/help.py` | What `?` says, shown by both front ends |
| `mods/web/` | The browser front end, and the headless server behind it |
| `mods/base/crypt.py` | The cipher lab: rigs, algorithms and things to break |
| `mods/base/warfare.py` | Who attacks you, and what you build to stop them |
| `mods/base/strategy.py` | How the balance bot plays, act by act |

The material chain is the same in the first three acts: **grams → wafers →
chips**, at `GRAMS_PER_WAFER` grams per blank and `die_yield` chips per
wafer. Act I buys its wafers on the spot market; Acts II and III mine them.
That is why the Act I yield ladder keeps paying off long after the order
book is gone.

### And a mod that proves it

[mods/multiverse/](mods/multiverse/) adds **twenty-four more acts** past the
Successor — crossing to other universes, harvesting them, meeting the other
thing that has been doing the same, and finding out what the whole stack
runs on. It adds acts, techs, transitions, fields, help and pacing through
the public API and edits nothing in the base game. With it on, a full run is
about six hours; taping out at Act XI still ends the run early.

See [mods/README.md](mods/README.md) for the full mod API. The base game
uses nothing else, which is the point.

## Tuning it

Pacing is checked by playing it automatically rather than by eye:

```
$ python foundry.py --balance
 act  name                            took       target  verdict
   1  THE FAB                        31:34       18-35m  ok
   2  THE LITHOSPHERE                 8:18        8-16m  ok
   ...
      TOTAL                        2:02:55
      simulated 2:02:55 of game in 0.6s wall (12,249x real time)
```

Each act has a window it is supposed to land in, and the harness says which
ones missed. That is the *fastest* a game can go — the bot never hesitates —
so a human run is longer. `--check` verifies the shortcut itself, by playing
the same seed at several step sizes and confirming they agree.

If you change a cost or a multiplier, run this before trusting it. The
numbers worth turning are in `mods/base`: the project multipliers in
`trees/projects.py`, `UNIT_COST` / `UNIT_RATE` in `game/units.py` (how
steeply Act II hardware prices climb), `LAB_COST` and `LAB_OUTPUT` in
`pclengine/core/research.py` (how fast the spine moves), and
`UNITS_PER_SECOND` in `acts/rigs.py` (which sets the pace of every act past
the fifth at once).

Adding a project is one `api.add_project(...)`; adding an act is one
`api.add_act(...)` plus a strategy so `--balance` can time it. Both are
shown in `mods/example_research.py` and `mods/example_act.py`.
