/* FOUNDRY web client.
   No simulation here: it posts keys and renders whatever /api/state returns.
   Anything that throws during boot is shown on the page, never swallowed. */

"use strict";

const $ = (sel) => document.querySelector(sel);

function el(tag, cls, text) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
}

function banner(message, detail) {
  const box = el("div");
  box.style.cssText =
    "border:2px solid var(--danger);background:var(--starve);" +
    "color:var(--fg);padding:10px;margin:8px;white-space:pre-wrap";
  box.appendChild(el("strong", null, "The page could not start: " + message));
  if (detail) box.appendChild(el("pre", null, detail));
  box.appendChild(el("p", "note",
    "If you just updated the game, hard-reload with Ctrl+F5."));
  document.body.insertBefore(box, document.body.firstChild);
}

window.addEventListener("error", (ev) => {
  banner(ev.message || "script error", (ev.error && ev.error.stack) || "");
});

let STATE = null;
let MENU = null;
let DEVPANEL = null;
let SCREEN = "game";
const SETUP = {};

// Every state-bearing response carries the order it was asked for, so a
// poll that started before a keypress cannot land after it and paint the
// older picture back over the newer one. That race is most of what made
// the game look like it was ignoring input.
let REQUEST = 0;
let RENDERED = 0;

const SAVE_KEY = "foundry-save";

// In client mode the server writes nothing: it hands the save bytes over
// and this is the only copy. Clearing the site data throws the run away,
// so the page says so rather than letting it be a surprise.
function keepSave(blob) {
  try {
    localStorage.setItem(SAVE_KEY, blob);
    setStatus("Saved in this browser.");
  } catch (err) {
    setStatus("This browser would not store the save - it is not kept.");
  }
}

function heldSave() {
  try {
    return localStorage.getItem(SAVE_KEY);
  } catch (err) {
    return null;
  }
}

async function offerHeldSave() {
  const blob = heldSave();
  if (!blob) return;
  const out = await api("/api/save/import", { blob: blob });
  setStatus(out.message || "");
}

function accept(state, ticket) {
  if (!state) return false;
  // The save blob is handed over exactly once -- the server drops it the
  // moment any snapshot carries it -- so it has to be stored before the
  // staleness check, not after. Discarding an out-of-order *picture* is
  // right; discarding the only copy of the save inside it is how a save
  // silently did nothing and the next reload restored an older one.
  if (state.saveBlob) keepSave(state.saveBlob);
  if (ticket < RENDERED) return false;
  RENDERED = ticket;
  STATE = state;
  renderHUD(STATE);
  return true;
}

async function api(path, body) {
  const options = body
    ? {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }
    : {};
  const response = await fetch(path, options);
  return response.json();
}

function setStatus(text) {
  const line = $("#statusline");
  line.textContent = text || "";
  if (text) {
    setTimeout(() => {
      if (line.textContent === text) line.textContent = "";
    }, 4000);
  }
}

/* ------------------------------------------------------------- screens */
function show(name) {
  SCREEN = name;
  document.querySelectorAll(".screen").forEach((pane) => {
    pane.classList.toggle("active", pane.id === "screen-" + name);
  });
  document.querySelectorAll("#menubar button").forEach((button) => {
    button.classList.toggle("active", button.dataset.screen === name);
  });
  if (name === "projects") renderTree();
  if (name === "tech") renderTechTree();
  if (name === "editor") loadEditor();
  if (name === "mods" || name === "newgame" || name === "dev") renderMenu();
}

/* ----------------------------------------------------------------- HUD */
function meter(fraction, danger) {
  const wrap = el("div", danger ? "meter low" : "meter");
  const fill = el("i");
  fill.style.width = (Math.max(0, Math.min(1, fraction)) * 100).toFixed(1) + "%";
  wrap.appendChild(fill);
  return wrap;
}

