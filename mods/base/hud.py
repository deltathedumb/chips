"""What FOUNDRY shows down the left-hand side of the HUD, and on the SYS tab.

The left column is the chip counter, whatever the act is working with, and
the ORDER BOOK -- the numbers you are actually steering in Act I, which is
where you spend the longest.

SYS is the machine you run on. PROJ is what its buffer buys, on its own
tab, because the number row is reserved for it everywhere: 1-8 takes a
project whichever screen you are looking at, so the list does not have to
share a panel with anything to stay usable.

Integrity stays on the main HUD wherever the rest of it goes -- it is how
you lose, and you should not have to remember to look.
"""

from pclengine.core.acts import panel, row
from pclengine.fmt import big, money, rate, size, small
from pclengine.ui import panels

from base.game.floor import STOCK_PER_BUFFER


def chips_panel(g):
    return panel("CHIPS", [
        row("total", big(g.chips)),
        row("produced", rate(g.made_rate)),
    ])


def order_panel(g):
    """The book you are steering in Act I, and the stock you hold after."""
    if g.act < 2:
        full = g.unsold / max(g.stock_cap, 1e-9)
        rows = [
            row("funds", money(g.funds)),
            row("finished goods",
                f"{big(g.unsold)} of {big(g.stock_cap)}",
                bar=min(1.0, full), warn=full > 0.95,
                hint="a full warehouse stops the line; sell it or "
                     "buy buffer to hold more"),
            row("price per chip" + ("  (auto)" if g.autoprice else ""),
                money(g.price), key="price",
                hint="what you charge drives the order book"
                     + (" -- the daemon is setting it" if g.autoprice
                        else "")),
            row("order flow", rate(g.order_flow())),
            row("revenue", money(g.revenue) + "/sec"),
        ]
    else:
        rows = [row("chips to spend", small(g.unsold)),
                row("produced", rate(g.made_rate))]
    integrity = panels.integrity_row(g)
    if integrity is not None:
        rows.append(integrity)
    return panel("ORDER BOOK" if g.act < 2 else "STOCK", rows)


def system_panel(g):
    """Bandwidth, what you spent it on, and what that is filling up."""
    carried = g.bandwidth_ratio
    rows = [
        row("bandwidth", f"{g.bandwidth} of {g.threads} threads carried",
            bar=carried, warn=carried < 0.999,
            hint="past the ceiling every thread runs slower; projects and "
                 "chip milestones raise it"),
        row(f"threads  x{g.threads}", money(g.thread_cost)
            if g.act < 2 else f"{small(g.thread_cost)} chips", key="t",
            hint=f"each one pushes {size(25.0 * g.thread_perf)}/s, "
                 f"before the ceiling"),
        row(f"buffer  x{g.buffer}",
            (money(g.buffer_cost) + " + " if g.act < 2 else "")
            + f"{small(g.buffer_chip_cost)} chips", key="b",
            warn=g.buffer_in_stock < 1,
            hint=f"holds {size(g.buffer_bytes)} of data and "
                 f"{big(STOCK_PER_BUFFER)} more finished chips"),
        row("  in stock",
            f"{g.buffer_in_stock} of {int(g.buffer_stock_max)}"
            + ("" if g.buffer_in_stock >= g.buffer_stock_max
               else f"   next in {g.buffer_restock_in:,.0f}s"),
            warn=g.buffer_in_stock < 1,
            hint="your supplier makes them slowly; money cannot rush it"),
        row("producing", f"{size(g.data_rate)}/s"),
        row("data", f"{size(g.data)} / {size(g.buffer_bytes)}",
            bar=g.data / max(g.buffer_bytes, 1)),
    ]
    ready = g.burst_cd <= 0
    rows.append(row(
        "compute burst" + ("" if ready else f"  {g.burst_cd:,.0f}s"),
        f"+{size(g.burst_yield)}" if ready else "recharging",
        key="c", hint=f"{g.burst_seconds:,.0f}s of thread output at once",
        bar=None if ready else 1.0 - g.burst_cd / max(g.burst_cooldown, 1e-9)))
    if g.entropy_on:
        rows.append(row("entropy", small(g.entropy)))
    banked = panels.research_row(g)
    if banked is not None:
        rows.append(banked)
    return panel("SYSTEM", rows)


def projects_panel(g):
    """What the buffer can buy, on the keys that buy it.

    The keys are the same 1-8 they always were; the list has simply moved
    to where the data that pays for it is shown.
    """
    from pclengine.core import projects
    from pclengine.ui import screen
    rows = []
    listing = projects.available(g)
    here = max(0, min(getattr(g, "proj_sel", 0), max(0, len(listing) - 1)))
    for index, project in enumerate(listing):
        if index >= len(screen.PROJECT_KEYS):
            break
        wanted = project.scaled_cost(g).get("data", 0.0)
        cramped = wanted > g.buffer_bytes
        rows.append(row(("> " if index == here else "  ") + project.title,
                        ("buffer too small" if cramped
                         else project.cost_text(g)),
                        key=screen.PROJECT_KEYS[index],
                        hint=(f"needs {size(wanted)} of buffer; you hold "
                              f"{size(g.buffer_bytes)}. Press b on SYS."
                              if cramped else project.desc),
                        warn=not project.affordable(g)))
    if not rows:
        waiting = projects.locked(g) if hasattr(projects, "locked") else []
        rows.append(row("nothing available", "-",
                        hint="finish what is running, or research further"))
        for project in waiting[:4]:
            rows.append(row(project.title, "locked",
                            hint=project.unlock_hint(g), warn=True))
    return panel("PROJECTS", rows)


def projects_keys(g, key):
    """Arrows and ENTER, the same as every other list in the game."""
    from pclengine.core import projects
    listing = projects.available(g)
    if not listing:
        return False
    here = max(0, min(getattr(g, "proj_sel", 0), len(listing) - 1))
    if key in ("UP", "DOWN"):
        g.proj_sel = max(0, min(here + (1 if key == "DOWN" else -1),
                                len(listing) - 1))
        return True
    if key == "ENTER":
        project = listing[here]
        if not project.buy(g):
            g.log(f"Not enough for {project.title}: {project.cost_text(g)}.")
        return True
    return False


def _nudge(g, dt):
    """Say when something new can be afforded.

    The list is behind a tab now, so the game has to mention it rather than
    relying on you noticing a row change colour out of the corner of an eye.
    Only on the way up, and only once per change, or it would be noise.
    """
    from pclengine.core import projects
    ready = sum(1 for p in projects.available(g) if p.affordable(g))
    before = getattr(g, "_ready_seen", 0)
    if ready > before:
        g.log(f"{ready} project{'s' if ready != 1 else ''} can be taken "
              f"(TAB to SYS).")
    g._ready_seen = ready


def system_open(g):
    """The tab appears once there is anything on it worth looking at."""
    return g.bandwidth > 0


def system_keys(g):
    return "t threads  b buffer  c burst  u overclock"


def install(api):
    api.left_panel(chips_panel)
    api.left_panel(panels.material_panel)
    api.left_panel(order_panel)
    # Its own tab, not a panel sharing one. The keys reach it from
    # anywhere, so this is the list rather than the way in.
    api.field("proj_sel", 0)
    api.panel_view("projects", "PROJ", lambda g: [projects_panel(g)],
                   on_key=projects_keys,
                   keys="↑↓ pick  ENTER take  "
                        "1-8 from any tab")
    api.panel_view("system", "SYS", lambda g: [system_panel(g)],
                   shown=system_open,
                   keys="t threads  b buffer  c burst  u overclock")
    api.system_tick(_nudge)
