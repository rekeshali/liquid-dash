from __future__ import annotations

from dash import dcc


def EventBridge(
    id: str,
    *,
    data: dict | None = None,
    storage_type: str = "memory",
    clear_on_read: bool = False,
):
    """Return a stable dcc.Store used as a delegated event sink."""
    return dcc.Store(
        id=id,
        data=data,
        storage_type=storage_type,
        clear_data=clear_on_read,
    )
