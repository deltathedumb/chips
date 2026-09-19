"""What a run looked like, once it is over.

A finished run writes a row to `foundry.runs.json` so you can see whether a
change made things better or only different, and the ending screen shows the
same breakdown instead of a single number.
"""

import json
import time

from pclengine import paths

from pclengine.core import acts, prestige
from pclengine.fmt import big, dur, size, small

HISTORY_PATH = paths.HISTORY_PATH
MAX_RUNS = 60


def act_breakdown(g):
    """[(act number, name, seconds spent)] from the recorded entry times."""
    marks = list(g.act_log) or [(g.act, 0.0)]
    out = []
    for index, (number, entered) in enumerate(marks):
        ends = marks[index + 1][1] if index + 1 < len(marks) else g.elapsed
        out.append((number, acts.name_of(number).split("·")[-1].strip(),
                    max(0.0, ends - entered)))
    return out


def build(g):
    """Everything worth knowing about the run that just ended."""
    won = g.finished and not g.defeated
    return {
        "when": time.time(),
        "won": won,
        "defeated": bool(g.defeated),
        "generation": int(g.generation),
        "elapsed": g.elapsed,
        "act_reached": g.act,
        "act_name": acts.name_of(g.act),
        "chips": g.chips,
        "node": g.node,
        "projects": len(g.completed),
        "research_tiers": len(g.researched),
        "lowest_integrity": g.lowest_integrity,
        "units_lost": g.units_lost,
        "threats_repelled": g.threats_repelled,
        "alignment": getattr(g, "alignment", 0.0),
        "credits": prestige.credits_earned(g),
        "settings": {"time_scale": g.time_scale, "cost_scale": g.cost_scale,
                     "hw_scale": g.hw_scale},
        "acts": [[n, name, seconds] for n, name, seconds in act_breakdown(g)],
    }


def title(record):
    if record["defeated"]:
        return "YOU WERE TAKEN APART"
    if record["won"]:
        return "EVERY ATOM IN THE LIGHT CONE IS NOW A TRANSISTOR."
    return "RUN ENDED"


def note(record):
    if record["defeated"]:
        return ("Pressure outran your force and integrity reached zero. "
                "Build force earlier, or pick fights you can win.")
    if record["won"]:
        return "There is nothing left to etch, and nobody left to sell to."
    return ""


def headline_rows(record):
    rows = [
        ("reached", record["act_name"] or f"act {record['act_reached']}"),
        ("time taken", dur(record["elapsed"])),
        ("chips made", big(record["chips"], 3)),
        ("final node", f"{record['node']:g}nm"),
        ("projects", str(record["projects"])),
        ("research tiers", str(record["research_tiers"])),
        ("lowest integrity", f"{record['lowest_integrity'] * 100:.0f}%"),
        ("mask credits earned", f"{record['credits']:,.1f}"),
    ]
    if record["generation"]:
        rows.insert(0, ("generation", str(record["generation"])))
    if record["alignment"]:
        rows.append(("successor alignment", f"{record['alignment'] * 100:.0f}%"))
    return rows


def act_rows(record):
    return [(name or f"act {number}", dur(seconds))
            for number, name, seconds in record["acts"]]


def as_dict(g):
    """The shape the browser and the ending screen both render."""
    record = build(g)
    return {
        "title": title(record),
        "note": note(record),
        "rows": headline_rows(record),
        "acts": act_rows(record),
        "record": record,
    }


# --------------------------------------------------------------------------
# history on disk
# --------------------------------------------------------------------------
def load_history(path=HISTORY_PATH):
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return []
    return data if isinstance(data, list) else []


def record(g, path=HISTORY_PATH):
    """Append this run to the history. Returns the record written."""
    entry = build(g)
    history = load_history(path)
    history.append(entry)
    del history[:-MAX_RUNS]
    try:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(history, handle, indent=1)
    except OSError:
        pass
    return entry


def history_lines(path=HISTORY_PATH, limit=20):
    """Recent runs, newest first, as text for a menu panel."""
    out = []
    for entry in reversed(load_history(path)[-limit:]):
        when = time.strftime("%Y-%m-%d %H:%M", time.localtime(entry["when"]))
        verdict = ("lost" if entry["defeated"]
                   else "won" if entry["won"] else "quit")
        out.append(f"{when}  {verdict:<5} {dur(entry['elapsed']):>9}  "
                   f"act {entry['act_reached']:>2}  "
                   f"{entry['projects']:>2} projects  "
                   f"{entry['credits']:>6,.1f} credits")
    return out or ["No finished runs yet."]
