from dash import Dash, dcc, html

import dash_relay as relay


def test_validate_flags_missing_bridge() -> None:
    # Action targets a bridge id that doesn't exist as a dcc.Store in the layout.
    layout = html.Div(
        [
            dcc.Store(id="bridge"),  # default bridge, but action points elsewhere
            relay.emitter(html.Button("Delete"), "card.delete", bridge="ghost-bus"),
        ]
    )
    report = relay.validate(layout)
    codes = {issue.code for issue in report.issues}
    assert "missing-bridge" in codes


def test_validate_flags_duplicate_ids() -> None:
    layout = html.Div(
        [
            dcc.Store(id="dup"),
            html.Div(id="dup"),
        ]
    )
    report = relay.validate(layout)
    codes = {issue.code for issue in report.issues}
    assert "duplicate-id" in codes


def test_validate_passes_on_clean_layout() -> None:
    layout = html.Div(
        [
            relay.bridge(),
            relay.emitter(html.Button("Add"), "add"),
            relay.emitter(html.Button("Delete"), "delete", target="row-1"),
        ]
    )
    report = relay.validate(layout)
    assert report.ok, f"unexpected issues: {report.issues}"


def _app_with_state() -> Dash:
    app = Dash(__name__)
    app.layout = html.Div([dcc.Store(id="state", data={}), relay.bridge()])
    return app


def test_validate_flags_emitter_with_no_matching_handler() -> None:
    app = _app_with_state()
    events = relay.registry(app, state="state")

    @events.handler("add")
    def _(s, p, e):
        return s

    # Emitter uses 'addd' (typo) — no matching handler on the registry.
    layout = html.Div(
        [
            dcc.Store(id="state"),
            relay.bridge(),
            relay.emitter(html.Button("Add"), "addd"),
        ]
    )
    report = relay.validate(layout, registry=events)
    codes = [i.code for i in report.issues]
    assert "orphan-emitter" in codes
    orphan = next(i for i in report.issues if i.code == "orphan-emitter")
    assert "addd" in orphan.message


def test_validate_flags_handler_with_no_emitter() -> None:
    app = _app_with_state()
    events = relay.registry(app, state="state")

    # 'delete' is registered but nothing in the layout emits it.
    @events.handler("delete")
    def _(s, p, e):
        return s

    @events.handler("add")
    def _(s, p, e):
        return s

    layout = html.Div(
        [
            dcc.Store(id="state"),
            relay.bridge(),
            relay.emitter(html.Button("Add"), "add"),
        ]
    )
    report = relay.validate(layout, registry=events)
    codes = [i.code for i in report.issues]
    assert "orphan-handler" in codes
    orphan = next(i for i in report.issues if i.code == "orphan-handler")
    assert "delete" in orphan.message


def test_validate_clean_when_emitters_and_handlers_match() -> None:
    app = _app_with_state()
    events = relay.registry(app, state="state")

    @events.handler("add")
    def _(s, p, e):
        return s

    @events.handler("delete")
    def _(s, p, e):
        return s

    layout = html.Div(
        [
            dcc.Store(id="state"),
            relay.bridge(),
            relay.emitter(html.Button("Add"), "add"),
            relay.emitter(html.Button("x"), "delete"),
        ]
    )
    report = relay.validate(layout, registry=events)
    assert report.ok, f"unexpected issues: {report.issues}"


def test_validate_registry_param_is_optional() -> None:
    # Backward compatibility: existing callers that don't pass registry=
    # still get the original behavior (no orphan checks).
    layout = html.Div(
        [
            dcc.Store(id="state"),
            relay.bridge(),
            relay.emitter(html.Button("Add"), "some-unregistered-action"),
        ]
    )
    report = relay.validate(layout)
    codes = {i.code for i in report.issues}
    assert "orphan-emitter" not in codes
    assert "orphan-handler" not in codes


def test_validate_rejects_registry_without_actions_method() -> None:
    layout = html.Div([dcc.Store(id="state"), relay.bridge()])
    import pytest

    class Fake:
        pass

    with pytest.raises(TypeError, match="actions"):
        relay.validate(layout, registry=Fake())


def test_registry_actions_method_returns_registered_names() -> None:
    app = _app_with_state()
    events = relay.registry(app, state="state")

    @events.handler("one")
    def _(s, p, e):
        return s

    @events.handler("two")
    def _(s, p, e):
        return s

    assert events.actions() == frozenset({"one", "two"})
