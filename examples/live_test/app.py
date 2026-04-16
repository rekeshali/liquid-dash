from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys

from dash import Dash, Input, Output, dcc, html, no_update

# Allow running the demo directly from the source tree before installation.
ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import liquid_dash as ld


BADGE_COLORS = ["#2563eb", "#7c3aed", "#db2777", "#f59e0b", "#059669"]
BADGE_LIBRARY = ["Hot", "QA", "Shared", "Draft", "Pinned"]
KIND_ORDER = ["timeseries", "histogram", "scatter"]

KIND_SPECS = {
    "timeseries": {
        "label": "Time Series",
        "subtitle": "Trace styling and smoothing",
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
        "type_color": "#db2777",
        "settings": {
            "marker_size": 6,
            "trendline": True,
            "density_overlay": False,
            "palette": "blue",
        },
    },
}


# -- State helpers ----------------------------------------------------------

def make_panel_state(index: int, kind: str) -> dict:
    spec = KIND_SPECS[kind]
    badges_seed = {
        "timeseries": [{"label": "Hot", "color": "#2563eb"}],
        "histogram": [{"label": "QA", "color": "#f59e0b"}],
        "scatter": [{"label": "Draft", "color": "#db2777"}],
    }
    return {
        "id": f"panel-{index}",
        "kind": kind,
        "title": f"{spec['label']} {index}",
        "subtitle": spec["subtitle"],
        "expanded": index == 1,
        "locked": False,
        "badges": list(badges_seed.get(kind, [])),
        "settings": deepcopy(spec["settings"]),
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
    i = len(panel["badges"])
    panel["badges"].append({
        "label": BADGE_LIBRARY[i % len(BADGE_LIBRARY)],
        "color": BADGE_COLORS[i % len(BADGE_COLORS)],
    })


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
    elif mode == "bump":
        value = int(settings.get(key, 0))
        delta = int(payload.get("delta", 0))
        minimum = int(payload.get("minimum", 0))
        maximum = int(payload.get("maximum", 99))
        settings[key] = max(minimum, min(maximum, value + delta))
    elif mode == "cycle":
        values = payload.get("values") or []
        settings[key] = cycle_value(settings.get(key), values)


def find_panel(state: dict, panel_id: str | None) -> dict | None:
    return next((p for p in state["panels"] if p["id"] == panel_id), None)


# -- App & handlers ---------------------------------------------------------

ASSETS = Path(__file__).with_name("assets")
app = Dash(__name__, assets_folder=str(ASSETS))
ld.melt(app)

events = ld.handler(app, state="app-state")


@events.on("panel.add")
def _(state, payload, event):
    kind = (payload or {}).get("kind", "timeseries")
    state["panels"].append(make_panel_state(state["next_index"], kind))
    state["next_index"] += 1


@events.on("panel.delete")
def _(state, payload, event):
    tid = event.get("target")
    state["panels"] = [p for p in state["panels"] if p["id"] != tid]


@events.on("panel.duplicate")
def _(state, payload, event):
    panel = find_panel(state, event.get("target"))
    if panel is None:
        return
    clone = deepcopy(panel)
    clone["id"] = f"panel-{state['next_index']}"
    clone["title"] = f"{panel['title']} Copy"
    clone["expanded"] = True
    state["next_index"] += 1
    state["panels"].append(clone)


@events.on("panel.drawer.toggle")
def _(state, payload, event):
    panel = find_panel(state, event.get("target"))
    if panel is not None:
        panel["expanded"] = not bool(panel.get("expanded"))


@events.on("panel.lock.toggle")
def _(state, payload, event):
    panel = find_panel(state, event.get("target"))
    if panel is not None:
        panel["locked"] = not bool(panel.get("locked"))


@events.on("panel.kind.set")
def _(state, payload, event):
    panel = find_panel(state, event.get("target"))
    if panel is not None:
        set_kind(panel, cycle_kind(panel["kind"], (payload or {}).get("kind")))


@events.on("panel.badge.add")
def _(state, payload, event):
    panel = find_panel(state, event.get("target"))
    if panel is not None:
        add_badge(panel)


@events.on("panel.badge.cycle")
def _(state, payload, event):
    panel = find_panel(state, event.get("target"))
    if panel is not None:
        cycle_badge(panel)


@events.on("panel.badge.remove")
def _(state, payload, event):
    panel = find_panel(state, event.get("target"))
    if panel is not None and panel["badges"]:
        panel["badges"].pop()


@events.on("panel.setting")
def _(state, payload, event):
    panel = find_panel(state, event.get("target"))
    if panel is not None and payload:
        apply_setting(panel, payload)


def apply_event(state: dict, event: dict | None) -> dict:
    """Thin wrapper used by tests: dispatches one liquid event through the registry."""
    if not event:
        return state
    result = events.dispatch(event, state)
    return state if result is no_update else result


# -- View helpers -----------------------------------------------------------

def icon_for(kind: str):
    if kind == "timeseries":
        return html.Div(className="preview-wave")
    if kind == "histogram":
        heights = [24, 42, 60, 38, 28, 18, 10]
        return html.Div(
            [html.Div(className="preview-bar", style={"height": f"{h}px"}) for h in heights],
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
        [html.Div(className="preview-dot", style=s) for s in dots],
        className="preview-scatter",
    )


def render_badges(panel: dict):
    badges = panel.get("badges") or []
    if not badges:
        return html.Span("No badges", className="panel-muted")
    return html.Div(
        [html.Span(b["label"], className="panel-badge", style={"background": b["color"]}) for b in badges],
        className="panel-badge-row",
    )


def stat_chip(label: str, value: str):
    return html.Div(
        [html.Div(label, className="panel-chip-label"), html.Div(value, className="panel-chip-value")],
        className="panel-chip",
    )


def preview_metrics(panel: dict):
    s = panel["settings"]
    kind = panel["kind"]
    if kind == "timeseries":
        return [
            stat_chip("Width", str(s["line_width"])),
            stat_chip("Style", s["line_style"]),
            stat_chip("Markers", "On" if s["show_markers"] else "Off"),
        ]
    if kind == "histogram":
        return [
            stat_chip("Bins", str(s["bins"])),
            stat_chip("Normalize", "On" if s["normalize"] else "Off"),
            stat_chip("Cumulative", "On" if s["cumulative"] else "Off"),
        ]
    return [
        stat_chip("Size", str(s["marker_size"])),
        stat_chip("Trend", "On" if s["trendline"] else "Off"),
        stat_chip("Palette", s["palette"]),
    ]


def settings_controls(panel: dict):
    pid = panel["id"]
    kind = panel["kind"]
    settings = panel["settings"]

    retype = html.Div(
        [
            html.Div("Retype panel", className="panel-section-title"),
            html.Div(
                [
                    ld.on(
                        html.Button(
                            KIND_SPECS[k]["label"],
                            className=("mini-btn is-active" if kind == k else "mini-btn"),
                        ),
                        "panel.kind.set", target=pid, payload={"kind": k},
                    )
                    for k in KIND_ORDER
                ],
                className="mini-btn-row",
            ),
        ],
        className="settings-block",
    )

    # One emitter per action, reused across buttons that share the same target.
    badge_add = ld.on("panel.badge.add", target=pid)
    badge_cycle = ld.on("panel.badge.cycle", target=pid)
    badge_remove = ld.on("panel.badge.remove", target=pid)
    setting = ld.on("panel.setting", target=pid)

    badges = html.Div(
        [
            html.Div("Badges", className="panel-section-title"),
            html.Div(
                [
                    badge_add(html.Button("Add", className="mini-btn")),
                    badge_cycle(html.Button("Cycle Color", className="mini-btn")),
                    badge_remove(html.Button("Remove Last", className="mini-btn")),
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
                    setting(html.Button("Width -", className="mini-btn"),
                            payload={"mode": "bump", "key": "line_width", "delta": -1, "minimum": 1, "maximum": 6}),
                    setting(html.Button("Width +", className="mini-btn"),
                            payload={"mode": "bump", "key": "line_width", "delta": 1, "minimum": 1, "maximum": 6}),
                    setting(html.Button("Cycle Style", className="mini-btn"),
                            payload={"mode": "cycle", "key": "line_style", "values": ["solid", "dash", "dot"]}),
                    setting(html.Button("Toggle Markers", className="mini-btn"),
                            payload={"mode": "toggle", "key": "show_markers"}),
                    setting(html.Button("Smoothing", className="mini-btn"),
                            payload={"mode": "cycle", "key": "smoothing", "values": ["off", "light", "heavy"]}),
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
                    setting(html.Button("Bins -", className="mini-btn"),
                            payload={"mode": "bump", "key": "bins", "delta": -2, "minimum": 4, "maximum": 24}),
                    setting(html.Button("Bins +", className="mini-btn"),
                            payload={"mode": "bump", "key": "bins", "delta": 2, "minimum": 4, "maximum": 24}),
                    setting(html.Button("Normalize", className="mini-btn"),
                            payload={"mode": "toggle", "key": "normalize"}),
                    setting(html.Button("Cumulative", className="mini-btn"),
                            payload={"mode": "toggle", "key": "cumulative"}),
                    setting(html.Button("Reference Lines", className="mini-btn"),
                            payload={"mode": "toggle", "key": "reference_lines"}),
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
                    setting(html.Button("Size -", className="mini-btn"),
                            payload={"mode": "bump", "key": "marker_size", "delta": -1, "minimum": 2, "maximum": 12}),
                    setting(html.Button("Size +", className="mini-btn"),
                            payload={"mode": "bump", "key": "marker_size", "delta": 1, "minimum": 2, "maximum": 12}),
                    setting(html.Button("Trendline", className="mini-btn"),
                            payload={"mode": "toggle", "key": "trendline"}),
                    setting(html.Button("Density", className="mini-btn"),
                            payload={"mode": "toggle", "key": "density_overlay"}),
                    setting(html.Button("Palette", className="mini-btn"),
                            payload={"mode": "cycle", "key": "palette", "values": ["blue", "teal", "rose"]}),
                ],
                className="mini-btn-row",
            ),
            html.Div(f"Density overlay: {'On' if settings['density_overlay'] else 'Off'}", className="panel-muted"),
        ]

    return html.Div(
        [html.Div(specifics, className="settings-block"), badges, retype],
        className="panel-settings",
    )


def render_panel(panel: dict):
    spec = KIND_SPECS[panel["kind"]]
    pid = panel["id"]
    locked = panel.get("locked", False)

    header_actions = html.Div(
        [
            ld.on(
                html.Button(
                    "Settings",
                    className=("panel-icon-btn is-active" if panel["expanded"] else "panel-icon-btn"),
                ),
                "panel.drawer.toggle", target=pid,
            ),
            ld.on(
                html.Button(
                    "Lock" if not locked else "Unlock",
                    className=("panel-icon-btn is-active" if locked else "panel-icon-btn"),
                ),
                "panel.lock.toggle", target=pid,
            ),
            ld.on(html.Button("Duplicate", className="panel-icon-btn"),
                  "panel.duplicate", target=pid),
            ld.on(html.Button("Delete", className="panel-icon-btn danger"),
                  "panel.delete", target=pid),
        ],
        className="panel-header-actions",
    )

    return html.Div(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(spec["label"], className="panel-type-pill",
                                     style={"background": spec["type_color"]}),
                            html.Div(panel["title"], className="panel-title"),
                            html.Div(panel["subtitle"], className="panel-subtitle"),
                            render_badges(panel),
                        ],
                        className="panel-header-copy",
                    ),
                    header_actions,
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
            html.Div(
                settings_controls(panel),
                className="panel-drawer",
                style={} if panel["expanded"] else {"display": "none"},
            ),
        ],
        className="panel-card",
    )


