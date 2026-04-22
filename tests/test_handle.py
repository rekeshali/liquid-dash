"""Tests for the 3.0 surface: @relay.handle + Action."""
from __future__ import annotations

import pytest
from dash import Dash, Input, Output, State, dcc, html, no_update

import dash_relay as relay
from dash_relay import Action
from dash_relay.handle import _PENDING_HANDLERS
from dash_relay.bridge import _REGISTERED_BRIDGE_IDS


@pytest.fixture(autouse=True)
def _isolate_pools():
    """Reset module-level pools before and after each test so tests don't bleed."""
    _PENDING_HANDLERS.clear()
    _REGISTERED_BRIDGE_IDS.clear()
    yield
    _PENDING_HANDLERS.clear()
    _REGISTERED_BRIDGE_IDS.clear()


def _app(*store_ids):
    app = Dash(__name__)
    children = [dcc.Store(id=sid, data={}) for sid in store_ids]
    children.append(relay.bridge())
    app.layout = html.Div(children)
    return app


# ---------------------------------------------------------------------------
# Action primitive
# ---------------------------------------------------------------------------


def test_action_holds_string_name():
    a = Action("tab.close")
    assert a.name == "tab.close"
    assert repr(a) == "Action('tab.close')"


def test_action_rejects_non_string():
    with pytest.raises(TypeError):
        Action(42)


def test_action_rejects_empty_string():
    with pytest.raises(ValueError):
        Action("")
    with pytest.raises(ValueError):
        Action("   ")


def test_action_equality_and_hashing():
    assert Action("a") == Action("a")
    assert Action("a") != Action("b")
    assert hash(Action("a")) == hash(Action("a"))


# ---------------------------------------------------------------------------
# @handle dependency parsing
# ---------------------------------------------------------------------------


def test_handle_requires_at_least_one_output():
    with pytest.raises(ValueError, match="at least one Output"):
        @relay.handle(Action("x"))
        def _(event): ...


def test_handle_requires_an_action():
    with pytest.raises(ValueError, match="Action is required"):
        @relay.handle(Output("a", "data"))
        def _(): ...


def test_handle_rejects_multiple_actions():
    with pytest.raises(NotImplementedError):
        @relay.handle(Output("a", "data"), Action("x"), Action("y"))
        def _(e1, e2): ...


def test_handle_rejects_unknown_dep_type():
    with pytest.raises(TypeError, match="unsupported dependency"):
        @relay.handle(Output("a", "data"), Action("x"), "stringy")
        def _(event): ...


def test_handle_appends_to_pending_pool():
    @relay.handle(Output("a", "data"), Action("x"))
    def fn(event): return None
    assert len(_PENDING_HANDLERS) == 1
    spec = _PENDING_HANDLERS[0]
    assert spec.fn is fn
    assert spec.action.name == "x"
    assert [o.component_id for o in spec.outputs] == ["a"]


# ---------------------------------------------------------------------------
# install() drains the pool and wires dispatchers
# ---------------------------------------------------------------------------


def test_install_drains_pending_pool():
    @relay.handle(Output("state", "data"), Action("bump"))
    def _(event): return None

    assert len(_PENDING_HANDLERS) == 1
    app = _app("state")
    relay.install(app)
    assert len(_PENDING_HANDLERS) == 0
    assert len(app._dash_relay_handlers) == 1


def test_install_registers_one_dispatcher_per_bridge():
    @relay.handle(Output("state", "data"), Action("x"))
    def _(event): return None

    app = _app("state")
    before = len(app.callback_map)
    relay.install(app)
    assert len(app.callback_map) == before + 1


def test_install_registers_one_dispatcher_per_distinct_bridge():
    # Two bridges in the layout → two dispatchers.
    @relay.handle(Output("state", "data"), Action("x"))
    def _(event): return None

    app = Dash(__name__)
    app.layout = html.Div([
        dcc.Store(id="state", data={}),
        relay.bridge("a"),
        relay.bridge("b"),
    ])
    before = len(app.callback_map)
    relay.install(app)
    assert len(app.callback_map) == before + 2  # one per bridge


