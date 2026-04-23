# Changelog

All notable changes to this project are documented here. Format based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.1] — 2026-04-22

Documentation cleanup pass. No library code changes; no PyPI release.
Lives on main as the working version while the next ship is being
prepared. When a future technical change ships, it inherits these
documentation fixes without a separate version bump for them.

### Cleanup

- README event-dict-keys table: cells like `str | int | dict | None`
  were breaking the markdown table because `|` is also the column
  separator. Switched to `str` / `int` / `dict` / `None` (separated
  backticks) to match the form already used in the CHANGELOG.
- Replaced "v4" / "v4 spec" / "v4 cut" references with neutral
  language in `__init__.py`, `app.py`, `callback.py` (×4 including
  two user-facing `InstallError` messages), `validation.py`, the
  client-side JS asset, the README, and three test docstrings. The
  shipped library is 2.x; "v4" was a label from the design-iteration
  branches that never published.
- Migrated comment-only references to the legacy 1.x API in
  `examples/workspace_demo/app.py` (×5: `@relay.handle`,
  `relay.registry()`, "3.0 handler signature") and
  `examples/pattern_matching_vs_event_bridge/nested_side_by_side.py`
  (×3) to the current `@relay.callback` vocabulary. Code itself was
  already migrated; only the comments lagged.
- Same migration in the example READMEs:
  `examples/workspace_demo/README.md` and
  `examples/pattern_matching_vs_event_bridge/README.md` no longer
  reference `relay.registry`, `relay.emitter`, or `@events.handler`.

## [2.0.0] — 2026-04-22

First major version after 1.1.2. The dispatch surface is rebuilt
around Dash's own callback primitives, bridge stores are minted by
the library at install time, and the emitter API is split into a
template class with two materialization methods. The library shrinks
to one decorator + one class for emitting + one class for action
references + two functions + one constant.

Hard cut from 1.x. No deprecation, no compatibility shims.

### Public surface

```python
import dash_relay as relay
from dash_relay import Action, Emitter, DEFAULT_BRIDGE
from dash import Output, State

relay.install(app)                                            # lifecycle entry
relay.validate(layout=None, *, strict=False, app=None)        # correctness linter

Emitter(action=..., bridge=..., target=..., payload=..., source=..., on=..., prevent_default=...)
    .wrap(component, **overrides) -> Component                # transparent display:contents Div
    .attrs(**overrides)           -> dict                     # raw data-relay-* dict (no wrapper)

@relay.callback(Output(...), Action(...), [Action(...)...], State(...))
def handler(event, *state_values): ...
```

The handler signature mirrors plain Dash callbacks: arguments appear
in declaration order, with `Output` declarations skipped (response
targets, not handler inputs). The `Action` slot becomes the event
envelope; each `State` slot becomes the current store value.

### Migration from 1.1.2

| 1.1.2 | 2.0.0 |
|---|---|
| `relay.bridge(id=...)` in layout | delete (auto-minted by `install()`) |
| `events = relay.registry(app, state="x")` | `@relay.callback(Output("x", "data"), Action("..."), State("x", "data"))` per handler |
| `events = relay.registry(app, state=["a", "b"])` | each handler declares only its own `Output(...)` and `State(...)` deps |
| `@events.handler("foo")` | `@relay.callback(Output(...), Action("foo"), State(...))` |
| `def _(state, payload, event):` | `def _(event, state):` (positional, mirrors Dash) |
| `def _(states, payload, event):` (multi-state) | `def _(event, a, b):` for `State("a", ...), State("b", ...)` |
| `state["x"] += 1; return state` | `return {**state, "x": state["x"] + 1}` (or mutate a `deepcopy` and return) |
| `events.dispatch(event, state)` (test wrapper) | `app._dash_relay_bridge_plans[bridge_name].dispatch(event, state)` |
| `relay.emitter(component, action, **kwargs)` | `Emitter(action=action, **kwargs).wrap(component)` |
| `relay.emitter(component, action, **kwargs)` (CSS-direct-child case) | `html.Button(..., **Emitter(action=action, **kwargs).attrs())` (no wrapper Div) |
| `relay.emitter(action, **kwargs)` (curried) | `Emitter(action=action, **kwargs)` (then `.wrap()` / `.attrs()` at use sites) |
| `relay.install(app)` (any time) | `relay.install(app)` AFTER `app.layout = ...` (lifecycle requirement) |
| `event["event_type"]` | `event["type"]` |
| `event["native"]` | `event["details"]` |

