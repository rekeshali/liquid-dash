"""Pure-Dash version of a toggleable, filterable, growable list.

This file is INTENTIONALLY buggy. See README.md for the three bugs and
what they look like in the dev tools callback panel.

Run:
    python examples/pure_dash_pitfall/pure_dash.py
Then watch /dash-update-component activity in browser dev tools while you:
    1. Click "Add item" once   ->  do_delete and do_toggle each fire
    2. Toggle filter, then back ->  same: callbacks fire on remount
    3. Click "Add item" rapidly ->  watch updates race
"""
from __future__ import annotations

from dash import ALL, Dash, Input, Output, State, ctx, dcc, html, no_update


app = Dash(__name__)

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
        html.Div(
            [
                html.Button("Toggle filter (all <-> open)", id="filter-toggle"),
                html.Button("Add item", id="add"),
            ],
            style={"display": "flex", "gap": "8px", "marginBottom": "12px"},
        ),
        html.Div(id="list"),
        html.Hr(),
        html.Pre(
            "Open dev tools -> Network -> filter on '_dash-update-component' "
            "and watch the callback panel as you click. Even when nothing "
            "changes meaningfully, callbacks fire.",
            style={"whiteSpace": "pre-wrap", "color": "#666"},
        ),
    ],
    style={"fontFamily": "sans-serif", "padding": "24px"},
)


@app.callback(Output("list", "children"), Input("state", "data"))
def render(state):
    visible = (
        state["items"]
        if state["filter"] == "all"
        else [i for i in state["items"] if not i["done"]]
    )
    return [
        html.Div(
            [
                html.Span(f"#{i['id']} {i['text']} {'(done)' if i['done'] else ''}",
                          style={"flex": 1}),
                html.Button("toggle", id={"type": "toggle", "index": i["id"]}),
                html.Button("x", id={"type": "del", "index": i["id"]}),
            ],
            style={"display": "flex", "gap": "8px", "padding": "4px 0"},
            key=str(i["id"]),
        )
        for i in visible
    ]


@app.callback(
    Output("state", "data"),
    Input("filter-toggle", "n_clicks"),
    State("state", "data"),
    prevent_initial_call=True,
)
def do_filter(_n, s):
    s["filter"] = "open" if s["filter"] == "all" else "all"
    return s


@app.callback(
    Output("state", "data", allow_duplicate=True),
    Input("add", "n_clicks"),
    State("state", "data"),
    prevent_initial_call=True,
)
def do_add(_n, s):
    nid = max((i["id"] for i in s["items"]), default=0) + 1
    s["items"].append({"id": nid, "text": f"Item {nid}", "done": False})
    return s


@app.callback(
    Output("state", "data", allow_duplicate=True),
    Input({"type": "del", "index": ALL}, "n_clicks"),
    State("state", "data"),
    prevent_initial_call=True,
)
def do_delete(_clicks, s):
    if not ctx.triggered_id:
        return no_update
    tid = ctx.triggered_id["index"]
    s["items"] = [i for i in s["items"] if i["id"] != tid]
    return s


@app.callback(
    Output("state", "data", allow_duplicate=True),
    Input({"type": "toggle", "index": ALL}, "n_clicks"),
    State("state", "data"),
    prevent_initial_call=True,
)
def do_toggle(_clicks, s):
    if not ctx.triggered_id:
        return no_update
    tid = ctx.triggered_id["index"]
    for i in s["items"]:
        if i["id"] == tid:
            i["done"] = not i["done"]
    return s


if __name__ == "__main__":
    app.run(debug=True)
