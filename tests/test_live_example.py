from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


EXAMPLE_PATH = Path(__file__).resolve().parents[1] / "examples" / "live_test" / "app.py"


def _load_example_module():
    spec = spec_from_file_location("liquid_dash_live_example", EXAMPLE_PATH)
    module = module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_live_example_can_add_retype_and_delete_panels():
    demo = _load_example_module()
    state = demo.default_state()

    state = demo.apply_event(state, {"action": "panel.add", "payload": {"kind": "timeseries"}})
    added = state["panels"][-1]
    assert added["kind"] == "timeseries"

    state = demo.apply_event(
        state,
        {
            "action": "panel.kind.set",
            "target": added["id"],
            "payload": {"kind": "scatter"},
        },
    )
    changed = next(panel for panel in state["panels"] if panel["id"] == added["id"])
    assert changed["kind"] == "scatter"
    assert "marker_size" in changed["settings"]

    state = demo.apply_event(state, {"action": "panel.delete", "target": changed["id"]})
    assert all(panel["id"] != changed["id"] for panel in state["panels"])


def test_live_example_badges_and_specific_settings_change():
    demo = _load_example_module()
    state = demo.default_state()
    panel_id = state["panels"][0]["id"]
    original_badge_count = len(state["panels"][0]["badges"])

    state = demo.apply_event(state, {"action": "panel.badge.add", "target": panel_id})
    state = demo.apply_event(
        state,
        {
            "action": "panel.setting",
            "target": panel_id,
            "payload": {"mode": "cycle", "key": "line_style", "values": ["solid", "dash", "dot"]},
        },
    )
    state = demo.apply_event(
        state,
        {
            "action": "panel.setting",
            "target": panel_id,
            "payload": {"mode": "toggle", "key": "show_markers"},
        },
    )

    panel = next(panel for panel in state["panels"] if panel["id"] == panel_id)
    assert len(panel["badges"]) == original_badge_count + 1
    assert panel["settings"]["line_style"] == "dash"
    assert panel["settings"]["show_markers"] is True
