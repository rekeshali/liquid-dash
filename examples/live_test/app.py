from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys

from dash import Dash, Input, Output, State, dcc, html, no_update

# Allow running the demo directly from the source tree before installation.
ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from liquid_dash import DynamicRegion, EventBridge, StableRegion, action_button, configure


BADGE_COLORS = ["#2563eb", "#7c3aed", "#db2777", "#f59e0b", "#059669"]
BADGE_LIBRARY = ["Hot", "QA", "Shared", "Draft", "Pinned"]
KIND_ORDER = ["timeseries", "histogram", "scatter"]

KIND_SPECS = {
    "timeseries": {
        "label": "Time Series",
        "subtitle": "Trace styling and smoothing",
        "icon": "wave",
        "type_color": "#2563eb",
        "settings": {
            "line_width": 2,
            "line_style": "solid",
            "show_markers": False,
            "smoothing": "off",
        },
    },
    "histogram": {
        "label": "Histogram",
        "subtitle": "Distribution bins and normalization",
        "icon": "bars",
        "type_color": "#f59e0b",
        "settings": {
            "bins": 12,
            "normalize": False,
            "cumulative": False,
            "reference_lines": False,
        },
    },
    "scatter": {
        "label": "Scatter",
        "subtitle": "Marker sizing and overlays",
        "icon": "dots",
        "type_color": "#db2777",
        "settings": {
            "marker_size": 6,
            "trendline": True,
            "density_overlay": False,
            "palette": "blue",
        },
    },
}


def default_state() -> dict:
    return {
        "next_index": 4,
        "panels": [
            make_panel_state(1, "timeseries"),
            make_panel_state(2, "histogram"),
            make_panel_state(3, "scatter"),
        ],
    }


def make_panel_state(index: int, kind: str) -> dict:
    spec = KIND_SPECS[kind]
    badges = []
    if kind == "timeseries":
        badges = [{"label": "Hot", "color": "#2563eb"}]
    elif kind == "histogram":
        badges = [{"label": "QA", "color": "#f59e0b"}]
    elif kind == "scatter":
        badges = [{"label": "Draft", "color": "#db2777"}]

    return {
        "id": f"panel-{index}",
        "kind": kind,
        "title": f"{spec['label']} {index}",
        "subtitle": spec["subtitle"],
        "expanded": index == 1,
        "locked": False,
        "badges": badges,
        "settings": deepcopy(spec["settings"]),
    }


def cycle_value(current, values: list):
    if not values:
        return current
    if current not in values:
        return values[0]
    idx = values.index(current)
    return values[(idx + 1) % len(values)]


def cycle_kind(current_kind: str, new_kind: str | None) -> str:
    if new_kind in KIND_SPECS:
        return new_kind
    return cycle_value(current_kind, KIND_ORDER)


def add_badge(panel: dict) -> None:
    badge_index = len(panel["badges"])
    panel["badges"].append(
        {
            "label": BADGE_LIBRARY[badge_index % len(BADGE_LIBRARY)],
            "color": BADGE_COLORS[badge_index % len(BADGE_COLORS)],
        }
    )


def cycle_badge(panel: dict) -> None:
    if not panel["badges"]:
        return
    badge = panel["badges"][-1]
    badge["color"] = cycle_value(badge.get("color"), BADGE_COLORS)


def set_kind(panel: dict, kind: str) -> None:
    spec = KIND_SPECS[kind]
    panel["kind"] = kind
    panel["subtitle"] = spec["subtitle"]
    panel["settings"] = deepcopy(spec["settings"])


def apply_setting(panel: dict, payload: dict) -> None:
    settings = panel["settings"]
    mode = payload.get("mode")
    key = payload.get("key")
    if not key:
        return

    if mode == "toggle":
        settings[key] = not bool(settings.get(key, False))
        return

    if mode == "bump":
        value = int(settings.get(key, 0))
        delta = int(payload.get("delta", 0))
        minimum = int(payload.get("minimum", 0))
        maximum = int(payload.get("maximum", 99))
        settings[key] = max(minimum, min(maximum, value + delta))
        return

    if mode == "cycle":
        values = payload.get("values") or []
        settings[key] = cycle_value(settings.get(key), values)


