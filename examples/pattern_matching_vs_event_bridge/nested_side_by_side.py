"""Nested dynamic surface: Folders -> Tabs -> Panels, two ways.

A workspace-shaped surface — three nested entity types, unbounded at
each level, with nine action types — implemented two ways so the wiring
cost of each pattern is directly comparable.

- Left column: pattern-matching callbacks, written with the canonical
  guard (`if not ctx.triggered_id or ctx.triggered[0]["value"] is None`)
  so phantom fires from remounted subscribers return no_update cleanly.
  Idiomatic modern Dash.
- Right column: the Dash Relay event bridge with per-action handlers
  registered on a single dispatch callback.

Both columns implement the same surface and call the same state-mutation
helpers. The difference is the plumbing between the UI and those helpers.

Run:
    python examples/pattern_matching_vs_event_bridge/nested_side_by_side.py

Click around in either column and compare:
  - callbacks registered (shown in each column header)
  - round-trips per click (shown in each column's console)
  - the code size needed to wire 9 actions (grep the Pure Dash section
    vs the Dash Relay section of this file).
"""
from __future__ import annotations

import sys
from copy import deepcopy
from pathlib import Path

from dash import ALL, Dash, Input, Output, State, ctx, dcc, html, no_update

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import dash_relay as relay
from dash_relay import Action, Emitter


# ---------------------------------------------------------------------------
# State model (shared between both columns)
# ---------------------------------------------------------------------------


KINDS = ("timeseries", "histogram", "scatter")


def _new_id(state, kind):
    key = f"next_{kind}_idx"
    idx = state.get(key, 1)
    state[key] = idx + 1
    return f"{kind[0]}-{idx}"


def _make_panel(pid, kind):
    return {"id": pid, "name": f"Panel {pid}", "kind": kind, "locked": False}


def _make_tab(tid, panels=None):
    return {"id": tid, "name": f"Tab {tid}", "panels": panels or [], "active_panel": None}


def _make_folder(fid, tabs=None):
    tabs = tabs or []
    return {
        "id": fid,
        "name": f"Folder {fid}",
        "tabs": tabs,
        "active_tab": tabs[0]["id"] if tabs else None,
    }


def initial_state():
    state = {"folders": [], "active_folder": None, "next_folder_idx": 1, "next_tab_idx": 1, "next_panel_idx": 1}
    # Seed with Folder 1 > Tab 1 > a couple panels so the demo opens non-empty.
    fid = _new_id(state, "folder")
    tid = _new_id(state, "tab")
    pid1 = _new_id(state, "panel")
    pid2 = _new_id(state, "panel")
    tab = _make_tab(tid, [_make_panel(pid1, "timeseries"), _make_panel(pid2, "histogram")])
    folder = _make_folder(fid, [tab])
    state["folders"].append(folder)
    state["active_folder"] = fid
    return state


def _find_folder(state, fid):
    for f in state["folders"]:
        if f["id"] == fid:
            return f
    return None


def _find_tab(state, tid):
    for f in state["folders"]:
        for t in f["tabs"]:
            if t["id"] == tid:
                return f, t
    return None, None


def _find_panel(state, pid):
    for f in state["folders"]:
        for t in f["tabs"]:
            for p in t["panels"]:
                if p["id"] == pid:
                    return f, t, p
    return None, None, None


def _active_folder(state):
    return _find_folder(state, state.get("active_folder"))


def _active_tab(state):
    f = _active_folder(state)
    if not f:
        return None
    return next((t for t in f["tabs"] if t["id"] == f.get("active_tab")), None)


# ---------------------------------------------------------------------------
# Action implementations (shared)
# ---------------------------------------------------------------------------


def do_folder_add(s):
    fid = _new_id(s, "folder")
    tid = _new_id(s, "tab")
    s["folders"].append(_make_folder(fid, [_make_tab(tid)]))
    s["active_folder"] = fid


def do_folder_activate(s, target):
    f = _find_folder(s, target)
    if f is not None:
        s["active_folder"] = f["id"]


def do_folder_delete(s, target):
    s["folders"] = [f for f in s["folders"] if f["id"] != target]
    if s["active_folder"] == target:
        s["active_folder"] = s["folders"][0]["id"] if s["folders"] else None


def do_tab_add(s):
    f = _active_folder(s)
    if f is None:
        return
    tid = _new_id(s, "tab")
    f["tabs"].append(_make_tab(tid))
    f["active_tab"] = tid


def do_tab_activate(s, target):
    f, t = _find_tab(s, target)
    if f is not None and t is not None:
        s["active_folder"] = f["id"]
        f["active_tab"] = t["id"]


def do_tab_delete(s, target):
    f, t = _find_tab(s, target)
    if f is None or t is None:
        return
    f["tabs"] = [x for x in f["tabs"] if x["id"] != target]
    if f["active_tab"] == target:
        f["active_tab"] = f["tabs"][0]["id"] if f["tabs"] else None


def do_panel_add(s, kind):
    t = _active_tab(s)
    if t is None:
        return
    if kind not in KINDS:
        kind = "timeseries"
    pid = _new_id(s, "panel")
    t["panels"].append(_make_panel(pid, kind))


def do_panel_delete(s, target):
    f, t, p = _find_panel(s, target)
    if t is None or p is None:
        return
    t["panels"] = [x for x in t["panels"] if x["id"] != target]


def do_panel_duplicate(s, target):
    f, t, p = _find_panel(s, target)
    if t is None or p is None:
        return
    idx = t["panels"].index(p)
    new = deepcopy(p)
    new["id"] = _new_id(s, "panel")
    new["name"] = p["name"] + " copy"
    t["panels"].insert(idx + 1, new)


# ---------------------------------------------------------------------------
# Rendering (per-side because ID structures differ)
# ---------------------------------------------------------------------------