function panelNode(panel) {
  const box = el("div", "panel");
  box.appendChild(el("div", "title", panel.title));
  const table = el("table");
  const body = el("tbody");

  (panel.rows || []).forEach((row) => {
    const tr = el("tr");
    if (row.warn) tr.className = "starving";
    tr.title = row.hint || "";
    tr.appendChild(el("td", null, row.label));

    if (row.setting || row.dial) {
      const cell = el("td", "v");
      const minus = el("button", "buy", "−");
      const plus = el("button", "buy", "+");
      const kind = row.setting ? "setting" : "dial";
      const name = row.setting || row.dial;
      minus.onclick = () => adjust(kind, name, -1);
      plus.onclick = () => adjust(kind, name, 1);
      cell.append(minus, " " + row.value + " ", plus);
      tr.appendChild(cell);
      tr.appendChild(el("td", "b"));
    } else {
      tr.appendChild(el("td", "v", row.value));
      const cell = el("td", "b");
      if (row.key && row.key !== "price") {
        const button = el("button", "buy", row.key);
        button.title = row.hint || "";
        button.onclick = () => press(row.key);
        cell.appendChild(button);
      }
      tr.appendChild(cell);
    }
    body.appendChild(tr);

    if (row.bar !== undefined && row.bar !== null) {
      const barRow = el("tr");
      const cell = el("td");
      cell.colSpan = 3;
      cell.appendChild(meter(row.bar, row.warn));
      barRow.appendChild(cell);
      body.appendChild(barRow);
    }
  });

  table.appendChild(body);
  box.appendChild(table);
  return box;
}

function actionButtons(state) {
  // Built from the engine's own binding table, not from whatever rows
  // happen to carry a key. That table is what the keyboard dispatches
  // against, so a button here cannot offer something a key would not do.
  const bar = $("#buttons");
  bar.textContent = "";
  const seen = {};
  (state.binds || []).forEach((bind) => {
    if (seen[bind.key]) return;
    seen[bind.key] = true;
    const button = el("button");
    const label = bind.key === " " ? "SPACE" : bind.key;
    button.innerHTML = "<b>" + label + "</b> " + (bind.label || "");
    button.title = bind.hint || "";
    button.dataset.press = bind.key;
    button.dataset.layer = bind.layer || "";
    bar.appendChild(button);
  });
}

// An overlay owns the keyboard on the server. If the page does not draw
// one the player presses keys into a void -- which is what happened the
// first time the softlock popup opened itself here.
function renderGameOverlay(info) {
  let box = $("#gameoverlay");
  if (!info) {
    if (box) box.remove();
    return;
  }
  if (box && box.dataset.kind === info.kind) return;   // already up
  if (box) box.remove();

  box = el("div");
  box.id = "gameoverlay";
  box.dataset.kind = info.kind;
  const panel = el("div", "panel");
  panel.appendChild(el("h2", null, info.title));
  if (info.headline) panel.appendChild(el("p", "headline", info.headline));
  (info.detail || []).forEach((line) => {
    panel.appendChild(el("p", "note", line));
  });
  if (info.terms) panel.appendChild(el("p", "terms", info.terms));

  const buttons = el("div", "buttons");
  if (info.accept) {
    const yes = el("button", "primary", info.accept);
    yes.onclick = () => { box.remove(); press("ENTER"); };
    buttons.appendChild(yes);
  }
  const no = el("button", null, info.dismiss || "Close");
  no.onclick = () => { box.remove(); press("ESC"); };
  buttons.appendChild(no);
  panel.appendChild(buttons);
  box.appendChild(panel);
  document.body.appendChild(box);
}

