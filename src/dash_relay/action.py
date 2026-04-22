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

The bridge an action travels on is determined by the emitter (which
declares ``bridge=...``); the handler doesn't need to know.
"""
from __future__ import annotations


class Action:
    """A relay action dependency.

    Wraps an action name string. In v1 only string names are supported;
    dict-shaped (pattern-matchable) actions are deferred to a future
    version.
    """

    __slots__ = ("name",)

    def __init__(self, name: str):
        if not isinstance(name, str):
            raise TypeError(
                f"Action(name): name must be a string (got {type(name).__name__})"
            )
        if not name.strip():
            raise ValueError("Action(name): name must be a non-empty string")
        self.name = name

    def __repr__(self) -> str:
        return f"Action({self.name!r})"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Action) and other.name == self.name

    def __hash__(self) -> int:
        return hash(("Action", self.name))