### Architecture

- **Bridge stores are auto-minted by `install()`.** No more
  user-constructed `relay.bridge()` factory or explicit catalog.
  `install()` walks the registered `@callback` pool, collects unique
  bridge names from `Action(...).bridge`, mints one `dcc.Store` per
  bridge with id `relay-bridge-<slug>` (where `slug` replaces `.`
  with `__` for CSS-selector safety), and injects them at the layout
  root. Per-bridge stores never appear in user-written layout code.

- **`Emitter` class replaces the `emitter()` factory.** Two
  materialization methods. `.wrap()` returns the transparent
  `display: contents` Div wrapper (the 1.x default). `.attrs()`
  returns a dict of `data-relay-*` attributes that splat onto an
  existing component with no wrapper Div, restoring CSS `>`
  direct-child selectors, flex/grid child positioning, and DOM
  queries that the wrapper broke. Override-by-replace template
  semantics: one `Emitter` reused across many call sites with
  `attrs(action=...)` per use.

- **One Dash callback per bridge with `allow_duplicate=True` always.**
  Modern Dash's stricter callback-graph validation rejects multiple
  callbacks with overlapping outputs on the same Input. v2
  consolidates: `install()` registers one `@app.callback` per bridge
  whose outputs are the union of every handler's declared outputs
  (each with `allow_duplicate=True`), and the dispatcher routes by
  action name internally.

- **`@relay.callback` mirrors `@app.callback` exactly.** Same
  `Output` / `Input` / `State` ordering, same return shape rules,
  same positional handler signature. The only substitution is `Action`
  in the slot where `Input` would go. Anyone reading `@relay.callback(
  Output, Action, State)` and recognizing the shape needs zero new
  vocabulary beyond what `Action` is.

- **Alias semantics for multiple Actions.** A single `@relay.callback`
  may declare multiple `Action(...)` deps; the wrapped function fires
  for every listed `(bridge, action)` pair. Useful for the
  "close-or-dismiss" shape and for any case where two action names
  map to the same handler.

- **Target wire encoding is plain string for str/int, JSON only for
  dict.** 1.x JSON-encoded all targets, breaking CSS selectors that
  matched against the resulting attribute. v2 keeps strings as
  strings, ints as digit-strings, and only escapes to JSON for dict
  values. Tradeoff documented: a `str` value that looks like a digit
  string round-trips as `int`. Wrap in a dict if you need to preserve
  it.

### Lifecycle contract

`install(app)` must be called exactly once per app, after `app.layout`
is set. Calling it before the layout is set raises `InstallError`.
Calling it twice raises `InstallError`. Reassigning `app.layout`
after `install()` removes the bridge stores; the library does not
re-inject.

### Event envelope (frozen for v2)

| key | type | what it is |
|---|---|---|
| `action` | `str` | the Action name |
| `bridge` | `str` | the bridge that fired |
| `target` | `str` / `int` / `dict` / `None` | user-defined target value, parsed back from the wire |
| `source` | `str` / `None` | source component id (auto-filled by `Emitter.wrap()` when the wrapped component has an `id`) |
| `payload` | `dict` / `None` | user-supplied payload |
| `type` | `str` | DOM event name — same as JS `event.type` |
| `details` | `dict` | extracted browser fields off the DOM event — same shape as `CustomEvent.detail` |
| `timestamp` | `float` | seconds since epoch (client clock) |

### `validate()` codes

When `app=app` is passed (post-install):

- `duplicate-handler` — two handlers register the same
  `(bridge, action)` key. Same condition that causes `InstallError`
  at install time; this is the pre-flight.
- `unreachable-handler` — a handler exists for a bridge that no
  emitter in the supplied layout writes to.
- `missing-handler` — an emitter targets a `(bridge, action)` key
  that no handler is registered for.

### Limits

