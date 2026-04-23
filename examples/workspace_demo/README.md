# Workspace demo

![Workspace demo](dash-relay-demo.gif)

A larger, product-shaped example: a nested Folders → Tabs → Panels
workspace with 18 action types (add, rename, reorder, duplicate,
delete, badge-cycle, per-panel settings, inline editor form, …). All
18 actions dispatch through a single Dash Relay registry, so the Dash
callback graph stays at 5 regardless of how many entities the user
adds.

```bash
python examples/workspace_demo/app.py
```

## What this example is for

This is the "does it scale to a real-looking app?" demo. If the
head-to-head comparison (`examples/pattern_matching_vs_event_bridge/`)
is the argument *for* the library, this is the existence proof that
the pattern survives contact with a non-trivial surface:

- **Nested entities** — folder > tab > panel, each with its own
  action surface
- **Shared editor form** — one form hydrates from whichever entity
  was most recently "opened"
- **Multiple stores from one bridge** — handlers declare their own
  Outputs/States; the library unions per bridge so one Dash callback
  writes both `canvas-store` and `editor-store` from the
  `ui-events` bridge
- **Pure-function dispatcher** — the same `_ACTIONS` table used at
  runtime is called directly from unit tests via
  `reduce_ui_event(canvas, editor, event)`

The callback graph size (5) is verified by
`tests/test_workspace_demo.py::test_workspace_demo_has_small_fixed_callback_graph`
— adding a new action type is a new entry in `_ACTIONS`, not a new
Dash callback.
