from dash import html

from liquid_dash import DynamicRegion, StableRegion, action_button, validate_layout


def test_validate_layout_flags_missing_bridge() -> None:
    layout = StableRegion(
        children=[
            DynamicRegion(children=[action_button("Delete", action="card.delete")])
        ]
    )
    report = validate_layout(layout, return_report=True)
    codes = {issue.code for issue in report.issues}
    assert "missing-bridge" in codes


def test_validate_layout_flags_raw_interactive_in_dynamic_region() -> None:
    layout = StableRegion(
        children=[
            DynamicRegion(bridge="ui-events", children=[html.Button("Plain")])
        ]
    )
    report = validate_layout(layout, return_report=True)
    codes = {issue.code for issue in report.issues}
    assert "raw-interactive-in-dynamic" in codes
