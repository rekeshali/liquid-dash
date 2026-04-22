"""The ``Action`` dependency primitive.

``Action`` slots into the same position Dash's ``Input`` would in a
callback's dependency list, but identifies a relay action name rather
than a component property.

Usage::

    from dash import Output, State
    from dash_relay import Action, handle

    @handle(
        Output("tab_store", "data"),
        Action("tab.close"),
        State("tab_store", "data"),
    )
    def close_tab(event, tab):
        ...

The bridge an action travels on is normally determined by the emitter
(which declares ``bridge=...``); the handler doesn't need to know.
The optional ``bridge=`` kwarg on ``Action`` is purely a
deduplication aid for apps where two emit-sites on different bridges
genuinely use the same action name and want different handlers.
"""
from __future__ import annotations


class Action:
    """A relay action dependency.

    Wraps an action name string. In v1 only string names are supported;
    dict-shaped (pattern-matchable) actions are deferred to a future
    version.

    The optional ``bridge`` kwarg pins this handler to a specific bridge:
    the dispatcher will only invoke this handler when the named bridge
    fires the matching action. With ``bridge=None`` (the default) the
    handler is a wildcard — invoked whenever any bridge fires the
    matching action. Pinned handlers shadow wildcards for their specific
    bridge; for any other bridge, the wildcard handler runs.

    Two handlers can't share the same ``(name, bridge)`` key. Two
    wildcards (``bridge=None``) for the same name are also a collision.
    A wildcard plus a per-bridge pin for the same name is fine — the
    pin shadows the wildcard for its bridge only.
    """

    __slots__ = ("name", "bridge_id")

    def __init__(self, name: str, *, bridge: str | None = None):
        if not isinstance(name, str):
            raise TypeError(
                f"Action(name): name must be a string (got {type(name).__name__})"
            )
        if not name.strip():
            raise ValueError("Action(name): name must be a non-empty string")
        if bridge is not None:
            if not isinstance(bridge, str):
                raise TypeError(
                    f"Action(bridge=): must be a string (got {type(bridge).__name__})"
                )
            if not bridge.strip():
                raise ValueError("Action(bridge=): must be a non-empty string when provided")
        self.name = name
        self.bridge_id = bridge

    def __repr__(self) -> str:
        if self.bridge_id is None:
            return f"Action({self.name!r})"
        return f"Action({self.name!r}, bridge={self.bridge_id!r})"

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, Action)
            and other.name == self.name
            and other.bridge_id == self.bridge_id
        )

    def __hash__(self) -> int:
        return hash(("Action", self.name, self.bridge_id))