def apply_event(state: dict, event: dict | None) -> dict:
    if not event:
        return state

    action = event.get("action")
    target = event.get("target")
    payload = event.get("payload") or {}

    next_state = deepcopy(state)
    panels = next_state["panels"]

    if action == "panel.add":
        kind = payload.get("kind", "timeseries")
        panels.append(make_panel_state(next_state["next_index"], kind))
        next_state["next_index"] += 1
        return next_state

    panel = next((item for item in panels if item["id"] == target), None)
    if panel is None:
        return next_state

    if action == "panel.delete":
        next_state["panels"] = [item for item in panels if item["id"] != target]
        return next_state

    if action == "panel.duplicate":
        clone = deepcopy(panel)
        clone["id"] = f"panel-{next_state['next_index']}"
        clone["title"] = f"{panel['title']} Copy"
        clone["expanded"] = True
        next_state["next_index"] += 1
        panels.append(clone)
        return next_state

    if action == "panel.drawer.toggle":
        panel["expanded"] = not bool(panel.get("expanded"))
        return next_state

    if action == "panel.lock.toggle":
        panel["locked"] = not bool(panel.get("locked"))
        return next_state

    if action == "panel.kind.set":
        set_kind(panel, cycle_kind(panel["kind"], payload.get("kind")))
        return next_state

    if action == "panel.badge.add":
        add_badge(panel)
        return next_state

    if action == "panel.badge.cycle":
        cycle_badge(panel)
        return next_state

    if action == "panel.badge.remove":
        if panel["badges"]:
            panel["badges"].pop()
        return next_state

    if action == "panel.setting":
        apply_setting(panel, payload)
        return next_state

    return next_state


def icon_for(kind: str):
    if kind == "timeseries":
        return html.Div(className="preview-wave")
    if kind == "histogram":
        heights = [24, 42, 60, 38, 28, 18, 10]
        return html.Div(
            [html.Div(className="preview-bar", style={"height": f"{height}px"}) for height in heights],
            className="preview-bars",
        )
    dots = [
        {"left": "8%", "top": "58%"},
        {"left": "20%", "top": "44%"},
        {"left": "38%", "top": "66%"},
        {"left": "55%", "top": "30%"},
        {"left": "72%", "top": "52%"},
        {"left": "84%", "top": "18%"},
    ]
    return html.Div(
        [html.Div(className="preview-dot", style=dot_style) for dot_style in dots],
        className="preview-scatter",
    )


def render_badges(panel: dict):
    badges = panel.get("badges") or []
    if not badges:
        return html.Span("No badges", className="panel-muted")
    return html.Div(
        [
            html.Span(
                badge["label"],
                className="panel-badge",
                style={"background": badge["color"]},
            )
            for badge in badges
        ],
        className="panel-badge-row",
    )


def stat_chip(label: str, value: str):
    return html.Div(
        [
            html.Div(label, className="panel-chip-label"),
            html.Div(value, className="panel-chip-value"),
        ],
        className="panel-chip",
    )


def preview_metrics(panel: dict):
    settings = panel["settings"]
    kind = panel["kind"]
    if kind == "timeseries":
        return [
            stat_chip("Width", str(settings["line_width"])),
            stat_chip("Style", settings["line_style"]),
            stat_chip("Markers", "On" if settings["show_markers"] else "Off"),
        ]
    if kind == "histogram":
        return [
            stat_chip("Bins", str(settings["bins"])),
            stat_chip("Normalize", "On" if settings["normalize"] else "Off"),
            stat_chip("Cumulative", "On" if settings["cumulative"] else "Off"),
        ]
    return [
        stat_chip("Size", str(settings["marker_size"])),
        stat_chip("Trend", "On" if settings["trendline"] else "Off"),
        stat_chip("Palette", settings["palette"]),
    ]