Pattern-matched ids (`MATCH`/`ALL`/`ALLSMALLER`) in handler
`Output`/`State` are not supported in v2. `install()` raises
`InstallError`. The per-bridge consolidation is incompatible with
MATCH-binding semantics. Workaround: write a separate non-relay
`@app.callback` for that case.

### New error type

`dash_relay.InstallError` — raised by `install()` for lifecycle
violations, duplicate `(bridge, action)` registrations, and
pattern-matched id rejections in `Output`/`State`.

### Removed

- `relay.bridge()` / `relay.Bridge` (replaced by automatic store creation)
- `relay.registry()` / `relay.Registry` (replaced by `@relay.callback`)
- `relay.emitter()` factory (replaced by `Emitter` class)
- `validate(layout, registry=...)` (replaced by `validate(layout, app=...)`)

### Iteration history

The 2.0 surface is the result of four design iterations carried out
on branches that were never published. PyPI's release history shows
1.0 → 1.0.1 → 1.1.1 → 1.1.2 → 2.0; the intermediate version numbers
below refer to internal branch labels, not releases.

- **Branch label `2.0` (registry surface alignment).** Renamed `state=`
  to `output=` and added a separate `state=` kwarg for read-only
  context; introduced dict-keyed handler args `(outputs, states,
  payload, event)`. Validated the architectural separation of "this
  registry writes" vs "this registry reads" but landed on a
  bespoke surface that didn't mirror Dash's vocabulary.

- **Branch label `3.0` (decorator + Action primitive).** Replaced the
  `Registry` class with `@relay.handle` decorators that read like
  Dash callbacks, with `Action` substituting for `Input`. Made the
  signature mirror Dash's positional convention exactly. This is the
  shape v2 ships with.

- **Branch label `3.1` (Action(bridge=) for collisions).** Added an
  optional `bridge=` kwarg on `Action` for cross-bridge action-name
  disambiguation, with specificity-based routing (pinned beats
  wildcard). Carried forward into v2's lifecycle (every `Action`
  resolves to a concrete bridge, defaulting to `DEFAULT_BRIDGE`).

- **Branch label `4.0` (auto-minted bridges + Emitter class +
  per-bridge consolidation).** Removed the user-facing `bridge()`
  factory; `install()` mints stores from the registered handler pool.
  Renamed `@relay.handle` to `@relay.callback` to make the Dash
  parallel literal. Replaced the `emitter()` factory with the
  `Emitter` class so `.attrs()` could provide a raw-attribute splat
  with no wrapper Div. Consolidated to one Dash callback per bridge
  with `allow_duplicate=True` to satisfy modern Dash's callback-graph
  validation. Renamed event-envelope keys `event_type → type` and
  `native → details` to align with DOM/JS vocabulary.

The branch labels were internal nomenclature; nothing in that
sequence ever shipped to PyPI. The single 2.0 entry above documents
the surface that ships.

## [1.1.2] — 2026-04-18

First release shipped via the new GitHub Actions Trusted-Publishing
pipeline. No library code or surface changes — this is the inaugural
test of `.github/workflows/publish.yml`. Future releases follow the
same path: tag `vX.Y.Z`, push the tag, approve the prod step.

## [1.1.1] — 2026-04-18

**Breaking kwarg renames on the public surface.** Normally these would
force a major-version bump; shipping under 1.1 instead because the
package is one day old on PyPI with effectively zero adopters and the
rename-cost-now vs carry-the-inconsistency-forward tradeoff clearly
favors fixing it now. No aliases, no deprecation warnings — callers
on 1.0.x must update their code.

### Renamed

| Old | New | Function |
|---|---|---|
| `register_asset=` | `register_runtime=` | `install()` |
| `to=` | `bridge=` | `emitter()` |
| `event=` | `on=` | `emitter()` |

Also the emitter's DOM data attribute `data-relay-event` renamed to
`data-relay-on` so the Python-side and DOM-side names stay aligned.

### Why each

- `register_runtime`: `register_asset` only named half of what the
  flag does (registers the Flask route *and* injects the `<script>`
  into `index_string`). "register_runtime" names the whole thing.
