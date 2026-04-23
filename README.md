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
from dash_relay import Action, Emitter, DEFAULT_BRIDGE
from dash import Output, State

relay.install(app)                                            # lifecycle entry
relay.validate(layout, app=app)                               # correctness linter

Emitter(action="...", bridge="...", target=..., payload={...})  # template
    .wrap(component, **overrides)   -> Component                  # transparent Div wrapper
    .attrs(**overrides)             -> dict[str, str]             # raw data-relay-* dict

@relay.callback(                                              # handler decorator
    Output("state", "data"),                                  # write target (Dash native)
    Action("my.action"),                                      # trigger (replaces Input)
    State("state", "data"),                                   # read context (Dash native)
)
def my_handler(event, state): ...
```

Two functions, one decorator, two classes (`Emitter`, `Action`), one
constant. Bridges are minted automatically from the actions your
handlers declare — there's no `bridge()` factory or store to construct.

The handler reads like a Dash callback with `Action` slotted in where
`Input` would be — same `Output`, same `State`, same positional
handler args, same return shape.

## A complete app

```python
from dash import Dash, Input, Output, State, dcc, html
import dash_relay as relay
from dash_relay import Action, Emitter

app = Dash(__name__)


# Per-action handlers — Dash-shaped callback declarations with Action
# standing in for Input. Each handler reads its current state via
# State(...) and returns the new value to write.

@relay.callback(Output("state", "data"), Action("add"), State("state", "data"))
def add_item(event, s):
    return {**s, "items": [*s["items"], {"id": len(s["items"]) + 1, "text": s["draft"]}], "draft": ""}


@relay.callback(Output("state", "data"), Action("delete"), State("state", "data"))
def delete_item(event, s):
    return {**s, "items": [t for t in s["items"] if t["id"] != event["target"]]}


@relay.callback(Output("state", "data"), Action("draft"), State("state", "data"))
def update_draft(event, s):
    return {**s, "draft": event["details"].get("value", "")}


# Layout: one state store + your interactive elements wrapped or
# splatted with Emitter. Bridge stores are minted by install() — you
# don't put them in the layout yourself.
draft_input = Emitter(action="draft", on="input").wrap(
    dcc.Input(placeholder="New task...")
)
add_button = html.Button("Add", **Emitter(action="add").attrs())  # raw splat — no wrapper Div

app.layout = html.Div([
    dcc.Store(id="state", data={"draft": "", "items": []}),
    draft_input,
    add_button,
    html.Ul(id="list"),
])


# Standard Dash renderer: state changes → HTML.
@app.callback(Output("list", "children"), Input("state", "data"))
def render(s):
    delete = Emitter(action="delete")
    return [
        html.Li([
            html.Span(t["text"]),
            html.Button("x", **delete.attrs(target=t["id"])),
        ]) for t in s["items"]
    ]


# install() last — it drains the @relay.callback pool, mints one
# bridge store per unique bridge mentioned in any Action, injects them
# into the layout, and registers one dispatcher Dash callback per bridge.
relay.install(app)


if __name__ == "__main__":
    app.run(debug=True)
```

## The pieces

### `relay.install(app)`

The lifecycle entry point. Three things happen, in order:

1. The client-side runtime script (~130 lines) is registered at
   `/_dash_relay/dash_relay.js` and a `<script>` tag is injected into
   `app.index_string`. The runtime watches the DOM for elements
   carrying `data-relay-*` attributes and lazily binds document-level
   listeners for whatever event types it finds. Event-agnostic:
   `on=` accepts any DOM event string — including non-bubbling ones
   like `focus`/`blur` and custom events dispatched via
   `element.dispatchEvent(new CustomEvent(...))`.
2. The pending handler pool (populated by `@relay.callback`
   decorators at import) is drained. One bridge name is collected
   per unique `Action(...).bridge`. For each, a `dcc.Store` with id
   `relay-bridge-<slug>` is minted and injected at the layout root.
3. One Dash callback per bridge is registered, with `allow_duplicate=True`
   on every `Output`. The callback dispatches by action name to the
   right handler in that bridge's pool.

**Lifecycle contract.** `install()` must be called once, after
`app.layout` is set. Calling it before layout is set raises
`InstallError`. Calling it twice raises `InstallError`. Reassigning
`app.layout` after `install()` removes the bridge stores — don't do
that.

### `Emitter(action=..., bridge=..., target=..., payload=..., source=..., on=..., prevent_default=...)`

Reusable template for relay-event emission. All constructor fields are
optional; only `action` is required by materialization time. Two
materialization methods:

- **`.attrs(**overrides)`** returns a dict of `data-relay-*`
  attributes you can splat onto an existing component:
  ```python
  html.Button("Pin", **Emitter(bridge="cards").attrs(action="pin", target=row_id))
  ```
  No wrapper Div, so CSS `>` direct-child selectors and direct-child
  flex/grid still work.

- **`.wrap(component, **overrides)`** wraps the given component in a
  transparent `display: contents` div carrying the attributes:
  ```python
  Emitter(action="pin", target=row_id, bridge="cards").wrap(html.Button("Pin"))
  ```
  Use this when splatting onto the component isn't possible (third-party
  components that don't forward arbitrary HTML attributes).

**Override semantics: replace, not merge.** `Emitter(payload={"a": 1}).attrs(payload={"b": 2})`
yields `{"b": 2}` — the override is absolute. To merge: `payload={**e.payload, "b": 2}`.

**Auto source-fill.** If `source` isn't set on either side and `.wrap()`
gets a component with an `id`, `source` defaults to that id.

**Target wire encoding.** `target` accepts `str`, `int`, or `dict`.
Encoded as plain string for str/int (so CSS attribute selectors work
without escape gymnastics) and compact JSON for dict. Tradeoff: a
`str` value that looks like a digit string round-trips as `int`.
If you need a digit-string preserved, wrap it: `target={"id": "42"}`.

### `Action(name, bridge=None)`

Identifies a `(bridge, action_name)` pair the handler responds to.
`bridge=` defaults to `DEFAULT_BRIDGE` (`"dash-relay-bridge"`). Multiple
`Action(...)` declarations in one `@relay.callback` register alias
semantics: the same handler fires for every listed pair.

### `@relay.callback(*deps)`

Mirrors Dash's `@app.callback(Output, Input, State)` signature with
`Action` substituting for `Input`. Dependency parsing rules:

- At least one `Output` required.
- At least one `Action` required (multiple = aliases).
- Any number of `State`s, including zero.

```python
from dash import Output, State
from dash_relay import Action

