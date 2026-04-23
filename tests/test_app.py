"""install() lifecycle and runtime-injection tests for v4."""
from __future__ import annotations

import pytest
from dash import Dash, Output, State, dcc, html

import dash_relay as relay
from dash_relay import Action, InstallError
from dash_relay.callback import _PENDING_CALLBACKS, _bridge_store_id


@pytest.fixture(autouse=True)
def _isolate_pool():
    _PENDING_CALLBACKS.clear()
    yield
    _PENDING_CALLBACKS.clear()


def _bare_app():
    app = Dash(__name__)
    app.layout = html.Div()
    return app


# ---------------------------------------------------------------------------
# Runtime injection (script + Flask route)
# ---------------------------------------------------------------------------


def test_install_registers_js_route_and_injects_script_tag():
    app = _bare_app()
    relay.install(app)

    assert '<script src="/_dash_relay/dash_relay.js"></script>' in app.index_string

    client = app.server.test_client()
    response = client.get("/_dash_relay/dash_relay.js")
    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith("application/javascript")
    assert "__dashRelayInstalled" in response.get_data(as_text=True)


# ---------------------------------------------------------------------------
# Lifecycle preconditions
# ---------------------------------------------------------------------------


def test_install_raises_when_layout_unset():
    app = Dash(__name__)
    # No app.layout assignment.
    with pytest.raises(InstallError, match="before app.layout was set"):
        relay.install(app)


def test_install_raises_on_double_install():
    app = _bare_app()
    relay.install(app)
    with pytest.raises(InstallError, match="already called"):
        relay.install(app)


def test_install_marks_app_with_installed_flag():
    app = _bare_app()
    relay.install(app)
    assert app._dash_relay_installed is True


# ---------------------------------------------------------------------------
# Auto store creation
# ---------------------------------------------------------------------------


def test_install_with_no_handlers_injects_no_stores():
    app = _bare_app()
    relay.install(app)
    # No bridges → no holder div added.
    assert app._dash_relay_handlers == []
    # The original layout is preserved (still html.Div).
    # Layout might have been wrapped or kept; either way no holder.
    rendered = app.layout.to_plotly_json() if hasattr(app.layout, "to_plotly_json") else None
    if rendered is not None:
        # No "_relay_bridges" id anywhere
        s = repr(rendered)
        assert "_relay_bridges" not in s


def test_install_creates_one_store_per_unique_bridge():
    @relay.callback(Output("a", "data"), Action("act-a", bridge="bridge-one"))
    def _(event): return None

    @relay.callback(Output("b", "data"), Action("act-b", bridge="bridge-two"))
    def _(event): return None

    @relay.callback(Output("c", "data"), Action("act-c", bridge="bridge-one"))
    def _(event): return None

    app = Dash(__name__)
    app.layout = html.Div([dcc.Store(id="a"), dcc.Store(id="b"), dcc.Store(id="c")])
    relay.install(app)

    # The injected holder Div should contain stores for bridge-one and bridge-two.
    s = repr(app.layout.to_plotly_json())
    assert _bridge_store_id("bridge-one") in s
    assert _bridge_store_id("bridge-two") in s


def test_install_uses_default_bridge_for_actions_without_bridge_kwarg():
    @relay.callback(Output("x", "data"), Action("ping"))
    def _(event): return None

    app = Dash(__name__)
    app.layout = html.Div([dcc.Store(id="x")])
    relay.install(app)

    s = repr(app.layout.to_plotly_json())
    assert _bridge_store_id(relay.DEFAULT_BRIDGE) in s


def test_bridge_store_id_replaces_dot_with_double_underscore():
    # CSS-safety rule from the spec — dots in bridge names break selectors.
    assert _bridge_store_id("panel.common") == "relay-bridge-panel__common"
    assert _bridge_store_id("simple") == "relay-bridge-simple"


def test_js_runtime_mirrors_bridge_store_id_rule():
    """The JS runtime derives the dcc.Store id from the bridge name with
    the same rule as Python's `_bridge_store_id`. If JS and Python drift,
    every click is a silent no-op (the JS writes to a store id that doesn't
    exist). This test asserts the rule appears in the JS asset as a string.

    Brittle on purpose — if the JS rule moves or changes shape, this fails
    loud and the regression message in `_bridge_store_id` points at the
    fix location.
    """
    from importlib import resources

    js_text = (
        resources.files("dash_relay")
        .joinpath("assets", "dash_relay.js")
        .read_text(encoding="utf-8")
    )
    # Two facts the JS must encode:
    #   1. The store-id prefix is "relay-bridge-".
    #   2. Dots in the bridge name are replaced with double-underscore.
    # Spelling tolerated: any standard JS replace expressions for "." → "__".
    assert '"relay-bridge-"' in js_text, (
        "JS runtime must prefix store ids with 'relay-bridge-'; "
        "see _bridge_store_id in callback.py for the canonical rule."
    )
    assert 'replace(/\\./g, "__")' in js_text, (
        "JS runtime must replace '.' with '__' to match Python's "
        "_bridge_store_id slug rule. Without this, clicks silently no-op "
        "because Dash has no store at the raw bridge name."
    )


# ---------------------------------------------------------------------------
# Layout injection — three shapes
# ---------------------------------------------------------------------------


def test_install_wraps_single_component_layout_in_div():
    @relay.callback(Output("x", "data"), Action("ping"))
    def _(event): return None

    app = Dash(__name__)
    app.layout = html.Div([dcc.Store(id="x")], id="user-root")
    relay.install(app)

    # The user's html.Div is now wrapped inside a parent Div alongside
    # the holder.
    j = app.layout.to_plotly_json()
    children = j["props"]["children"]
    # Two children: the original layout and the holder.
    assert len(children) == 2
    assert any("_relay_bridges" in repr(c) for c in children)


def test_install_handles_callable_layout():
    @relay.callback(Output("x", "data"), Action("ping"))
    def _(event): return None

    app = Dash(__name__)

    def page_layout():
        return html.Div([dcc.Store(id="x")], id="page-root")

    app.layout = page_layout
    relay.install(app)

    # app.layout is now a wrapper callable.
    assert callable(app.layout)
    rendered = app.layout()
    s = repr(rendered.to_plotly_json() if hasattr(rendered, "to_plotly_json") else rendered)
    assert "_relay_bridges" in s
    assert "page-root" in s


# ---------------------------------------------------------------------------
# Dispatcher registration
# ---------------------------------------------------------------------------


def test_install_registers_one_dash_callback_per_bridge():
    @relay.callback(Output("a", "data"), Action("ping", bridge="b1"))
    def _(event): return None

    @relay.callback(Output("b", "data"), Action("ping", bridge="b2"))
    def _(event): return None

    app = Dash(__name__)
    app.layout = html.Div([dcc.Store(id="a"), dcc.Store(id="b")])
    before = len(app.callback_map)
    relay.install(app)
    # Two bridges → two dispatchers.
    assert len(app.callback_map) == before + 2


def test_install_dispatcher_routes_event_to_handler():
    @relay.callback(
        Output("state", "data"),
        Action("bump", bridge="counter"),
        State("state", "data"),
    )
    def bump(event, current):
        return {"count": (current or {}).get("count", 0) + 1}

    app = Dash(__name__)
    app.layout = html.Div([dcc.Store(id="state")])
    relay.install(app)

    plan = app._dash_relay_bridge_plans["counter"]
    result = plan.dispatch({"action": "bump"}, {"count": 5})
    assert result == {"count": 6}
