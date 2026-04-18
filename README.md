# Dash Relay

A tiny layer for building **dynamic Dash interfaces** without wiring a
callback per interactive element.

![Dash Relay demo](examples/workspace_demo/dash-relay-demo.gif)

## Why it exists

For layouts where regions are rebuilt at runtime, the same interaction
pattern repeats in many places, or interactive elements live inside
regions that come and go, the amount of callback wiring can grow
faster than the UI itself — pattern-matching callbacks, canonical
guards, and `allow_duplicate` coordination across many writers.

Dash Relay moves UI events off the Dash callback graph and onto a
single client-side bridge. You wrap existing Dash components with one
call; events flow into a `dcc.Store`; one server-side registry
dispatches them to handlers by action name. Layouts can be rerendered
freely without touching the callback graph. The pattern-matching
approach stays cleaner for static layouts; the bridge earns its keep
once things start moving.

## The whole surface

```python
import dash_relay as relay

relay.install(app)                      # install the client-side runtime once
relay.bridge()                          # a dcc.Store sink (put it in the layout)
relay.emitter(component, action, ...)   # wrap a component as an event emitter
relay.registry(app, state="...")        # registry for server-side handlers
relay.validate(layout)                  # optional linter
```

Five names. That's it.

## A complete app

```python
from copy import deepcopy
from dash import Dash, Input, Output, dcc, html
import dash_relay as relay

app = Dash(__name__)
relay.install(app)

events = relay.registry(app, state="state")


@events.handle("add")
def _(state, payload, event):
    state["items"].append({"id": len(state["items"]) + 1, "text": state["draft"]})
    state["draft"] = ""


@events.handle("delete")
def _(state, payload, event):
    state["items"] = [t for t in state["items"] if t["id"] != event["target"]]


@events.handle("draft")
def _(state, payload, event):
    state["draft"] = event["native"].get("value", "")


app.layout = html.Div([
    dcc.Store(id="state", data={"draft": "", "items": []}),
    relay.bridge(),
    relay.emitter(dcc.Input(placeholder="New task..."), "draft", event="input"),
    relay.emitter(html.Button("Add"), "add"),
    html.Ul(id="list"),
])


@app.callback(Output("list", "children"), Input("state", "data"))
def render(s):
    return [
        html.Li([
            html.Span(t["text"]),
            relay.emitter(html.Button("x"), "delete", target=t["id"]),
        ]) for t in s["items"]
    ]


if __name__ == "__main__":
    app.run(debug=True)
```

## The pieces

**`relay.install(app)`** — installs a ~120-line client-side script that
watches the DOM for elements carrying `data-relay-event` attributes and
lazily binds document-level listeners for whatever DOM events it finds.
No event whitelist: `"click"`, `"input"`, `"change"`, `"submit"`,
`"dblclick"`, `"contextmenu"`, `"pointerdown"`, or any other DOM event
string works out of the box.

**`relay.bridge(id="bridge")`** — returns a `dcc.Store` with an id
matching the default that `emitter()` and `registry()` target. Drop it
in the layout. Name it explicitly (`relay.bridge("analytics")`) if you
need more than one.

**`relay.emitter(component, action, ...)`** — wraps a Dash component in
a transparent `display: contents` div carrying the event metadata.
Works with `html.*`, `dcc.*`, and third-party components alike because
the wrapper owns the data attributes. Accepts:

- `payload=` — JSON-serializable value passed to the handler
- `event=` — DOM event name (default `"click"`)
- `to=` — target bridge id (default `"bridge"`)
- `target=`, `source=` — optional context values on the event
  (any JSON-serializable; types round-trip to the handler)
- `prevent_default=True` — calls `event.preventDefault()` client-side

Curried form: `relay.emitter(action, ...)` with no component returns a
reusable emitter factory, convenient for list rendering:

```python
delete = relay.emitter("delete")
[delete(html.Button("x"), payload={"id": t["id"]}) for t in items]
```

**`relay.registry(app, state="store_id")`** — registers one internal
Dash callback wired from the bridge to the state store. Register
per-action handlers with `@events.handle("action")`. Handlers have
signature `(state, payload, event) -> new_state | None`:

- `state` — a deep copy of the state store (safe to mutate)
- `payload` — the user-defined payload from `relay.emitter(..., payload=...)`
- `event` — the full Dash Relay event dict
  (`action`, `target`, `source`, `event_type`, `native`, `timestamp`)

`event["native"]` carries browser-level fields extracted from the
original DOM event: `value`, `checked`, `key`, `clientX/Y`, `deltaX/Y`,
etc. Pick whatever you need.

For apps that don't fit the single-state-store shape (e.g. multiple
stores updated from one bridge), skip `registry()` and write a normal
`@app.callback(Input("bridge", "data"), ...)`.

**`relay.validate(layout)`** — walks the layout and reports duplicate
ids, empty actions, and actions targeting bridge ids with no matching
`dcc.Store`. Optional. Run it during development.

## Installation

```bash
pip install dash-relay
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
