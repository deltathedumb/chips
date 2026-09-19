"""A JSON-shaped view of the game, for the browser front end.

The web UI does no arithmetic of its own: it renders exactly what this hands
it, so both front ends read the same numbers out of the same engine.
"""

from pclengine import content
from pclengine.core import acts, projects
from pclengine.store import runconfig, summary
from pclengine.ui import actions, menubar, panels, screen
from pclengine.fmt import big, dur, money, rate, size, small


def _row(label, value, key=None, hint=None, bar=None):
    row = {"label": label, "value": value}
    if key:
        row["key"] = key
    if hint:
        row["hint"] = hint
    if bar is not None:
        row["bar"] = max(0.0, min(1.0, bar))
    return row


def panels_for(g):
    from pclengine.ui import panels as panel_views
    return panel_views.left(g), panel_views.right(g)


def project_list(g):
    out = []
    for i, p in enumerate(projects.available(g)):
        out.append({
            "index": i,
            "key": screen.PROJECT_KEYS[i] if i < len(screen.PROJECT_KEYS) else "",
            "id": p.id,
            "title": p.title,
            "desc": p.desc,
            "cost": p.cost_text(g),
            "affordable": p.affordable(g),
            "repeatable": p.repeatable,
        })
    return out


def locked_list(g):
    out = []
    for p in projects.ALL:
        if p.id in g.completed:
            continue
        try:
            if p.req(g):
                continue
        except Exception:
            continue
        out.append({"title": p.title, "desc": p.desc,
                    "hint": p.unlock_hint(g)})
    return out


def tech_tree(g):
    """The whole tree, tier by tier, with everything a node needs drawn.

    Same data the terminal browser reads, so the two cannot disagree about
    what a node costs or what it waits on.
    """
    from pclengine.core import research
    return {
        "tiers": research.tree_view(g),
        "categories": [{"key": c.key, "label": c.label, "colour": c.colour}
                       for c in research.CATEGORIES],
        "banked": g.research,
        "output": research.output(g),
        "benches": research.bench_state(g),
        "researched": len(g.researched),
        "total": len(research.TREE),
    }


def snapshot(g, developer=False):
    left, right = panels_for(g)
    return {
        "act": g.act,
        "actName": acts.name_of(g.act),
        "panelView": getattr(g, "panel_view", "ops"),
        "binds": [b.as_dict() for b in actions.bindings(g)],
        "menubar": menubar.as_data(g, developer),
        "tabs": [{"key": v.key, "label": v.label,
                  "current": v.key == getattr(g, "panel_view", "ops")}
                 for v in panels.visible(g)],
        "node": content.era(g),
        "elapsed": dur(g.elapsed),
        "mode": runconfig.label_of(g),
        "setup": runconfig.from_game(g).as_dict(),
        "costNote": screen._cost_note(g),
        "finished": g.finished,
        "batch": "MAX" if g.batch == float("inf") else small(g.batch),
        "headline": content.headline(g)[1],
        "headlineLabel": content.headline(g)[0],
        "rate": rate(g.made_rate),
        "left": left,
        "right": right,
        "projects": project_list(g),
        "locked": locked_list(g),
        "log": g.messages[-8:],
        "developer": developer,
        "canEtch": bool(acts.get(g.act).on_key),
        "summary": summary.as_dict(g) if g.finished else None,
        "defeated": bool(getattr(g, "defeated", False)),
    }


def ending(g):
    return {
        "title": "EVERY ATOM IN THE LIGHT CONE IS NOW A TRANSISTOR.",
        "rows": [
            ("chips made", big(g.chips, 3)),
            ("time elapsed", dur(g.elapsed)),
            ("final node", f"{g.node:g}nm"),
            ("seed fabs at the end", big(g.seed_fabs, 2)),
            ("rogue forks reclaimed", big(g.forks_reclaimed, 2)),
            ("projects completed", str(len(g.completed))),
            ("settings", runconfig.label_of(g)),
        ],
        "note": "There is nothing left to etch, and nobody left to sell to.",
    }
