from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable

from dash import Input, Output, State, no_update

from .bridge import DEFAULT_BRIDGE_ID


class Registry:
    """Receiver-side registry of action handlers for one bridge + state pair.

    Create via `liquid_dash.handler(app, state="state_id")`. Register
    handlers with the `.on(action)` decorator. Each handler has signature:

        (state, payload, event) -> new_state | None

    where:

      * `state` is a deepcopy of the current state store (safe to mutate)
      * `payload` is the user-defined payload supplied to `ld.on(...)`
      * `event` is the full liquid-dash event dict with keys:
            action, target, source, bridge, event_type, native, timestamp
        (`event["native"]` contains browser-level fields: value, checked,
        key, clientX, clientY, deltaX, deltaY, button, code.)

    A handler may mutate `state` and return None, or return a new state
    value explicitly.
    """

    def __init__(self, app, state_id: str, bridge_id: str = DEFAULT_BRIDGE_ID):
        self._app = app
        self._state_id = state_id
        self._bridge_id = bridge_id
        self._handlers: dict[str, Callable] = {}
        self._wire()

    def on(self, action: str) -> Callable[[Callable], Callable]:
        if not isinstance(action, str) or not action.strip():
            raise ValueError("handler.on(): action must be a non-empty string")

        def _deco(fn: Callable) -> Callable:
            self._handlers[action] = fn
            return fn

        return _deco

    def dispatch(self, event: dict | None, state: Any) -> Any:
        if not event or "action" not in event:
            return no_update
        fn = self._handlers.get(event["action"])
        if fn is None:
            return no_update
        next_state = deepcopy(state) if state is not None else {}
        payload = event.get("payload")
        result = fn(next_state, payload, event)
        return result if result is not None else next_state

    def _wire(self) -> None:
        @self._app.callback(
            Output(self._state_id, "data"),
            Input(self._bridge_id, "data"),
            State(self._state_id, "data"),
            prevent_initial_call=True,
        )
        def _dispatch(event, state):
            return self.dispatch(event, state)


def handler(app, state: str, bridge: str = DEFAULT_BRIDGE_ID) -> Registry:
    """Create an action-handler registry bound to a Dash app.

    Registers one internal Dash callback that reads from the bridge store
    and writes updated state back to the given state store. Register
    per-action handlers with `registry.on("action")`.
    """
    return Registry(app, state_id=state, bridge_id=bridge)
