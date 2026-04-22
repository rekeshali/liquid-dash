# Dash Relay

[![PyPI version](https://img.shields.io/pypi/v/dash-relay.svg)](https://pypi.org/project/dash-relay/)
[![Python versions](https://img.shields.io/pypi/pyversions/dash-relay.svg)](https://pypi.org/project/dash-relay/)
[![Tests](https://github.com/rekeshali/dash-relay/actions/workflows/test.yml/badge.svg)](https://github.com/rekeshali/dash-relay/actions/workflows/test.yml)

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
faster than the UI itself — pattern-matching callbacks, defensive
guards, and `allow_duplicate` coordination across many writers.

Dash Relay moves UI events off the Dash callback graph and onto a
single client-side bridge. You wrap existing Dash components with one
call; events flow into a `dcc.Store`; per-action handlers — declared
with the same `Output` / `State` primitives Dash already uses — are
dispatched from a single internal callback. Layouts can be rerendered
freely without touching the callback graph. The pattern-matching
approach stays cleaner for static layouts; the bridge earns its keep
once things start moving.

## The whole surface

```python
import dash_relay as relay
from dash_relay import Action
from dash import Output, State

relay.install(app)                                            # client-side runtime + dispatcher
relay.bridge()                                                # a dcc.Store event sink
relay.emitter(component, action, ...)                         # wrap a component as an event emitter
relay.validate(layout)                                        # optional linter

@relay.handle(                                                # registers a handler with the dispatcher
    Output("state", "data"),                                  # write target (Dash native)
    Action("my.action"),                                      # trigger (replaces Input)
    State("state", "data"),                                   # read context (Dash native)
)
def my_handler(event, state): ...
```

Four functions, one decorator, one dependency primitive. The handler
reads like a Dash callback with `Action` slotted in where `Input`
would be — same `Output`, same `State`, same positional handler args.

## A complete app

```python
from dash import Dash, Input, Output, State, dcc, html
import dash_relay as relay
from dash_relay import Action

app = Dash(__name__)


# Per-action handlers — declared just like Dash callbacks, with one
# Action standing in for the Input. Each handler reads its current
# state via State(...) and returns the new value to write.

@relay.handle(Output("state", "data"), Action("add"), State("state", "data"))
def add_item(event, s):
    return {**s, "items": [*s["items"], {"id": len(s["items"]) + 1, "text": s["draft"]}], "draft": ""}


@relay.handle(Output("state", "data"), Action("delete"), State("state", "data"))
def delete_item(event, s):
    return {**s, "items": [t for t in s["items"] if t["id"] != event["target"]]}


@relay.handle(Output("state", "data"), Action("draft"), State("state", "data"))
def update_draft(event, s):
    return {**s, "draft": event["native"].get("value", "")}


# Layout: one state store, one bridge, wrapped interactive elements.
app.layout = html.Div([
    dcc.Store(id="state", data={"draft": "", "items": []}),
    relay.bridge(),
    relay.emitter(dcc.Input(placeholder="New task..."), "draft", on="input"),
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


# install() last — it drains the @relay.handle pool and registers
# one dispatcher Dash callback per registered bridge.
relay.install(app)


if __name__ == "__main__":
    app.run(debug=True)
```

## The pieces

### `relay.install(app)`

Installs a ~130-line client-side script that watches the DOM for
elements carrying `data-relay-on` attributes and lazily binds
document-level listeners for whatever event types it finds. The
runtime is event-agnostic: `on=` accepts any DOM event string —
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
| `on=` | DOM event name | `"click"` |
| `bridge=` | target bridge id | `"bridge"` |
| `target=`, `source=` | context values on the event (any JSON-serializable; types round-trip) | `None` |
| `prevent_default=` | calls `event.preventDefault()` client-side | `False` |

**Curried form.** Called with just an action string, `emitter()` returns
a reusable factory — convenient for list rendering:

```python
delete = relay.emitter("delete")
[delete(html.Button("x"), payload={"id": t["id"]}) for t in items]
```

### `relay.handle(*deps)` and `Action(name)`

`@relay.handle` is the decorator that registers a handler. It takes
positional `Output`, `Action`, and `State` dependencies — the same
`Output` and `State` Dash users already know, plus one `Action`
dependency that names which relay action triggers the handler.

```python
from dash import Output, State
from dash_relay import Action

@relay.handle(
    Output("tab_store", "data"),                  # write target
    Action("tab.close"),                          # trigger
    State("tab_store", "data"),                   # read self
    State("path", "data"),                        # read other context
)
def close_tab(event, tab, path):
    return {**tab, "tabs": [t for t in tab["tabs"] if t["id"] != event["target"]]}
```

**Handler signature** mirrors plain Dash: arguments appear in
declaration order, with one rule — `Output` declarations don't appear
as handler arguments (they're response targets). The `Action` slot
gives you the event dict; each `State` slot gives you that store's
current value.

| arg | what it is |
|---|---|
| `event` | the full Dash Relay event dict (keys below) |
| `state values...` | one positional arg per `State(...)` declared, in declaration order; current store value |

**Return shapes:**

| return | effect |
|---|---|
| value | new state for the single declared `Output` |
| tuple | positional, must match the number of declared `Output`s |
| `dash.no_update` | every output stays untouched |

**Bridge ownership.** The bridge an action travels on is determined by
the emitter's `bridge=` kwarg. Handlers don't need to declare it; the
dispatcher routes by action name across whichever bridge fired.

**No registry instance.** Handlers register globally via the decorator
and are wired up at `install()` time. You never construct a
`Registry`. To rerun handlers in tests without going through Dash, the
bare dispatcher function is exposed as `app._dash_relay_dispatcher`.

**Coexisting with non-registry writers.** If an `Output(...)` store
also has external writers (intervals, modal callbacks, server-side
pushes) using Dash's `allow_duplicate=True`, declare your handler's
Output the same way: `Output("toast", "data", allow_duplicate=True)`.
Dash's standard multi-writer rules apply — no relay-specific magic.

**Multi-bridge.** When more than one bridge is registered (you called
`relay.bridge(id)` for several distinct ids), `install()` registers a
dispatcher per bridge automatically and forces `allow_duplicate=True`
on every `Output` so they coexist correctly. Adding a second bridge
to an existing app is a layout-only change.

**Action-name collisions.** Action names live in a global namespace
— one handler per name across the app. If two emitters on different
bridges genuinely use the same action string and you want different
handlers per bridge, pin them with `Action(name, bridge="...")`:

```python
@relay.handle(
    Output("tab_store", "data"),
    Action("close", bridge="folder.tabbar"),       # only fires from this bridge
    State("tab_store", "data"),
)
def close_tab(event, tabs): ...

@relay.handle(
    Output("panel_store", "data"),
    Action("close", bridge="panel-grid"),          # only fires from this bridge
    State("panel_store", "data"),
)
def close_panel(event, panels): ...
```

Routing rule: the dispatcher prefers a pinned `(name, bridge)` match;
if none matches the firing bridge, it falls back to the wildcard
`Action(name)` if one is registered. So a wildcard handler can be the
default with per-bridge overrides for surfaces that need different
behavior. Two wildcards for the same name still raise (today's dedupe
rule). Two pinned handlers for the same `(name, bridge)` pair also
raise. A wildcard plus per-bridge pins for the same name is fine —
each pin shadows the wildcard for its specific bridge only.

**Escape hatch.** Skip `@relay.handle` and write a normal
`@app.callback(Input("bridge", "data"), ...)` yourself. The bridge
store is a regular `dcc.Store`; nothing prevents direct use.

**Event dict keys:** `action`, `target`, `source`, `event_type`,
`native`, `timestamp`, `bridge`. `event["native"]` carries browser-level
fields from the original DOM event — `value`, `checked`, `key`,
`clientX/Y`, `deltaX/Y`, etc. `event["bridge"]` identifies which
bridge fired.

### `relay.validate(layout, app=None)`

Optional development-time linter. Walks the layout and reports:

- **duplicate ids** — two components sharing the same id
- **empty actions** — an emitter with an empty action string
- **missing bridge** — an emitter targeting a bridge id that isn't
  present as a `dcc.Store` in the layout

Pass `app=app` after `relay.install(app)` has run to also cross-check
the registered handlers against the layout:

- **orphan-emitter** — an emitter's action has no matching handler
  (clicking that element is a no-op)
- **orphan-handler** — a handler is registered for an action that no
  emitter in the layout uses (false-positive-prone if emitters are
  rendered dynamically from callbacks)
- **output-not-found** — a handler declares an `Output` whose store id
  isn't a `dcc.Store` in the layout
- **state-not-found** — same for `State` ids
- **unreachable-handler** — a handler is pinned via `Action(bridge=)`
  to a bridge that no emitter in the layout writes to (handler will
  never fire — typo or stale wiring)

```python
relay.install(app)
report = relay.validate(app.layout, app=app)
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
