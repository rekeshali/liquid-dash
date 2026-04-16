# Pure-Dash pitfalls vs liquid-dash

Two side-by-side implementations of the same toggleable, filterable,
growable list. Use them to *see* the difference in callback activity in
the browser dev tools, not just read about it.

```bash
python examples/pure_dash_pitfall/pure_dash.py          # buggy by design
python examples/pure_dash_pitfall/with_liquid_dash.py   # same UX, no pitfalls
python examples/pure_dash_pitfall/side_by_side.py       # both, in one page
```

Open the browser dev tools, filter Network by `_dash-update-component`,
and click around. The two apps look identical; their callback panels
do not.

`side_by_side.py` mounts both implementations next to each other and
embeds an in-page console under each that logs every
`_dash-update-component` fire attributed to its side — the same
information you'd squint at in dev tools, visible at a glance.

## Three pitfalls in `pure_dash.py`

### 1. Spurious callback fires when dynamic subscribers appear

Pattern-matching Inputs like
`Input({"type": "del", "index": ALL}, "n_clicks")` subscribe to *every*
component in the layout that matches the pattern. When the layout
re-renders and adds a new matching component, the callback's input list
changes — so Dash fires it.

Click **Add item**: `do_delete` and `do_toggle` both fire even though
nobody clicked delete or toggle. The `if not ctx.triggered_id` guard
catches the no-op, but the round trip happened, the function ran, and
any logging or metric inside it would have recorded a phantom event.
With every new ALL pattern in the app this footgun multiplies.

The liquid-dash version has exactly one Input on the bridge store. The
store only updates when a real DOM event reaches it. Mounting new
buttons does nothing.

### 2. Race between concurrent writers to the same Store

The pure-Dash app has four callbacks writing to `Output("state", "data",
allow_duplicate=True)`. If two of them fire in the same round
(double-click, fast keyboard, network delay coalescing), each reads the
current state and writes back its independent version. One write wins;
the other is silently overwritten.

This is why `allow_duplicate=True` exists with a warning in the Dash
docs. It's also why production apps that grow this pattern eventually
add an idempotency layer, an external state machine, or a Redux-style
single reducer — all of which liquid-dash gives you for free with one
writer.

The liquid-dash version has exactly one writer (`handler`'s internal
dispatch callback). Updates are linearized by Dash's normal callback
ordering against a single Output.

### 3. Stale `n_clicks` on remount

`html.Button` carries its click count in the component's `n_clicks`
prop. When a component is unmounted and a new one with the same id
appears, Dash's reconciliation may carry the prior `n_clicks` value
forward — version-dependent and timing-dependent — which can fire the
callback as if the button were just clicked.

To reproduce: toggle item 2 (it becomes done), switch filter to "open"
(item 2 disappears), switch back to "all" (item 2 reappears). Depending
on Dash version and reconciliation, you may see the toggle re-fire on
remount and flip `done` back without any user action. Even when it
doesn't actively misbehave, you're trusting reconciliation to do the
right thing across rebuilds.

The liquid-dash version doesn't read state from component props. The
toggle action is sent on the click event itself; remounting carries no
history.

## Why the contrast matters

The pure-Dash version isn't naive — every guard and `prevent_initial_call`
flag is in the right place. The bugs come from the architecture, not
sloppiness:

- **Pattern-matching Inputs** subscribe to layout, so layout changes
  fire callbacks.
- **`allow_duplicate=True`** is the official escape hatch when many
  callbacks want to update one Store, and it leaks the fact that Dash
  doesn't serialize them for you.
- **Component-prop click counters** make a click history live in the DOM
  tree, so any reconciliation has to preserve or reset that history
  correctly.

liquid-dash dodges the architecture rather than fighting it: events ride
on actual DOM events through one client-side handler, deliver to one
store, and one server-side reducer transforms state. Same Dash, same
components, fewer ways for it to go sideways.

## Callback graph size

Counted at load time:

| | callbacks registered |
|---|---|
| `pure_dash.py` | **5** (one per action type, plus the renderer) |
| `with_liquid_dash.py` | **2** (bridge dispatch + renderer) |

The pure-Dash count grows with the number of action types; liquid-dash
stays at 2 no matter how many actions you add.

You can verify this in either file:

```python
print(len(app.callback_map))
```

What grows with list size in the pure-Dash app is **callback firings
per user interaction**, not just registrations — every ALL-pattern
subscriber re-evaluates whenever the matching layout subset changes.
