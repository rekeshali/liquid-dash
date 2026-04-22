# Changelog

All notable changes to this project are documented here. Format based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [4.0.0] — 2026-04-22

The minimum surface. Bridge stores are minted by the library, the
emitter API is split into a template class with two materialization
methods, and the dispatcher consolidates handlers per bridge so
modern Dash's stricter callback-graph validation works out of the box.

Hard cut. No deprecation, no compatibility shims.

### Surface

```python
import dash_relay as relay
from dash_relay import Action, Emitter, DEFAULT_BRIDGE
from dash import Output, State

relay.install(app)                              # lifecycle entry
relay.validate(layout=None, *, strict=False, app=None)

Emitter(action=..., bridge=..., target=..., payload=..., source=..., on=..., prevent_default=...)
    .wrap(component, **overrides) -> Component  # transparent display:contents Div
    .attrs(**overrides)           -> dict       # raw data-relay-* dict (no wrapper)

@relay.callback(Output(...), Action(...), [Action(...)...], State(...))
def handler(event, *state_values): ...
```

Two functions, one decorator, two classes (`Emitter`, `Action`), one
constant. Bridges are minted automatically from the actions handlers
declare — there's no `bridge()` factory, no store catalog, no
`Registry` instance.

### What changed

- **Bridge stores are auto-created by `install()`.** Drop the
  `relay.bridge(id=...)` factory and the `Bridge` class entirely.
  `install()` walks the registered `@callback` pool, collects unique
  bridge names from `Action(...).bridge`, mints one `dcc.Store` per
  bridge with id `relay-bridge-<slug>` (`.` → `__` for CSS safety),
  and injects them into the layout.

- **`Emitter` class replaces the `emitter()` factory.** Two
  materialization methods: `.wrap()` returns a `display: contents`
  div wrapper (the 3.x default), `.attrs()` returns a dict of
  `data-relay-*` attributes that splat onto an existing component
  with no wrapper Div — restoring CSS `>` direct-child selectors,
  flex/grid child positioning, and DOM queries that the wrapper
  broke. Override-by-replace template semantics: one `Emitter` reused
  across many call sites with `attrs(action=...)` per use.

- **One Dash callback per bridge with `allow_duplicate=True` always.**
  3.x registered N handlers per bridge with overlapping outputs —
  Dash 4.1's stricter callback-graph validation rejects that pattern.
  v4 consolidates: `install()` registers one `@app.callback` per
  bridge whose outputs are the union of every handler's declared
  outputs (each with `allow_duplicate=True`), and the dispatcher
  routes by action name internally.

- **`@relay.handle` renamed to `@relay.callback`.** The 3.x parallel
  with Dash's `@app.callback` was already there; the rename makes it
  literal. A Dash user reads `@relay.callback(Output, Action, State)`
  and recognizes the shape immediately.

- **Alias semantics for multiple Actions.** A single
  `@relay.callback` may declare multiple `Action(...)` deps; the
  wrapped function fires for each `(bridge, action)` pair. Useful for
  the "close-or-dismiss" shape and for any case where two action
  names map to the same handler.

- **Target wire encoding is plain string for str/int, JSON only for
  dict.** 3.x JSON-encoded all targets, breaking CSS selectors that
  matched against the resulting attribute. v4 keeps strings as
  strings, ints as digit-strings, and only escapes to JSON for dict
  values. Tradeoff documented: a `str` value that looks like a digit
  string round-trips as `int`. Wrap in a dict if you need to preserve
  it.

- **`Action(name)` defaults to `DEFAULT_BRIDGE` immediately.** No more
  wildcard semantics. Every `Action.bridge_id` is a concrete string
  after construction — either the explicit value or
  `"dash-relay-bridge"`.

- **Event dict keys finalized.** The envelope passed to handlers is
  frozen for v4 with these keys:

    | key | type | what it is |
    |---|---|---|
    | `action` | `str` | the Action name |
    | `bridge` | `str` | the bridge that fired |
    | `target` | `str | int | dict | None` | user-defined target value, parsed back from the wire |
    | `source` | `str | None` | source component id (auto-filled by `Emitter.wrap()`) |
    | `payload` | `dict | None` | user-supplied payload |
    | `type` | `str` | DOM event name — same as JS `event.type` (renamed from 3.x `event_type`) |
    | `details` | `dict` | extracted browser fields off the DOM event — same shape as `CustomEvent.detail` (renamed from 3.x `native`) |
    | `timestamp` | `float` | seconds since epoch (client clock) |

  The renames `event_type → type` and `native → details` align with
  DOM/JS vocabulary. Handler bodies that read `event["event_type"]`
  or `event["native"]` need updating to `event["type"]` /
  `event["details"]`.

### Lifecycle contract

`install(app)` must be called exactly once per app, after `app.layout`
is set. Calling it before the layout is set raises `InstallError`.
Calling it twice raises `InstallError`. Reassigning `app.layout`
after `install()` removes the bridge stores; the library does not
re-inject.