def test_install_works_with_no_handlers():
    app = _app("state")
    relay.install(app)
    assert app._dash_relay_handlers == []


def test_install_works_with_default_bridge_when_no_bridges_explicitly_called():
    # Decorate a handler but don't call relay.bridge() at all.
    # install() should fall back to the default bridge id.
    @relay.handle(Output("state", "data"), Action("x"))
    def _(event): return None

    app = Dash(__name__)
    app.layout = html.Div([dcc.Store(id="state", data={})])  # no bridge in layout!
    before = len(app.callback_map)
    relay.install(app)
    assert len(app.callback_map) == before + 1


# ---------------------------------------------------------------------------
# Dispatcher behavior — invoke through the registered Dash callback
# ---------------------------------------------------------------------------


def _last_dispatcher(app):
    """Return the bare dispatcher function (not Dash-wrapped) for direct invocation."""
    return app._dash_relay_dispatcher


def test_dispatcher_routes_event_to_matching_handler():
    @relay.handle(Output("state", "data"), Action("bump"), State("state", "data"))
    def bump(event, current):
        return {"count": (current or {}).get("count", 0) + 1}

    app = _app("state")
    relay.install(app)
    dispatcher = _last_dispatcher(app)

    # Single output, single state: dispatcher returns bare value.
    result = dispatcher({"action": "bump"}, {"count": 5})
    assert result == {"count": 6}


def test_dispatcher_returns_no_update_for_empty_event():
    @relay.handle(Output("state", "data"), Action("bump"))
    def _(event): return {"set": True}

    app = _app("state")
    relay.install(app)
    dispatcher = _last_dispatcher(app)

    assert dispatcher(None) is no_update
    assert dispatcher({}) is no_update


def test_dispatcher_returns_no_update_for_unknown_action():
    @relay.handle(Output("state", "data"), Action("known"))
    def _(event): return {"x": 1}

    app = _app("state")
    relay.install(app)
    dispatcher = _last_dispatcher(app)

    assert dispatcher({"action": "unknown"}) is no_update


def test_dispatcher_pads_no_update_for_outputs_other_handlers_touch():
    # Two handlers writing different stores. When 'a' fires, only the
    # 'a' output should change; 'b' stays no_update.
    @relay.handle(Output("a", "data"), Action("touch-a"), State("a", "data"))
    def _(event, current):
        return {"a_touched": True}

    @relay.handle(Output("b", "data"), Action("touch-b"), State("b", "data"))
    def _(event, current):
        return {"b_touched": True}

    app = _app("a", "b")
    relay.install(app)
    dispatcher = _last_dispatcher(app)

    # Dispatcher's args order: (event, *all_states_in_union_order).
    # all_states union = [State("a"), State("b")] in declaration order.
    result = dispatcher({"action": "touch-a"}, {}, {})
    # Multi-output return is a list aligned with all_outputs union.
    assert result == [{"a_touched": True}, no_update]

    result = dispatcher({"action": "touch-b"}, {}, {})
    assert result == [no_update, {"b_touched": True}]


def test_dispatcher_passes_state_values_in_handler_declaration_order():
    @relay.handle(
        Output("write", "data"),
        Action("compute"),
        State("ctx2", "data"),  # declared 2nd
        State("ctx1", "data"),  # declared 1st
    )
    def compute(event, ctx2, ctx1):
        return {"order": [ctx1, ctx2]}

    app = _app("write", "ctx1", "ctx2")
    relay.install(app)
    dispatcher = _last_dispatcher(app)

    # Dispatcher's union state order is the order of first declaration
    # across handlers. With one handler, it's ctx2, ctx1 (handler order).
    # Dispatcher signature: (event, ctx2_val, ctx1_val).
    result = dispatcher({"action": "compute"}, "ctx2_value", "ctx1_value")
    assert result == {"order": ["ctx1_value", "ctx2_value"]}