- `bridge` on the emitter: every other surface used "bridge" already
  (the `bridge()` factory, `registry(bridge=)`, the DOM data
  attribute). The emitter's `to=` was the sole outlier.
- `on`: mirrors JSX/React (`on="click"`), reads naturally next to the
  component being wrapped, and avoids the in-code echo with the
  handler's `event` parameter name (which carries the full event
  envelope, not the DOM event type).

### Migration

```python
# before
relay.install(app, register_asset=False)
relay.emitter(dcc.Input(...), "draft", event="input", to="analytics")

# after
relay.install(app, register_runtime=False)
relay.emitter(dcc.Input(...), "draft", on="input", bridge="analytics")
```

## [1.0.1] — 2026-04-18

PyPI polish only — no library code changes.

### Fixed
- Hero image on the PyPI project page. 1.0.0's README used a relative
  path (`examples/.../comparison-demo.gif`); GitHub resolves relative
  paths against the repo but PyPI renders the long description in
  isolation, so the image showed as a broken placeholder. Switched to
  an absolute `raw.githubusercontent.com` URL so both surfaces render.

### Added (metadata)
- `[project.urls]` with Homepage, Repository, Issues, Changelog — PyPI
  now shows a "Project links" sidebar.
- Richer classifiers: `Development Status :: 5 - Production/Stable`,
  `Framework :: Dash`, per-Python-version markers for 3.10 / 3.11 /
  3.12, and `Topic :: Software Development :: Libraries :: Python
  Modules`.

## [1.0.0] — 2026-04-18

First release under the `dash-relay` name. This package replaces `liquid-dash`
(last version 0.2.3) — a hard rename, not a continuation. Anyone migrating
from `liquid-dash` has a five-minute find/replace (see table below); there is
no legacy shim.

### Public API

Five functions and one decorator:

```python
import dash_relay as relay

relay.install(app)                          # client-side runtime + <script> injection
relay.bridge(id="bridge")                   # dcc.Store event sink
relay.emitter(component, action, ...)       # wrap a component as an event emitter
events = relay.registry(app, state="...")   # dispatch registry; single or multi-state
relay.validate(layout, registry=None)       # optional layout linter
@events.handler("action")                   # per-action handler
```

### Rename map (from liquid-dash 0.2.x)

| liquid-dash 0.2.x        | dash-relay 1.0.0          |
|--------------------------|---------------------------|
| `import liquid_dash as ld` | `import dash_relay as relay` |
| `ld.melt(app)`           | `relay.install(app)`      |
| `ld.on(...)`             | `relay.emitter(...)`      |
| `ld.handler(...)`        | `relay.registry(...)`     |
| `@events.on("foo")`      | `@events.handler("foo")`  |
| `data-ld-*` attributes   | `data-relay-*`            |
| `window.__liquidDashInstalled` | `window.__dashRelayInstalled` |
| `/_liquid_dash/...`      | `/_dash_relay/...`        |
| `LiquidDashError`        | `DashRelayError`          |

### Features in 1.0.0

- **Event-agnostic client runtime.** Any DOM event name accepted via
  `event=`, including non-bubbling ones (`focus`, `blur`) and custom events
  dispatched through `element.dispatchEvent(new CustomEvent(...))`. Listeners
  bind lazily in capture phase.
- **Curried emitter form.** `relay.emitter("action", ...)` returns a reusable
  factory for list-rendering patterns.
- **Multi-state registries.** `relay.registry(app, state=["a", "b", ...])`
  lets one bridge dispatch to multiple stores; handlers receive a tuple
  aligned with the state-id list.
- **Validator cross-check.** `relay.validate(layout, registry=events)` reports
  `orphan-emitter` (emitter with no matching handler) and `orphan-handler`
  (handler with no matching emitter) at load time.
- **JSON-round-tripping context.** `target=` and `source=` on the emitter are
  JSON-encoded at the boundary so ints, lists, and dicts survive the trip
  back to handlers unchanged.

### Tests

- 35 unit tests (registry, emitter, validator, app install, workspace demo,
  live example)
- 15 Playwright integration tests verifying every claimed DOM event type
  actually reaches the bridge (opt-in via `pip install -e .[integration]`)
