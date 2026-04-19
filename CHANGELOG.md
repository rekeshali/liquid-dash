# Changelog

All notable changes to this project are documented here. Format based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