def test_dispatcher_handles_multi_output_handler_with_tuple_return():
    @relay.handle(Output("a", "data"), Output("b", "data"), Action("set-both"))
    def _(event):
        return {"a_new": True}, {"b_new": True}

    app = _app("a", "b")
    relay.install(app)
    dispatcher = _last_dispatcher(app)

    result = dispatcher({"action": "set-both"})
    assert result == [{"a_new": True}, {"b_new": True}]


def test_multi_output_handler_must_return_tuple():
    @relay.handle(Output("a", "data"), Output("b", "data"), Action("oops"))
    def _(event):
        return {"a": 1}  # not a tuple — wrong shape for multi-output

    app = _app("a", "b")
    relay.install(app)
    dispatcher = _last_dispatcher(app)

    with pytest.raises(TypeError, match="must return a tuple"):
        dispatcher({"action": "oops"})


def test_multi_output_handler_tuple_length_mismatch_raises():
    @relay.handle(Output("a", "data"), Output("b", "data"), Action("oops"))
    def _(event):
        return ({"a": 1},)  # tuple of 1, but 2 outputs declared

    app = _app("a", "b")
    relay.install(app)
    dispatcher = _last_dispatcher(app)

    with pytest.raises(ValueError, match="returned tuple of length 1"):
        dispatcher({"action": "oops"})


def test_handler_can_return_no_update_to_skip_all_writes():
    @relay.handle(Output("a", "data"), Action("abort"), State("a", "data"))
    def _(event, current):
        return no_update

    app = _app("a")
    relay.install(app)
    dispatcher = _last_dispatcher(app)

    assert dispatcher({"action": "abort"}, {}) is no_update


# ---------------------------------------------------------------------------
# allow_duplicate threading
# ---------------------------------------------------------------------------


def test_allow_duplicate_propagates_when_any_handler_asks_for_it():
    @relay.handle(
        Output("state", "data", allow_duplicate=True),
        Action("bump"),
    )
    def _(event): return {}

    app = _app("state")
    relay.install(app)
    cb_id = list(app.callback_map.keys())[-1]
    # Dash encodes allow_duplicate in the callback id with a @<hash> suffix.
    assert cb_id.startswith("state.data@"), cb_id


def test_default_no_allow_duplicate_keeps_plain_callback_id():
    @relay.handle(Output("state", "data"), Action("bump"))
    def _(event): return {}

    app = _app("state")
    relay.install(app)
    cb_id = list(app.callback_map.keys())[-1]
    assert cb_id == "state.data"


def test_allow_duplicate_lets_external_writer_coexist():
    # External writer (e.g. an interval) also writes state with allow_duplicate.
    # Dash distinguishes co-writing callbacks by their full (Output+Input+State)
    # signature, so the external writer needs its own Input to coexist.
    @relay.handle(Output("state", "data", allow_duplicate=True), Action("bump"))
    def _(event): return {"from": "handler"}

    app = Dash(__name__)
    app.layout = html.Div([
        dcc.Store(id="state", data={}),
        relay.bridge(),
        dcc.Store(id="ping"),
    ])

    @app.callback(
        Output("state", "data", allow_duplicate=True),
        Input("ping", "data"),
        prevent_initial_call=True,
    )
    def _ext(_): return {"from": "external"}

    relay.install(app)
    # Both registered: external writer + dispatcher.
    assert len(app.callback_map) >= 2


# ---------------------------------------------------------------------------
# Multi-bridge — same handler pool, dispatcher on each bridge
# ---------------------------------------------------------------------------


