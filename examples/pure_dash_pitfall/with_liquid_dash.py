"""Equivalent app, written with liquid-dash.

Same behavior as pure_dash.py, but:
  - one writer to the state store (no allow_duplicate races)
  - no pattern-matching subscriptions that fire on remount
  - actions are sent on the DOM event itself, not derived from n_clicks

Run:
    python examples/pure_dash_pitfall/with_liquid_dash.py

(File is named with_liquid_dash.py rather than liquid_dash.py so that
`import liquid_dash` inside it doesn't shadow the installed package.)
"""
from __future__ import annotations

from pathlib import Path
import sys

from dash import Dash, Input, Output, dcc, html

# Allow running directly from the source tree.
ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import liquid_dash as ld


app = Dash(__name__)
ld.melt(app)

events = ld.handler(app, state="state")


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


app.layout = html.Div(
    [
        dcc.Store(
            id="state",
            data={
                "filter": "all",
                "items": [
                    {"id": 1, "text": "Write docs", "done": False},
                    {"id": 2, "text": "Ship v1", "done": True},
                ],
            },
        ),
        ld.bridge(),
        html.Div(
            [
                ld.on(html.Button("Toggle filter (all <-> open)"), "filter"),
                ld.on(html.Button("Add item"), "add"),
            ],
            style={"display": "flex", "gap": "8px", "marginBottom": "12px"},
        ),
        html.Div(id="list"),
        html.Hr(),
        html.Pre(
            "Open dev tools and watch /dash-update-component activity. "
            "Adding items, toggling the filter, and remounting rows produce "
            "exactly one server callback per actual user click.",
            style={"whiteSpace": "pre-wrap", "color": "#666"},
        ),
    ],
    style={"fontFamily": "sans-serif", "padding": "24px"},
)


@app.callback(Output("list", "children"), Input("state", "data"))
def render(s):
    visible = (
        s["items"]
        if s["filter"] == "all"
        else [i for i in s["items"] if not i["done"]]
    )
    return [
        html.Div(
            [
                html.Span(f"#{i['id']} {i['text']} {'(done)' if i['done'] else ''}",
                          style={"flex": 1}),
                ld.on(html.Button("toggle"), "toggle", target=i["id"]),
                ld.on(html.Button("x"), "del", target=i["id"]),
            ],
            style={"display": "flex", "gap": "8px", "padding": "4px 0"},
        )
        for i in visible
    ]


if __name__ == "__main__":
    app.run(debug=True)
