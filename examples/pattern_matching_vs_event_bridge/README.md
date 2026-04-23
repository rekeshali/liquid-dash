# Pattern-matching callbacks vs. the event bridge

![Head-to-head demo](comparison-demo.gif)

A nested workspace surface — Folders → Tabs → Panels with 9 action types
across 3 entity levels — implemented two ways in one Dash app. Each
column calls the same state-mutation helpers. Only the wiring between
the UI and those helpers differs.

- **Left column: pattern-matching callbacks**, written with the
  canonical guard so phantom fires from remounted ALL-pattern
  subscribers return `no_update` cleanly. This is idiomatic modern
  Dash.
- **Right column: the Dash Relay event bridge** with per-action
  handlers registered on a single dispatch callback.

```bash
python examples/pattern_matching_vs_event_bridge/nested_side_by_side.py
```

Each column has a **▶ Run test** button that plays the same 9-click
sequence against its side. Below each timeline, a running summary
tracks cumulative activity:

```
Tests run: N    Round-trips: N    Total: N KB    Total time: N s
```

A fixed **Head-to-head** panel in the top-right corner has a
**▶ Run both tests** button that fires both columns in parallel and
aggregates the per-run deltas into percent-difference cards
(`80% fewer round-trips`, `83% less data`, `40% faster`). The aggregate
accumulates across every Run-both click so the raw before → after
numbers grow with use.

## Measured contrast (one test run = 9 clicks)

Numbers below are from an Apple M1 Pro running the Dash dev server
locally (so "network transit" is loopback). Absolute times will differ
on other hardware; the percent deltas are more transferable because
both columns live in the same process.

| | callback graph | round-trips | bytes | wall time |
|---|---|---|---|---|
| Pattern-matching column | 10 callbacks | ~88 | ~190 KB | ~1.7 s |
| Event-bridge column | 2 callbacks + 9 handlers | ~18 | ~33 KB | ~1.0 s |
| Event-bridge delta | ~80% smaller graph | ~80% fewer | ~83% less | ~40% faster |

Percentages are stable across runs (both columns scale proportionally).
Absolute numbers grow per run because each click operates on more
state — which is exactly where the pattern-matching column's per-trip
payload cost scales linearly and the event-bridge column's doesn't.

### What "wall time" is measured between

Per click, the timer starts when a capture-phase JS listener sees the
`click` event (before any Dash callback) and stops when the *last*
`fetch(_dash-update-component)` triggered by that click resolves
(response headers + body received at the browser, before Dash parses
the payload or rerenders the DOM). "Total time" is the sum of those
per-click intervals across all 9 clicks in a run.

So wall time captures **server round-trip cost** — server processing
plus network transit plus any serialized fetch queueing Dash does for
dependent callbacks. It does **not** include client-side rendering or
browser paint. Instrumentation DOM mutations (the dot and console-line
draws) are deferred via `requestAnimationFrame` so they don't sit
inside the timing window and bias whichever side fires more fetches.

### What "2 callbacks + 9 handlers" means

Both sides have the same number of *actions* (9). The difference is
whether those actions are first-class Dash callbacks.

- **Pattern-matching column:** one Dash callback per action type
  (9) + renderer (1) = **10 in the callback graph**. Every action
  callback is a pattern-matching subscriber. Adding a new action
  adds a new pattern callback.
- **Event-bridge column:** one Dash callback for dispatch
  (1) + renderer (1) = **2 in the callback graph**. Per-action logic
  lives as 9 handlers registered against the bridge via
  `@relay.callback(Output(...), Action("..."), State(...))`. Adding
  a new action is a new handler — not a new Dash callback, not a new
  pattern-matching subscriber, no new phantom-fire surface.

The callback *graph* is what carries cost. Handlers are Python dict
lookups at dispatch time — they don't phantom-fire, don't subscribe
to layout, don't compete for `allow_duplicate` writes.

## Where the contrast comes from

### 1. Pattern-matching Inputs subscribe to layout

`Input({"type": "del", "index": ALL}, "n_clicks")` re-fires whenever
the set of matching components changes. In a nested dynamic surface,
every `folder.add`, `tab.add`, `panel.delete`, etc. reshapes several
pattern sets at once. Even with the canonical guard
(`if not ctx.triggered_id or ctx.triggered[0]["value"] is None: return
no_update`), the server still does the round-trip to return
`no_update` — and ships the full State store with it.

### 2. Payload threads through pattern IDs

