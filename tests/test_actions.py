from liquid_dash import action_button, action_div


def test_action_button_sets_data_attributes() -> None:
    component = action_button(
        "Delete",
        action="card.delete",
        target="card-1",
        payload={"kind": "plot"},
        bridge="ui-events",
    )
    props = component.to_plotly_json()["props"]
    assert props["data-ld-action"] == "card.delete"
    assert props["data-ld-target"] == "card-1"
    assert props["data-ld-bridge"] == "ui-events"
    assert props["data-ld-payload"] == '{"kind": "plot"}'


def test_action_div_defaults_to_keyboard_accessible_button_role() -> None:
    component = action_div("Open", action="menu.open", bridge="ui-events")
    props = component.to_plotly_json()["props"]
    assert props["role"] == "button"
    assert props["tabIndex"] == 0
