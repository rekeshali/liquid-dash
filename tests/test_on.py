import json

from dash import dcc, html

import liquid_dash as ld


def _props(component):
    return component.to_plotly_json()["props"]


def test_on_wraps_any_component_with_data_attributes():
    wrapped = ld.on(html.Button("Delete"), "card.delete", target="card-1",
                    payload={"kind": "plot"})
    props = _props(wrapped)
    assert props["data-ld-action"] == "card.delete"
    assert props["data-ld-target"] == "card-1"
    assert props["data-ld-event"] == "click"
    assert props["data-ld-bridge"] == "bridge"
    assert json.loads(props["data-ld-payload"]) == {"kind": "plot"}
    # Wrapper is transparent for layout purposes
    assert props["style"] == {"display": "contents"}


def test_on_supports_non_html_components_via_wrapper():
    wrapped = ld.on(dcc.Input(placeholder="search"), "search", event="input")
    props = _props(wrapped)
    assert props["data-ld-action"] == "search"
    assert props["data-ld-event"] == "input"
    # The wrapped Input is the sole child
    children = props["children"]
    first = children[0] if isinstance(children, list) else children
    assert type(first).__name__ == "Input"


def test_on_curried_form_returns_reusable_emitter():
    delete = ld.on("delete", to="bus")
    a = delete(html.Button("x"), payload={"id": 1})
    b = delete(html.Button("y"), payload={"id": 2})
    assert _props(a)["data-ld-bridge"] == "bus"
    assert _props(b)["data-ld-bridge"] == "bus"
    assert json.loads(_props(a)["data-ld-payload"]) == {"id": 1}
    assert json.loads(_props(b)["data-ld-payload"]) == {"id": 2}


def test_on_prevent_default_flag_is_serialized():
    wrapped = ld.on(html.Form([]), "save", event="submit", prevent_default=True)
    props = _props(wrapped)
    assert props["data-ld-prevent-default"] == "true"


def test_on_rejects_empty_action():
    try:
        ld.on(html.Button("x"), "")
    except ValueError:
        pass
    else:
        raise AssertionError("Expected ValueError for empty action")


def test_on_rejects_non_json_payload():
    try:
        ld.on(html.Button("x"), "a", payload={"s": {1, 2}})
    except ValueError:
        pass
    else:
        raise AssertionError("Expected ValueError for non-JSON payload")
