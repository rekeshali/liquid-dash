"""Pure Dash and Liquid Dash side by side, in one Dash app.

Two implementations of the same toggleable, filterable, growable list,
mounted in two columns. Each column has an in-page console that logs
every `_dash-update-component` fire attributed to its side, so you can
*watch* callback activity per click instead of squinting at dev tools.

Run:
    python examples/pure_dash_pitfall/side_by_side.py

Click "Add item" once on each side and compare the consoles. The
pure-Dash column fires multiple callbacks per click (including extra
fires triggered by remounted ALL-pattern subscribers); the Liquid Dash
column fires exactly two (bridge dispatch + renderer).
"""
from __future__ import annotations

import sys
from pathlib import Path

from dash import ALL, Dash, Input, Output, State, ctx, dcc, html, no_update

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import liquid_dash as ld


_INITIAL_ITEMS = [
    {"id": 1, "text": "Write docs", "done": False},
    {"id": 2, "text": "Ship v1", "done": True},
]


# Injected into <head> so the fetch interceptor is in place before the
# Dash renderer makes its first network call. Each `_dash-update-component`
# request is parsed, attributed to a side by output id prefix (pd- vs ld-),
# and appended to that side's console panel. Ground truth — what the
# console shows is exactly what hit the wire.
_CONSOLE_JS = r"""
<script>
(function () {
  if (window.__sideBySideInstalled) return;
  window.__sideBySideInstalled = true;
  var origFetch = window.fetch;
  function append(side, line) {
    var el = document.getElementById(side + "-console");
    if (!el) return;
    var div = document.createElement("div");
    div.textContent = line;
    el.appendChild(div);
    el.scrollTop = el.scrollHeight;
    while (el.children.length > 120) el.removeChild(el.firstChild);
  }
  function sideOf(out) {
    if (typeof out !== "string") return null;
    if (out.indexOf("pd-") === 0) return "pd";
    if (out.indexOf("ld-") === 0) return "ld";
    return null;
  }
  function shortTrig(ids) {
    if (!ids || !ids.length) return "(init)";
    return ids.map(function (s) {
      return s.replace(/"/g, "").replace(/[\{\}]/g, "");
    }).join(", ");
  }
  window.fetch = function () {
    var args = arguments;
    var url = typeof args[0] === "string" ? args[0] : args[0].url;
    if (!url || url.indexOf("_dash-update-component") < 0) {
      return origFetch.apply(this, args);
    }
    var body = null;
    try { body = JSON.parse(args[1].body); } catch (e) {}
    var out = body && body.output;
    var trig = body && body.changedPropIds;
    var side = sideOf(out);
    if (side) {
      var t = new Date();
      var stamp = String(t.getMinutes()).padStart(2, "0") + ":" +
                  String(t.getSeconds()).padStart(2, "0") + "." +
                  String(t.getMilliseconds()).padStart(3, "0");
      var label = (out || "?").split("@")[0];
      append(side, stamp + "  " + label + "  <-  " + shortTrig(trig));
    }
    return origFetch.apply(this, args);
  };
})();
</script>
"""


app = Dash(__name__)
ld.melt(app)
app.index_string = app.index_string.replace("<head>", "<head>" + _CONSOLE_JS, 1)


# ---------------------------------------------------------------------------
# Pure-Dash column (id prefix: pd-)
# ---------------------------------------------------------------------------


@app.callback(Output("pd-list", "children"), Input("pd-state", "data"))
def pd_render(state):
    visible = (
        state["items"]
        if state["filter"] == "all"
        else [i for i in state["items"] if not i["done"]]
    )
    return [
        html.Div(
            [
                html.Span(
                    f"#{i['id']} {i['text']} {'(done)' if i['done'] else ''}",
                    style={"flex": 1},
                ),
                html.Button("toggle", id={"type": "pd-toggle", "index": i["id"]}),
                html.Button("x", id={"type": "pd-del", "index": i["id"]}),
            ],
            style={"display": "flex", "gap": "8px", "padding": "4px 0"},
            key=str(i["id"]),
        )
        for i in visible
    ]


@app.callback(
    Output("pd-state", "data"),
    Input("pd-filter", "n_clicks"),
    State("pd-state", "data"),
    prevent_initial_call=True,
)
def pd_filter(_n, s):
    s["filter"] = "open" if s["filter"] == "all" else "all"
    return s


@app.callback(
    Output("pd-state", "data", allow_duplicate=True),
    Input("pd-add", "n_clicks"),
    State("pd-state", "data"),
    prevent_initial_call=True,
)
def pd_add(_n, s):
    nid = max((i["id"] for i in s["items"]), default=0) + 1
    s["items"].append({"id": nid, "text": f"Item {nid}", "done": False})
    return s


@app.callback(
    Output("pd-state", "data", allow_duplicate=True),
    Input({"type": "pd-del", "index": ALL}, "n_clicks"),
    State("pd-state", "data"),
    prevent_initial_call=True,
)
def pd_delete(_clicks, s):
    if not ctx.triggered_id:
        return no_update
    tid = ctx.triggered_id["index"]
    s["items"] = [i for i in s["items"] if i["id"] != tid]
    return s


