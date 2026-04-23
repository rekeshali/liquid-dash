"""``@relay.callback`` decorator and per-bridge dispatcher wiring.

A handler is registered with ``@callback(*deps)`` where ``deps`` mixes
``Output``, ``Action``, and ``State`` instances. Decorators accumulate
handlers in a module-level pending pool. ``install(app)`` consumes the
pool: for each unique bridge it builds one Dash callback whose Outputs
are the union of every handler on that bridge, and whose States are the
union of every handler's States. The dispatcher routes by action name
within a single bridge, padding non-touched outputs with ``no_update``.
"""
from __future__ import annotations

import inspect
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Callable

from dash import Input, Output, State, no_update

from .action import Action, DEFAULT_BRIDGE
from .exceptions import InstallError


@dataclass
class CallbackSpec:
    """One ``@callback`` registration.

    A single callback may declare multiple ``Action``s (alias semantics):
    the wrapped function is registered as the handler for every
    ``(bridge, action)`` pair its Actions enumerate.
    """

    fn: Callable
    outputs: list[Output]
    actions: list[Action]
    states: list[State]
    source_file: str = ""
    source_line: int = 0


_PENDING_CALLBACKS: list[CallbackSpec] = []


def callback(*deps, **_kwargs) -> Callable[[Callable], Callable]:
    """Register a handler that fires when one of its declared ``Action``s dispatches.

    Mirrors Dash's ``@app.callback(Output, Input, State)`` signature with
    ``Action`` substituting for ``Input``. Handler argument shape:
    positional, declaration order, with ``Output``s skipped — same rule
    as plain Dash. Each ``Action`` slot in the declaration becomes a
    handler argument receiving the event dict; with multiple Actions
    (alias), the dispatcher invokes the same function for each fire and
    only the firing event arrives.

    Example::

        @relay.callback(
            Output("tab_store", "data"),
            Action("close", bridge="tabbar"),
            Action("dismiss", bridge="tabbar"),     # alias — same handler
            State("tab_store", "data"),
        )
        def close_tab(event, tabs):
            return {**tabs, "tabs": [t for t in tabs["tabs"] if t["id"] != event["target"]]}

    Pattern-matched component ids in ``Output`` / ``State`` are not
    supported in v4 (the per-bridge consolidation in ``install()`` is
    incompatible with MATCH-binding). ``InstallError`` is raised at
    install time if any handler declares them.
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
                f"@callback: unsupported dependency type {type(dep).__name__}; "
                "expected Output, Action, or State"
            )

    if not outputs:
        raise ValueError("@callback: at least one Output is required")
    if not actions:
        raise ValueError("@callback: at least one Action is required")

    def _deco(fn: Callable) -> Callable:
        try:
            source_file = inspect.getfile(fn)
        except (TypeError, OSError):
            source_file = "<unknown>"
        try:
            source_line = inspect.getsourcelines(fn)[1]
        except (TypeError, OSError):
            source_line = 0
        spec = CallbackSpec(
            fn=fn,
            outputs=outputs,
            actions=actions,
            states=states,
            source_file=source_file,
            source_line=source_line,
        )
        _PENDING_CALLBACKS.append(spec)
        return fn

    return _deco


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _output_key(o: Output) -> tuple:
    return (o.component_id, o.component_property)


def _state_key(s: State) -> tuple:
    return (s.component_id, s.component_property)


def _is_pattern_id(component_id: Any) -> bool:
    """Detect Dash pattern-matching ids (dict-shaped with ALL/MATCH/ALLSMALLER)."""
    if not isinstance(component_id, dict):
        return False
    # Dash represents pattern wildcards as objects with a `wildcard` attribute,
    # but the canonical surface is `dash.MATCH` / `dash.ALL` / `dash.ALLSMALLER`,
    # which are sentinels of type Wildcard. Detection by repr is brittle, so
    # we conservatively flag any dict-shaped id as a pattern (the v4 cut
    # rejects dict ids on relay callbacks regardless of wildcard presence).
    return True


def _validate_no_pattern_ids(spec: CallbackSpec) -> None:
    for o in spec.outputs:
        if _is_pattern_id(o.component_id):
            raise InstallError(
                f"@callback declared in {spec.source_file}:{spec.source_line} "
                f"uses a pattern-matched dict id in Output ({o.component_id!r}). "
                "Pattern-matched ids are not supported in dash-relay v4 — "
                "use a fixed store id or write a separate non-relay callback."
            )
    for s in spec.states:
        if _is_pattern_id(s.component_id):
            raise InstallError(
                f"@callback declared in {spec.source_file}:{spec.source_line} "
                f"uses a pattern-matched dict id in State ({s.component_id!r}). "
                "Pattern-matched ids are not supported in dash-relay v4 — "
                "use a fixed store id or write a separate non-relay callback."
            )


def _drain_pending() -> list[CallbackSpec]:
    handlers = list(_PENDING_CALLBACKS)
    _PENDING_CALLBACKS.clear()
    return handlers


# ---------------------------------------------------------------------------
# Per-bridge dispatcher construction
# ---------------------------------------------------------------------------


@dataclass
class BridgePlan:
    """Computed per-bridge plan: handlers, unioned outputs/states, lookup."""

    bridge_name: str
    handlers_by_action: dict[str, CallbackSpec] = field(default_factory=dict)
    all_outputs: list[Output] = field(default_factory=list)
    all_states: list[State] = field(default_factory=list)
    output_index: dict[tuple, int] = field(default_factory=dict)
    state_index: dict[tuple, int] = field(default_factory=dict)


def _plan_bridges(handlers: list[CallbackSpec]) -> dict[str, BridgePlan]:
    """Build one BridgePlan per bridge mentioned in any handler's Actions.

    Raises ``InstallError`` on duplicate ``(bridge, action)`` registrations.
    """
    plans: dict[str, BridgePlan] = {}
    seen_keys: dict[tuple, CallbackSpec] = {}

    for h in handlers:
        _validate_no_pattern_ids(h)
        for action in h.actions:
            key = (action.bridge_id, action.name)
            if key in seen_keys:
                first = seen_keys[key]
                raise InstallError(
                    f"Duplicate handler for (bridge={action.bridge_id!r}, "
                    f"action={action.name!r}).\n"
                    f"    Registered at: {first.source_file}:{first.source_line} "
                    f"and {h.source_file}:{h.source_line}.\n"
                    "    Add a distinct bridge= argument, remove the duplicate, "
                    "or use alias semantics by declaring both actions in one "
                    "@relay.callback decorator."
                )
            seen_keys[key] = h

            plan = plans.setdefault(action.bridge_id, BridgePlan(bridge_name=action.bridge_id))
            plan.handlers_by_action[action.name] = h

    # Union outputs and states per bridge.
    for plan in plans.values():
        seen_out: set[tuple] = set()
        seen_state: set[tuple] = set()
        for h in plan.handlers_by_action.values():
            for o in h.outputs:
                k = _output_key(o)
                if k not in seen_out:
                    seen_out.add(k)
                    plan.all_outputs.append(o)
            for s in h.states:
                k = _state_key(s)
                if k not in seen_state:
                    seen_state.add(k)
                    plan.all_states.append(s)
        plan.output_index = {_output_key(o): i for i, o in enumerate(plan.all_outputs)}
        plan.state_index = {_state_key(s): i for i, s in enumerate(plan.all_states)}

    return plans


def _build_bridge_dispatcher(plan: BridgePlan):
    """Return a dispatcher function for one bridge.

    Signature: ``dispatch(event, *state_values)`` where ``state_values``
    align with ``plan.all_states``. Returns a single value when the bridge
    has exactly one Output, a list of length len(all_outputs) otherwise,
    or ``no_update`` (or list of) when nothing applies.
    """
    n_outputs = len(plan.all_outputs)
    handlers_by_action = plan.handlers_by_action
    state_index = plan.state_index
    output_index = plan.output_index

    def _no_update_response():
        return [no_update] * n_outputs if n_outputs > 1 else no_update

    def _dispatch(event, *state_values):
        if not event or "action" not in event:
            return _no_update_response()
        handler = handlers_by_action.get(event["action"])
        if handler is None:
            return _no_update_response()

        handler_state_values = [
            deepcopy(state_values[state_index[_state_key(s)]])
            for s in handler.states
        ]
        result = handler.fn(event, *handler_state_values)

        if result is no_update:
            return _no_update_response()

        response = [no_update] * n_outputs
        h_n_outputs = len(handler.outputs)

        if h_n_outputs == 1:
            response[output_index[_output_key(handler.outputs[0])]] = result
        else:
            if not isinstance(result, tuple):
                raise TypeError(
                    f"handler for action {event['action']!r} declares "
                    f"{h_n_outputs} Outputs; must return a tuple of that length "
                    f"(got {type(result).__name__})"
                )
            if len(result) != h_n_outputs:
                raise ValueError(
                    f"handler for action {event['action']!r} declares "
                    f"{h_n_outputs} Outputs but returned tuple of length {len(result)}"
                )
            for o, value in zip(handler.outputs, result):
                response[output_index[_output_key(o)]] = value

        return response if n_outputs > 1 else response[0]

    return _dispatch


# ---------------------------------------------------------------------------
# Bridge naming (slug)
# ---------------------------------------------------------------------------


def _bridge_store_id(bridge_name: str) -> str:
    """Convert a bridge name to its dcc.Store id.

    Per the v4 spec (B1), ``.`` characters in bridge names are replaced
    with ``__`` so CSS selectors don't parse the dot as a class separator.

    This rule MUST stay in sync with the JS runtime's store-id derivation
    in ``src/dash_relay/assets/dash_relay.js`` (search for "storeId").
    The regression guard is ``tests/test_app.py::
    test_js_runtime_mirrors_bridge_store_id_rule``.
    """
    return f"relay-bridge-{bridge_name.replace('.', '__')}"