# -- Layout -----------------------------------------------------------------

app.layout = html.Div(
    className="demo-shell",
    children=[
        dcc.Store(id="app-state", data=default_state()),
        ld.bridge(),
        html.Div(
            [
                html.Div(
                    [
                        html.H1("liquid-dash panel playground"),
                        html.P(
                            "Add panel types, tweak settings, duplicate, retype, badge, and delete. "
                            "The panel surface is rebuilt from state each time."
                        ),
                    ]
                ),
                html.Div(
                    [
                        ld.on(html.Button("Add Time Series", className="add-panel-btn"),
                              "panel.add", payload={"kind": "timeseries"}),
                        ld.on(html.Button("Add Histogram", className="add-panel-btn"),
                              "panel.add", payload={"kind": "histogram"}),
                        ld.on(html.Button("Add Scatter", className="add-panel-btn"),
                              "panel.add", payload={"kind": "scatter"}),
                    ],
                    className="toolbar-row",
                ),
            ],
            className="hero-block",
        ),
        html.Div(id="panel-grid", className="panel-grid"),
    ],
)


@app.callback(Output("panel-grid", "children"), Input("app-state", "data"))
def render_panels(state):
    panels = (state or {}).get("panels", [])
    if not panels:
        return [html.Div("No panels left. Add a new one from the toolbar.", className="empty-state")]
    return [render_panel(p) for p in panels]


if __name__ == "__main__":
    app.run(debug=True)