_CARD = {"display": "flex", "alignItems": "center", "gap": "6px", "padding": "6px 10px",
         "borderWidth": "1px", "borderStyle": "solid", "borderColor": "#ccc",
         "borderRadius": "6px", "background": "white",
         "fontSize": "13px", "cursor": "default"}
_ACTIVE = {"borderColor": "#3b82f6", "background": "#eff6ff"}
_STRIP = {"display": "flex", "gap": "6px", "flexWrap": "wrap", "marginBottom": "8px"}
_SECTION = {"marginBottom": "12px"}
_LABEL = {"fontSize": "11px", "color": "#666", "textTransform": "uppercase",
          "letterSpacing": "0.05em", "marginBottom": "4px"}
_GRID = {"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "8px"}
_PANEL_CARD = {"padding": "10px", "border": "1px solid #ddd", "borderRadius": "6px",
               "background": "#fcfcfc", "display": "flex", "flexDirection": "column", "gap": "6px"}
_KIND_BADGE = {"fontSize": "10px", "padding": "1px 6px", "background": "#e5e7eb",
               "borderRadius": "10px", "color": "#374151", "alignSelf": "flex-start"}
_BTN = {"padding": "2px 6px", "fontSize": "11px", "border": "1px solid #ccc",
        "background": "white", "borderRadius": "4px", "cursor": "pointer"}


def _render_pd_column(state):
    active_fid = state.get("active_folder")
    folder = _active_folder(state)
    tab = _active_tab(state)

    folder_tiles = []
    for f in state["folders"]:
        style = {**_CARD, **(_ACTIVE if f["id"] == active_fid else {})}
        folder_tiles.append(html.Div([
            html.Button(
                f["name"],
                id={"type": "pd-folder-activate", "target": f["id"]},
                style={"border": "none", "background": "none", "cursor": "pointer",
                       "padding": "0", "fontSize": "13px"},
            ),
            html.Button("×", id={"type": "pd-folder-delete", "target": f["id"]}, style=_BTN),
        ], style=style))
    folder_tiles.append(html.Button("+ Folder", id="pd-folder-add", style=_BTN))

    tab_tiles = []
    if folder:
        for t in folder["tabs"]:
            style = {**_CARD, **(_ACTIVE if tab and t["id"] == tab["id"] else {})}
            tab_tiles.append(html.Div([
                html.Button(
                    t["name"],
                    id={"type": "pd-tab-activate", "target": t["id"]},
                    style={"border": "none", "background": "none", "cursor": "pointer",
                           "padding": "0", "fontSize": "13px"},
                ),
                html.Button("×", id={"type": "pd-tab-delete", "target": t["id"]}, style=_BTN),
            ], style=style))
        tab_tiles.append(html.Button("+ Tab", id="pd-tab-add", style=_BTN))

    panel_cards = []
    if tab:
        for p in tab["panels"]:
            panel_cards.append(html.Div([
                html.Div(p["name"], style={"fontWeight": "600", "fontSize": "13px"}),
                html.Span(p["kind"], style=_KIND_BADGE),
                html.Div([
                    html.Button("dup", id={"type": "pd-panel-duplicate", "target": p["id"]}, style=_BTN),
                    html.Button("×", id={"type": "pd-panel-delete", "target": p["id"]}, style=_BTN),
                ], style={"display": "flex", "gap": "4px", "marginTop": "auto"}),
            ], style=_PANEL_CARD))

    add_panel_buttons = html.Div([
        html.Button(
            f"+ {k}",
            id={"type": "pd-panel-add", "kind": k},
            style=_BTN,
        ) for k in KINDS
    ], style={"display": "flex", "gap": "6px", "marginTop": "10px"})

    return html.Div([
        html.Div([
            html.Div("Folders", style=_LABEL),
            html.Div(folder_tiles, style=_STRIP),
        ], style=_SECTION),
        html.Div([
            html.Div("Tabs (active folder)", style=_LABEL),
            html.Div(tab_tiles, style=_STRIP) if tab_tiles else html.Div("no folder selected", style={"color": "#999"}),
        ], style=_SECTION),
        html.Div([
            html.Div("Panels (active tab)", style=_LABEL),
            html.Div(panel_cards, style=_GRID) if panel_cards else html.Div("no tab selected", style={"color": "#999"}),
            add_panel_buttons if tab else html.Span(),
        ], style=_SECTION),
    ])


def _render_ld_column(state):
    active_fid = state.get("active_folder")
    folder = _active_folder(state)
    tab = _active_tab(state)

    _label = {"border": "none", "background": "none", "cursor": "pointer",
              "padding": "0", "fontSize": "13px"}

    folder_tiles = []
    for f in state["folders"]:
        style = {**_CARD, **(_ACTIVE if f["id"] == active_fid else {})}
        folder_tiles.append(html.Div([
            Emitter(action="folder.activate", bridge="relay-bridge", target=f["id"]).wrap(
                html.Button(f["name"], style=_label)
            ),
            Emitter(action="folder.delete", bridge="relay-bridge", target=f["id"]).wrap(
                html.Button("×", style=_BTN)
            ),
        ], style=style))
    folder_tiles.append(
        Emitter(action="folder.add", bridge="relay-bridge").wrap(html.Button("+ Folder", style=_BTN))
    )

    tab_tiles = []
    if folder:
        for t in folder["tabs"]:
            style = {**_CARD, **(_ACTIVE if tab and t["id"] == tab["id"] else {})}
            tab_tiles.append(html.Div([
                Emitter(action="tab.activate", bridge="relay-bridge", target=t["id"]).wrap(
                    html.Button(t["name"], style=_label)
                ),
                Emitter(action="tab.delete", bridge="relay-bridge", target=t["id"]).wrap(
                    html.Button("×", style=_BTN)
                ),
            ], style=style))
        tab_tiles.append(
            Emitter(action="tab.add", bridge="relay-bridge").wrap(html.Button("+ Tab", style=_BTN))
        )

    panel_cards = []
    if tab:
        for p in tab["panels"]:
            panel_cards.append(html.Div([
                html.Div(p["name"], style={"fontWeight": "600", "fontSize": "13px"}),
                html.Span(p["kind"], style=_KIND_BADGE),
                html.Div([
                    Emitter(action="panel.duplicate", bridge="relay-bridge", target=p["id"]).wrap(
                        html.Button("dup", style=_BTN)
                    ),
                    Emitter(action="panel.delete", bridge="relay-bridge", target=p["id"]).wrap(
                        html.Button("×", style=_BTN)
                    ),
                ], style={"display": "flex", "gap": "4px", "marginTop": "auto"}),
            ], style=_PANEL_CARD))

    add_panel_buttons = html.Div([
        Emitter(action="panel.add", bridge="relay-bridge", payload={"kind": k}).wrap(
            html.Button(f"+ {k}", style=_BTN)
        )
        for k in KINDS
    ], style={"display": "flex", "gap": "6px", "marginTop": "10px"})

    return html.Div([
        html.Div([
            html.Div("Folders", style=_LABEL),
            html.Div(folder_tiles, style=_STRIP),
        ], style=_SECTION),
        html.Div([
            html.Div("Tabs (active folder)", style=_LABEL),
            html.Div(tab_tiles, style=_STRIP) if tab_tiles else html.Div("no folder selected", style={"color": "#999"}),
        ], style=_SECTION),
        html.Div([
            html.Div("Panels (active tab)", style=_LABEL),
            html.Div(panel_cards, style=_GRID) if panel_cards else html.Div("no tab selected", style={"color": "#999"}),
            add_panel_buttons if tab else html.Span(),
        ], style=_SECTION),
    ])


# ---------------------------------------------------------------------------
# App + console interceptor
# ---------------------------------------------------------------------------


_CONSOLE_JS = r"""
<style>
  .tl-runbtn {
    margin-left: auto;
    padding: 4px 12px;
    background: #111;
    color: white;
    border: 0;
    border-radius: 6px;
    font-size: 12px;
    cursor: pointer;
    font-family: inherit;
  }
  .tl-runbtn:hover { background: #333; }
  .tl-runbtn:disabled { background: #999; cursor: wait; }
  .tl-summary {
    display: flex; gap: 16px; margin-top: 8px;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 11px; color: #555;
  }
  .tl-summary b { color: #111; font-weight: 600; }

  .cmp-panel {
    position: fixed; top: 20px; right: 20px; width: 240px;
    padding: 16px; background: white;
    border: 1px solid #ddd; border-radius: 8px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.06);
    z-index: 100;
    font-family: system-ui, -apple-system, sans-serif; font-size: 12px;
  }
  .cmp-panel h3 { margin: 0 0 10px 0; font-size: 13px; letter-spacing: 0.02em; }
  .cmp-panel .cmp-runbtn {
    display: block; width: 100%;
    padding: 6px 10px; background: #111; color: white; border: 0;
    border-radius: 6px; font-size: 12px; cursor: pointer; font-family: inherit;
  }
  .cmp-panel .cmp-runbtn:hover { background: #333; }
  .cmp-panel .cmp-runbtn:disabled { background: #999; cursor: wait; }
  .cmp-results { margin-top: 14px; display: flex; flex-direction: column; gap: 12px; }
  .cmp-results .cmp-metric { border-top: 1px solid #eee; padding-top: 8px; }
  .cmp-results .cmp-label { color: #666; font-size: 11px; margin-bottom: 2px; }
  .cmp-results .cmp-value {
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 11px; color: #555;
  }
  .cmp-results .cmp-pct { font-size: 22px; font-weight: 700; color: #111; }
  .cmp-results .cmp-dir { font-size: 11px; color: #666; margin-left: 6px; }
  .cmp-results .cmp-win { color: #1f8a4c; }
  .cmp-results .cmp-loss { color: #c43838; }
  .cmp-empty { color: #888; font-style: italic; font-size: 11px; }
  .cmp-runs {
    color: #888; font-size: 10px; text-transform: uppercase;
    letter-spacing: 0.06em; margin-bottom: 2px;
  }
  .tl-row {
    display: flex; align-items: center; gap: 8px;
    padding: 4px 6px; border-bottom: 1px solid #eee;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 11px;
  }
  .tl-row:last-child { border-bottom: none; }
  .tl-badge {
    background: #111; color: white; padding: 2px 8px; border-radius: 10px;
    font-size: 10px; flex-shrink: 0; min-width: 80px; text-align: center;
  }
  .tl-dots { flex: 1; display: flex; flex-wrap: wrap; align-items: center; gap: 3px; }
  .tl-click-dot {
    width: 10px; height: 10px; border-radius: 50%; background: #22c55e;
    box-shadow: 0 0 4px rgba(34, 197, 94, 0.6); display: inline-block;
  }
  .tl-rt-dot {
    width: 8px; height: 8px; border-radius: 50%; background: #ef4444;
    display: inline-block;
    animation: tl-pop 0.3s ease-out;
  }
  @keyframes tl-pop {
    0% { transform: scale(0); opacity: 0; }
    60% { transform: scale(1.4); opacity: 1; }
    100% { transform: scale(1); opacity: 1; }
  }
  .tl-duration {
    color: #666; font-size: 10px; flex-shrink: 0; min-width: 120px; text-align: right;
    font-variant-numeric: tabular-nums;
  }
  .tl-pending .tl-duration { color: #f59e0b; }
  .tl-panel {
    background: white; border: 1px solid #ddd; border-radius: 4px;
    height: 200px; overflow-y: auto; margin-top: 8px;
  }
</style>
<script>
(function () {
  if (window.__nestedSbsInstalled) return;
  window.__nestedSbsInstalled = true;
  var origFetch = window.fetch;
  var tlState = { pd: {row: null, start: 0, timer: null}, relay: {row: null, start: 0, timer: null} };

  function sideOf(out) {
    if (typeof out !== "string") return null;
    if (out.indexOf("pd-") === 0) return "pd";
    if (out.indexOf("relay-") === 0) return "relay";
    return null;
  }

  function sideOfClick(el) {
    var node = el;
    while (node && node.nodeType === 1) {
      if (node.id === "pd-root") return "pd";
      if (node.id === "relay-root") return "relay";
      node = node.parentElement;
    }
    return null;
  }

  function appendRaw(side, line) {
    var el = document.getElementById(side + "-console");
    if (!el) return;
    var div = document.createElement("div");
    div.textContent = line;
    el.appendChild(div);
    el.scrollTop = el.scrollHeight;
    while (el.children.length > 200) el.removeChild(el.firstChild);
  }

  function shortTrig(ids) {
    if (!ids || !ids.length) return "(init)";
    return ids.map(function (s) {
      return s.replace(/"/g, "").replace(/[\{\}]/g, "").replace(/\.n_clicks$/, "");
    }).join(", ");
  }

  function fmtBytes(n) {
    if (n < 1024) return n + " B";
    if (n < 1024 * 1024) return (n / 1024).toFixed(1) + " KB";
    return (n / 1024 / 1024).toFixed(1) + " MB";
  }

  function finalizeRow(side) {
    var st = tlState[side];
    if (!st.row) return;
    // Use last-round-trip timestamp (not now()) so the 600ms idle-finalize
    // window doesn't inflate the reported duration. That way "Total time"
    // reflects real click→last-response latency, not the debounce tail.
    var endTs = st.lastRtTime || st.start;
    var dur = Math.max(0, endTs - st.start);
    var bytes = parseInt(st.row.dataset.bytes || "0", 10);
    var d = st.row.querySelector(".tl-duration");
    if (d) d.textContent = fmtBytes(bytes) + " · " + dur + "ms";
    st.row.classList.remove("tl-pending");
    st.row = null;
    st.lastRtTime = 0;
    if (st.timer) { clearTimeout(st.timer); st.timer = null; }
    // Account the row's real click→last-RT duration against the running total.
    totals[side].time_ms += dur;
    refreshSummary(side);
  }

  function scheduleFinalize(side) {
    var st = tlState[side];
    if (st.timer) clearTimeout(st.timer);
    st.timer = setTimeout(function () { finalizeRow(side); }, 600);
  }

  function startRow(side, label) {
    finalizeRow(side);  // close any pending row
    var tl = document.getElementById(side + "-timeline");
    if (!tl) return;
    var row = document.createElement("div");
    row.className = "tl-row tl-pending";
    row.dataset.bytes = "0";
    var badge = document.createElement("span");
    badge.className = "tl-badge";
    badge.textContent = label;
    var dots = document.createElement("span");
    dots.className = "tl-dots";
    var click = document.createElement("span");
    click.className = "tl-click-dot";
    click.title = "user click";
    dots.appendChild(click);
    var dur = document.createElement("span");
    dur.className = "tl-duration";
    dur.textContent = "...";
    row.appendChild(badge);
    row.appendChild(dots);
    row.appendChild(dur);
    tl.appendChild(row);
    tl.scrollTop = tl.scrollHeight;
    while (tl.children.length > 20) tl.removeChild(tl.firstChild);
    tlState[side].row = row;
    tlState[side].start = Date.now();
    scheduleFinalize(side);
  }

  // Queue of deferred DOM work (dot draws, console appends). We defer these
  // via requestAnimationFrame so instrumentation mutations don't sit inside
  // the per-row timing window — otherwise the side that does more fetches
  // pays more DOM cost and the wall-time delta partly measures ourselves.
  var domQueue = [];
  var domFlushing = false;
  function queueDom(fn) {
    domQueue.push(fn);
    if (domFlushing) return;
    domFlushing = true;
    requestAnimationFrame(function () {
      var q = domQueue; domQueue = []; domFlushing = false;
      for (var i = 0; i < q.length; i++) { try { q[i](); } catch (e) {} }
    });
  }

  function addRoundTrip(side, bytes) {
    var st = tlState[side];
    if (!st.row) {
      // round-trip with no preceding click (e.g. init, or a click we didn't
      // catch) — create an "init" row so the dots still show up somewhere.
      startRow(side, "(init)");
    }
    var row = st.row;
    // Bytes counter update is cheap and needed for finalizeRow readout;
    // dot-draw (DOM mutation) is deferred.
    row.dataset.bytes = String(parseInt(row.dataset.bytes || "0", 10) + bytes);
    queueDom(function () {
      var dots = row.querySelector(".tl-dots");
      if (!dots) return;
      var d = document.createElement("span");
      d.className = "tl-rt-dot";
      d.title = "server round-trip · " + fmtBytes(bytes);
      dots.appendChild(d);
    });
    scheduleFinalize(side);
  }

  // Called when a tracked fetch *resolves* (response received), not when
  // it's initiated. This is what makes the per-row duration reflect
  // click → last-response-received rather than click → last-request-sent.
  function markResponseReceived(side) {
    var st = tlState[side];
    if (!st) return;
    st.lastRtTime = Date.now();
    scheduleFinalize(side);
  }

  // Intercept clicks before Dash sees them so we get clean per-click rows.
  document.addEventListener("click", function (e) {
    var side = sideOfClick(e.target);
    if (!side) return;
    var btn = e.target.closest("button");
    if (!btn) return;
    var label = (btn.textContent || "").trim().replace(/\s+/g, " ").slice(0, 24) || "(click)";
    startRow(side, label);
  }, true);

  // Running totals per side
  var totals = {
    pd: { runs: 0, trips: 0, bytes: 0, time_ms: 0 },
    relay: { runs: 0, trips: 0, bytes: 0, time_ms: 0 },
  };
  function fmtTime(ms) {
    if (ms < 1000) return ms + " ms";
    return (ms / 1000).toFixed(1) + " s";
  }
  function refreshSummary(side) {
    var el = document.getElementById(side + "-summary");
    if (!el) return;
    var t = totals[side];
    el.innerHTML =
      '<span>Tests run: <b>' + t.runs + '</b></span>' +
      '<span>Round-trips: <b>' + t.trips + '</b></span>' +
      '<span>Total: <b>' + fmtBytes(t.bytes) + '</b></span>' +
      '<span>Total time: <b>' + fmtTime(t.time_ms) + '</b></span>';
  }

  window.fetch = function () {
    var args = arguments;
    var url = typeof args[0] === "string" ? args[0] : args[0].url;
    if (!url || url.indexOf("_dash-update-component") < 0) {
      return origFetch.apply(this, args);
    }
    var rawBody = args[1].body || "";
    var bytes = rawBody.length || 0;
    var body = null;
    try { body = JSON.parse(rawBody); } catch (e) {}
    var out = body && body.output;
    var trig = body && body.changedPropIds;
    var side = sideOf(out);
    if (side) {
      var t = new Date();
      var stamp = String(t.getMinutes()).padStart(2, "0") + ":" +
                  String(t.getSeconds()).padStart(2, "0") + "." +
                  String(t.getMilliseconds()).padStart(3, "0");
      var label = (out || "?").split("@")[0];
      var line = stamp + "  " + label + "  (" + fmtBytes(bytes) + ")  <-  " + shortTrig(trig);
      // Console line is a DOM mutation — defer it so the side with more
      // fetches doesn't pay more layout cost inside the timing window.
      queueDom(function () { appendRaw(side, line); });
      addRoundTrip(side, bytes);
      totals[side].trips += 1;
      totals[side].bytes += bytes;
      refreshSummary(side);
    }
    var p = origFetch.apply(this, args);
    if (side) {
      p.then(function () { markResponseReceived(side); },
             function () { markResponseReceived(side); });
    }
    return p;
  };

  // ---- Test runner ----
  // Same sequence fired on both sides. Each step waits long enough for the
  // previous click's round-trips to settle before issuing the next click.
  var TEST_SEQUENCE = [
    { kind: "text", text: "+ Folder" },
    { kind: "text", text: "+ Tab" },
    { kind: "text", text: "+ timeseries" },
    { kind: "text", text: "+ histogram" },
    { kind: "text", text: "+ scatter" },
    { kind: "panel", which: "first", btn: "dup" },
    { kind: "panel", which: "first", btn: "\u00d7" },  // delete first panel
    { kind: "text", text: "+ Folder" },
    { kind: "text", text: "+ timeseries" },
  ];

  function clickByText(side, text) {
    var root = document.getElementById(side + "-root");
    if (!root) return false;
    var btns = root.querySelectorAll("button");
    for (var i = 0; i < btns.length; i++) {
      if (btns[i].textContent.trim() === text) { btns[i].click(); return true; }
    }
    return false;
  }

  function clickFirstPanelButton(side, btnText) {
    var root = document.getElementById(side + "-root");
    if (!root) return false;
    // panel cards are divs that contain a 'Panel p-N' label div
    var divs = root.querySelectorAll("div");
    for (var i = 0; i < divs.length; i++) {
      var d = divs[i];
      var firstChild = d.firstElementChild;
      if (firstChild && /^Panel p-\d+$/.test(firstChild.textContent || "")) {
        var btns = d.querySelectorAll("button");
        for (var j = 0; j < btns.length; j++) {
          if (btns[j].textContent.trim() === btnText) { btns[j].click(); return true; }
        }
      }
    }
    return false;
  }

  function sleep(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }

  async function runTest(side) {
    var btn = document.getElementById(side + "-runbtn");
    if (btn) btn.disabled = true;
    totals[side].runs += 1;
    refreshSummary(side);
    try {
      for (var i = 0; i < TEST_SEQUENCE.length; i++) {
        var step = TEST_SEQUENCE[i];
        if (step.kind === "text") {
          clickByText(side, step.text);
        } else if (step.kind === "panel") {
          clickFirstPanelButton(side, step.btn);
        }
        await sleep(900);
      }
    } finally {
      if (btn) btn.disabled = false;
    }
  }
  window.__runNestedTest = runTest;  // expose for tests

  // ---- Side-by-side comparison: run both tests, aggregate deltas ----
  function snapTotals() {
    return {
      pd: { trips: totals.pd.trips, bytes: totals.pd.bytes, time_ms: totals.pd.time_ms },
      relay: { trips: totals.relay.trips, bytes: totals.relay.bytes, time_ms: totals.relay.time_ms },
    };
  }

  function diff(a, b) {
    return { trips: a.trips - b.trips, bytes: a.bytes - b.bytes, time_ms: a.time_ms - b.time_ms };
  }

  // Cumulative totals across every "Run both tests" click. Percentages
  // stay stable (both sides scale proportionally) but the before→after
  // raw numbers grow with every run, so the panel shows the aggregate.
  var cmpAggregate = {
    runs: 0,
    pd: { trips: 0, bytes: 0, time_ms: 0 },
    relay: { trips: 0, bytes: 0, time_ms: 0 },
  };

  // Returns percent reduction from pd to relay. Positive = relay smaller.
  function pctReduction(pd, relay) {
    if (pd === 0) return relay === 0 ? 0 : -Infinity;
    return Math.round(((pd - relay) / pd) * 100);
  }

  function metricRow(label, pdVal, ldVal, pdFmt, ldFmt, winWord, loseWord) {
    var pct = pctReduction(pdVal, ldVal);
    var cls = pct >= 0 ? "cmp-win" : "cmp-loss";
    var word = pct >= 0 ? winWord : loseWord;
    var shown = pct === -Infinity ? "∞" : Math.abs(pct);
    return '<div class="cmp-metric">' +
      '<div class="cmp-label">' + label + '</div>' +
      '<div><span class="cmp-pct ' + cls + '">' + shown + '%</span>' +
      '<span class="cmp-dir">' + word + ' (Relay)</span></div>' +
      '<div class="cmp-value">' + pdFmt + ' → ' + ldFmt + '</div>' +
      '</div>';
  }

  function renderCompareAggregate() {
    var el = document.getElementById("cmp-results");
    if (!el) return;
    var a = cmpAggregate;
    var runWord = a.runs === 1 ? "run" : "runs";
    el.innerHTML =
      '<div class="cmp-runs">Aggregated over ' + a.runs + ' ' + runWord + '</div>' +
      metricRow("Round-trips", a.pd.trips, a.relay.trips,
                a.pd.trips, a.relay.trips, "fewer", "more") +
      metricRow("Data sent", a.pd.bytes, a.relay.bytes,
                fmtBytes(a.pd.bytes), fmtBytes(a.relay.bytes),
                "less", "more") +
      metricRow("Wall time", a.pd.time_ms, a.relay.time_ms,
                fmtTime(a.pd.time_ms), fmtTime(a.relay.time_ms),
                "faster", "slower");
  }

  async function runBothTests() {
    var cmpBtn = document.getElementById("cmp-runbtn");
    if (cmpBtn) cmpBtn.disabled = true;
    var before = snapTotals();
    await Promise.all([runTest("pd"), runTest("relay")]);
    var after = snapTotals();
    var pdDelta = diff(after.pd, before.pd);
    var relayDelta = diff(after.relay, before.relay);
    cmpAggregate.runs += 1;
    cmpAggregate.pd.trips += pdDelta.trips;
    cmpAggregate.pd.bytes += pdDelta.bytes;
    cmpAggregate.pd.time_ms += pdDelta.time_ms;
    cmpAggregate.relay.trips += relayDelta.trips;
    cmpAggregate.relay.bytes += relayDelta.bytes;
    cmpAggregate.relay.time_ms += relayDelta.time_ms;
    renderCompareAggregate();
    if (cmpBtn) cmpBtn.disabled = false;
  }

  // Wire run buttons once the Dash layout has mounted them.
  var wireTries = 0;
  function tryWire() {
    var pdBtn = document.getElementById("pd-runbtn");
    var relayBtn = document.getElementById("relay-runbtn");
    var cmpBtn = document.getElementById("cmp-runbtn");
    if (pdBtn && relayBtn && cmpBtn) {
      pdBtn.addEventListener("click", function () { runTest("pd"); });
      relayBtn.addEventListener("click", function () { runTest("relay"); });
      cmpBtn.addEventListener("click", function () { runBothTests(); });
      refreshSummary("pd");
      refreshSummary("relay");
      return;
    }
    wireTries += 1;
    if (wireTries < 60) setTimeout(tryWire, 100);
  }
  tryWire();
})();
</script>
"""


app = Dash(__name__, suppress_callback_exceptions=True)
app.index_string = app.index_string.replace("<head>", "<head>" + _CONSOLE_JS, 1)


# ---------------------------------------------------------------------------
# Pure Dash column (approach A done right)
#
# One callback per action type. Dynamic entities use pattern-matching IDs
# (ALL). Each pattern-matching callback uses the canonical guard
# `if not ctx.triggered_id or ctx.triggered[0]["value"] is None: return no_update`
# so phantom fires from changing matched sets don't mutate state. All nine
# action callbacks share the single Output("pd-state","data") with
# allow_duplicate=True.
# ---------------------------------------------------------------------------
# >>> PD-ACTIONS-BEGIN


def _pd_guard():
    """Return True iff this callback was actually triggered by a real click."""
    return bool(ctx.triggered_id) and ctx.triggered and ctx.triggered[0]["value"] is not None


@app.callback(
    Output("pd-root", "children"),
    Input("pd-state", "data"),
)
def pd_render(state):
    return _render_pd_column(state)


@app.callback(
    Output("pd-state", "data", allow_duplicate=True),
    Input("pd-folder-add", "n_clicks"),
    State("pd-state", "data"),
    prevent_initial_call=True,
)
def pd_folder_add(_n, s):
    if _n is None:
        return no_update
    do_folder_add(s)
    return s


@app.callback(
    Output("pd-state", "data", allow_duplicate=True),
    Input({"type": "pd-folder-activate", "target": ALL}, "n_clicks"),
    State("pd-state", "data"),
    prevent_initial_call=True,
)
def pd_folder_activate(_clicks, s):
    if not _pd_guard():
        return no_update
    do_folder_activate(s, ctx.triggered_id["target"])
    return s


@app.callback(
    Output("pd-state", "data", allow_duplicate=True),
    Input({"type": "pd-folder-delete", "target": ALL}, "n_clicks"),
    State("pd-state", "data"),
    prevent_initial_call=True,
)
def pd_folder_delete(_clicks, s):
    if not _pd_guard():
        return no_update
    do_folder_delete(s, ctx.triggered_id["target"])
    return s


@app.callback(
    Output("pd-state", "data", allow_duplicate=True),
    Input("pd-tab-add", "n_clicks"),
    State("pd-state", "data"),
    prevent_initial_call=True,
)
def pd_tab_add(_n, s):
    if _n is None:
        return no_update
    do_tab_add(s)
    return s


@app.callback(
    Output("pd-state", "data", allow_duplicate=True),
    Input({"type": "pd-tab-activate", "target": ALL}, "n_clicks"),
    State("pd-state", "data"),
    prevent_initial_call=True,
)
def pd_tab_activate(_clicks, s):
    if not _pd_guard():
        return no_update
    do_tab_activate(s, ctx.triggered_id["target"])
    return s


@app.callback(
    Output("pd-state", "data", allow_duplicate=True),
    Input({"type": "pd-tab-delete", "target": ALL}, "n_clicks"),
    State("pd-state", "data"),
    prevent_initial_call=True,
)
def pd_tab_delete(_clicks, s):
    if not _pd_guard():
        return no_update
    do_tab_delete(s, ctx.triggered_id["target"])
    return s


@app.callback(
    Output("pd-state", "data", allow_duplicate=True),
    Input({"type": "pd-panel-add", "kind": ALL}, "n_clicks"),
    State("pd-state", "data"),
    prevent_initial_call=True,
)
def pd_panel_add(_clicks, s):
    if not _pd_guard():
        return no_update
    do_panel_add(s, ctx.triggered_id["kind"])
    return s


@app.callback(
    Output("pd-state", "data", allow_duplicate=True),
    Input({"type": "pd-panel-delete", "target": ALL}, "n_clicks"),
    State("pd-state", "data"),
    prevent_initial_call=True,
)
def pd_panel_delete(_clicks, s):
    if not _pd_guard():
        return no_update
    do_panel_delete(s, ctx.triggered_id["target"])
    return s


@app.callback(
    Output("pd-state", "data", allow_duplicate=True),
    Input({"type": "pd-panel-duplicate", "target": ALL}, "n_clicks"),
    State("pd-state", "data"),
    prevent_initial_call=True,
)
def pd_panel_duplicate(_clicks, s):
    if not _pd_guard():
        return no_update
    do_panel_duplicate(s, ctx.triggered_id["target"])
    return s


# <<< PD-ACTIONS-END


# ---------------------------------------------------------------------------
# Dash Relay column
#
# One bridge. One dispatch callback (registered by relay.install). One renderer.
# Nine handlers registered via @relay.callback against the bridge, each just
# calls the shared do_* helper. The callback graph is the same whether we
# have 9 actions or 90.
# ---------------------------------------------------------------------------
# >>> RELAY-ACTIONS-BEGIN


_RELAY_OUTPUT = Output("relay-state", "data")
_RELAY_STATE = State("relay-state", "data")


def _relay_state(s):
    return deepcopy(s) if s is not None else initial_state()


@relay.callback(_RELAY_OUTPUT, Action("folder.add", bridge="relay-bridge"), _RELAY_STATE)
def _(event, s):
    s = _relay_state(s)
    do_folder_add(s)
    return s


@relay.callback(_RELAY_OUTPUT, Action("folder.activate", bridge="relay-bridge"), _RELAY_STATE)
def _(event, s):
    s = _relay_state(s)
    do_folder_activate(s, event["target"])
    return s


@relay.callback(_RELAY_OUTPUT, Action("folder.delete", bridge="relay-bridge"), _RELAY_STATE)
def _(event, s):
    s = _relay_state(s)
    do_folder_delete(s, event["target"])
    return s


@relay.callback(_RELAY_OUTPUT, Action("tab.add", bridge="relay-bridge"), _RELAY_STATE)
def _(event, s):
    s = _relay_state(s)
    do_tab_add(s)
    return s


@relay.callback(_RELAY_OUTPUT, Action("tab.activate", bridge="relay-bridge"), _RELAY_STATE)
def _(event, s):
    s = _relay_state(s)
    do_tab_activate(s, event["target"])
    return s


@relay.callback(_RELAY_OUTPUT, Action("tab.delete", bridge="relay-bridge"), _RELAY_STATE)
def _(event, s):
    s = _relay_state(s)
    do_tab_delete(s, event["target"])
    return s


@relay.callback(_RELAY_OUTPUT, Action("panel.add", bridge="relay-bridge"), _RELAY_STATE)
def _(event, s):
    s = _relay_state(s)
    do_panel_add(s, (event.get("payload") or {}).get("kind", "timeseries"))
    return s


@relay.callback(_RELAY_OUTPUT, Action("panel.delete", bridge="relay-bridge"), _RELAY_STATE)
def _(event, s):
    s = _relay_state(s)
    do_panel_delete(s, event["target"])
    return s


@relay.callback(_RELAY_OUTPUT, Action("panel.duplicate", bridge="relay-bridge"), _RELAY_STATE)
def _(event, s):
    s = _relay_state(s)
    do_panel_duplicate(s, event["target"])
    return s


@app.callback(Output("relay-root", "children"), Input("relay-state", "data"))
def ld_render(state):
    return _render_ld_column(state)


# <<< RELAY-ACTIONS-END


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------


_CONSOLE_STYLE = {
    "fontFamily": "ui-monospace, SFMono-Regular, Menlo, monospace",
    "fontSize": "11px",
    "background": "#0e1014",
    "color": "#9eff9e",
    "padding": "8px 10px",
    "height": "140px",
    "overflowY": "auto",
    "borderRadius": "4px",
    "border": "1px solid #2a2a2a",
    "marginTop": "4px",
    "lineHeight": "1.5",
}


# Count callbacks once at startup for each side. We re-filter the map by
# output-id prefix so the numbers are honest.
def _count_callbacks(prefix):
    count = 0
    for key in app.callback_map.keys():
        # Multi-output keys look like "out1...out2"; single like "pd-state.data"
        if prefix in key:
            count += 1
    return count


# Count the lines of code that WIRE each column's UI to its mutation helpers.
# We measure the sections between marker comments so the numbers track the
# file as it evolves.
def _count_source_lines(begin_marker, end_marker):
    try:
        text = Path(__file__).read_text(encoding="utf-8")
    except OSError:
        return 0
    lines = text.splitlines()
    begin = end = None
    for i, line in enumerate(lines):
        if begin is None and begin_marker in line:
            begin = i
        elif end is None and end_marker in line:
            end = i
            break
    if begin is None or end is None:
        return 0
    # Count non-blank, non-pure-comment lines in between
    count = 0
    for line in lines[begin + 1:end]:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        count += 1
    return count


_PD_CB_COUNT = _count_callbacks("pd-")
_RELAY_CB_COUNT = _count_callbacks("relay-")
# Dash Relay also has per-action handlers registered via @relay.callback(...).
# They're not in the Dash callback graph (one Dash dispatch callback per
# bridge routes to all of them by action name), so they don't inflate
# phantom-fire cost the way pattern-matching callbacks do. But they're
# still code we wrote.
# Counted from the pending pool BEFORE relay.install(app) drains it.
from dash_relay.callback import _PENDING_CALLBACKS as _relay_pending
_RELAY_HANDLER_COUNT = sum(
    1 for h in _relay_pending
    if any(a.name.split(".")[0] in ("folder", "tab", "panel") for a in h.actions)
)
_PD_LINES = _count_source_lines("PD-ACTIONS-BEGIN", "PD-ACTIONS-END")
_RELAY_LINES = _count_source_lines("RELAY-ACTIONS-BEGIN", "RELAY-ACTIONS-END")


def _column(title, badges, root_id, timeline_id, console_id, summary_id, runbtn_id):
    stat_style = {"fontSize": "11px", "color": "#666",
                  "fontFamily": "ui-monospace, monospace",
                  "padding": "2px 8px", "background": "#eee", "borderRadius": "10px",
                  "whiteSpace": "nowrap", "flexShrink": 0}
    return html.Div([
        html.Div([
            html.H2(title, style={"margin": 0, "whiteSpace": "nowrap", "flexShrink": 0}),
            *[html.Span(b, style=stat_style) for b in badges],
            html.Button("\u25b6 Run test", id=runbtn_id, className="tl-runbtn",
                        style={"whiteSpace": "nowrap", "flexShrink": 0}),
        ], style={"display": "flex", "alignItems": "center", "gap": "8px",
                  "marginBottom": "16px", "flexWrap": "wrap"}),
        html.Div(id=root_id),
        html.Hr(),
        html.Div([
            html.Span("click timeline", style={"fontSize": "12px", "color": "#666"}),
            html.Span(
                "  ● user click    ● server round-trip",
                style={"fontSize": "11px", "color": "#888", "marginLeft": "12px"},
            ),
        ]),
        html.Div(id=timeline_id, className="tl-panel"),
        html.Div(id=summary_id, className="tl-summary"),
        html.Div(
            "raw callback log (live):",
            style={"fontSize": "12px", "color": "#666", "marginTop": "12px"},
        ),
        html.Div(id=console_id, style=_CONSOLE_STYLE),
    ], style={
        "padding": "20px",
        "border": "1px solid #ddd",
        "borderRadius": "8px",
        "background": "#fafafa",
        "flex": 1,
        "minWidth": 0,
    })


_compare_panel = html.Div(
    [
        html.H3("Head-to-head"),
        html.Button("\u25b6 Run both tests", id="cmp-runbtn", className="cmp-runbtn"),
        html.Div(
            html.Div("Click to run the same 9-step test on both sides.",
                     className="cmp-empty"),
            id="cmp-results",
            className="cmp-results",
        ),
    ],
    className="cmp-panel",
)


app.layout = html.Div([
    _compare_panel,
    html.H1(
        "Dynamically Generated Nested Components: Pure Dash vs. Dash Relay",
        style={"marginBottom": "4px"},
    ),
    html.P(
        "Folders contain tabs, tabs contain panels. Nine action types across "
        "three entity levels. Both columns run the same mutation logic; only "
        "the wiring between the UI and that logic differs.",
        style={"color": "#555", "marginTop": 0, "marginBottom": "20px"},
    ),
    dcc.Store(id="pd-state", data=initial_state()),
    dcc.Store(id="relay-state", data=initial_state()),
    html.Div([
        _column(
            "Pure Dash",
            [f"{_PD_CB_COUNT} callbacks", f"{_PD_LINES} lines of wiring"],
            "pd-root", "pd-timeline", "pd-console", "pd-summary", "pd-runbtn",
        ),
        _column(
            "Dash Relay",
            [f"{_RELAY_CB_COUNT} callbacks + {_RELAY_HANDLER_COUNT} handlers",
             f"{_RELAY_LINES} lines of wiring"],
            "relay-root", "relay-timeline", "relay-console", "relay-summary", "relay-runbtn",
        ),
    ], style={"display": "flex", "gap": "20px", "alignItems": "stretch"}),
], style={
    "fontFamily": "system-ui, -apple-system, sans-serif",
    "padding": "24px",
    "paddingRight": "290px",  # keep content clear of the fixed compare panel
    "maxWidth": "1700px",
    "margin": "0 auto",
})


# install() drains the @relay.callback pool registered above, mints the
# bridge stores, registers the JS runtime + Flask route, and wires one
# dispatcher Dash callback per bridge.
relay.install(app)


if __name__ == "__main__":
    app.run(debug=True)