function renderHUD(state) {
  if (!state) return;
  renderGameOverlay(state.overlay);
  if (state.fatal) {
    showOverlay("SOMETHING BROKE", [["in", state.fatal.where]],
      state.fatal.trace, "resume", async () => {
        await api("/api/resume", {});
        $("#ending").classList.remove("show");
      });
    if (!state.left) return;
  }

  $("#clock").textContent = state.elapsed;
  $("#node").textContent = state.node + " node";
  $("#modename").textContent =
    state.mode + (state.costNote ? "  " + state.costNote : "");
  $("#actname").textContent = state.actName;

  const left = $("#leftcol");
  const right = $("#rightcol");
  left.textContent = "";
  right.textContent = "";

  // The first left-hand panel is the headline: its first row is the big
  // number, the rest sit under it. What it is called comes from the engine,
  // so a different game reads correctly without touching this.
  const panels = state.left || [];
  const top = panels[0] || { title: state.headlineLabel || "", rows: [] };
  const headlinePanel = el("div", "panel");
  headlinePanel.appendChild(el("div", "title", top.title));
  const table = el("table");
  const body = el("tbody");
  const rows = top.rows || [];
  const headline = el("tr", "big");
  const headlineCell = el("td", null, rows.length ? rows[0].value
    : state.headline);
  headlineCell.colSpan = 3;
  headline.appendChild(headlineCell);
  body.appendChild(headline);
  rows.slice(1).forEach((r) => {
    const tr = el("tr");
    tr.append(el("td", null, r.label), el("td", "v", r.value), el("td", "b"));
    body.appendChild(tr);
  });
  table.appendChild(body);
  headlinePanel.appendChild(table);
  left.appendChild(headlinePanel);

  panels.slice(1).forEach((p) => left.appendChild(panelNode(p)));

  // The tab strip is built from whatever the engine says is showing, so a
  // mod that adds a panel gets a button here without touching this file.
  renderMenubar(state.menubar);
  document.querySelectorAll("#menubar button[data-screen]").forEach((b) => {
    b.classList.toggle("active", b.dataset.screen === SCREEN);
  });

  const tabs = state.tabs || [];
  if (tabs.length > 1) {
    const strip = el("div", "tabs");
    tabs.forEach((t) => {
      const b = el("button", t.current ? "tab on" : "tab", t.label);
      b.onclick = () => {
        // TAB cycles; press it until the one that was clicked comes up.
        let hops = tabs.findIndex((x) => x.key === t.key)
          - tabs.findIndex((x) => x.current);
        if (hops < 0) hops += tabs.length;
        for (let i = 0; i < hops; i += 1) press("TAB");
      };
      strip.appendChild(b);
    });
    right.appendChild(strip);
  }
  (state.right || []).forEach((p) => right.appendChild(panelNode(p)));

  const firstRight = (state.right || [])[0] || { rows: [] };
  const priceRow = (firstRight.rows || []).filter((r) => r.key === "price")[0];
  $("#priceout").textContent = priceRow ? priceRow.value : "";
  $("#pricebox").style.display = state.act === 1 ? "" : "none";
  $("#batchbtn").textContent = "x" + state.batch;

  actionButtons(state);
  $("#log").textContent = (state.log || []).join("\n");

  if (state.finished && state.summary) showSummary(state.summary);
}

/* --------------------------------------------------------- end screens */
function showOverlay(title, rows, pre, buttonText, onClick) {
  const box = $("#ending");
  if (box.classList.contains("show")) return;
  box.textContent = "";
  box.appendChild(el("h1", null, title));
  if (rows && rows.length) {
    const table = el("table");
    const body = el("tbody");
    rows.forEach((pair) => {
      const tr = el("tr");
      tr.append(el("td", null, pair[0]), el("td", null, pair[1]));
      body.appendChild(tr);
    });
    table.appendChild(body);
    box.appendChild(table);
  }
  if (pre) {
    const block = el("pre", null, pre);
    block.style.cssText = "text-align:left;max-height:18em;overflow:auto";
    box.appendChild(block);
  }
  const button = el("button", null, buttonText || "close");
  button.onclick = onClick || function () { box.classList.remove("show"); };
  box.appendChild(button);
  box.classList.add("show");
}

function showSummary(summary) {
  showOverlay(summary.title, summary.rows || [], summary.note || "", "close");
}

/* --------------------------------------------------------------- input */
async function press(key) {
  const ticket = ++REQUEST;
  const out = await api("/api/key", { key });
  if (out && out.state) accept(out.state, ticket);
  return out;
}

async function adjust(kind, name, delta) {
  const route = kind === "dial" ? "/api/dial" : "/api/firmware";
  STATE = await api(route, { setting: name, delta: delta });
  renderHUD(STATE);
}

// One listener, on a node that is never replaced. The HUD is rebuilt four
// times a second, and a handler bound to a button that gets thrown away
// between mousedown and mouseup never fires -- which is why clicking used
// to work only sometimes.
document.addEventListener("click", (ev) => {
  const target = ev.target && ev.target.closest
    ? ev.target.closest("[data-press]")
    : null;
  if (!target || target.disabled) return;
  ev.preventDefault();
  // Keep focus off the button, or the next SPACE or ENTER presses it again
  // as well as reaching the game.
  if (target.blur) target.blur();
  press(target.dataset.press);
});

document.addEventListener("keydown", (ev) => {
  if (SCREEN !== "game") return;
  if (ev.target && ev.target.tagName === "INPUT") return;
  if (ev.target && ev.target.tagName === "TEXTAREA") return;
  const special = {
    ArrowLeft: "LEFT", ArrowRight: "RIGHT", ArrowUp: "UP",
    ArrowDown: "DOWN", Enter: "ENTER", Tab: "TAB",
  };
  const key = special[ev.key] || ev.key;
  if (key === "q") return;
  if (key.length === 1 || special[ev.key]) {
    ev.preventDefault();
    press(key);
  }
});