@relay.callback(
    Output("tab_store", "data"),                  # write target
    Action("tab.close"),                          # trigger
    State("tab_store", "data"),                   # read self
    State("path", "data"),                        # read other context
)
def close_tab(event, tab, path):
    return {**tab, "tabs": [t for t in tab["tabs"] if t["id"] != event["target"]]}
```

**Handler signature** follows Dash positional convention. `Output`
declarations are skipped (they're response targets, not handler
inputs). Each `Action` slot gives you the event dict; each `State`
slot gives you that store's current value.

| arg | what it is |
|---|---|
| `event` | the full Dash Relay event dict (keys below) |
| `state values...` | one positional arg per `State(...)` declared, in declaration order |

**Return shapes:**

| return | effect |
|---|---|
| value | new state for the single declared `Output` |
| tuple | positional, must match number of declared `Output`s |
| `dash.no_update` | every output stays untouched |
| `dash.Patch(...)` | passed through unchanged (single or in a tuple) |

**Alias semantics.** Multiple `Action(...)` declarations in one
decorator route every listed `(bridge, action)` pair through the same
handler:

```python
@relay.callback(
    Output("modal", "data"),
    Action("close", bridge="modal.signup"),
    Action("dismiss", bridge="modal.signup"),
    State("modal", "data"),
)
def on_close_or_dismiss(event, current):
    return {**current, "is_open": False}
```

Both `(modal.signup, close)` and `(modal.signup, dismiss)` invoke this
handler. Doesn't trigger duplicate-handler detection.

**Per-bridge dispatcher.** When two handlers' Actions point at
different bridges, `install()` registers a separate Dash callback per
bridge. Each dispatcher's `Output`/`State` union is scoped to handlers
on its bridge — no wire cost for irrelevant state.

**Coexisting with non-relay writers.** Bridge stores are standard
`dcc.Store` components. Any external `@app.callback` (server or
clientside) can also write to them with `allow_duplicate=True`. The
relay dispatcher's outputs are always declared with `allow_duplicate=True`
internally so coexistence works without extra effort.

**Pattern-matched ids are not supported.** If a handler declares
an `Output` or `State` with a dict-shaped (`MATCH`/`ALL`/`ALLSMALLER`)
id, `install()` raises `InstallError`. Use a fixed store id, or write
a separate non-relay `@app.callback` for the pattern-matched case.

**Event dict keys** (frozen for v2):

| key | type | what it is |
|---|---|---|
| `action` | `str` | the Action name |
| `bridge` | `str` | the bridge that fired |
| `target` | `str` / `int` / `dict` / `None` | user-defined target value, parsed back from the wire |
| `source` | `str` / `None` | source component id (auto-filled from wrap, optional) |
| `payload` | `dict` / `None` | user-supplied payload |
| `type` | `str` | DOM event name (click, keydown, blur, ...) — same as JS `event.type` |
| `details` | `dict` | extracted browser fields off the DOM event (value, checked, key, clientX/Y, deltaX/Y, button) — same shape as `CustomEvent.detail` |
| `timestamp` | `float` | seconds since epoch (client clock) |

### `relay.validate(layout=None, *, strict=False, app=None)`

Correctness-only linter. Three checks:

- **`duplicate-handler`** — two handlers register the same
  `(bridge, action)` key. Same condition that causes `InstallError`
  at install time; this is the pre-flight.
- **`unreachable-handler`** — a handler exists for a bridge that no
  emitter in the supplied layout writes to. Only when a layout is given.
- **`missing-handler`** — an emitter targets a `(bridge, action)` key
  that no handler is registered for. Only when a layout is given.

`strict=True` raises `UnsafeLayoutError` if any issues are found.

Pre-install: reads the global pending pool. Post-install: pass
`app=app` to read the cached handler set from the installed app.

```python
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
