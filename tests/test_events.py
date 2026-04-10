from liquid_dash import emit_event
from liquid_dash.exceptions import InvalidEventError


def test_emit_event_builds_payload() -> None:
    event = emit_event(
        "card.delete",
        target="card-1",
        payload={"kind": "plot"},
        bridge="ui-events",
        timestamp=123.0,
    )
    assert event["action"] == "card.delete"
    assert event["target"] == "card-1"
    assert event["payload"] == {"kind": "plot"}
    assert event["bridge"] == "ui-events"
    assert event["timestamp"] == 123.0


def test_emit_event_rejects_empty_action() -> None:
    try:
        emit_event("")
    except InvalidEventError:
        pass
    else:
        raise AssertionError("Expected InvalidEventError")
