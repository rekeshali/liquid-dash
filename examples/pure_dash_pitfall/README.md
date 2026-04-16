# Pure Dash vs Liquid Dash

A side-by-side demo of the same toggleable, filterable, growable list,
implemented two ways in one Dash app. Each column has an in-page
console that logs every `_dash-update-component` fire attributed to its
side, so you can *see* the difference in callback activity.

```bash
python examples/pure_dash_pitfall/side_by_side.py
```

The two columns look identical to a user. Their consoles do not.

## Three patterns where pure-Dash gets noisy

### 1. Pattern-matching Inputs subscribe to layout

Pattern-matching Inputs like `Input({"type": "del", "index": ALL},
"n_clicks")` subscribe to *every* component in the layout that matches
the pattern. When the layout re-renders and adds a new matching
component, the callback's input list changes — so Dash fires it.

Click **Add item** in the pure-Dash column: the delete and toggle
callbacks both fire as their input lists grow, even though nobody
clicked delete or toggle. Whether `ctx.triggered_id` is set or `None`
depends on Dash's matching rules at the moment, so an `if not
ctx.triggered_id` guard isn't always enough — the body can still run
and mutate state.

The Liquid Dash column has exactly one Input on the bridge store. The
store only updates when a real DOM event reaches it. Mounting new
buttons does nothing.

### 2. Many writers to the same Store

The pure-Dash column has four callbacks writing to `Output("state",
"data", allow_duplicate=True)`. If two of them fire in the same round
(double-click, fast keyboard, network delay coalescing), each reads the
current state and writes back its independent version. One write wins;
the other is silently overwritten.

`allow_duplicate=True` exists for this case and the Dash docs flag it.
Production apps that grow this pattern eventually add an idempotency
layer, an external state machine, or a Redux-style single reducer.

The Liquid Dash column has exactly one writer (`handler`'s internal
dispatch callback). Updates are linearized by Dash's normal callback
ordering against a single Output.

### 3. `n_clicks` lives in the DOM tree

`html.Button` carries its click count in the component's `n_clicks`
prop. When a component is unmounted and a new one with the same id
appears, Dash's reconciliation may carry the prior `n_clicks` value
forward — version-dependent and timing-dependent — which can fire the
callback as if the button were just clicked.

To reproduce: toggle item 2 (it becomes done), switch filter to "open"
(item 2 disappears), switch back to "all" (item 2 reappears).
Reconciliation usually does the right thing, but you're trusting it
across rebuilds.

The Liquid Dash column doesn't read state from component props. The
toggle action is sent on the click event itself; remounting carries no
history.

## Why the contrast matters

The pure-Dash column isn't naive — every guard and `prevent_initial_call`
flag is in the right place. The extra activity comes from the patterns,
not sloppiness:

- **Pattern-matching Inputs** subscribe to layout, so layout changes
  fire callbacks.
- **`allow_duplicate=True`** is the official escape hatch when many
  callbacks want to update one Store, and it leaves the linearization
  to Dash's callback ordering.
- **Component-prop click counters** put click history inside the DOM
  tree, so reconciliation has to preserve or reset that history.

Liquid Dash sidesteps the patterns rather than fighting them: events
ride on actual DOM events through one client-side handler, deliver to
one store, and one server-side reducer transforms state. Same Dash,
same components, fewer moving parts that can interact unexpectedly.

## Callback graph size

Counted at load time:

| | callbacks registered |
|---|---|
| pure-Dash column | **5** (one per action type, plus the renderer) |
| Liquid Dash column | **2** (bridge dispatch + renderer) |

The pure-Dash count grows with the number of action types; Liquid Dash
stays at 2 no matter how many actions you add.

What grows with list size in the pure-Dash column is **callback
firings per user interaction**, not just registrations — every
ALL-pattern subscriber re-evaluates whenever the matching layout
subset changes.
