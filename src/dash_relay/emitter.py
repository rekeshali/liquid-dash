from __future__ import annotations

import json
from typing import Any, Callable

from dash import html

from .bridge import DEFAULT_BRIDGE_ID


_WRAP_STYLE = {"display": "contents"}


def _wrap(
    component,
    *,
    action: str,
    payload: Any = None,
    on: str = "click",
    bridge: str = DEFAULT_BRIDGE_ID,
    target: Any = None,
    source: Any = None,
    prevent_default: bool = False,
):
    if not isinstance(action, str) or not action.strip():
        raise ValueError("emitter(): action must be a non-empty string")
    if not isinstance(on, str) or not on.strip():
        raise ValueError("emitter(): on must be a non-empty string")

    try:
        payload_json = json.dumps(payload)
        target_json = json.dumps(target)
        source_json = json.dumps(source)
    except TypeError as exc:
        raise ValueError("emitter(): payload, target, and source must be JSON serializable") from exc

    attrs = {
        "data-relay-action": action,
        "data-relay-on": on,
        "data-relay-payload": payload_json,
        "data-relay-bridge": bridge or "",
        "data-relay-target": target_json,
        "data-relay-source": source_json,
        "data-relay-prevent-default": "true" if prevent_default else "false",
    }

    return html.Div([component], style=_WRAP_STYLE, **attrs)


def emitter(
    *args,
    payload: Any = None,
    on: str = "click",
    bridge: str = DEFAULT_BRIDGE_ID,
    target: Any = None,
    source: Any = None,
    prevent_default: bool = False,
) -> Any:
    """Wrap a Dash component as a Dash Relay event emitter.

    Two forms:

        emitter(component, action, ...) -> wrapped component
            Wraps `component` so that when the DOM event named by `on=`
            (default "click") fires on it or any descendant, a payload
            is written to the target bridge store.

        emitter(action, ...) -> callable
            Returns a reusable emitter factory `f(component, **extra)` that
            applies the same action + defaults to any component passed to it.
            Keyword overrides (e.g. `payload=...`) supplied to `f` override
            those supplied to `emitter()`.

    Any DOM event name works for `on=`. The client-side handler registers
    listeners in capture phase, lazily, as new event names appear in the
    layout — so non-bubbling events (`focus`, `blur`) and custom events
    dispatched via `element.dispatchEvent(new CustomEvent(...))` work too.
    See `tests/test_event_types.py` for the verified matrix.
    """
    kw = {
        "payload": payload,
        "on": on,
        "bridge": bridge,
        "target": target,
        "source": source,
        "prevent_default": prevent_default,
    }

    if len(args) == 1 and isinstance(args[0], str):
        action = args[0]

        def _emitter(component, **extra) -> Any:
            merged = {**kw, **extra}
            return _wrap(component, action=action, **merged)

        return _emitter

    if len(args) == 2:
        component, action = args
        if not isinstance(action, str):
            raise TypeError("emitter(): second argument must be the action name (str)")
        return _wrap(component, action=action, **kw)

    raise TypeError(
        "emitter() requires either (component, action, ...) or (action, ...) "
        "to create a reusable emitter factory."
    )
