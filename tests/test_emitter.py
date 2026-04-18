import json

from dash import dcc, html

import dash_relay as relay


def _props(component):
    return component.to_plotly_json()["props"]


def test_emitter_wraps_any_component_with_data_attributes():
    wrapped = relay.emitter(html.Button("Delete"), "card.delete", target="card-1",
                            payload={"kind": "plot"})
    props = _props(wrapped)
    assert props["data-relay-action"] == "card.delete"
    assert json.loads(props["data-relay-target"]) == "card-1"
    assert props["data-relay-on"] == "click"
    assert props["data-relay-bridge"] == "bridge"
    assert json.loads(props["data-relay-payload"]) == {"kind": "plot"}
    # Wrapper is transparent for layout purposes
    assert props["style"] == {"display": "contents"}


def test_emitter_supports_non_html_components_via_wrapper():
    wrapped = relay.emitter(dcc.Input(placeholder="search"), "search", on="input")
    props = _props(wrapped)
    assert props["data-relay-action"] == "search"
    assert props["data-relay-on"] == "input"
    # The wrapped Input is the sole child
    children = props["children"]
    first = children[0] if isinstance(children, list) else children
    assert type(first).__name__ == "Input"


def test_emitter_curried_form_returns_reusable_emitter():
    delete = relay.emitter("delete", bridge="bus")
    a = delete(html.Button("x"), payload={"id": 1})
    b = delete(html.Button("y"), payload={"id": 2})
    assert _props(a)["data-relay-bridge"] == "bus"
    assert _props(b)["data-relay-bridge"] == "bus"
    assert json.loads(_props(a)["data-relay-payload"]) == {"id": 1}
    assert json.loads(_props(b)["data-relay-payload"]) == {"id": 2}


def test_emitter_prevent_default_flag_is_serialized():
    wrapped = relay.emitter(html.Form([]), "save", on="submit", prevent_default=True)
    props = _props(wrapped)
    assert props["data-relay-prevent-default"] == "true"


def test_emitter_rejects_empty_action():
    try:
        relay.emitter(html.Button("x"), "")
    except ValueError:
        pass
    else:
        raise AssertionError("Expected ValueError for empty action")


def test_emitter_rejects_non_json_payload():
    try:
        relay.emitter(html.Button("x"), "a", payload={"s": {1, 2}})
    except ValueError:
        pass
    else:
        raise AssertionError("Expected ValueError for non-JSON payload")


def test_emitter_target_round_trips_integer():
    # target/source are JSON-encoded so types survive the trip through
    # HTML data-* attributes and JSON.parse on the JS side. Handlers
    # receive the original Python type back.
    wrapped = relay.emitter(html.Button("x"), "delete", target=42)
    assert json.loads(_props(wrapped)["data-relay-target"]) == 42


def test_emitter_target_round_trips_zero():
    wrapped = relay.emitter(html.Button("x"), "delete", target=0)
    assert json.loads(_props(wrapped)["data-relay-target"]) == 0


def test_emitter_target_round_trips_none():
    wrapped = relay.emitter(html.Button("x"), "delete", target=None)
    assert json.loads(_props(wrapped)["data-relay-target"]) is None


def test_emitter_target_round_trips_string():
    wrapped = relay.emitter(html.Button("x"), "delete", target="card-1")
    assert json.loads(_props(wrapped)["data-relay-target"]) == "card-1"


def test_emitter_source_round_trips_integer():
    wrapped = relay.emitter(html.Button("x"), "delete", source=7)
    assert json.loads(_props(wrapped)["data-relay-source"]) == 7


def test_emitter_rejects_non_json_target():
    try:
        relay.emitter(html.Button("x"), "a", target={1, 2})
    except ValueError:
        pass
    else:
        raise AssertionError("Expected ValueError for non-JSON target")
