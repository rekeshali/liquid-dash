# liquid-dash

`liquid-dash` is a small helper library for building **more app-like Dash interfaces**.

Dash is great when your page is mostly known ahead of time. It gets awkward when people can keep creating, renaming, deleting, and switching between things like cards, tabs, or workspaces while the interface is already running. You can absolutely make that work in plain Dash, but the wiring gets repetitive fast.

`liquid-dash` gives you a simple pattern for that kind of interface:

- send clicks through a **stable event bridge**
- treat fast-changing areas as **dynamic regions**
- render the screen from state instead of attaching lots of one-off callback plumbing

It is **not** a replacement for Dash. It is a focused layer for the part of Dash that starts feeling clumsy when the UI becomes highly dynamic.

## What problem it solves

A common Dash pain point looks like this:

- the user can add and remove lots of items
- each item has buttons or menus
- the whole section gets rebuilt often
- direct callback wiring starts to feel brittle or hard to read

`liquid-dash` helps by making those moving parts easier to route through a small, predictable callback graph.

## Why this library exists

There are already good Dash tools out there. Some help with layout. Some add utility components. Some make browser events easier to listen to.

But there is not much that turns this specific idea into a small approachable API:

> “I want parts of my Dash app to behave more like a little workspace or editor, without exploding the callback wiring.”

That is the gap `liquid-dash` is trying to fill.

## What you get

- **`EventBridge`** for sending UI actions through one stable input
- **`StableRegion`** and **`DynamicRegion`** for marking which parts of the layout are steady vs frequently rebuilt
- **`action_button`**, **`action_div`**, and **`action_item`** for delegated UI actions
- **`validate_layout`** for catching a few common mistakes early
- **`configure(app)`** to copy the required browser asset into your Dash app’s assets folder

## Install

```bash
pip install -e .
```

## Run tests

```bash
pytest
```

## Run the examples

```bash
python examples/live_test/app.py
python examples/workspace_demo/app.py
```

### `examples/live_test/app.py`

A tiny starter demo.

It shows a dynamic list of cards that can be added and deleted while the list is rebuilt from state.

### `examples/workspace_demo/app.py`

A larger demo.

It shows a nested interface with:

- folders
- tabs inside folders
- panels inside tabs
- per-panel actions
- one shared editor for renaming and settings

It is meant to show that you can build a fairly dynamic interface without pre-registering separate callback sets for every possible panel.

## Minimal example

```python
from dash import Dash, Input, Output, State, dcc, no_update
from liquid_dash import EventBridge, StableRegion, DynamicRegion, action_button, configure

app = Dash(__name__)
configure(app)

app.layout = StableRegion(
    id="shell",
    children=[
        dcc.Store(id="app-state", data={"cards": [{"id": "card-1", "title": "One"}]}),
        EventBridge(id="ui-events"),
        DynamicRegion(
            id="cards",
            bridge="ui-events",
            children=[
                action_button("Delete", action="card.delete", target="card-1", bridge="ui-events")
            ],
        ),
    ],
)

@app.callback(
    Output("app-state", "data"),
    Input("ui-events", "data"),
    State("app-state", "data"),
    prevent_initial_call=True,
)
def on_event(event, state):
    if not event:
        return no_update
    return state
```

## Current status

This package is intentionally small.

It is best thought of as an early, focused utility for people building highly dynamic Dash interfaces.
