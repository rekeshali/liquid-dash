"""``@relay.handle`` decorator and the install-time dispatcher wiring.

A handler is registered with ``@handle(*deps)`` where ``deps`` mixes
``Output``, ``Action``, and ``State`` instances. Decorators accumulate
handlers in a module-level pending pool. ``install(app)`` consumes the
pool: for each registered bridge it builds one Dash callback whose
Outputs are the union of every handler's Outputs and whose States are
the union of every handler's States. The dispatcher routes by action
name and pads non-touched outputs with ``no_update``.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Callable

from dash import Input, Output, State, no_update

from .action import Action
from .bridge import DEFAULT_BRIDGE_ID, _registered_bridge_ids, _reset_bridge_pool


@dataclass
class HandlerSpec:
    """One registered ``@handle`` entry."""

    fn: Callable
    outputs: list[Output]
    action: Action
    states: list[State]


# Module-level pending pool. Decorators append; install() drains.
_PENDING_HANDLERS: list[HandlerSpec] = []


def handle(*deps, **_kwargs) -> Callable[[Callable], Callable]:
    """Register a handler that fires when its declared ``Action`` is dispatched.

    Positional ``deps`` accept any mix of ``Output``, ``Action``, and
    ``State`` instances. Each ``@handle`` block must contain exactly one
    ``Action`` and at least one ``Output``.

    The wrapped handler signature mirrors plain Dash callbacks: arguments
    appear in the same order as the dependencies were declared, with one
    exception — ``Output`` declarations don't appear as handler arguments
    (they're response targets). Each ``Action`` becomes a positional arg
    receiving the full event dict. Each ``State`` becomes a positional
    arg receiving its current value.

    Example::

        @handle(
            Output("tab_store", "data"),
            Action("tab.close"),
            State("tab_store", "data"),
            State("path", "data"),
        )
        def close_tab(event, tab, path):
            return {**tab, "tabs": [t for t in tab["tabs"] if t["id"] != event["target"]]}

    Return shapes:

      * Single ``Output`` declared → return its new value (or ``no_update``).
      * Multiple ``Output`` declared → return a tuple aligned with declaration
        order. Each entry can be a value or ``no_update``.
      * Returning ``dash.no_update`` (not in a tuple) skips every output.

    Handlers are not registered with Dash directly. They sit in a
    pending pool; ``install(app)`` builds one dispatcher Dash callback
    per registered bridge that knows about all handlers.
    """
    outputs: list[Output] = []
    actions: list[Action] = []
    states: list[State] = []
    for dep in deps:
        if isinstance(dep, Output):
            outputs.append(dep)
        elif isinstance(dep, Action):
            actions.append(dep)
        elif isinstance(dep, State):
            states.append(dep)
        else:
            raise TypeError(
                f"@handle: unsupported dependency type {type(dep).__name__}; "
                "expected Output, Action, or State"
            )

    if not outputs:
        raise ValueError("@handle: at least one Output is required")
    if len(actions) == 0:
        raise ValueError("@handle: exactly one Action is required")
    if len(actions) > 1:
        raise NotImplementedError(
            "@handle: multi-Action handlers are not supported in v1; "
            "register one handler per action"
        )

    spec = HandlerSpec(
        fn=None,  # filled in by the decorator below
        outputs=outputs,
        action=actions[0],
        states=states,
    )

    def _deco(fn: Callable) -> Callable:
        spec.fn = fn
        _PENDING_HANDLERS.append(spec)
        return fn

    return _deco


def _output_key(o: Output) -> tuple:
    """Hashable identity for an Output: (id, property)."""
    return (o.component_id, o.component_property)


def _state_key(s: State) -> tuple:
    return (s.component_id, s.component_property)


def _drain_pending() -> list[HandlerSpec]:
    handlers = list(_PENDING_HANDLERS)
    _PENDING_HANDLERS.clear()
    return handlers


def _build_dispatcher(handlers: list[HandlerSpec], *, force_allow_duplicate: bool = False):
    """Build a dispatcher function plus the unioned Output/State lists.

    Returns ``(dispatch_fn, all_outputs, all_states)``. The dispatcher
    is a plain Python function with signature ``(event, *state_values)``
    where ``state_values`` are aligned with ``all_states`` (each
    State's current value as Dash passes it). It returns either a single
    value (when only one Output is unioned), a list (when multiple), or
    ``no_update`` for "no writes."

    Pass ``force_allow_duplicate=True`` when the dispatcher will be
    registered against more than one bridge — Dash needs every Output
    on every co-writing callback to opt into ``allow_duplicate``.

    Exposed for direct testing without going through Dash's add_context
    wrapper.
    """
    # Union of unique Outputs and States. Track allow_duplicate from any
    # handler that asked, OR force it if the dispatcher will be wired
    # against multiple bridges (multi-callback writers must agree).
    all_outputs: list[Output] = []
    seen_output_keys: set[tuple] = set()
    allow_dup_by_key: dict[tuple, bool] = {}
    for h in handlers:
        for o in h.outputs:
            key = _output_key(o)
            if key not in seen_output_keys:
                seen_output_keys.add(key)
                all_outputs.append(o)
                allow_dup_by_key[key] = bool(o.allow_duplicate)
            else:
                allow_dup_by_key[key] = allow_dup_by_key[key] or bool(o.allow_duplicate)

    all_outputs = [
        Output(
            o.component_id,
            o.component_property,
            allow_duplicate=force_allow_duplicate or allow_dup_by_key[_output_key(o)],
        )
        for o in all_outputs
    ]

    all_states: list[State] = []
    seen_state_keys: set[tuple] = set()
    for h in handlers:
        for s in h.states:
            key = _state_key(s)
            if key not in seen_state_keys:
                seen_state_keys.add(key)
                all_states.append(s)

    state_index_by_key = {_state_key(s): i for i, s in enumerate(all_states)}
    output_index_by_key = {_output_key(o): i for i, o in enumerate(all_outputs)}
    n_outputs = len(all_outputs)

    # Routing tables. Pinned handlers (Action(name, bridge="x")) keyed
    # by (name, bridge_id). Wildcard handlers (Action(name)) keyed by
    # name only. Pinned shadows wildcard for its specific bridge; the
    # wildcard handles every other bridge that fires the same action.
    pinned_by_key: dict[tuple, HandlerSpec] = {}
    wildcard_by_action: dict[str, HandlerSpec] = {}
    for h in handlers:
        if h.action.bridge_id is None:
            if h.action.name in wildcard_by_action:
                raise ValueError(
                    f"Multiple wildcard handlers registered for action "
                    f"{h.action.name!r}; use bridge= on Action to disambiguate"
                )
            wildcard_by_action[h.action.name] = h
        else:
            key = (h.action.name, h.action.bridge_id)
            if key in pinned_by_key:
                raise ValueError(
                    f"Multiple handlers for action {h.action.name!r} pinned "
                    f"to bridge {h.action.bridge_id!r}"
                )
            pinned_by_key[key] = h

    def _no_update_response():
        return [no_update] * n_outputs if n_outputs > 1 else no_update

    def _dispatch(event, *state_values):
        if not event or "action" not in event:
            return _no_update_response()
        action_name = event["action"]
        bridge_of_event = event.get("bridge")
        # Pinned wins over wildcard for the firing bridge; otherwise fall back.
        handler = (
            pinned_by_key.get((action_name, bridge_of_event))
            or wildcard_by_action.get(action_name)
        )
        if handler is None:
            return _no_update_response()

        handler_state_values = [
            deepcopy(state_values[state_index_by_key[_state_key(s)]])
            for s in handler.states
        ]

        result = handler.fn(event, *handler_state_values)

        if result is no_update:
            return _no_update_response()

        response = [no_update] * n_outputs
        h_n_outputs = len(handler.outputs)

        if h_n_outputs == 1:
            response[output_index_by_key[_output_key(handler.outputs[0])]] = result
        else:
            if not isinstance(result, tuple):
                raise TypeError(
                    f"handler for action {handler.action.name!r} declares "
                    f"{h_n_outputs} Outputs; must return a tuple of that length "
                    f"(got {type(result).__name__})"
                )
            if len(result) != h_n_outputs:
                raise ValueError(
                    f"handler for action {handler.action.name!r} declares "
                    f"{h_n_outputs} Outputs but returned tuple of length {len(result)}"
                )
            for o, value in zip(handler.outputs, result):
                response[output_index_by_key[_output_key(o)]] = value

        return response if n_outputs > 1 else response[0]

    return _dispatch, all_outputs, all_states


def _wire_dispatchers(app) -> None:
    """Consume the pending handler pool and register one dispatcher per bridge.

    Called from ``install(app)`` after the runtime script has been
    injected. Always drains the pool, even if no bridges are registered
    (so subsequent installs with new handlers stay clean).

    Also caches the drained handlers and the testable dispatcher
    function on the app object as ``_dash_relay_handlers`` and
    ``_dash_relay_dispatcher`` so tests and ``validate()`` can
    introspect after install.
    """
    handlers = _drain_pending()
    bridge_ids = sorted(_registered_bridge_ids() or frozenset({DEFAULT_BRIDGE_ID}))
    _reset_bridge_pool()

    app._dash_relay_handlers = list(handlers)

    if not handlers:
        app._dash_relay_dispatcher = None
        return

    # When dispatching to multiple bridges, every Output must opt into
    # allow_duplicate (Dash's symmetric multi-writer rule).
    force_dup = len(bridge_ids) > 1
    dispatch_fn, all_outputs, all_states = _build_dispatcher(
        handlers, force_allow_duplicate=force_dup
    )
    app._dash_relay_dispatcher = dispatch_fn

    for bridge_id in bridge_ids:
        app.callback(
            *all_outputs,
            Input(bridge_id, "data"),
            *all_states,
            prevent_initial_call=True,
        )(dispatch_fn)


def _registered_handlers_snapshot() -> tuple[HandlerSpec, ...]:
    """Read-only view of pending handlers; used by validate()."""
    return tuple(_PENDING_HANDLERS)
