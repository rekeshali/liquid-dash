from dash import Dash, dcc, html

import liquid_dash as ld


def _make_app():
    app = Dash(__name__)
    app.layout = html.Div([
        dcc.Store(id="state", data={"count": 0, "items": []}),
        ld.bridge(),
    ])
    ld.melt(app)
    return app


def test_handler_dispatches_registered_action():
    app = _make_app()
    events = ld.handler(app, state="state")

    @events.on("bump")
    def _(state, payload, event):
        state["count"] += int((payload or {}).get("by", 1))

    new_state = events.dispatch(
        {"action": "bump", "payload": {"by": 3}}, {"count": 10, "items": []}
    )
    assert new_state["count"] == 13


def test_handler_ignores_unknown_action():
    from dash import no_update

    app = _make_app()
    events = ld.handler(app, state="state")

    @events.on("known")
    def _(state, payload, event):
        state["count"] = 1

    result = events.dispatch({"action": "unknown"}, {"count": 0, "items": []})
    assert result is no_update


def test_handler_passes_full_event_to_handler():
    app = _make_app()
    events = ld.handler(app, state="state")
    seen = {}

    @events.on("touch")
    def _(state, payload, event):
        seen["target"] = event.get("target")
        seen["native"] = event.get("native")

    events.dispatch(
        {"action": "touch", "target": "row-7", "native": {"value": "hi"}},
        {"count": 0, "items": []},
    )
    assert seen == {"target": "row-7", "native": {"value": "hi"}}


def test_handler_registers_exactly_one_callback():
    app = _make_app()
    before = len(app.callback_map)
    ld.handler(app, state="state")
    assert len(app.callback_map) == before + 1


def _make_multi_state_app():
    app = Dash(__name__)
    app.layout = html.Div([
        dcc.Store(id="a", data={"count": 0}),
        dcc.Store(id="b", data={"count": 0}),
        ld.bridge(),
    ])
    ld.melt(app)
    return app


def test_handler_multi_state_dispatches_and_returns_tuple():
    app = _make_multi_state_app()
    events = ld.handler(app, state=["a", "b"])

    @events.on("bump-a")
    def _(states, payload, event):
        a, b = states
        a["count"] += 1

    result = events.dispatch({"action": "bump-a"}, {"count": 0}, {"count": 0})
    assert result == ({"count": 1}, {"count": 0})


def test_handler_multi_state_supports_explicit_tuple_return():
    # Handlers that reassign (rather than mutate) must return a tuple
    app = _make_multi_state_app()
    events = ld.handler(app, state=["a", "b"])

    @events.on("swap")
    def _(states, payload, event):
        a, b = states
        return b, a

    result = events.dispatch({"action": "swap"}, {"id": 1}, {"id": 2})
    assert result == ({"id": 2}, {"id": 1})


def test_handler_multi_state_registers_exactly_one_callback():
    app = _make_multi_state_app()
    before = len(app.callback_map)
    ld.handler(app, state=["a", "b"])
    assert len(app.callback_map) == before + 1


def test_handler_rejects_empty_state_list():
    app = _make_app()
    try:
        ld.handler(app, state=[])
    except ValueError:
        pass
    else:
        raise AssertionError("Expected ValueError for empty state list")
