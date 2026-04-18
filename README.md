# Dash Relay

A tiny layer for building **dynamic Dash interfaces** without wiring a
callback per interactive element.

![Head-to-head demo](https://raw.githubusercontent.com/rekeshali/dash-relay/main/examples/pattern_matching_vs_event_bridge/comparison-demo.gif)

*One nested workspace surface (Folders → Tabs → Panels, 9 actions)
built two ways in the same Dash app. Each column runs the same scripted
9-click sequence; the compare panel in the top-right aggregates:*

- ***Round-trips*** — `_dash-update-component` fetches fired · **~80% fewer** on the bridge side
- ***Data sent*** — total bytes over the wire · **~83% less** on the bridge side
- ***Wall time*** — click → last server response · **~40% less** on the bridge side

*Left column: pattern-matching callbacks with the canonical guard.
Right column: the Dash Relay event bridge. Measured on an M1 Pro.*

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

relay.install(app)                          # install the client-side runtime once
relay.bridge()                              # a dcc.Store sink (put it in the layout)
relay.emitter(component, action, ...)       # wrap a component as an event emitter
events = relay.registry(app, state="...")   # registry for server-side handlers
relay.validate(layout)                      # optional linter

@events.handler("action")                   # one per action — registers the handler
def _(state, payload, event): ...
```

Five functions and one decorator. That's it.

## A complete app

```python
from dash import Dash, Input, Output, dcc, html
import dash_relay as relay

app = Dash(__name__)

# Install the client-side runtime and a `<script>` tag into the app's index page.
relay.install(app)

# Wire one dispatch callback: bridge events in → state updates out.
events = relay.registry(app, state="state")


# Per-action handlers. Each receives a deepcopy of state, safe to mutate.
@events.handler("add")
def _(state, payload, event):
    state["items"].append({"id": len(state["items"]) + 1, "text": state["draft"]})
    state["draft"] = ""


@events.handler("delete")
def _(state, payload, event):
    state["items"] = [t for t in state["items"] if t["id"] != event["target"]]


@events.handler("draft")
def _(state, payload, event):
    state["draft"] = event["native"].get("value", "")


# Layout: one state store, one bridge, wrapped interactive elements.
app.layout = html.Div([
    dcc.Store(id="state", data={"draft": "", "items": []}),
    relay.bridge(),
    relay.emitter(dcc.Input(placeholder="New task..."), "draft", event="input"),
    relay.emitter(html.Button("Add"), "add"),
    html.Ul(id="list"),
])


# Standard Dash renderer: state changes → HTML. Relay stays out of this path.
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

### `relay.install(app)`

Installs a ~130-line client-side script that watches the DOM for
elements carrying `data-relay-event` attributes and lazily binds
document-level listeners for whatever event types it finds. The
runtime is event-agnostic: `event=` accepts any DOM event string —
including non-bubbling ones like `focus`/`blur` and custom events
dispatched via `element.dispatchEvent(new CustomEvent(...))`.

### `relay.bridge(id="bridge")`

Returns a `dcc.Store` that acts as the event sink. Drop one in the
layout. The default id `"bridge"` matches what `emitter()` and
`registry()` target. Use `relay.bridge("analytics")` if you need more
than one bridge.

### `relay.emitter(component, action, ...)`

Wraps a Dash component in a transparent `display: contents` div that
carries the event metadata. Works with `html.*`, `dcc.*`, and
third-party components alike — the wrapper owns the attributes, not
the component.

**Keyword arguments:**

| kwarg | purpose | default |
|---|---|---|
| `payload=` | JSON-serializable value passed to the handler | `None` |
| `event=` | DOM event name | `"click"` |
| `to=` | target bridge id | `"bridge"` |
| `target=`, `source=` | context values on the event (any JSON-serializable; types round-trip) | `None` |
| `prevent_default=` | calls `event.preventDefault()` client-side | `False` |

**Curried form.** Called with just an action string, `emitter()` returns
a reusable factory — convenient for list rendering:

```python
delete = relay.emitter("delete")
[delete(html.Button("x"), payload={"id": t["id"]}) for t in items]
```

### `relay.registry(app, state="store_id")`

Returns a `Registry` and registers one internal Dash callback wired
from the bridge to the state store. Accepts a single store id for the
common case or `state=["a", "b", ...]` for apps that update multiple
stores from one bridge. Attach per-action logic with
`@events.handler("action")` (below).

With `state=[...]`, handlers receive a tuple of states —
`(states, payload, event)` — and either mutate in place (return `None`)
or return an explicit tuple of new values. See
`examples/workspace_demo/app.py` for a full worked example.

**Escape hatch.** For apps that don't fit the registry shape at all,
skip `registry()` and write a normal `@app.callback(Input("bridge",
"data"), ...)` yourself.

### `@events.handler(action)`

Decorator on the registry object — where per-action application logic
lives. One decorator per action name.

```python
events = relay.registry(app, state="state")

@events.handler("add")
def _(state, payload, event):
    state["items"].append(...)
```

**Handler signature:** `(state, payload, event) -> new_state | None`

| arg | what it is |
|---|---|
| `state` | a deep copy of the state store — safe to mutate in place |
| `payload` | the user-defined payload from `relay.emitter(..., payload=...)` |
| `event` | the full Dash Relay event dict (keys below) |

Returning `None` keeps the mutated deep copy. Returning a value replaces
the store with that value.

**Event dict keys:** `action`, `target`, `source`, `event_type`,
`native`, `timestamp`, `bridge`. `event["native"]` carries browser-level
fields extracted from the original DOM event — `value`, `checked`,
`key`, `clientX/Y`, `deltaX/Y`, etc.

### `relay.validate(layout, registry=None)`

Optional development-time linter. Walks the layout and reports:

- **duplicate ids** — two components sharing the same id
- **empty actions** — an emitter with an empty action string
- **missing bridge** — an emitter targeting a bridge id that isn't
  present as a `dcc.Store` in the layout

Pass `registry=events` to also cross-check action strings against
registered handlers:

- **orphan-emitter** — an emitter's action has no matching handler
  (clicking that element is a no-op)
- **orphan-handler** — a handler is registered for an action that no
  emitter in the layout uses (false-positive-prone if emitters are
  rendered dynamically from callbacks)

```python
report = relay.validate(app.layout, registry=events)
if not report.ok:
    for issue in report.issues:
        print(f"[{issue.code}] {issue.message}")
```

## Installation

```bash
pip install dash-relay
```

## Examples

```bash
# Minimal starting point: one screen of panels with add/delete/retype/badge.
python examples/live_test/app.py

# Workspace-shaped app: folders → tabs → panels with 18 action types.
# The callback graph stays at 5 no matter how many entities you add
# (verified by test_workspace_demo_has_small_fixed_callback_graph).
python examples/workspace_demo/app.py

# Head-to-head: same 9-action nested surface built two ways. In-page
# timelines show every _dash-update-component fire attributed to each
# side; the top-right compare panel aggregates percent differences
# across runs (~80% fewer round-trips, ~83% less data over the wire,
# ~40% less time from click to last server response, i.e.
# server-round-trip time — client-render time is not counted).
# Measured on an Apple M1 Pro.
python examples/pattern_matching_vs_event_bridge/nested_side_by_side.py
```

See [`examples/pattern_matching_vs_event_bridge/README.md`](examples/pattern_matching_vs_event_bridge/README.md)
for a deeper write-up of what the comparison demo measures and why.

## Development

```bash
pip install -e .[dev]
pytest                                    # 35 unit tests
```

### Integration tests (real browser)

`tests/test_event_types.py` launches the app in a background thread
and drives a headless Chromium via Playwright to verify every claimed
DOM event type actually flows to the bridge. Opt-in because of the
browser-binary footprint:

```bash
pip install -e .[integration]
playwright install chromium
pytest                                    # 50 tests total (35 unit + 15 browser)
# or just the browser tests:
pytest tests/test_event_types.py -v
```

`tests/test_event_types.py` auto-skips if `playwright` isn't installed,
so the default `pytest` run stays lightweight.

### Scripts

`scripts/record_comparison_demo.py` regenerates the head-to-head GIF
used in the example's README. Requires `ffmpeg` on `$PATH` and the
`[integration]` extras for Playwright.

```bash
python scripts/record_comparison_demo.py
```

## License

MIT
