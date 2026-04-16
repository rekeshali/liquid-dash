from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable

from dash import Input, Output, State, no_update

from .bridge import DEFAULT_BRIDGE_ID


class Registry:
    """Receiver-side registry of action handlers for a bridge + state(s) pair.

    Create via ``liquid_dash.handler(app, state="store_id")`` for an app with a
    single state store, or ``liquid_dash.handler(app, state=["a", "b", ...])``
    for apps with multiple state stores updated from the same bridge.

    Register handlers with the ``.on(action)`` decorator.

    Single-state handler signature::

        @events.on("my.action")
        def _(state, payload, event) -> new_state | None:
            ...

    Multi-state handler signature::

        @events.on("my.action")
        def _(states, payload, event) -> tuple[new_state, ...] | None:
            a, b = states
            ...

    In both cases:

      * The state passed to the handler is a deep copy, safe to mutate.
      * ``payload`` is the user-defined payload supplied to ``ld.on(...)``.
      * ``event`` is the full Liquid Dash event dict with keys:
        ``action``, ``target``, ``source``, ``bridge``, ``event_type``,
        ``native``, ``timestamp``. ``event["native"]`` contains browser-level
        scalar fields (value, checked, key, clientX/Y, etc.).

    Returning ``None`` uses the (possibly mutated) deep copy. Returning a new
    value overrides it. For multi-state, handlers that *reassign* one of the
    state variables must return the tuple explicitly; handlers that only
    mutate in place can return ``None``.
    """

    def __init__(
        self,
        app,
        state_id: str | list[str],
        bridge_id: str = DEFAULT_BRIDGE_ID,
    ):
        self._app = app
        self._bridge_id = bridge_id
        self._multi = isinstance(state_id, list)
        self._state_ids: list[str] = list(state_id) if self._multi else [state_id]
        if not self._state_ids:
            raise ValueError("handler(): state must be a store id or non-empty list")
        self._handlers: dict[str, Callable] = {}
        self._wire()

    def on(self, action: str) -> Callable[[Callable], Callable]:
        if not isinstance(action, str) or not action.strip():
            raise ValueError("handler.on(): action must be a non-empty string")

        def _deco(fn: Callable) -> Callable:
            self._handlers[action] = fn
            return fn

        return _deco

    def dispatch(self, event: dict | None, *states: Any) -> Any:
        if not event or "action" not in event:
            return no_update
        fn = self._handlers.get(event["action"])
        if fn is None:
            return no_update

        next_states = tuple(
            deepcopy(s) if s is not None else {} for s in states
        )
        payload = event.get("payload")

        if self._multi:
            result = fn(next_states, payload, event)
            if result is not None:
                return tuple(result)
            return next_states
        else:
            result = fn(next_states[0], payload, event)
            return result if result is not None else next_states[0]

    def _wire(self) -> None:
        if self._multi:
            outputs = [Output(sid, "data") for sid in self._state_ids]
            states = [State(sid, "data") for sid in self._state_ids]

            @self._app.callback(
                *outputs,
                Input(self._bridge_id, "data"),
                *states,
                prevent_initial_call=True,
            )
            def _dispatch(event, *state_values):
                result = self.dispatch(event, *state_values)
                if result is no_update:
                    return [no_update] * len(self._state_ids)
                return list(result)
        else:
            sid = self._state_ids[0]

            @self._app.callback(
                Output(sid, "data"),
                Input(self._bridge_id, "data"),
                State(sid, "data"),
                prevent_initial_call=True,
            )
            def _dispatch(event, state):
                return self.dispatch(event, state)


def handler(
    app,
    state: str | list[str],
    bridge: str = DEFAULT_BRIDGE_ID,
) -> Registry:
    """Create an action-handler registry bound to a Dash app.

    Registers one internal Dash callback that reads from the bridge store
    and writes updated state back to the given state store(s).

    Pass ``state="store_id"`` for a single state store (handlers receive
    ``(state, payload, event)``), or ``state=["a", "b", ...]`` for multiple
    stores updated together (handlers receive ``(states, payload, event)``
    where ``states`` is a tuple aligned with the id list).

    Register per-action handlers with ``registry.on("action")``.
    """
    return Registry(app, state_id=state, bridge_id=bridge)