/* ------------------------------------------------------------ tech tree */
function formatEta(seconds) {
  const whole = Math.max(0, Math.round(seconds));
  if (whole >= 3600) {
    return Math.floor(whole / 3600) + "h "
      + String(Math.floor((whole % 3600) / 60)).padStart(2, "0") + "m";
  }
  return Math.floor(whole / 60) + ":"
    + String(whole % 60).padStart(2, "0");
}

const TECH = { data: null, selected: null };
const NODE_W = 190;
const NODE_H = 56;

async function renderTechTree() {
  TECH.data = await api("/api/techtree");
  drawTech();
}

function drawTech() {
  const data = TECH.data;
  if (!data) return;
  const bench = data.benches || { used: 0, total: 1, working: [], share: 0 };
  let summary = data.researched + " of " + data.total + " researched · "
    + "benches " + bench.used + "/" + bench.total;
  if (bench.used > 1) {
    summary += " at " + Math.round(bench.share * 100) + "% each";
  }
  summary += " · " + Math.round(data.output || 0).toLocaleString()
    + " research/sec";
  $("#techsummary").textContent = summary;

  const legend = $("#techlegend");
  legend.textContent = "";
  (data.categories || []).forEach((c) => {
    const item = el("span");
    const swatch = el("i");
    swatch.style.background = c.colour;
    item.append(swatch, el("span", null, c.label));
    legend.appendChild(item);
  });

  const tiers = data.tiers || [];
  const rows = Math.max(1, ...tiers.map((t) => t.length));
  const width = tiers.length * NODE_W + 40;
  const height = rows * NODE_H + 40;
  const at = {};
  tiers.forEach((tier, column) => {
    tier.forEach((node, index) => {
      at[node.id] = { x: 30 + column * NODE_W, y: 30 + index * NODE_H };
    });
  });

  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("width", width);
  svg.setAttribute("height", height);
  const make = (tag) =>
    document.createElementNS("http://www.w3.org/2000/svg", tag);

  // Edges first, so nodes sit on top of them.
  tiers.forEach((tier) => tier.forEach((node) => {
    const to = at[node.id];
    (node.requires || []).forEach((need) => {
      const from = at[need.id];
      if (!from) return;
      const path = make("path");
      const mid = (from.x + to.x) / 2;
      path.setAttribute("d",
        "M" + (from.x + 14) + " " + from.y +
        " C" + mid + " " + from.y + " " + mid + " " + to.y +
        " " + (to.x - 14) + " " + to.y);
      path.setAttribute("class", need.done ? "edge done" : "edge");
      svg.appendChild(path);
    });
  }));

  tiers.forEach((tier) => tier.forEach((node) => {
    const spot = at[node.id];
    const group = make("g");
    group.setAttribute("class",
      "node " + node.state + (TECH.selected === node.id ? " selected" : ""));
    group.setAttribute("transform", "translate(" + spot.x + "," + spot.y + ")");
    group.style.color = node.colour;

    const ring = make("circle");
    ring.setAttribute("r", 13);
    ring.setAttribute("class", "ring");
    group.appendChild(ring);

    if (node.state === "working") {
      // How far along, drawn round the node itself so the tree shows
      // where the labs are without anything having to be selected.
      const r = 17;
      const arc = make("circle");
      arc.setAttribute("r", r);
      arc.setAttribute("class", "progress");
      const circumference = 2 * Math.PI * r;
      arc.setAttribute("stroke-dasharray", circumference);
      arc.setAttribute("stroke-dashoffset",
        circumference * (1 - (node.fraction || 0)));
      arc.setAttribute("transform", "rotate(-90)");
      group.appendChild(arc);
    }

    const icon = make("path");
    icon.setAttribute("d", node.path);
    icon.setAttribute("class", "icon");
    // The paths are drawn in a 24x24 box; centre and shrink to fit the ring.
    icon.setAttribute("transform", "translate(-8,-8) scale(0.667)");
    group.appendChild(icon);

    const label = make("text");
    label.setAttribute("class", "label");
    label.setAttribute("x", 19);
    label.setAttribute("y", 4);
    label.textContent = node.name;
    group.appendChild(label);

    group.addEventListener("click", () => {
      TECH.selected = node.id;
      drawTech();
    });
    svg.appendChild(group);
  }));

  const canvas = $("#techcanvas");
  canvas.textContent = "";
  canvas.appendChild(svg);
  drawTechDetail();
}