def test_multi_bridge_dispatchers_share_same_handler_pool():
    @relay.handle(Output("state", "data"), Action("bump"), State("state", "data"))
    def bump(event, current):
        return {"count": (current or {}).get("count", 0) + 1, "via": event["bridge"]}

    app = Dash(__name__)
    app.layout = html.Div([
        dcc.Store(id="state", data={}),
        relay.bridge("a"),
        relay.bridge("b"),
    ])
    before = len(app.callback_map)
    relay.install(app)
    # Two bridges → two Dash callbacks, each with allow_duplicate (since
    # they share the same Output set).
    assert len(app.callback_map) == before + 2

    # Both Dash callbacks dispatch through the same underlying function.
    dispatch_fn = app._dash_relay_dispatcher
    result = dispatch_fn({"action": "bump", "bridge": "?"}, {"count": 0})
    assert result["count"] == 1


# ---------------------------------------------------------------------------
# Lifecycle: pool isolation
# ---------------------------------------------------------------------------


def test_install_clears_bridge_pool_for_next_app():
    relay.bridge("first-bridge")  # adds to pool
    @relay.handle(Output("state", "data"), Action("x"))
    def _(event): return {}

    app1 = _app("state")  # adds default "bridge" to pool too
    relay.install(app1)
    # Now the pool should be empty.
    assert _REGISTERED_BRIDGE_IDS == set()


def test_re_decorating_after_install_starts_fresh():
    @relay.handle(Output("a", "data"), Action("a-bump"))
    def _(event): return {}

    app1 = _app("a")
    relay.install(app1)
    assert len(app1._dash_relay_handlers) == 1

    # New handler for a new app, pool starts fresh.
    @relay.handle(Output("b", "data"), Action("b-bump"))
    def _(event): return {}

    app2 = _app("b")
    relay.install(app2)
    assert len(app2._dash_relay_handlers) == 1
    assert app2._dash_relay_handlers[0].action.name == "b-bump"


# ---------------------------------------------------------------------------
# Duplicate handler-per-action rejection
# ---------------------------------------------------------------------------


def test_two_handlers_same_action_rejected_at_install():
    @relay.handle(Output("a", "data"), Action("dup"))
    def _(event): return {}

    @relay.handle(Output("a", "data"), Action("dup"))
    def _(event): return {}

    app = _app("a")
    with pytest.raises(ValueError, match="Multiple wildcard handlers"):
        relay.install(app)


# ---------------------------------------------------------------------------
# Action(bridge=) — pinning, deduplication, specificity routing
# ---------------------------------------------------------------------------


def test_action_accepts_bridge_kwarg():
    a = Action("close", bridge="folder.tabbar")
    assert a.name == "close"
    assert a.bridge_id == "folder.tabbar"
    assert repr(a) == "Action('close', bridge='folder.tabbar')"


def test_action_default_bridge_is_none_wildcard():
    a = Action("close")
    assert a.bridge_id is None
    assert repr(a) == "Action('close')"


def test_action_rejects_non_string_bridge():
    with pytest.raises(TypeError):
        Action("close", bridge=42)


def test_action_rejects_empty_bridge():
    with pytest.raises(ValueError):
        Action("close", bridge="")
    with pytest.raises(ValueError):
        Action("close", bridge="   ")


def test_action_equality_includes_bridge():
    assert Action("a") != Action("a", bridge="x")
    assert Action("a", bridge="x") == Action("a", bridge="x")
    assert Action("a", bridge="x") != Action("a", bridge="y")
    assert hash(Action("a", bridge="x")) != hash(Action("a"))


