"""Tests for relay.validate() against the 3.0 surface."""
from __future__ import annotations

import pytest
from dash import Dash, Output, State, dcc, html

import dash_relay as relay
from dash_relay import Action
from dash_relay.handle import _PENDING_HANDLERS
from dash_relay.bridge import _REGISTERED_BRIDGE_IDS


@pytest.fixture(autouse=True)
def _isolate_pools():
    _PENDING_HANDLERS.clear()
    _REGISTERED_BRIDGE_IDS.clear()
    yield
    _PENDING_HANDLERS.clear()
    _REGISTERED_BRIDGE_IDS.clear()


def test_validate_flags_missing_bridge():
    layout = html.Div([
        dcc.Store(id="bridge"),
        relay.emitter(html.Button("Delete"), "card.delete", bridge="ghost-bus"),
    ])
    report = relay.validate(layout)
    codes = {issue.code for issue in report.issues}
    assert "missing-bridge" in codes


def test_validate_flags_duplicate_ids():
    layout = html.Div([dcc.Store(id="dup"), html.Div(id="dup")])
    report = relay.validate(layout)
    codes = {issue.code for issue in report.issues}
    assert "duplicate-id" in codes


def test_validate_passes_on_clean_layout():
    layout = html.Div([
        relay.bridge(),
        relay.emitter(html.Button("Add"), "add"),
        relay.emitter(html.Button("Delete"), "delete", target="row-1"),
    ])
    report = relay.validate(layout)
    assert report.ok, f"unexpected issues: {report.issues}"


def test_validate_with_app_flags_emitter_with_no_matching_handler():
    @relay.handle(Output("state", "data"), Action("add"))
    def _(event): return None

    app = Dash(__name__)
    app.layout = html.Div([dcc.Store(id="state"), relay.bridge()])
    relay.install(app)

    layout = html.Div([
        dcc.Store(id="state"),
        relay.bridge(),
        relay.emitter(html.Button("Add"), "addd"),  # typo
    ])
    report = relay.validate(layout, app=app)
    codes = [i.code for i in report.issues]
    assert "orphan-emitter" in codes
    assert "addd" in next(i.message for i in report.issues if i.code == "orphan-emitter")


def test_validate_with_app_flags_handler_with_no_emitter():
    @relay.handle(Output("state", "data"), Action("delete"))
    def _(event): return None

    @relay.handle(Output("state", "data"), Action("add"))
    def _(event): return None

    app = Dash(__name__)
    app.layout = html.Div([dcc.Store(id="state"), relay.bridge()])
    # Note: install() will fail because two handlers can't both write
    # the same Output without allow_duplicate. Use distinct Outputs.

    _PENDING_HANDLERS.clear()  # reset

    @relay.handle(Output("state", "data"), Action("add"))
    def _(event): return None

    @relay.handle(Output("other", "data"), Action("delete"))
    def _(event): return None

    app2 = Dash(__name__)
    app2.layout = html.Div([
        dcc.Store(id="state"),
        dcc.Store(id="other"),
        relay.bridge(),
    ])
    relay.install(app2)

    layout = html.Div([
        dcc.Store(id="state"),
        dcc.Store(id="other"),
        relay.bridge(),
        relay.emitter(html.Button("Add"), "add"),
        # No emitter for 'delete' — should be flagged.
    ])
    report = relay.validate(layout, app=app2)
    codes = [i.code for i in report.issues]
    assert "orphan-handler" in codes
    assert "delete" in next(i.message for i in report.issues if i.code == "orphan-handler")


def test_validate_clean_when_emitters_and_handlers_match():
    @relay.handle(Output("a", "data"), Action("add"))
    def _(event): return None

    @relay.handle(Output("b", "data"), Action("delete"))
    def _(event): return None

    app = Dash(__name__)
    app.layout = html.Div([
        dcc.Store(id="a"),
        dcc.Store(id="b"),
        relay.bridge(),
    ])
    relay.install(app)

    layout = html.Div([
        dcc.Store(id="a"),
        dcc.Store(id="b"),
        relay.bridge(),
        relay.emitter(html.Button("Add"), "add"),
        relay.emitter(html.Button("x"), "delete"),
    ])
    report = relay.validate(layout, app=app)
    assert report.ok, f"unexpected issues: {report.issues}"


def test_validate_app_param_is_optional():
    layout = html.Div([
        dcc.Store(id="state"),
        relay.bridge(),
        relay.emitter(html.Button("Add"), "some-unregistered-action"),
    ])
    report = relay.validate(layout)  # no app=
    codes = {i.code for i in report.issues}
    assert "orphan-emitter" not in codes
    assert "orphan-handler" not in codes


def test_validate_flags_output_id_with_no_store_in_layout():
    @relay.handle(Output("missing-store", "data"), Action("touch"))
    def _(event): return None

    app = Dash(__name__)
    app.layout = html.Div([dcc.Store(id="missing-store"), relay.bridge()])
    relay.install(app)

    # Validate against a layout that lacks the output store.
    layout = html.Div([relay.bridge()])
    report = relay.validate(layout, app=app)
    codes = {i.code for i in report.issues}
    assert "output-not-found" in codes


def test_validate_flags_state_id_with_no_store_in_layout():
    @relay.handle(
        Output("write", "data"),
        Action("touch"),
        State("read", "data"),
    )
    def _(event, val): return None

    app = Dash(__name__)
    app.layout = html.Div([
        dcc.Store(id="write"),
        dcc.Store(id="read"),
        relay.bridge(),
    ])
    relay.install(app)

    # Layout has write but not read.
    layout = html.Div([dcc.Store(id="write"), relay.bridge()])
    report = relay.validate(layout, app=app)
    codes = {i.code for i in report.issues}
    assert "state-not-found" in codes
    assert "output-not-found" not in codes


def test_validate_clean_when_output_and_state_stores_present():
    @relay.handle(
        Output("write", "data"),
        Action("touch"),
        State("read", "data"),
    )
    def _(event, val): return None

    app = Dash(__name__)
    app.layout = html.Div([
        dcc.Store(id="write"),
        dcc.Store(id="read"),
        relay.bridge(),
        relay.emitter(html.Button("Touch"), "touch"),
    ])
    relay.install(app)

    report = relay.validate(app.layout, app=app)
    codes = {i.code for i in report.issues}
    assert "output-not-found" not in codes
    assert "state-not-found" not in codes
