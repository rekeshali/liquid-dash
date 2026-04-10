from __future__ import annotations

import json
import time
from typing import Any

from .exceptions import InvalidEventError
from .types import EventPayload


_JSON_PRIMITIVES = (dict, list, str, int, float, bool, type(None))


def _ensure_jsonable(value: Any) -> None:
    try:
        json.dumps(value)
    except TypeError as exc:
        raise InvalidEventError("Event payload must be JSON serializable.") from exc


def emit_event(
    action: str,
    *,
    target: str | None = None,
    payload: Any = None,
    source: str | None = None,
    bridge: str | None = None,
    event_type: str = "click",
    timestamp: float | None = None,
) -> EventPayload:
    """Build and validate a normalized event payload."""
    if not isinstance(action, str) or not action.strip():
        raise InvalidEventError("Event action must be a non-empty string.")

    if payload is not None and not isinstance(payload, _JSON_PRIMITIVES):
        _ensure_jsonable(payload)
    else:
        _ensure_jsonable(payload)

    return {
        "action": action,
        "target": target,
        "payload": payload,
        "source": source,
        "bridge": bridge,
        "event_type": event_type,
        "timestamp": time.time() if timestamp is None else timestamp,
    }