function findTech(id) {
  const tiers = (TECH.data && TECH.data.tiers) || [];
  for (const tier of tiers) {
    for (const node of tier) if (node.id === id) return node;
  }
  return null;
}

function drawTechDetail() {
  const box = $("#techdetail");
  box.textContent = "";
  const node = findTech(TECH.selected);
  if (!node) {
    box.appendChild(el("p", "note", "Pick a technology to see what it does, "
      + "what it needs, and what it leads to."));
    return;
  }
  const title = el("h3", null, node.name);
  title.style.color = node.colour;
  box.appendChild(title);
  box.appendChild(el("p", "note",
    node.categoryLabel + " \u00b7 tier " + node.depth));
  box.appendChild(el("p", null, node.blurb));

  const list = el("dl");
  const pair = (term, build) => {
    list.appendChild(el("dt", null, term));
    const dd = el("dd");
    build(dd);
    list.appendChild(dd);
  };

  const bench = (TECH.data && TECH.data.benches) || { total: 1 };
  const words = {
    researched: "researched",
    working: "on a bench",
    affordable: "a bench is free",
    available: "all " + bench.total + " benches are busy",
    locked: "locked",
    foreclosed: "ruled out by a choice earlier this run",
  };
  pair("status", (dd) => {
    dd.textContent = words[node.state] || node.state;
    dd.className = "dd " + (node.state === "researched" ? "done" : node.state);
  });
  if (node.state === "working") {
    pair("progress", (dd) => {
      const track = el("div", "progressbar");
      const fill = el("i");
      fill.style.width = Math.round((node.fraction || 0) * 100) + "%";
      track.appendChild(fill);
      dd.appendChild(track);
      dd.appendChild(el("span", "note",
        Math.round(node.progress).toLocaleString() + " of "
        + Math.round(node.cost).toLocaleString()
        + (node.eta != null
          ? " · " + formatEta(node.eta) + " left at this split" : "")));
    });
  } else {
    pair("cost", (dd) => {
      dd.textContent = Math.round(node.cost).toLocaleString() + " research"
        + (node.progress > 0
          ? " (" + Math.round(node.progress).toLocaleString() + " done)" : "");
    });
  }
  if (node.note) {
    pair("effect", (dd) => {
      dd.textContent = node.note;
      dd.className = "dd effect";
    });
  }
  if (node.excludes && node.excludes.length && node.state !== "researched") {
    // The one thing a player must not discover after the fact.
    pair("rules out", (dd) => {
      dd.textContent = node.excludes.join(", ");
      dd.className = "dd warn";
    });
  }
  if (node.requires.length) {
    pair("requires", (dd) => {
      const ul = el("ul");
      node.requires.forEach((need) => {
        const li = el("li", need.done ? "done" : "pending",
          (need.done ? "\u2713 " : "\u00b7 ") + need.name);
        ul.appendChild(li);
      });
      dd.appendChild(ul);
    });
  }
  if (node.unlocks.length) {
    pair("unlocks", (dd) => {
      dd.textContent = node.unlocks.join(", ").replace(/_/g, " ");
    });
  }
  if (node.act) {
    pair("opens", (dd) => { dd.textContent = "act " + node.act; });
  }
  if (node.leadsTo.length) {
    pair("leads to", (dd) => {
      dd.textContent = node.leadsTo.map((t) => t.name).join(", ");
    });
  }
  box.appendChild(list);

  if (node.state !== "researched" && node.state !== "foreclosed") {
    const take = el("button", null,
      node.state === "working" ? "Put aside" : "Start work");
    take.disabled = node.state !== "affordable" && node.state !== "working";
    take.onclick = async () => {
      const out = await api("/api/research", { id: node.id });
      setStatus(out.message || "");
      if (out.tree) {
        TECH.data = out.tree;
        drawTech();
      }
    };
    box.appendChild(take);
  }
}

