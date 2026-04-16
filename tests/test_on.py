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


def test_on_stringifies_integer_target():
    # Client JS reads dataset attributes as strings; stringify at the boundary
    # so handlers comparing `event["target"]` to `item["id"]` don't silently
    # fail on int-vs-str mismatch.
    wrapped = ld.on(html.Button("x"), "delete", target=42)
    assert _props(wrapped)["data-ld-target"] == "42"


def test_on_stringifies_zero_target():
    # target=0 used to fall through `target or ""` and become "" — a silent
    # data-loss bug. Now it becomes "0".
    wrapped = ld.on(html.Button("x"), "delete", target=0)
    assert _props(wrapped)["data-ld-target"] == "0"


def test_on_treats_none_target_as_empty():
    wrapped = ld.on(html.Button("x"), "delete", target=None)
    assert _props(wrapped)["data-ld-target"] == ""


def test_on_stringifies_source():
    wrapped = ld.on(html.Button("x"), "delete", source=7)
    assert _props(wrapped)["data-ld-source"] == "7"