def settings_controls(panel: dict):
    panel_id = panel["id"]
    kind = panel["kind"]
    settings = panel["settings"]

    retype = html.Div(
        [
            html.Div("Retype panel", className="panel-section-title"),
            html.Div(
                [
                    action_button(
                        KIND_SPECS[kind_name]["label"],
                        action="panel.kind.set",
                        target=panel_id,
                        payload={"kind": kind_name},
                        bridge="ui-events",
                        className=("mini-btn is-active" if kind == kind_name else "mini-btn"),
                    )
                    for kind_name in KIND_ORDER
                ],
                className="mini-btn-row",
            ),
        ],
        className="settings-block",
    )

    badges = html.Div(
        [
            html.Div("Badges", className="panel-section-title"),
            html.Div(
                [
                    action_button("Add", action="panel.badge.add", target=panel_id, bridge="ui-events", className="mini-btn"),
                    action_button("Cycle Color", action="panel.badge.cycle", target=panel_id, bridge="ui-events", className="mini-btn"),
                    action_button("Remove Last", action="panel.badge.remove", target=panel_id, bridge="ui-events", className="mini-btn"),
                ],
                className="mini-btn-row",
            ),
        ],
        className="settings-block",
    )

    if kind == "timeseries":
        specifics = [
            html.Div("Trace controls", className="panel-section-title"),
            html.Div(
                [
                    action_button("Width -", action="panel.setting", target=panel_id, payload={"mode": "bump", "key": "line_width", "delta": -1, "minimum": 1, "maximum": 6}, bridge="ui-events", className="mini-btn"),
                    action_button("Width +", action="panel.setting", target=panel_id, payload={"mode": "bump", "key": "line_width", "delta": 1, "minimum": 1, "maximum": 6}, bridge="ui-events", className="mini-btn"),
                    action_button("Cycle Style", action="panel.setting", target=panel_id, payload={"mode": "cycle", "key": "line_style", "values": ["solid", "dash", "dot"]}, bridge="ui-events", className="mini-btn"),
                    action_button("Toggle Markers", action="panel.setting", target=panel_id, payload={"mode": "toggle", "key": "show_markers"}, bridge="ui-events", className="mini-btn"),
                    action_button("Smoothing", action="panel.setting", target=panel_id, payload={"mode": "cycle", "key": "smoothing", "values": ["off", "light", "heavy"]}, bridge="ui-events", className="mini-btn"),
                ],
                className="mini-btn-row",
            ),
            html.Div(f"Smoothing: {settings['smoothing']}", className="panel-muted"),
        ]
    elif kind == "histogram":
        specifics = [
            html.Div("Distribution controls", className="panel-section-title"),
            html.Div(
                [
                    action_button("Bins -", action="panel.setting", target=panel_id, payload={"mode": "bump", "key": "bins", "delta": -2, "minimum": 4, "maximum": 24}, bridge="ui-events", className="mini-btn"),
                    action_button("Bins +", action="panel.setting", target=panel_id, payload={"mode": "bump", "key": "bins", "delta": 2, "minimum": 4, "maximum": 24}, bridge="ui-events", className="mini-btn"),
                    action_button("Normalize", action="panel.setting", target=panel_id, payload={"mode": "toggle", "key": "normalize"}, bridge="ui-events", className="mini-btn"),
                    action_button("Cumulative", action="panel.setting", target=panel_id, payload={"mode": "toggle", "key": "cumulative"}, bridge="ui-events", className="mini-btn"),
                    action_button("Reference Lines", action="panel.setting", target=panel_id, payload={"mode": "toggle", "key": "reference_lines"}, bridge="ui-events", className="mini-btn"),
                ],
                className="mini-btn-row",
            ),
            html.Div(f"Reference lines: {'On' if settings['reference_lines'] else 'Off'}", className="panel-muted"),
        ]
    else:
        specifics = [
            html.Div("Scatter controls", className="panel-section-title"),
            html.Div(
                [
                    action_button("Size -", action="panel.setting", target=panel_id, payload={"mode": "bump", "key": "marker_size", "delta": -1, "minimum": 2, "maximum": 12}, bridge="ui-events", className="mini-btn"),
                    action_button("Size +", action="panel.setting", target=panel_id, payload={"mode": "bump", "key": "marker_size", "delta": 1, "minimum": 2, "maximum": 12}, bridge="ui-events", className="mini-btn"),
                    action_button("Trendline", action="panel.setting", target=panel_id, payload={"mode": "toggle", "key": "trendline"}, bridge="ui-events", className="mini-btn"),
                    action_button("Density", action="panel.setting", target=panel_id, payload={"mode": "toggle", "key": "density_overlay"}, bridge="ui-events", className="mini-btn"),
                    action_button("Palette", action="panel.setting", target=panel_id, payload={"mode": "cycle", "key": "palette", "values": ["blue", "teal", "rose"]}, bridge="ui-events", className="mini-btn"),
                ],
                className="mini-btn-row",
            ),
            html.Div(f"Density overlay: {'On' if settings['density_overlay'] else 'Off'}", className="panel-muted"),
        ]

    return html.Div([html.Div(specifics, className="settings-block"), badges, retype], className="panel-settings")