/* ---------------------------------------------------------------- theme */
function applyTheme(name) {
  document.documentElement.setAttribute("data-theme", name);
  const button = $("#themebtn");
  if (button) {
    button.textContent = name === "dark" ? "\u25d3" : "\u25d1";
    button.title = name === "dark" ? "Switch to light" : "Switch to dark";
  }
  try {
    localStorage.setItem("foundry-theme", name);
  } catch (err) {
    /* private window, or storage switched off. The theme still applies. */
  }
}

function initTheme() {
  let saved = null;
  try {
    saved = localStorage.getItem("foundry-theme");
  } catch (err) {
    saved = null;
  }
  const prefersDark = window.matchMedia
    && window.matchMedia("(prefers-color-scheme: dark)").matches;
  applyTheme(saved || (prefersDark ? "dark" : "light"));
  const button = $("#themebtn");
  if (button) {
    button.onclick = () => {
      const now = document.documentElement.getAttribute("data-theme");
      applyTheme(now === "dark" ? "light" : "dark");
    };
  }
}

/* ---------------------------------------------------------- whole tree */
function renderTree() {
  const body = $("#alltree tbody");
  body.textContent = "";
  if (!STATE) return;
  (STATE.projects || []).forEach((project) => {
    const tr = el("tr");
    const take = el("button", "take", "take");
    take.disabled = !project.affordable;
    take.onclick = () => press(project.key);
    const cell = el("td");
    cell.appendChild(take);
    tr.append(cell, el("td", null, project.title),
      el("td", "cost", project.cost), el("td", "desc", project.desc));
    body.appendChild(tr);
  });
  (STATE.locked || []).forEach((project) => {
    const tr = el("tr", "locked");
    tr.append(el("td"), el("td", null, project.title),
      el("td", "cost", "locked"), el("td", "desc", project.hint));
    body.appendChild(tr);
  });
}

/* ------------------------------------------------------------- new run */
function renderSetup() {
  const body = $("#modelist tbody");
  body.textContent = "";
  (MENU.knobs || []).forEach((knob) => {
    if (!(knob.attr in SETUP)) SETUP[knob.attr] = knob.default;
    const readout = el("td", "cost", "x" + SETUP[knob.attr]);
    const step = function (direction) {
      let value = SETUP[knob.attr] * (direction > 0 ? 1.25 : 1 / 1.25);
      if ((SETUP[knob.attr] - 1) * (value - 1) < 0) value = 1;
      value = Math.min(knob.high, Math.max(knob.low, value));
      SETUP[knob.attr] = Math.round(value * 1e4) / 1e4;
      readout.textContent = "x" + SETUP[knob.attr];
    };
    const minus = el("button", null, "−");
    const plus = el("button", null, "+");
    minus.onclick = () => step(-1);
    plus.onclick = () => step(1);
    const controls = el("td");
    controls.append(minus, " ", plus);
    const tr = el("tr");
    tr.append(controls, el("td", null, knob.name), readout,
      el("td", "desc", knob.blurb));
    body.appendChild(tr);
  });

  const start = el("button", null, "start this run");
  start.onclick = async () => {
    STATE = await api("/api/new", { setup: SETUP });
    renderHUD(STATE);
    show("game");
    setStatus("new run: " + STATE.mode);
  };
  const cell = el("td");
  cell.appendChild(start);
  const go = el("tr");
  go.append(cell, el("td", null, ""), el("td", null, ""),
    el("td", "desc", "The run in progress is lost unless you saved it."));
  body.appendChild(go);
}

function renderMods() {
  const body = $("#modlist tbody");
  body.textContent = "";
  const list = MENU.mods || [];
  if (!list.length) {
    const tr = el("tr");
    const cell = el("td", "desc", "No mod files in mods/.");
    cell.colSpan = 3;
    tr.appendChild(cell);
    body.appendChild(tr);
    return;
  }
  list.forEach((mod) => {
    const tr = el("tr");
    const box = el("input");
    box.type = "checkbox";
    box.checked = mod.enabled;
    box.dataset.key = mod.key;
    const cell = el("td");
    cell.appendChild(box);
    tr.append(cell, el("td", null, mod.name),
      el("td", "desc", mod.error ? "ERROR " + mod.error : mod.description));
    body.appendChild(tr);
  });
}

async function renderMenu() {
  MENU = await api("/api/menu");
  document.body.classList.toggle("developer", Boolean(MENU.developer));
  renderSetup();
  renderMods();
  $("#savepath").value = MENU.savePath || "";
  renderHelp(MENU.help);
  if (MENU.developer) await renderDevPanel();
}

