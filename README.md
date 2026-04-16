# Liquid Dash

A tiny layer for building **dynamic Dash interfaces** without wiring a
callback per interactive element.

![Liquid Dash demo](examples/workspace_demo/liquid-dash-demo.gif)

## Why it exists

Dash is great when your layout is mostly static. It gets awkward once
parts of the UI are rebuilt at runtime, when the same interaction pattern
repeats in many places, or when interactive elements live inside regions
that come and go.

Liquid Dash moves UI events off the Dash callback graph and onto a
single client-side bridge. You wrap existing Dash components with one
call; events flow into a `dcc.Store`; one server-side handler dispatches
them. Layouts can be rerendered freely without touching the callback
graph.

## The whole surface

```python
import liquid_dash as ld

ld.melt(app)                     # install the client-side runtime once
ld.bridge()                      # a dcc.Store sink (put it in the layout)
ld.on(component, action, ...)    # attach an event to any Dash component
ld.handler(app, state="...")     # registry for server-side handlers
ld.validate(layout)              # optional linter
```

Five names. That's it.

## A complete app

```python
from copy import deepcopy
from dash import Dash, Input, Output, dcc, html
import liquid_dash as ld

app = Dash(__name__)
ld.melt(app)

events = ld.handler(app, state="state")


@events.on("add")
def _(state, payload, event):
    state["items"].append({"id": len(state["items"]) + 1, "text": state["draft"]})
    state["draft"] = ""


@events.on("delete")
def _(state, payload, event):
    state["items"] = [t for t in state["items"] if t["id"] != event["target"]]


@events.on("draft")
def _(state, payload, event):
    state["draft"] = event["native"].get("value", "")


app.layout = html.Div([
    dcc.Store(id="state", data={"draft": "", "items": []}),
    ld.bridge(),
    ld.on(dcc.Input(placeholder="New task..."), "draft", event="input"),
    ld.on(html.Button("Add"), "add"),
    html.Ul(id="list"),
])


@app.callback(Output("list", "children"), Input("state", "data"))
def render(s):
    return [
        html.Li([
            html.Span(t["text"]),
            ld.on(html.Button("x"), "delete", target=t["id"]),
        ]) for t in s["items"]
    ]


if __name__ == "__main__":
    app.run(debug=True)
```

## The pieces

**`ld.melt(app)`** — installs a ~120-line client-side script that watches
the DOM for elements carrying `data-ld-event` attributes and lazily binds
document-level listeners for whatever DOM events it finds. No event
whitelist: `"click"`, `"input"`, `"change"`, `"submit"`, `"dblclick"`,
`"contextmenu"`, `"pointerdown"`, or any other DOM event string works
out of the box.

**`ld.bridge(id="bridge")`** — returns a `dcc.Store` with an id matching
the default that `on()` and `handler()` target. Drop it in the layout.
Name it explicitly (`ld.bridge("analytics")`) if you need more than one.

**`ld.on(component, action, ...)`** — wraps a Dash component in a
transparent `display: contents` div carrying the event metadata. Works
with `html.*`, `dcc.*`, and third-party components alike because the
wrapper owns the data attributes. Accepts:

- `payload=` — JSON-serializable value passed to the handler
- `event=` — DOM event name (default `"click"`)
- `to=` — target bridge id (default `"bridge"`)
- `target=`, `source=` — optional context values on the event
  (any JSON-serializable; types round-trip to the handler)
- `prevent_default=True` — calls `event.preventDefault()` client-side

Curried form: `ld.on(action, ...)` with no component returns a reusable
emitter, convenient for list rendering:

```python
delete = ld.on("delete")
[delete(html.Button("x"), payload={"id": t["id"]}) for t in items]
```

**`ld.handler(app, state="store_id")`** — registers one internal Dash
callback wired from the bridge to the state store. Register per-action
handlers with `@events.on("action")`. Handlers have signature
`(state, payload, event) -> new_state | None`:

- `state` — a deep copy of the state store (safe to mutate)
- `payload` — the user-defined payload from `ld.on(..., payload=...)`
- `event` — the full Liquid Dash event dict
  (`action`, `target`, `source`, `event_type`, `native`, `timestamp`)

`event["native"]` carries browser-level fields extracted from the
original DOM event: `value`, `checked`, `key`, `clientX/Y`, `deltaX/Y`,
etc. Pick whatever you need.

For apps that don't fit the single-state-store shape (e.g. multiple
stores updated from one bridge), skip `handler()` and write a normal
`@app.callback(Input("bridge", "data"), ...)`.

**`ld.validate(layout)`** — walks the layout and reports duplicate ids,
empty actions, and actions targeting bridge ids with no matching
`dcc.Store`. Optional. Run it during development.

## Installation

```bash
pip install liquid-dash
```

## Examples

```bash
python examples/live_test/app.py       # simple panel playground
python examples/workspace_demo/app.py  # nested folders/tabs/panels
```

## Development

```bash
pip install -e .
pytest
```

## License

MIT