`panel.add` wants a `kind`. The idiomatic approach is to put the kind
in the pattern ID: `{"type": "panel-add", "kind": ALL}`. That works,
but multi-parameter actions (e.g. `panel.badge.cycle` needing
panel_id + badge_index) mean more fields in the ID dict. The event
bridge gives you a separate JSON `payload` field, which carries
whatever shape you want without widening the ID.

### 3. Multiple writers to one store

Every action callback in the pattern-matching column writes to
`canvas.data` with `allow_duplicate=True`. Ten writers against one
store work fine, but any invariant you want to maintain (e.g. undo,
optimistic updates) has to account for all ten writers. The
event-bridge column has one writer — the dispatch callback — so
invariants live in one place.

## What the event bridge buys you (and what it doesn't claim)

### Directly measured in this demo

- **Faster round-trips** — ~40% less time from user click to final
  server response arriving at the browser (summed across the 9-click
  test sequence). This is specifically the server-round-trip window;
  client-side render time is not counted.
- **Less network traffic** — ~83% fewer bytes over the wire, because
  every phantom round-trip on the pattern-matching side ships the
  full State store just to return `no_update`.
- **Less wiring code** — 108 lines vs 31 lines (71% less) for the
  plumbing between UI and mutation helpers. The mutation helpers
  themselves (`do_folder_add`, `do_panel_duplicate`, …) are identical
  on both sides — the savings are all in the plumbing.
- **Smaller callback graph** — 10 Dash callbacks vs 2 + 9 handlers.
  Handlers aren't Dash primitives, so they don't carry pattern
  subscription, phantom-fire, or `allow_duplicate` overhead.

### Inferred but not measured

- **Memory / allocation pressure** is almost certainly lower on the
  event-bridge side — each phantom round-trip on the pattern-matching
  side allocates a full State copy only to return `no_update`, so the
  per-click allocation count is ~5× higher. The bytes-over-wire
  number is a decent proxy but not proof; we never put the server
  process on a scale.

### Qualitative but real

- **Easier to reason about.** One dispatch callback, one store
  writer, one place where invariants live.
- **Fewer details to remember.** The pattern-matching approach asks
  the author to remember:
    - `if not ctx.triggered_id or ctx.triggered[0]["value"] is None:
      return no_update` — the canonical guard for ALL-pattern
      callbacks. The weaker `if not ctx.triggered_id` variant
      silently mutates state on phantom fires.
    - Pattern-matching ALL semantics and knowing when matched sets
      change.
    - `allow_duplicate=True` multi-writer coordination on shared
      stores.
    - Payload threading through pattern ID dicts for
      multi-parameter actions.
    - Re-checking phantom-fire behavior every time a new pattern
      callback is added.

Event-bridge handlers are just `@relay.callback(Output(...),
Action("name"), State(...)) def _(event, s): ...` with no defensive
boilerplate. None of the above applies.

## What Dash Relay trades away

Dash Relay adds a client-side script (~120 lines) and one wrapper
`html.Div` per interactive element. Events flow through `dcc.Store`
rather than the standard Dash callback graph. Concretely, the
tradeoffs are:

- **Optional extra DOM nodes.** `Emitter(...).wrap(component)` puts
  the component inside a `display: contents` div. Visually invisible,
  and layout is unchanged, but the extra node is there. CSS selectors
  or third-party JS that walk DOM siblings may need to account for
  it. Use `Emitter(...).attrs()` splatted onto the component when you
  need no wrapper at all (preserves `>` direct-child selectors and
  flex/grid child positioning).
- **Action names are magic strings.** `Emitter(action="panel.add")`
  and `Action("panel.add")` are linked by string identity, with no
  "find references" path through the IDE. `relay.validate(app.layout,
  app=app)` catches mismatches (`missing-handler`,
  `unreachable-handler`, `duplicate-handler`) at load time — but it
  has to be called. Pure-Dash's Python-symbol linkage is enforced
  without any tooling step.
- **Stack traces go through the dispatcher.** A `ZeroDivisionError` in a
  handler shows the relay dispatcher frame before landing
  in your code. Pure-Dash tracebacks land directly on the failing
  callback. Small ergonomics tax when debugging.
- **The Dash dev panel callback view is less useful.** The graph
  visualizer shows one dispatch callback, not 9 per-action handlers,
  because handlers aren't Dash primitives. If you rely on the dev
  panel's callback graph heavily, you'll need to read the handler
  registry separately.

For a static layout with a fixed number of interactions, pattern
matching is lighter-weight. The event bridge earns its keep when the
layout is dynamic, entities nest, and the number of action types is
growing.
