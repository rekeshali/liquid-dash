from dash import dcc, html

import liquid_dash as ld


def test_validate_flags_missing_bridge() -> None:
    # Action targets a bridge id that doesn't exist as a dcc.Store in the layout.
    layout = html.Div(
        [
            dcc.Store(id="bridge"),  # default bridge, but action points elsewhere
            ld.on(html.Button("Delete"), "card.delete", to="ghost-bus"),
        ]
    )
    report = ld.validate(layout)
    codes = {issue.code for issue in report.issues}
    assert "missing-bridge" in codes


def test_validate_flags_duplicate_ids() -> None:
    layout = html.Div(
        [
            dcc.Store(id="dup"),
            html.Div(id="dup"),
        ]
    )
    report = ld.validate(layout)
    codes = {issue.code for issue in report.issues}
    assert "duplicate-id" in codes


def test_validate_passes_on_clean_layout() -> None:
    layout = html.Div(
        [
            ld.bridge(),
            ld.on(html.Button("Add"), "add"),
            ld.on(html.Button("Delete"), "delete", target="row-1"),
        ]
    )
    report = ld.validate(layout)
    assert report.ok, f"unexpected issues: {report.issues}"
