from __future__ import annotations

import json
from typing import Any

from dash import html

from .events import emit_event
from ._util import drop_none


def _action_attrs(
    *,
    action: str,
    target: str | None,
    payload: Any,
    source: str | None,
    bridge: str | None,
    event_type: str,
) -> dict[str, Any]:
    emit_event(
        action,
        target=target,
        payload=payload,
        source=source,
        bridge=bridge,
        event_type=event_type,
    )
    return {
        "data-ld-action": action,
        "data-ld-target": target or "",
        "data-ld-payload": json.dumps(payload),
        "data-ld-source": source or "",
        "data-ld-bridge": bridge or "",
        "data-ld-event": event_type,
    }


def action_button(
    label,
    *,
    action: str,
    target: str | None = None,
    payload: Any = None,
    source: str | None = None,
    bridge: str | None = None,
    event_type: str = "click",
    id: str | None = None,
    className: str | None = None,
    style: dict | None = None,
    disabled: bool = False,
    title: str | None = None,
    n_clicks=None,
    **kwargs,
):
    return html.Button(
        label,
        **drop_none({
            "id": id,
            "className": className,
            "style": style,
            "disabled": disabled,
            "title": title,
            "n_clicks": n_clicks,
        }),
        **_action_attrs(
            action=action,
            target=target,
            payload=payload,
            source=source,
            bridge=bridge,
            event_type=event_type,
        ),
        **kwargs,
    )


def action_div(
    children=None,
    *,
    action: str,
    target: str | None = None,
    payload: Any = None,
    source: str | None = None,
    bridge: str | None = None,
    event_type: str = "click",
    id: str | None = None,
    className: str | None = None,
    style: dict | None = None,
    role: str = "button",
    tabIndex: int = 0,
    title: str | None = None,
    **kwargs,
):
    return html.Div(
        children,
        **drop_none({
            "id": id,
            "className": className,
            "style": style,
            "role": role,
            "tabIndex": tabIndex,
            "title": title,
        }),
        **_action_attrs(
            action=action,
            target=target,
            payload=payload,
            source=source,
            bridge=bridge,
            event_type=event_type,
        ),
        **kwargs,
    )


def action_item(
    children=None,
    *,
    action: str,
    target: str | None = None,
    payload: Any = None,
    source: str | None = None,
    bridge: str | None = None,
    event_type: str = "click",
    id: str | None = None,
    className: str | None = None,
    style: dict | None = None,
    role: str = "button",
    tabIndex: int = 0,
    title: str | None = None,
    **kwargs,
):
    return action_div(
        children,
        action=action,
        target=target,
        payload=payload,
        source=source,
        bridge=bridge,
        event_type=event_type,
        id=id,
        className=className,
        style=style,
        role=role,
        tabIndex=tabIndex,
        title=title,
        **kwargs,
    )
