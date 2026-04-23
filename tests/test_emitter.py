"""Emitter (template class) tests."""
from __future__ import annotations

import json

import pytest
from dash import dcc, html

from dash_relay import Emitter, DEFAULT_BRIDGE


def _props(component):
    return component.to_plotly_json()["props"]


# ---------------------------------------------------------------------------
# .attrs() — raw attribute dict, no wrapper
# ---------------------------------------------------------------------------


def test_attrs_returns_data_relay_dict_with_no_component():
    e = Emitter(bridge="cards")
    attrs = e.attrs(action="pin", target="row-7")
    assert attrs["data-relay-action"] == "pin"
    assert attrs["data-relay-bridge"] == "cards"
    assert attrs["data-relay-target"] == "row-7"
    assert attrs["data-relay-on"] == "click"
    assert attrs["data-relay-prevent-default"] == "false"


def test_attrs_can_be_splatted_onto_html_component():
    e = Emitter(bridge="cards")
    button = html.Button("Pin", **e.attrs(action="pin", target="row-7"))
    p = _props(button)
    assert p["data-relay-action"] == "pin"
    # Crucially, no wrapper Div — the attrs live directly on the Button.
    assert "Button" in type(button).__name__


def test_attrs_default_bridge_when_none_set():
    e = Emitter()
    attrs = e.attrs(action="ping")
    assert attrs["data-relay-bridge"] == DEFAULT_BRIDGE


def test_attrs_raises_when_action_missing_on_template_and_overrides():
    e = Emitter(bridge="cards")
    with pytest.raises(ValueError, match="requires an action"):
        e.attrs()


# ---------------------------------------------------------------------------
# .wrap() — Component wrapped in a transparent Div
# ---------------------------------------------------------------------------


def test_wrap_wraps_component_in_display_contents_div():
    e = Emitter(bridge="cards")
    wrapped = e.wrap(html.Button("Pin"), action="pin")
    p = _props(wrapped)
    assert p["style"] == {"display": "contents"}
    assert p["data-relay-action"] == "pin"
    children = p["children"]
    inner = children[0] if isinstance(children, list) else children
    assert "Button" in type(inner).__name__


def test_wrap_auto_fills_source_from_component_id():
    # B9: when source isn't set on template or override and the component
    # has an id, source defaults to that id.
    e = Emitter(bridge="cards")
    wrapped = e.wrap(html.Button("Pin", id="pin-btn"), action="pin")
    assert _props(wrapped)["data-relay-source"] == "pin-btn"


def test_wrap_explicit_source_override_beats_component_id():
    e = Emitter(bridge="cards", source="from-template")
    wrapped = e.wrap(html.Button("Pin", id="pin-btn"), action="pin")
    assert _props(wrapped)["data-relay-source"] == "from-template"


# ---------------------------------------------------------------------------
# Template + override semantics (B7)
# ---------------------------------------------------------------------------


def test_overrides_replace_not_merge():
    # B7: payload overrides REPLACE the template payload, not merge into it.
    e = Emitter(bridge="cards", payload={"scope": "panel-1", "region": "panel"})
    attrs = e.attrs(action="link", payload={"scope": "panel-2"})
    decoded = json.loads(attrs["data-relay-payload"])
    assert decoded == {"scope": "panel-2"}
    assert "region" not in decoded


def test_explicit_merge_via_unpacking_works():
    e = Emitter(bridge="cards", payload={"scope": "panel-1", "region": "panel"})
    attrs = e.attrs(action="link", payload={**e.payload, "scope": "panel-2"})
    decoded = json.loads(attrs["data-relay-payload"])
    assert decoded == {"scope": "panel-2", "region": "panel"}


def test_template_reused_across_many_call_sites():
    e = Emitter(bridge="panel.common", target="panel-99")
    a = e.attrs(action="lock")
    b = e.attrs(action="link")
    c = e.attrs(action="add", target="panel-100")
    assert a["data-relay-action"] == "lock"
    assert a["data-relay-target"] == "panel-99"
    assert b["data-relay-action"] == "link"
    assert b["data-relay-target"] == "panel-99"
    assert c["data-relay-action"] == "add"
    assert c["data-relay-target"] == "panel-100"


def test_unknown_override_raises():
    e = Emitter(bridge="cards")
    with pytest.raises(TypeError, match="unexpected keyword"):
        e.attrs(action="pin", garbage="?")


# ---------------------------------------------------------------------------
# Target wire encoding (B10) — plain string for str/int, JSON for dict
# ---------------------------------------------------------------------------


def test_target_string_encoded_as_plain_string():
    e = Emitter()
    attrs = e.attrs(action="pin", target="card-1")
    assert attrs["data-relay-target"] == "card-1"


def test_target_int_encoded_as_plain_string_of_digits():
    e = Emitter()
    attrs = e.attrs(action="pin", target=42)
    assert attrs["data-relay-target"] == "42"


def test_target_dict_encoded_as_compact_json():
    e = Emitter()
    attrs = e.attrs(action="pin", target={"entity_id": "x", "scope": "y"})
    decoded = json.loads(attrs["data-relay-target"])
    assert decoded == {"entity_id": "x", "scope": "y"}


def test_target_none_encoded_as_empty_string():
    e = Emitter()
    attrs = e.attrs(action="pin", target=None)
    assert attrs["data-relay-target"] == ""


def test_target_bool_rejected_explicitly():
    # bool is an int subclass in Python — would silently become "1"/"0".
    # Reject explicitly so callers know they're losing information.
    e = Emitter()
    with pytest.raises(TypeError, match="bool"):
        e.attrs(action="pin", target=True)


def test_target_unsupported_type_rejected():
    e = Emitter()
    with pytest.raises(TypeError, match="must be str, int, or dict"):
        e.attrs(action="pin", target=[1, 2, 3])


def test_target_dict_with_non_serializable_value_rejected():
    e = Emitter()
    with pytest.raises(ValueError, match="JSON-serializable"):
        e.attrs(action="pin", target={"set": {1, 2}})


# ---------------------------------------------------------------------------
# Payload encoding (always JSON)
# ---------------------------------------------------------------------------


def test_payload_dict_round_trips_via_json():
    e = Emitter()
    attrs = e.attrs(action="pin", payload={"a": 1, "b": "two"})
    assert json.loads(attrs["data-relay-payload"]) == {"a": 1, "b": "two"}


def test_payload_none_encoded_as_empty_string():
    e = Emitter()
    attrs = e.attrs(action="pin")
    assert attrs["data-relay-payload"] == ""


def test_payload_must_be_dict():
    e = Emitter()
    with pytest.raises(TypeError, match="payload must be a dict"):
        e.attrs(action="pin", payload=[1, 2])


# ---------------------------------------------------------------------------
# on / prevent_default
# ---------------------------------------------------------------------------


def test_on_defaults_to_click():
    attrs = Emitter().attrs(action="x")
    assert attrs["data-relay-on"] == "click"


def test_on_can_be_overridden():
    attrs = Emitter().attrs(action="x", on="input")
    assert attrs["data-relay-on"] == "input"


def test_prevent_default_serialized_as_string_bool():
    attrs = Emitter(prevent_default=True).attrs(action="x")
    assert attrs["data-relay-prevent-default"] == "true"
    attrs = Emitter().attrs(action="x")
    assert attrs["data-relay-prevent-default"] == "false"
