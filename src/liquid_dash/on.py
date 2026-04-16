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
    event: str = "click",
    to: str = DEFAULT_BRIDGE_ID,
    target: Any = None,
    source: Any = None,
    prevent_default: bool = False,
):
    if not isinstance(action, str) or not action.strip():
        raise ValueError("on(): action must be a non-empty string")
    if not isinstance(event, str) or not event.strip():
        raise ValueError("on(): event must be a non-empty string")

    try:
        payload_json = json.dumps(payload)
        target_json = json.dumps(target)
        source_json = json.dumps(source)
    except TypeError as exc:
        raise ValueError("on(): payload, target, and source must be JSON serializable") from exc

    attrs = {
        "data-ld-action": action,
        "data-ld-event": event,
        "data-ld-payload": payload_json,
        "data-ld-bridge": to or "",
        "data-ld-target": target_json,
        "data-ld-source": source_json,
        "data-ld-prevent-default": "true" if prevent_default else "false",
    }

    return html.Div([component], style=_WRAP_STYLE, **attrs)


def on(
    *args,
    payload: Any = None,
    event: str = "click",
    to: str = DEFAULT_BRIDGE_ID,
    target: Any = None,
    source: Any = None,
    prevent_default: bool = False,
) -> Any:
    """Attach a Liquid Dash event to a Dash component.

    Two forms:

        on(component, action, ...) -> wrapped component
            Wraps `component` so that when the named DOM `event` (default
            "click") fires on it or any descendant, a payload is written to
            the target bridge store.

        on(action, ...) -> callable
            Returns a reusable emitter `f(component, **extra)` that applies
            the same action + defaults to any component passed to it. Keyword
            overrides (e.g. `payload=...`) supplied to `f` override those
            supplied to `on()`.

    Any DOM event name works for `event=`. The client-side handler registers
    listeners lazily as new event names appear in the layout.
    """
    kw = {
        "payload": payload,
        "event": event,
        "to": to,
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
            raise TypeError("on(): second argument must be the action name (str)")
        return _wrap(component, action=action, **kw)

    raise TypeError(
        "on() requires either (component, action, ...) or (action, ...) "
        "to create a reusable emitter."
    )