/* ----------------------------------------------------------- developer */
document.querySelectorAll("#devnav button").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll("#devnav button").forEach((other) =>
      other.classList.toggle("active", other === button));
    document.querySelectorAll(".devpane").forEach((pane) =>
      pane.classList.toggle("active", pane.id === "dev-" + button.dataset.pane));
    if (button.dataset.pane === "state") loadDevFields();
  });
});

async function renderDevPanel() {
  DEVPANEL = await api("/api/dev/panel");
  const box = $("#dev-actions");
  box.textContent = "";
  if (DEVPANEL.error) {
    box.textContent = DEVPANEL.error;
    return;
  }
  (DEVPANEL.actionGroups || []).forEach((group) => {
    const wrap = el("div", "devgroup");
    wrap.appendChild(el("div", "title", group.title));
    const table = el("table");
    const body = el("tbody");
    (group.actions || []).forEach((action) => {
      const button = el("button", null, action.name);
      let input = null;
      if (action.arg) {
        input = el("input");
        input.type = "text";
        input.value = action.default === null ? "" : action.default;
        input.title = action.arg;
      }
      button.onclick = async () => {
        const out = await api("/api/dev", {
          action: action.key,
          value: input ? input.value : null,
        });
        setStatus(out.message || action.name);
        if (out.lines && out.lines.length) {
          consoleWrite(action.name, "echo");
          consoleWrite(out.lines.join("\n"));
          const tab = document.querySelector(
            "#devnav button[data-pane=console]");
          if (tab) tab.click();
        }
        STATE = await api("/api/state");
        renderHUD(STATE);
      };
      const first = el("td", "act");
      first.appendChild(button);
      const second = el("td", "arg");
      if (input) second.appendChild(input);
      const tr = el("tr");
      tr.append(first, second, el("td", "desc", action.blurb));
      body.appendChild(tr);
    });
    table.appendChild(body);
    wrap.appendChild(table);
    box.appendChild(wrap);
  });
  $("#consolehelp").textContent = DEVPANEL.consoleHelp || "";
  $("#consolehint").textContent =
    (DEVPANEL.history || []).length + " previous statement(s)";
}

function fieldEditor(groups, container) {
  container.textContent = "";
  groups.forEach((group) => {
    const wrap = el("div", "edgroup");
    wrap.appendChild(el("div", "title", group.title));
    const table = el("table");
    const body = el("tbody");
    (group.fields || []).forEach((field) => {
      const tr = el("tr", field.changed ? "changed" : "");
      const input = el("input");
      input.value = field.value;
      input.onchange = async () => {
        const out = await api("/api/editor/set",
          { name: field.name, value: input.value });
        if (out.ok) {
          input.value = out.value;
          tr.className = "changed";
          setStatus(field.label + " set");
        } else {
          setStatus("rejected: " + out.error);
          input.value = field.value;
        }
        STATE = await api("/api/state");
        renderHUD(STATE);
      };
      const cell = el("td");
      cell.appendChild(input);
      tr.append(el("td", null, field.label), cell,
        el("td", "kind", field.kind));
      body.appendChild(tr);
    });
    table.appendChild(body);
    wrap.appendChild(table);
    container.appendChild(wrap);
  });
}

async function loadDevFields() {
  const data = await api("/api/editor");
  if (data.error) {
    $("#devfields").textContent = data.error;
    return;
  }
  fieldEditor(data.groups || [], $("#devfields"));
}

async function loadEditor() {
  const data = await api("/api/editor");
  if (data.error) {
    $("#editorfields").textContent = data.error;
    return;
  }
  fieldEditor(data.groups || [], $("#editorfields"));
  const box = $("#editorprojects");
  box.textContent = "";
  (data.projects || []).forEach((project) => {
    const label = el("label");
    const check = el("input");
    check.type = "checkbox";
    check.checked = project.done;
    check.onchange = async () => {
      await api("/api/editor/project", { id: project.id, on: check.checked });
      STATE = await api("/api/state");
      renderHUD(STATE);
    };
    label.append(check,
      " " + project.title + (project.repeatable ? " (repeatable)" : ""));
    box.appendChild(label);
  });
}

/* ------------------------------------------------------------- console */
function consoleWrite(text, cls) {
  const out = $("#consoleout");
  out.appendChild(el("div", cls || null, text));
  out.scrollTop = out.scrollHeight;
}

