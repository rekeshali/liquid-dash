from __future__ import annotations

from dash import dcc


DEFAULT_BRIDGE_ID = "bridge"


def bridge(id: str = DEFAULT_BRIDGE_ID) -> dcc.Store:
    """Return a dcc.Store that acts as the event sink for liquid-dash.

    Drop this component into your layout once per bridge you need. The default
    id `"bridge"` matches what `on()` and `handler()` target by default.
    """
    return dcc.Store(id=id, data=None, storage_type="memory")