@app.callback(
    Output("pd-state", "data", allow_duplicate=True),
    Input({"type": "pd-toggle", "index": ALL}, "n_clicks"),
    State("pd-state", "data"),
    prevent_initial_call=True,
)
def pd_toggle(_clicks, s):
    if not ctx.triggered_id:
        return no_update
    tid = ctx.triggered_id["index"]
    for i in s["items"]:
        if i["id"] == tid:
            i["done"] = not i["done"]
    return s


# ---------------------------------------------------------------------------
# Liquid Dash column (id prefix: ld-)
# ---------------------------------------------------------------------------


events = ld.handler(app, state="ld-state", bridge="ld-bridge")


@events.on("filter")
def _(s, payload, event):
    s["filter"] = "open" if s["filter"] == "all" else "all"


@events.on("add")
def _(s, payload, event):
    nid = max((i["id"] for i in s["items"]), default=0) + 1
    s["items"].append({"id": nid, "text": f"Item {nid}", "done": False})


@events.on("del")
def _(s, payload, event):
    tid = event["target"]
    s["items"] = [i for i in s["items"] if i["id"] != tid]


@events.on("toggle")
def _(s, payload, event):
    tid = event["target"]
    for i in s["items"]:
        if i["id"] == tid:
            i["done"] = not i["done"]


@app.callback(Output("ld-list", "children"), Input("ld-state", "data"))
def ld_render(s):
    visible = (
        s["items"]
        if s["filter"] == "all"
        else [i for i in s["items"] if not i["done"]]
    )
    return [
        html.Div(
            [
                html.Span(
                    f"#{i['id']} {i['text']} {'(done)' if i['done'] else ''}",
                    style={"flex": 1},
                ),
                ld.on(html.Button("toggle"), "toggle", target=i["id"], to="ld-bridge"),
                ld.on(html.Button("x"), "del", target=i["id"], to="ld-bridge"),
            ],
            style={"display": "flex", "gap": "8px", "padding": "4px 0"},
        )
        for i in visible
    ]


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------


def _initial_state():
    return {"filter": "all", "items": [dict(i) for i in _INITIAL_ITEMS]}


_console_style = {
    "fontFamily": "ui-monospace, SFMono-Regular, Menlo, monospace",
    "fontSize": "11px",
    "background": "#0e1014",
    "color": "#9eff9e",
    "padding": "8px 10px",
    "height": "200px",
    "overflowY": "auto",
    "borderRadius": "4px",
    "border": "1px solid #2a2a2a",
    "marginTop": "8px",
    "lineHeight": "1.5",
}


def _column(title, controls, list_id, console_id):
    return html.Div(
        [
            html.H2(title, style={"margin": "0 0 12px 0"}),
            html.Div(controls, style={"display": "flex", "gap": "8px", "marginBottom": "8px"}),
            html.Div(id=list_id, style={"minHeight": "120px"}),
            html.Hr(),
            html.Div(
                "callback activity (live):",
                style={"fontSize": "12px", "color": "#666", "marginBottom": "4px"},
            ),
            html.Div(id=console_id, style=_console_style),
        ],
        style={
            "padding": "20px",
            "border": "1px solid #ddd",
            "borderRadius": "8px",
            "background": "#fafafa",
            "flex": 1,
        },
    )


app.layout = html.Div(
    [
        html.H1(
            "Dynamically Generated Components: Pure Dash vs. Liquid Dash",
            style={"marginBottom": "4px"},
        ),
        html.P(
            "Same UX, two implementations. Each column logs every "
            "_dash-update-component fire to its own console. Click around "
            "and compare callback activity per interaction.",
            style={"color": "#555", "marginTop": 0, "marginBottom": "20px"},
        ),
        dcc.Store(id="pd-state", data=_initial_state()),
        dcc.Store(id="ld-state", data=_initial_state()),
        ld.bridge("ld-bridge"),
        html.Div(
            [
                _column(
                    "Pure Dash",
                    [
                        html.Button("Toggle filter (all <-> open)", id="pd-filter"),
                        html.Button("Add item", id="pd-add"),
                    ],
                    "pd-list",
                    "pd-console",
                ),
                _column(
                    "Liquid Dash",
                    [
                        ld.on(html.Button("Toggle filter (all <-> open)"), "filter", to="ld-bridge"),
                        ld.on(html.Button("Add item"), "add", to="ld-bridge"),
                    ],
                    "ld-list",
                    "ld-console",
                ),
            ],
            style={"display": "flex", "gap": "20px", "alignItems": "stretch"},
        ),
    ],
    style={
        "fontFamily": "system-ui, -apple-system, sans-serif",
        "padding": "24px",
        "maxWidth": "1400px",
        "margin": "0 auto",
    },
)


if __name__ == "__main__":
    app.run(debug=True)