def test_two_pinned_handlers_same_name_different_bridges_coexist():
    # Two emitters in two bridges using the same action name "close",
    # each handled by its own pinned handler. Today this would force
    # action-name namespacing; with bridge= it just works.
    @relay.handle(
        Output("a", "data"),
        Action("close", bridge="bridge-a"),
        State("a", "data"),
    )
    def for_a(event, current):
        return {"closed_by": "a"}

    @relay.handle(
        Output("b", "data"),
        Action("close", bridge="bridge-b"),
        State("b", "data"),
    )
    def for_b(event, current):
        return {"closed_by": "b"}

    app = Dash(__name__)
    app.layout = html.Div([
        dcc.Store(id="a"),
        dcc.Store(id="b"),
        relay.bridge("bridge-a"),
        relay.bridge("bridge-b"),
    ])
    relay.install(app)

    dispatch = app._dash_relay_dispatcher
    # bridge-a fires "close" → only for_a runs (writes "a", b stays no_update)
    result = dispatch({"action": "close", "bridge": "bridge-a"}, {}, {})
    assert result == [{"closed_by": "a"}, no_update]

    # bridge-b fires "close" → only for_b runs
    result = dispatch({"action": "close", "bridge": "bridge-b"}, {}, {})
    assert result == [no_update, {"closed_by": "b"}]


def test_two_pinned_to_same_bridge_same_action_collide():
    @relay.handle(Output("a", "data"), Action("close", bridge="x"))
    def _(event): return {}

    @relay.handle(Output("a", "data"), Action("close", bridge="x"))
    def _(event): return {}

    app = Dash(__name__)
    app.layout = html.Div([dcc.Store(id="a"), relay.bridge("x")])
    with pytest.raises(ValueError, match="pinned to bridge"):
        relay.install(app)


def test_pinned_shadows_wildcard_for_its_specific_bridge():
    @relay.handle(Output("a", "data"), Action("close"), State("a", "data"))
    def wildcard(event, current):
        return {"by": "wildcard"}

    @relay.handle(Output("a", "data"), Action("close", bridge="bridge-special"), State("a", "data"))
    def pinned(event, current):
        return {"by": "pinned"}

    app = Dash(__name__)
    app.layout = html.Div([
        dcc.Store(id="a"),
        relay.bridge("bridge-default"),
        relay.bridge("bridge-special"),
    ])
    relay.install(app)
    dispatch = app._dash_relay_dispatcher

    # Special bridge → pinned wins
    result = dispatch({"action": "close", "bridge": "bridge-special"}, {})
    assert result == {"by": "pinned"}

    # Default bridge → no pinned match → wildcard
    result = dispatch({"action": "close", "bridge": "bridge-default"}, {})
    assert result == {"by": "wildcard"}


def test_wildcard_fallback_when_pinned_does_not_match_firing_bridge():
    @relay.handle(Output("a", "data"), Action("close"), State("a", "data"))
    def fallback(event, current):
        return {"by": "wildcard"}

    @relay.handle(Output("a", "data"), Action("close", bridge="other"), State("a", "data"))
    def pinned(event, current):
        return {"by": "pinned"}

    app = Dash(__name__)
    app.layout = html.Div([
        dcc.Store(id="a"),
        relay.bridge("primary"),
        relay.bridge("other"),
    ])
    relay.install(app)
    dispatch = app._dash_relay_dispatcher

    # primary fires → no pinned for primary, wildcard wins
    result = dispatch({"action": "close", "bridge": "primary"}, {})
    assert result == {"by": "wildcard"}


def test_event_with_no_bridge_field_uses_wildcard():
    # Defensive: if the event somehow lacks a bridge (e.g. test driving
    # the dispatcher with a bare event), fall through to wildcard.
    @relay.handle(Output("a", "data"), Action("close"), State("a", "data"))
    def _(event, current): return {"by": "wildcard"}

    @relay.handle(Output("a", "data"), Action("close", bridge="x"), State("a", "data"))
    def _(event, current): return {"by": "pinned"}

    app = Dash(__name__)
    app.layout = html.Div([dcc.Store(id="a"), relay.bridge("x")])
    relay.install(app)
    dispatch = app._dash_relay_dispatcher

    # No bridge field → no pinned match → wildcard runs
    result = dispatch({"action": "close"}, {})
    assert result == {"by": "wildcard"}
