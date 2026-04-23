"""Tests for relay.validate()."""
from __future__ import annotations

import pytest
from dash import Dash, Output, State, dcc, html

import dash_relay as relay
from dash_relay import Action
from dash_relay.callback import _PENDING_CALLBACKS


@pytest.fixture(autouse=True)
def _isolate_pool():
    _PENDING_CALLBACKS.clear()
    yield
    _PENDING_CALLBACKS.clear()


# ---------------------------------------------------------------------------
# Pre-install: pool-based checks
# ---------------------------------------------------------------------------


def test_validate_pre_install_clean_when_no_handlers():
    report = relay.validate()
    assert report.ok


def test_validate_pre_install_flags_duplicate_handler():
    @relay.callback(Output("a", "data"), Action("close", bridge="x"))
    def _(event): return None

    @relay.callback(Output("a", "data"), Action("close", bridge="x"))
    def _(event): return None

    report = relay.validate()
    codes = {i.code for i in report.issues}
    assert "duplicate-handler" in codes


def test_validate_aliases_in_one_callback_are_not_duplicates():
    @relay.callback(
        Output("a", "data"),
        Action("close", bridge="x"),
        Action("dismiss", bridge="x"),
    )
    def _(event): return None

    report = relay.validate()
    assert report.ok


# ---------------------------------------------------------------------------
# Post-install: app-aware checks via app._dash_relay_handlers
# ---------------------------------------------------------------------------


def test_validate_post_install_uses_app_handler_set():
    @relay.callback(Output("a", "data"), Action("close", bridge="x"))
    def _(event): return None

    app = Dash(__name__)
    app.layout = html.Div([dcc.Store(id="a")])
    relay.install(app)
    # Pool drained; validate should still see the handler via app cache.
    report = relay.validate(app=app)
    assert report.ok


# ---------------------------------------------------------------------------
# Layout-aware: unreachable-handler and missing-handler
# ---------------------------------------------------------------------------


def test_validate_flags_unreachable_handler_when_no_emitter_targets_bridge():
    @relay.callback(Output("a", "data"), Action("close", bridge="ghost"))
    def _(event): return None

    layout = html.Div([
        dcc.Store(id="a"),
        Action_emitter("real-bridge", "close"),  # uses different bridge
    ])
    report = relay.validate(layout)
    codes = {i.code for i in report.issues}
    assert "unreachable-handler" in codes


def test_validate_flags_missing_handler_when_emitter_has_no_handler():
    layout = html.Div([
        dcc.Store(id="a"),
        Action_emitter("x", "orphaned-action"),
    ])
    report = relay.validate(layout)
    codes = {i.code for i in report.issues}
    assert "missing-handler" in codes


def test_validate_clean_when_emitter_handler_pair_exists():
    @relay.callback(Output("a", "data"), Action("close", bridge="bridge-a"))
    def _(event): return None

    layout = html.Div([
        dcc.Store(id="a"),
        Action_emitter("bridge-a", "close"),
    ])
    report = relay.validate(layout)
    assert report.ok, f"unexpected: {report.issues}"


def test_validate_strict_raises_on_any_issue():
    @relay.callback(Output("a", "data"), Action("close", bridge="ghost"))
    def _(event): return None

    layout = html.Div([dcc.Store(id="a")])
    with pytest.raises(relay.UnsafeLayoutError):
        relay.validate(layout, strict=True)


# ---------------------------------------------------------------------------
# Helper: build a layout fragment with an emitter (Emitter.attrs splat)
# ---------------------------------------------------------------------------


def Action_emitter(bridge_name, action_name):
    """Return a Button with relay attrs for the given (bridge, action)."""
    e = relay.Emitter(bridge=bridge_name)
    return html.Button("X", **e.attrs(action=action_name))