### Removed

- `relay.bridge()` / `relay.Bridge` — replaced by automatic store
  creation.
- `relay.registry()` / `relay.Registry` — replaced by `@relay.callback`.
- `relay.emitter()` factory — replaced by `Emitter` class.
- `@relay.handle` — renamed to `@relay.callback`.
- `validate(layout, registry=...)` — replaced by
  `validate(layout, app=...)`. The 3.x `output-not-found`,
  `state-not-found`, and (3.1) `unreachable-handler` codes are
  superseded by v4's `unreachable-handler` and `missing-handler`,
  scoped to relay-specific concerns. (Auto store creation makes
  `output-not-found` / `state-not-found` mostly obsolete; user-declared
  output stores are still subject to standard Dash validation.)

### New error type

- `dash_relay.InstallError` — raised by `install()` for lifecycle
  violations, duplicate `(bridge, action)` registrations, and
  pattern-matched id rejections in `Output`/`State`.

### Patterns and limits

- Pattern-matched ids (`MATCH`/`ALL`/`ALLSMALLER`) in handler
  `Output`/`State` are not supported. `install()` raises if any
  handler declares them. The per-bridge consolidation is incompatible
  with MATCH-binding semantics. Workaround: write a separate non-relay
  `@app.callback` for that case.

### Migration

Mechanical from 3.x. Roughly:

1. `relay.bridge(id=...)` → delete (auto-created).
2. `@relay.handle(...)` → `@relay.callback(...)`.
3. `relay.emitter(component, action, **kwargs)` →
   `Emitter(action=action, **kwargs).wrap(component)` (or `.attrs()`
   splatted onto the component for no wrapper).
4. `relay.emitter(action, **kwargs)` (curried) →
   `Emitter(action=action, **kwargs)` (use later via `.wrap()` /
   `.attrs()`).
5. Move `relay.install(app)` to AFTER `app.layout = ...`.
6. Tests using `app._dash_relay_dispatcher(...)` switch to
   `app._dash_relay_bridge_plans[bridge_name].dispatch(...)`.

## [3.1.0] — 2026-04-22

`Action` gains an optional `bridge=` kwarg for disambiguating
action-name collisions across bridges. Strictly additive — every 3.0
call site continues to work unchanged.

### What changed

```python
# 3.0 — action names live in a global namespace
@relay.handle(Output(...), Action("close"), State(...))
def _(event, ...): ...

# 3.1 — pin a handler to a specific bridge
@relay.handle(Output(...), Action("close", bridge="folder.tabbar"), State(...))
def _(event, ...): ...
```

### Why

In 3.0, action names lived in a global namespace — one handler per
name across the entire app. If two emitters on different bridges
genuinely used the same action string, you had to namespace at the
action-name level (`tabbar.close` vs `drawer.close`) because there
could only be one handler per name. The `bridge=` kwarg on `Action`
lets you keep the short name and disambiguate via bridge instead.

### Routing rule (specificity)

When a bridge fires an action, the dispatcher prefers a pinned
`(name, bridge)` match over a wildcard `(name, None)`. Concretely:

  * `Action("close")` (no bridge) is a wildcard — fires for any bridge
    that emits "close" and has no pinned override.
  * `Action("close", bridge="x")` is pinned — fires only when bridge
    "x" emits "close", shadowing any wildcard for that bridge.

Per (action_name, bridge_id) key, at most one handler can register.
Two wildcards for the same name still collide (today's rule). Two
pinned handlers for the same `(name, bridge)` collide. A wildcard
plus per-bridge pins for the same name is fine — pins shadow the
wildcard for their bridge only.

### `validate()` addition

  * `unreachable-handler` — a handler is pinned to a bridge id that no
    emitter in the layout actually writes to. The handler will never
    fire; usually a typo or stale wiring.

### Backwards compatibility

`Action(name)` (no `bridge=`) behaves exactly as in 3.0. Every
existing `@relay.handle` decorator continues to work without
modification. The error message for two wildcards colliding now
mentions `bridge=` as the disambiguation tool.

### Implementation

`Action` stores `name` and `bridge_id` (default `None`). Routing
tables in the dispatcher split into `pinned_by_key{(name, bridge)}`
and `wildcard_by_action{name}`. Lookup tries pinned first, falls
back to wildcard. Roughly 25 lines of changes plus tests and docs.

## [3.0.0] — 2026-04-22

The dispatch surface is rebuilt around Dash's own callback primitives.
`relay.registry(...)` and the `Registry` class are gone; handlers are
declared with `@relay.handle` decorators that read like Dash callbacks
with a single `Action(...)` dependency standing in for `Input`.

### Why

The 1.x and 2.x registries packaged the bridge wiring as a custom
class with its own kwargs (`state=` / `output=` / `bridge=`) and its
own handler-signature contract. Reading a registry call required
learning a small DSL that mirrored — but didn't reuse — Dash's own
vocabulary. 3.0 collapses that:

  * Handlers are decorated, not registered through a class.
  * Dependencies are spelled with the same `Output`, `State` Dash
    users already know, plus one new `Action(name)` primitive that
    slots where `Input` would.
  * The handler signature follows Dash's positional convention (one
    arg per declared dependency, in declaration order, with `Output`
    declarations excluded).
  * Bridge ownership lives at the emitter side only; handlers don't
    declare which bridge they listen on.

