# Changelog

All notable changes to this project are documented here. Format based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