def render_panel(panel: dict):
    spec = KIND_SPECS[panel["kind"]]
    locked = panel.get("locked", False)
    return html.Div(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(spec["label"], className="panel-type-pill", style={"background": spec["type_color"]}),
                            html.Div(panel["title"], className="panel-title"),
                            html.Div(panel["subtitle"], className="panel-subtitle"),
                            render_badges(panel),
                        ],
                        className="panel-header-copy",
                    ),
                    html.Div(
                        [
                            action_button(
                                "Settings",
                                action="panel.drawer.toggle",
                                target=panel["id"],
                                bridge="ui-events",
                                className=("panel-icon-btn is-active" if panel["expanded"] else "panel-icon-btn"),
                            ),
                            action_button(
                                "Lock" if not locked else "Unlock",
                                action="panel.lock.toggle",
                                target=panel["id"],
                                bridge="ui-events",
                                className=("panel-icon-btn is-active" if locked else "panel-icon-btn"),
                            ),
                            action_button(
                                "Duplicate",
                                action="panel.duplicate",
                                target=panel["id"],
                                bridge="ui-events",
                                className="panel-icon-btn",
                            ),
                            action_button(
                                "Delete",
                                action="panel.delete",
                                target=panel["id"],
                                bridge="ui-events",
                                className="panel-icon-btn danger",
                            ),
                        ],
                        className="panel-header-actions",
                    ),
                ],
                className="panel-header",
            ),
            html.Div(
                [
                    html.Div(icon_for(panel["kind"]), className="panel-preview-graphic"),
                    html.Div(preview_metrics(panel), className="panel-chip-row"),
                ],
                className="panel-preview",
            ),
            html.Div(settings_controls(panel), className="panel-drawer", style={} if panel["expanded"] else {"display": "none"}),
        ],
        className="panel-card",
    )


ASSETS = Path(__file__).with_name("assets")
app = Dash(__name__, assets_folder=str(ASSETS))
configure(app)

app.layout = StableRegion(
    id="shell",
    region_name="shell",
    className="demo-shell",
    children=[
        dcc.Store(id="app-state", data=default_state()),
        EventBridge(id="ui-events"),
        html.Div(
            [
                html.Div(
                    [
                        html.H1("liquid-dash panel playground"),
                        html.P(
                            "Add different panel types, tweak settings inside each card, duplicate, retype, badge, and delete. "
                            "The whole panel surface is rebuilt from state each time."
                        ),
                    ]
                ),
                html.Div(
                    [
                        action_button("Add Time Series", action="panel.add", payload={"kind": "timeseries"}, bridge="ui-events", className="add-panel-btn"),
                        action_button("Add Histogram", action="panel.add", payload={"kind": "histogram"}, bridge="ui-events", className="add-panel-btn"),
                        action_button("Add Scatter", action="panel.add", payload={"kind": "scatter"}, bridge="ui-events", className="add-panel-btn"),
                    ],
                    className="toolbar-row",
                ),
            ],
            className="hero-block",
        ),
        DynamicRegion(
            id="panel-grid",
            bridge="ui-events",
            region_name="panel-grid",
            className="panel-grid",
            children=[],
        ),
    ],
)


@app.callback(
    Output("app-state", "data"),
    Input("ui-events", "data"),
    State("app-state", "data"),
    prevent_initial_call=True,
)
def handle_event(event, state):
    if not event:
        return no_update
    return apply_event(state, event)


@app.callback(Output("panel-grid", "children"), Input("app-state", "data"))
def render_panels(state):
    panels = state.get("panels", [])
    if not panels:
        return [html.Div("No panels left. Add a new one from the toolbar.", className="empty-state")]
    return [render_panel(panel) for panel in panels]


if __name__ == "__main__":
    app.run(debug=True)