async function runConsole() {
  const source = $("#consoleinput").value;
  if (!source.trim()) return;
  consoleWrite(">>> " + source, "echo");
  const result = await api("/api/dev/exec", { source: source });
  if (result.output) consoleWrite(result.output.replace(/\n$/, ""));
  if (result.result) consoleWrite(result.result, "val");
  if (result.error) consoleWrite(result.error.replace(/\n$/, ""), "err");
  STATE = await api("/api/state");
  renderHUD(STATE);
}

/* --------------------------------------------------------------- wires */
// The bar is built from what the engine says is in it, so a mod that adds,
// renames or hides a button changes this page without editing it. One
// delegated listener, so rebuilding the bar never loses a click.
let MENUBAR = "";

function renderMenubar(buttons) {
  const signature = JSON.stringify(buttons || []);
  if (signature === MENUBAR) return;
  MENUBAR = signature;
  const bar = $("#menubuttons");
  bar.textContent = "";
  (buttons || []).forEach((spec) => {
    const button = el("button", null, spec.label);
    button.dataset.screen = spec.screen || "";
    button.dataset.action = spec.action || "";
    if (spec.title) button.title = spec.title;
    button.classList.toggle("active", SCREEN === spec.screen);
    bar.appendChild(button);
  });
}

document.getElementById("menubar").addEventListener("click", (ev) => {
  const button = ev.target && ev.target.closest
    ? ev.target.closest("button[data-screen], button[data-action]")
    : null;
  if (!button) return;
  if (button.dataset.action) {
    api("/api/menu/" + button.dataset.action, {});
    return;
  }
  if (button.dataset.screen) show(button.dataset.screen);
});

$("#pricebox").addEventListener("click", (ev) => {
  const key = ev.target.dataset ? ev.target.dataset.key : null;
  if (key) press(key);
});

$("#consolerun").onclick = runConsole;
$("#consoleclear").onclick = function () { $("#consoleout").textContent = ""; };
$("#consoleinput").addEventListener("keydown", (ev) => {
  if (ev.key === "Enter" && (ev.ctrlKey || ev.metaKey)) {
    ev.preventDefault();
    runConsole();
  }
});

$("#modsave").onclick = async () => {
  const boxes = document.querySelectorAll("#modlist input:checked");
  const enabled = [].slice.call(boxes).map((box) => box.dataset.key);
  const out = await api("/api/mods", { enabled: enabled });
  setStatus(out.message);
  renderMenu();
};
$("#dosave").onclick = async () => {
  const out = await api("/api/save", { path: $("#savepath").value });
  setStatus(out.message);
};
$("#doload").onclick = async () => {
  const out = await api("/api/load", { path: $("#savepath").value });
  setStatus(out.message);
  STATE = await api("/api/state");
  renderHUD(STATE);
};

function renderHelp(sections) {
  // The help is content's, served by the engine, so the browser and the
  // terminal always say the same thing about the same game.
  const box = $("#helptext");
  box.textContent = "";
  (sections || []).forEach(([heading, lines]) => {
    box.appendChild(el("h3", null, heading));
    let para = [];
    const flush = () => {
      if (para.length) box.appendChild(el("p", null, para.join(" ")));
      para = [];
    };
    lines.forEach((line) => {
      const text = line.trim();
      if (text) para.push(text);
      else flush();
    });
    flush();
  });
}

/* ---------------------------------------------------------------- boot */
initTheme();

// If this server keeps saves in the browser, hand ours back before the
// first frame, or we would be looking at a fresh game for a moment.
async function boot() {
  try {
    const first = await api("/api/state");
    if (first && first.saveMode === "client") await offerHeldSave();
  } catch (err) {
    /* the poll below reports it properly */
  }
}

async function poll() {
  if (SCREEN === "game" || SCREEN === "editor" || SCREEN === "projects") {
    try {
      const ticket = ++REQUEST;
      const fresh = await api("/api/state");
      if (accept(fresh, ticket) && SCREEN === "projects") renderTree();
    } catch (err) {
      setStatus("lost the server");
    }
  }
  setTimeout(poll, 250);
}

(async function start() {
  try {
    await renderMenu();
    await boot();
    STATE = await api("/api/state");
    renderHUD(STATE);
    show("game");
    poll();
  } catch (err) {
    banner((err && err.message) || String(err), (err && err.stack) || "");
  }
})();