The library shrinks: no `Registry` class, no `output=`/`state=`
kwargs, no per-handler signature contract beyond "Dash with `Action`
in the trigger slot."

### Public surface

```python
import dash_relay as relay
from dash_relay import Action
from dash import Output, State

relay.install(app)                                            # runtime + dispatcher
relay.bridge(id="bridge")                                     # dcc.Store sink
relay.emitter(component, action, bridge="bridge", ...)        # wrap a component
relay.validate(layout, app=None)                              # linter

@relay.handle(Output("x", "data"), Action("a"), State("x", "data"))
def handler(event, x): ...
```

### Rename map (from 1.x)

| 1.x | 3.0 |
|---|---|
| `events = relay.registry(app, state="x")` | `@relay.handle(Output("x", "data"), Action("..."), State("x", "data"))` |
| `events = relay.registry(app, state=["a", "b"])` | each handler declares its own `Output(...)` and `State(...)` deps |
| `@events.handler("foo")` | `@relay.handle(Output(...), Action("foo"), State(...))` |
| `def _(state, payload, event):` | `def _(event, state):` (positional, mirrors Dash) |
| `def _(states, payload, event):` (multi-state) | `def _(event, a, b):` for `State("a", ...), State("b", ...)` |
| `state["x"] += 1; return state` | `return {**state, "x": state["x"] + 1}` (or `s = deepcopy(state); s["x"] += 1; return s`) |
| `events.dispatch(event, state)` | `app._dash_relay_dispatcher(event, state)` (test wrapper) |

### Architecture

`@relay.handle` decorators accumulate in a module-level pending pool.
`install(app)` consumes the pool: for each registered bridge it
registers one Dash callback whose `Output`s are the union of every
handler's declared outputs and whose `State`s are the union of every
handler's declared states. The dispatcher routes by action name and
pads non-touched outputs with `no_update`. When more than one bridge
is registered, `install()` forces `allow_duplicate=True` on every
output so the per-bridge dispatchers coexist.

### Construction-time invariants

- Each `@handle` block must contain at least one `Output` and exactly
  one `Action` (multi-`Action` handlers raise `NotImplementedError`
  in v1).
- Two handlers can't claim the same action name — `install()` raises
  `ValueError` if you try.
- Handler-declared `Output`/`State` ids are checked against the
  layout's `dcc.Store`s by `validate()`.

### `validate()` codes

When `app=` is passed (after install):
- `orphan-emitter` — emitter action has no matching handler
- `orphan-handler` — handler has no emitter in the layout
- `output-not-found` — handler `Output` id not in layout
- `state-not-found` — handler `State` id not in layout

The handler pool is cached on the app object as `app._dash_relay_handlers`
so `validate()` can introspect after install.

### Migration

Migration is mechanical:

1. Delete every `events = relay.registry(...)` construction.
2. For each `@events.handler("foo")`, rewrite as
   `@relay.handle(Output(...), Action("foo"), State(...))` with the
   appropriate Output/State dependencies pulled from the old
   registry's `state=` arg.
3. Convert the handler signature: `def _(state, payload, event)` →
   `def _(event, state)`. For multi-state handlers, each of the old
   `state` tuple's slots becomes its own positional arg matching the
   declared `State(...)`.
4. Move `relay.install(app)` to AFTER all decorators run.
5. Tests that called `events.dispatch(...)` switch to
   `app._dash_relay_dispatcher(...)` (same shape: positional event +
   state values).

### Removed

- `relay.registry()` and `Registry` class
- `Registry.dispatch()`, `Registry.handler()`, `Registry.actions()`,
  `Registry.output_ids()`, `Registry.state_ids()`, `Registry.bridge_ids()`
- `validate(layout, registry=...)` — replaced with `validate(layout, app=...)`

## [1.1.2] — 2026-04-18

First release shipped via the new GitHub Actions Trusted-Publishing
pipeline. No library code or surface changes — this is the inaugural
test of `.github/workflows/publish.yml`. Future releases follow the
same path: tag `vX.Y.Z`, push the tag, approve the prod step.

## [1.1.1] — 2026-04-18

**Breaking kwarg renames on the public surface.** Normally these would
force a major-version bump; shipping under 1.1 instead because the
package is one day old on PyPI with effectively zero adopters and the
rename-cost-now vs carry-the-inconsistency-forever tradeoff clearly
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
