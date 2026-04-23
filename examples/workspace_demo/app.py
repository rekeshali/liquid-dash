from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys
from typing import Any, Callable

from dash import Dash, Input, Output, State, dcc, html, no_update

# Allow running the demo directly from the source tree before installation.
ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import dash_relay as relay
from dash_relay import Action, Emitter


ASSETS_DIR = Path(__file__).resolve().parent / "assets"
UI_EVENT_BRIDGE = "ui-events"
CANVAS_STORE = "canvas-store"
EDITOR_STORE = "editor-store"

PANEL_KINDS = ["timeseries", "histogram", "scatter"]
PANEL_MODES = ["filter", "style", "subplot", "badges"]
BADGE_LIBRARY = ["Hot", "QA", "Shared", "Pinned", "Draft", "VIP"]
BADGE_COLORS = ["#2563eb", "#7c3aed", "#db2777", "#f59e0b", "#059669", "#0f172a"]

KIND_META = {
    "timeseries": {
        "label": "Time Series",
        "subtitle": "Trace styling and smoothing",
        "accent": "#2563eb",
        "summary": "Good for time-history traces and threshold overlays.",
        "style_defaults": {"line_width": 2, "line_style": "solid", "show_markers": False, "smoothing": "off"},
    },
    "histogram": {
        "label": "Histogram",
        "subtitle": "Bins, normalization, and cumulative views",
        "accent": "#f59e0b",
        "summary": "Good for distributions and envelope checks.",
        "style_defaults": {"bins": 12, "normalize": False, "cumulative": False, "reference_lines": False},
    },
    "scatter": {
        "label": "Scatter",
        "subtitle": "Marker sizing and trendline overlays",
        "accent": "#db2777",
        "summary": "Good for pairwise sensitivity and cluster views.",
        "style_defaults": {"marker_size": 7, "trendline": True, "density_overlay": False, "palette": "blue"},
    },
}


# --- Internal helper: convenience wrapper for action buttons ---------------

def _btn(label, action, *, target=None, payload=None, className=None, style=None, title=None):
    """Build an html.Button carrying relay attrs targeted at UI_EVENT_BRIDGE."""
    kwargs: dict[str, Any] = {}
    if className is not None:
        kwargs["className"] = className
    if style is not None:
        kwargs["style"] = style
    if title is not None:
        kwargs["title"] = title
    template = Emitter(action=action, bridge=UI_EVENT_BRIDGE, target=target, payload=payload)
    return template.wrap(html.Button(label, **kwargs))


# --- State factories -------------------------------------------------------

def default_filter_controls() -> dict[str, Any]:
    return {"variable": "altitude", "operator": ">", "value": 10000, "invert": False}


def default_subplot_controls() -> dict[str, Any]:
    return {"rows": 1, "cols": 1, "share_x": True, "share_y": False}


def default_style_controls(kind: str) -> dict[str, Any]:
    return deepcopy(KIND_META[kind]["style_defaults"])


def make_panel(index: int, kind: str) -> dict[str, Any]:
    meta = KIND_META[kind]
    badge_label = BADGE_LIBRARY[(index - 1) % len(BADGE_LIBRARY)]
    badge_color = BADGE_COLORS[(index - 1) % len(BADGE_COLORS)]
    return {
        "id": f"panel-{index}",
        "kind": kind,
        "title": f"{meta['label']} {index}",
        "subtitle": meta["subtitle"],
        "locked": False,
        "linked": index == 1,
        "active_mode": "style",
        "filter": default_filter_controls(),
        "style": default_style_controls(kind),
        "subplot": default_subplot_controls(),
        "badges": [{"label": badge_label, "color": badge_color}],
    }


def make_tab(index: int, title: str | None = None, panels: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {"id": f"tab-{index}", "title": title or f"Canvas {index}", "panels": panels or []}


def make_folder(index: int, tabs: list[dict[str, Any]], title: str | None = None,
                active_tab_id: str | None = None) -> dict[str, Any]:
    return {
        "id": f"folder-{index}",
        "title": title or f"Folder {index}",
        "tabs": tabs,
        "active_tab_id": active_tab_id or (tabs[0]["id"] if tabs else None),
    }


def default_canvas_state() -> dict[str, Any]:
    tab1 = make_tab(1, "Overview", [make_panel(1, "timeseries"), make_panel(2, "histogram")])
    tab2 = make_tab(2, "Comparisons", [make_panel(3, "scatter")])
    tab3 = make_tab(3, "Deep Dive", [make_panel(4, "timeseries")])
    folder1 = make_folder(1, [tab1, tab2], title="Workspace 1", active_tab_id=tab1["id"])
    folder2 = make_folder(2, [tab3], title="Workspace 2", active_tab_id=tab3["id"])
    return {
        "next_folder_index": 3,
        "next_tab_index": 4,
        "next_panel_index": 5,
        "active_folder_id": folder1["id"],
        "folders": [folder1, folder2],
    }


def default_editor_state() -> dict[str, Any]:
    return {"is_open": False, "entity_type": None, "entity_id": None, "context": {}, "draft": None}


# --- Lookups ---------------------------------------------------------------

def active_folder(state: dict[str, Any] | None) -> dict[str, Any] | None:
    data = state or default_canvas_state()
    folder_id = data.get("active_folder_id")
    return next((f for f in data.get("folders", []) if f.get("id") == folder_id), None)


def active_tab(state: dict[str, Any] | None) -> dict[str, Any] | None:
    folder = active_folder(state)
    if folder is None:
        return None
    tab_id = folder.get("active_tab_id")
    return next((t for t in folder.get("tabs", []) if t.get("id") == tab_id), None)


def find_folder(state: dict[str, Any], folder_id: str | None) -> dict[str, Any] | None:
    if not folder_id:
        return None
    return next((f for f in state.get("folders", []) if f.get("id") == folder_id), None)


def locate_tab(state: dict[str, Any], tab_id: str | None):
    if not tab_id:
        return None, None
    for folder in state.get("folders", []):
        for tab in folder.get("tabs", []):
            if tab.get("id") == tab_id:
                return folder, tab
    return None, None


def find_tab(state: dict[str, Any], tab_id: str | None) -> dict[str, Any] | None:
    _folder, tab = locate_tab(state, tab_id)
    return tab


def locate_panel(state: dict[str, Any], panel_id: str | None):
    if not panel_id:
        return None, None, None
    for folder in state.get("folders", []):
        for tab in folder.get("tabs", []):
            for panel in tab.get("panels", []):
                if panel.get("id") == panel_id:
                    return folder, tab, panel
    return None, None, None


def find_panel(state: dict[str, Any], panel_id: str | None) -> dict[str, Any] | None:
    _folder, _tab, panel = locate_panel(state, panel_id)
    return panel


# --- Pure helpers ----------------------------------------------------------

def cycle_value(current: Any, values: list[Any]) -> Any:
    if not values:
        return current
    if current not in values:
        return values[0]
    idx = values.index(current)
    return values[(idx + 1) % len(values)]


def clone_panel(panel: dict[str, Any], next_index: int) -> dict[str, Any]:
    copied = deepcopy(panel)
    copied["id"] = f"panel-{next_index}"
    copied["title"] = f"{panel['title']} Copy"
    copied["linked"] = False
    return copied


def add_badge(panel: dict[str, Any]) -> None:
    idx = len(panel.get("badges", []))
    panel.setdefault("badges", []).append({
        "label": BADGE_LIBRARY[idx % len(BADGE_LIBRARY)],
        "color": BADGE_COLORS[idx % len(BADGE_COLORS)],
    })


def copy_folder_to_editor(folder: dict[str, Any]) -> dict[str, Any]:
    return {
        "is_open": True, "entity_type": "folder", "entity_id": folder["id"],
        "context": {"folder_id": folder["id"]}, "draft": {"title": folder["title"]},
    }


def copy_tab_to_editor(folder: dict[str, Any], tab: dict[str, Any]) -> dict[str, Any]:
    return {
        "is_open": True, "entity_type": "tab", "entity_id": tab["id"],
        "context": {"folder_id": folder["id"], "tab_id": tab["id"]},
        "draft": {"title": tab["title"]},
    }


def copy_panel_to_editor(folder: dict[str, Any], tab: dict[str, Any], panel: dict[str, Any]) -> dict[str, Any]:
    return {
        "is_open": True, "entity_type": "panel", "entity_id": panel["id"],
        "context": {"folder_id": folder["id"], "tab_id": tab["id"], "panel_id": panel["id"]},
        "draft": deepcopy(panel),
    }


def close_editor_state() -> dict[str, Any]:
    return default_editor_state()


def editor_targets_folder(editor: dict[str, Any], folder_id: str) -> bool:
    return editor.get("context", {}).get("folder_id") == folder_id


def editor_targets_tab(editor: dict[str, Any], tab_id: str) -> bool:
    return editor.get("context", {}).get("tab_id") == tab_id


def editor_targets_panel(editor: dict[str, Any], panel_id: str) -> bool:
    return editor.get("context", {}).get("panel_id") == panel_id


def ensure_folder_has_tab(state: dict[str, Any], folder: dict[str, Any]) -> None:
    if folder.get("tabs"):
        if not folder.get("active_tab_id") or folder["active_tab_id"] not in {t["id"] for t in folder["tabs"]}:
            folder["active_tab_id"] = folder["tabs"][0]["id"]
        return
    new_tab = make_tab(state["next_tab_index"], title="Canvas")
    state["next_tab_index"] += 1
    folder["tabs"] = [new_tab]
    folder["active_tab_id"] = new_tab["id"]


def ensure_state_has_folder(state: dict[str, Any]) -> None:
    if state.get("folders"):
        if state.get("active_folder_id") not in {f["id"] for f in state["folders"]}:
            state["active_folder_id"] = state["folders"][0]["id"]
        return
    new_tab = make_tab(state["next_tab_index"], title="Canvas")
    state["next_tab_index"] += 1
    new_folder = make_folder(state["next_folder_index"], [new_tab], title="Folder")
    state["next_folder_index"] += 1
    state["folders"] = [new_folder]
    state["active_folder_id"] = new_folder["id"]


def active_ids_text(state: dict[str, Any]) -> str:
    folder = active_folder(state)
    tab = active_tab(state)
    if folder is None or tab is None:
        return "No active folder"
    return f"{folder['title']} / {tab['title']}"


# --- Action handlers (one function per UI action) --------------------------
#
# Handlers take (states, payload, event) where states is a tuple
# (canvas, editor). They may mutate canvas/editor in place and return None,
# or return an explicit (canvas, editor) tuple when they need to reassign
# one of the state variables (e.g. wholesale replacing editor).
#
# Every handler is registered in `_ACTIONS` at import time so it can be
# dispatched both by the @relay.callback wrappers in `build_app()` and by the
# pure-function `reduce_ui_event()` wrapper used in tests.

_ACTIONS: dict[str, Callable] = {}


def _action(name: str) -> Callable[[Callable], Callable]:
    def deco(fn: Callable) -> Callable:
        _ACTIONS[name] = fn
        return fn
    return deco


@_action("folder.add")
def _(states, payload, event):
    canvas, _editor = states
    new_tab = make_tab(canvas["next_tab_index"], title="Canvas")
    canvas["next_tab_index"] += 1
    new_folder = make_folder(
        canvas["next_folder_index"], [new_tab],
        title=f"Folder {canvas['next_folder_index']}",
    )
    canvas["next_folder_index"] += 1
    canvas["folders"].append(new_folder)
    canvas["active_folder_id"] = new_folder["id"]


@_action("folder.activate")
def _(states, payload, event):
    canvas, _editor = states
    folder = find_folder(canvas, event.get("target"))
    if folder is not None:
        canvas["active_folder_id"] = folder["id"]
        ensure_folder_has_tab(canvas, folder)


@_action("folder.delete")
def _(states, payload, event):
    canvas, editor = states
    target = event.get("target")
    if find_folder(canvas, target) is None:
        return
    canvas["folders"] = [f for f in canvas["folders"] if f["id"] != target]
    ensure_state_has_folder(canvas)
    if editor_targets_folder(editor, target):
        return canvas, close_editor_state()


@_action("folder.rename.open")
def _(states, payload, event):
    canvas, editor = states
    folder = find_folder(canvas, event.get("target"))
    if folder is None:
        return
    return canvas, copy_folder_to_editor(folder)


@_action("tab.add")
def _(states, payload, event):
    canvas, _editor = states
    folder = active_folder(canvas)
    if folder is None:
        ensure_state_has_folder(canvas)
        folder = active_folder(canvas)
    if folder is None:
        return
    new_tab = make_tab(canvas["next_tab_index"], title=f"Canvas {canvas['next_tab_index']}")
    canvas["next_tab_index"] += 1
    folder["tabs"].append(new_tab)
    folder["active_tab_id"] = new_tab["id"]


@_action("tab.activate")
def _(states, payload, event):
    canvas, _editor = states
    folder, tab = locate_tab(canvas, event.get("target"))
    if folder is not None and tab is not None:
        canvas["active_folder_id"] = folder["id"]
        folder["active_tab_id"] = tab["id"]


@_action("tab.delete")
def _(states, payload, event):
    canvas, editor = states
    folder, tab = locate_tab(canvas, event.get("target"))
    if folder is None or tab is None:
        return
    folder["tabs"] = [t for t in folder["tabs"] if t["id"] != tab["id"]]
    ensure_folder_has_tab(canvas, folder)
    if editor_targets_tab(editor, tab["id"]):
        return canvas, close_editor_state()


@_action("tab.rename.open")
def _(states, payload, event):
    canvas, editor = states
    folder, tab = locate_tab(canvas, event.get("target"))
    if folder is None or tab is None:
        return
    return canvas, copy_tab_to_editor(folder, tab)


@_action("panel.add")
def _(states, payload, event):
    canvas, _editor = states
    current_tab = active_tab(canvas)
    if current_tab is None:
        return
    kind = (payload or {}).get("kind", "timeseries")
    if kind not in KIND_META:
        kind = "timeseries"
    current_tab["panels"].append(make_panel(canvas["next_panel_index"], kind))
    canvas["next_panel_index"] += 1


@_action("panel.delete")
def _(states, payload, event):
    canvas, editor = states
    _folder, tab, panel = locate_panel(canvas, event.get("target"))
    if tab is None or panel is None:
        return
    tab["panels"] = [p for p in tab["panels"] if p["id"] != panel["id"]]
    if editor_targets_panel(editor, panel["id"]):
        return canvas, close_editor_state()


@_action("panel.duplicate")
def _(states, payload, event):
    canvas, _editor = states
    _folder, tab, panel = locate_panel(canvas, event.get("target"))
    if tab is None or panel is None:
        return
    tab["panels"].append(clone_panel(panel, canvas["next_panel_index"]))
    canvas["next_panel_index"] += 1


@_action("panel.lock.toggle")
def _(states, payload, event):
    canvas, _editor = states
    panel = find_panel(canvas, event.get("target"))
    if panel is not None:
        panel["locked"] = not bool(panel.get("locked"))


@_action("panel.link.toggle")
def _(states, payload, event):
    canvas, _editor = states
    panel = find_panel(canvas, event.get("target"))
    if panel is not None:
        panel["linked"] = not bool(panel.get("linked"))


@_action("panel.mode.set")
def _(states, payload, event):
    canvas, editor = states
    panel = find_panel(canvas, event.get("target"))
    if panel is None:
        return
    mode = (payload or {}).get("mode")
    if mode in PANEL_MODES:
        panel["active_mode"] = mode
        if editor_targets_panel(editor, panel["id"]) and editor.get("draft"):
            editor["draft"]["active_mode"] = mode


@_action("panel.badge.add")
def _(states, payload, event):
    canvas, editor = states
    panel = find_panel(canvas, event.get("target"))
    if panel is None:
        return
    add_badge(panel)
    if editor_targets_panel(editor, panel["id"]) and editor.get("draft"):
        add_badge(editor["draft"])


@_action("panel.badge.remove")
def _(states, payload, event):
    canvas, editor = states
    panel = find_panel(canvas, event.get("target"))
    if panel is None:
        return
    bidx = int((payload or {}).get("index", -1))
    if 0 <= bidx < len(panel.get("badges", [])):
        panel["badges"].pop(bidx)
    if editor_targets_panel(editor, panel["id"]) and editor.get("draft"):
        if 0 <= bidx < len(editor["draft"].get("badges", [])):
            editor["draft"]["badges"].pop(bidx)


@_action("panel.badge.cycle")
def _(states, payload, event):
    canvas, editor = states
    panel = find_panel(canvas, event.get("target"))
    if panel is None:
        return
    bidx = int((payload or {}).get("index", -1))
    if 0 <= bidx < len(panel.get("badges", [])):
        badge = panel["badges"][bidx]
        badge["color"] = cycle_value(badge.get("color"), BADGE_COLORS)
    if editor_targets_panel(editor, panel["id"]) and editor.get("draft"):
        if 0 <= bidx < len(editor["draft"].get("badges", [])):
            badge = editor["draft"]["badges"][bidx]
            badge["color"] = cycle_value(badge.get("color"), BADGE_COLORS)


@_action("panel.settings.open")
def _(states, payload, event):
    canvas, _editor = states
    folder, tab, panel = locate_panel(canvas, event.get("target"))
    if folder is None or tab is None or panel is None:
        return
    return canvas, copy_panel_to_editor(folder, tab, panel)


# --- Pure-function dispatcher used by tests --------------------------------
#
# Tests call `demo.reduce_ui_event(canvas, editor, event)` directly without
# constructing a Dash app. This wrapper preserves that interface by going
# through the same `_ACTIONS` table the @relay.callback dispatchers use.


def reduce_ui_event(
    canvas_state: dict[str, Any] | None,
    editor_state: dict[str, Any] | None,
    event: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    canvas = deepcopy(canvas_state) if canvas_state is not None else default_canvas_state()
    editor = deepcopy(editor_state) if editor_state is not None else default_editor_state()

    if not event or "action" not in event:
        return canvas, editor

    fn = _ACTIONS.get(event["action"])
    if fn is None:
        return canvas, editor

    payload = event.get("payload") or {}
    result = fn((canvas, editor), payload, event)
    if result is None:
        return canvas, editor
    new_canvas, new_editor = result
    return new_canvas, new_editor


# --- Editor form helpers ---------------------------------------------------

def editor_form_from_state(editor_state: dict[str, Any] | None) -> dict[str, Any]:
    editor = editor_state or {}
    draft = editor.get("draft") or {}
    entity_type = editor.get("entity_type")
    if not editor.get("is_open"):
        entity_type = None

    if entity_type != "panel":
        title_value = draft.get("title", "")
        entity_label = {"folder": "Folder", "tab": "Tab"}.get(entity_type, "Nothing selected")
        return {
            "is_open": bool(editor.get("is_open")),
            "entity_type": entity_type,
            "entity_label": entity_label,
            "entity_title": title_value or "No selection",
            "entity_id": editor.get("entity_id") or "—",
            "title": title_value,
            "kind": "timeseries",
            "mode": "style",
            "filter_variable": "altitude", "filter_operator": ">",
            "filter_value": 10000, "filter_invert": [],
            "line_width": 2, "line_style": "solid", "show_markers": [], "smoothing": "off",
            "bins": 12, "normalize": [], "cumulative": [], "reference_lines": [],
            "marker_size": 7, "trendline": ["trendline"], "density_overlay": [], "palette": "blue",
            "rows": 1, "cols": 1, "share_x": ["share_x"], "share_y": [],
            "badges": [],
        }

    filter_state = draft["filter"]
    style_state = draft["style"]
    subplot_state = draft["subplot"]
    return {
        "is_open": True,
        "entity_type": "panel",
        "entity_label": "Panel",
        "entity_title": draft["title"],
        "entity_id": editor.get("entity_id") or draft.get("id", "—"),
        "title": draft["title"],
        "kind": draft["kind"],
        "mode": draft.get("active_mode", "style"),
        "filter_variable": filter_state.get("variable", "altitude"),
        "filter_operator": filter_state.get("operator", ">"),
        "filter_value": filter_state.get("value", 10000),
        "filter_invert": ["invert"] if filter_state.get("invert") else [],
        "line_width": style_state.get("line_width", 2),
        "line_style": style_state.get("line_style", "solid"),
        "show_markers": ["markers"] if style_state.get("show_markers") else [],
        "smoothing": style_state.get("smoothing", "off"),
        "bins": style_state.get("bins", 12),
        "normalize": ["normalize"] if style_state.get("normalize") else [],
        "cumulative": ["cumulative"] if style_state.get("cumulative") else [],
        "reference_lines": ["reference_lines"] if style_state.get("reference_lines") else [],
        "marker_size": style_state.get("marker_size", 7),
        "trendline": ["trendline"] if style_state.get("trendline", True) else [],
        "density_overlay": ["density_overlay"] if style_state.get("density_overlay") else [],
        "palette": style_state.get("palette", "blue"),
        "rows": subplot_state.get("rows", 1),
        "cols": subplot_state.get("cols", 1),
        "share_x": ["share_x"] if subplot_state.get("share_x") else [],
        "share_y": ["share_y"] if subplot_state.get("share_y") else [],
        "badges": deepcopy(draft.get("badges", [])),
    }


def build_style_controls(kind: str, form: dict[str, Any]) -> dict[str, Any]:
    if kind == "timeseries":
        return {
            "line_width": int(form["line_width"] or 2),
            "line_style": form["line_style"] or "solid",
            "show_markers": "markers" in (form["show_markers"] or []),
            "smoothing": form["smoothing"] or "off",
        }
    if kind == "histogram":
        return {
            "bins": int(form["bins"] or 12),
            "normalize": "normalize" in (form["normalize"] or []),
            "cumulative": "cumulative" in (form["cumulative"] or []),
            "reference_lines": "reference_lines" in (form["reference_lines"] or []),
        }
    return {
        "marker_size": int(form["marker_size"] or 7),
        "trendline": "trendline" in (form["trendline"] or []),
        "density_overlay": "density_overlay" in (form["density_overlay"] or []),
        "palette": form["palette"] or "blue",
    }


def build_form_payload(
    title, kind, mode,
    filter_variable, filter_operator, filter_value, filter_invert,
    line_width, line_style, show_markers, smoothing,
    bins, normalize, cumulative, reference_lines,
    marker_size, trendline, density_overlay, palette,
    rows, cols, share_x, share_y,
) -> dict[str, Any]:
    return {
        "title": title, "kind": kind, "mode": mode,
        "filter_variable": filter_variable, "filter_operator": filter_operator,
        "filter_value": filter_value, "filter_invert": filter_invert,
        "line_width": line_width, "line_style": line_style,
        "show_markers": show_markers, "smoothing": smoothing,
        "bins": bins, "normalize": normalize, "cumulative": cumulative,
        "reference_lines": reference_lines,
        "marker_size": marker_size, "trendline": trendline,
        "density_overlay": density_overlay, "palette": palette,
        "rows": rows, "cols": cols, "share_x": share_x, "share_y": share_y,
    }


def apply_editor_form(
    canvas_state: dict[str, Any] | None,
    editor_state: dict[str, Any] | None,
    form: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    state = deepcopy(canvas_state or default_canvas_state())
    editor = deepcopy(editor_state or default_editor_state())
    entity_type = editor.get("entity_type")
    entity_id = editor.get("entity_id")

    if entity_type == "folder":
        folder = find_folder(state, entity_id)
        if folder is None:
            return state, close_editor_state()
        folder["title"] = form.get("title") or folder["title"]
        return state, copy_folder_to_editor(folder)

    if entity_type == "tab":
        folder, tab = locate_tab(state, entity_id)
        if folder is None or tab is None:
            return state, close_editor_state()
        tab["title"] = form.get("title") or tab["title"]
        return state, copy_tab_to_editor(folder, tab)

    if entity_type != "panel":
        return state, editor

    folder, tab, panel = locate_panel(state, entity_id)
    if folder is None or tab is None or panel is None:
        return state, close_editor_state()

    kind = form.get("kind", panel["kind"])
    if kind not in KIND_META:
        kind = panel["kind"]
    panel["kind"] = kind
    panel["title"] = form.get("title") or panel["title"]
    panel["subtitle"] = KIND_META[kind]["subtitle"]
    panel["active_mode"] = form.get("mode") if form.get("mode") in PANEL_MODES else panel.get("active_mode", "style")
    panel["filter"] = {
        "variable": form.get("filter_variable") or "altitude",
        "operator": form.get("filter_operator") or ">",
        "value": int(form.get("filter_value") or 0),
        "invert": "invert" in (form.get("filter_invert") or []),
    }
    panel["style"] = build_style_controls(kind, form)
    panel["subplot"] = {
        "rows": int(form.get("rows") or 1),
        "cols": int(form.get("cols") or 1),
        "share_x": "share_x" in (form.get("share_x") or []),
        "share_y": "share_y" in (form.get("share_y") or []),
    }
    return state, copy_panel_to_editor(folder, tab, panel)


# --- View helpers ----------------------------------------------------------

def preview_for(panel: dict[str, Any]):
    kind = panel["kind"]
    if kind == "timeseries":
        return html.Div(className="proof-preview proof-preview-wave")
    if kind == "histogram":
        heights = [18, 42, 56, 38, 26, 16]
        return html.Div(
            [html.Div(className="proof-preview-bar", style={"height": f"{h}px"}) for h in heights],
            className="proof-preview proof-preview-bars",
        )
    dots = [
        {"left": "10%", "top": "65%"},
        {"left": "26%", "top": "42%"},
        {"left": "44%", "top": "58%"},
        {"left": "60%", "top": "28%"},
        {"left": "76%", "top": "48%"},
    ]
    return html.Div(
        [html.Div(className="proof-preview-dot", style=s) for s in dots],
        className="proof-preview proof-preview-scatter",
    )


def badge_row(panel: dict[str, Any]):
    badges = panel.get("badges", [])
    if not badges:
        return html.Div("No badges", className="proof-muted")
    return html.Div(
        [
            _btn(
                badge["label"], "panel.badge.cycle",
                target=panel["id"], payload={"index": idx},
                className="proof-badge", style={"background": badge["color"]},
                title="Cycle badge color",
            )
            for idx, badge in enumerate(badges)
        ],
        className="proof-badge-row",
    )


def panel_summary(panel: dict[str, Any]) -> html.Ul:
    filter_state = panel["filter"]
    style_state = panel["style"]
    subplot_state = panel["subplot"]
    if panel["kind"] == "timeseries":
        style_text = f"{style_state['line_style']} / width {style_state['line_width']} / markers {'on' if style_state['show_markers'] else 'off'}"
    elif panel["kind"] == "histogram":
        style_text = f"{style_state['bins']} bins / normalize {'on' if style_state['normalize'] else 'off'}"
    else:
        style_text = f"marker {style_state['marker_size']} / trendline {'on' if style_state['trendline'] else 'off'}"
    return html.Ul(
        [
            html.Li(f"Filter: {filter_state['variable']} {filter_state['operator']} {filter_state['value']}",
                    className="proof-summary-item"),
            html.Li(f"Style: {style_text}", className="proof-summary-item"),
            html.Li(
                f"Subplot: {subplot_state['rows']}x{subplot_state['cols']} / share X {'on' if subplot_state['share_x'] else 'off'}",
                className="proof-summary-item",
            ),
        ],
        className="proof-summary-list",
    )


def render_panel_card(panel: dict[str, Any]):
    meta = KIND_META[panel["kind"]]
    pid = panel["id"]

    mode_buttons = html.Div(
        [
            _btn(
                mode.title(), "panel.mode.set",
                target=pid, payload={"mode": mode},
                className=("proof-pill is-active" if panel.get("active_mode") == mode else "proof-pill"),
            )
            for mode in PANEL_MODES
        ],
        className="proof-pill-row",
    )

    return html.Div(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(meta["label"], className="proof-type-chip", style={"background": meta["accent"]}),
                            html.Div(panel["title"], className="proof-panel-title"),
                            html.Div(panel["subtitle"], className="proof-panel-subtitle"),
                        ],
                        className="proof-panel-heading",
                    ),
                    html.Div(
                        [
                            _btn("Lock", "panel.lock.toggle", target=pid,
                                 className="proof-mini-btn" + (" is-active" if panel.get("locked") else "")),
                            _btn("Link", "panel.link.toggle", target=pid,
                                 className="proof-mini-btn" + (" is-active" if panel.get("linked") else "")),
                            _btn("Settings", "panel.settings.open", target=pid, className="proof-mini-btn"),
                            _btn("Duplicate", "panel.duplicate", target=pid, className="proof-mini-btn"),
                            _btn("Delete", "panel.delete", target=pid, className="proof-mini-btn proof-danger"),
                        ],
                        className="proof-panel-actions",
                    ),
                ],
                className="proof-panel-topbar",
            ),
            preview_for(panel),
            html.Div(meta["summary"], className="proof-panel-blurb"),
            mode_buttons,
            html.Div(
                [
                    html.Div("Badges", className="proof-section-label"),
                    badge_row(panel),
                    html.Div(
                        [
                            _btn("Add Badge", "panel.badge.add", target=pid, className="proof-inline-btn"),
                            _btn(
                                "Remove Last", "panel.badge.remove",
                                target=pid, payload={"index": max(len(panel.get('badges', [])) - 1, 0)},
                                className="proof-inline-btn",
                            ),
                        ],
                        className="proof-inline-btn-row",
                    ),
                ],
                className="proof-card-section",
            ),
            html.Div([html.Div("Current Settings", className="proof-section-label"), panel_summary(panel)],
                     className="proof-card-section"),
            html.Div(f"Panel ID: {panel['id']}", className="proof-panel-id"),
        ],
        className="proof-panel-card",
    )


def render_folder_strip(canvas_state: dict[str, Any] | None):
    state = canvas_state or default_canvas_state()
    active_id = state.get("active_folder_id")
    chips = []
    for folder in state.get("folders", []):
        chips.append(
            html.Div(
                [
                    _btn(
                        f"{folder['title']} ({len(folder.get('tabs', []))})",
                        "folder.activate", target=folder["id"],
                        className=("proof-chip is-active" if folder["id"] == active_id else "proof-chip"),
                    ),
                    _btn("Rename", "folder.rename.open", target=folder["id"], className="proof-inline-btn"),
                    _btn("Delete", "folder.delete", target=folder["id"],
                         className="proof-inline-btn proof-danger"),
                ],
                className="proof-chip-group",
            )
        )
    return chips


def render_tab_strip(canvas_state: dict[str, Any] | None):
    state = canvas_state or default_canvas_state()
    folder = active_folder(state)
    if folder is None:
        return [html.Div("No tabs", className="proof-muted")]
    chips = []
    for tab in folder.get("tabs", []):
        panel_count = len(tab.get("panels", []))
        chips.append(
            html.Div(
                [
                    _btn(
                        f"{tab['title']} ({panel_count})",
                        "tab.activate", target=tab["id"],
                        className=("proof-pill is-active" if tab["id"] == folder.get("active_tab_id") else "proof-pill"),
                    ),
                    _btn("Rename", "tab.rename.open", target=tab["id"], className="proof-inline-btn"),
                    _btn("Delete", "tab.delete", target=tab["id"],
                         className="proof-inline-btn proof-danger"),
                ],
                className="proof-chip-group",
            )
        )
    return chips


def render_panel_grid(canvas_state: dict[str, Any] | None):
    tab = active_tab(canvas_state)
    if tab is None:
        return [html.Div("No active tab", className="proof-muted")]
    if not tab.get("panels"):
        return [html.Div("No panels in this tab yet. Add one from the toolbar.", className="proof-empty-surface")]
    return [render_panel_card(panel) for panel in tab.get("panels", [])]


def render_editor_badges(editor_state: dict[str, Any] | None):
    editor = editor_state or {}
    if editor.get("entity_type") != "panel":
        return html.Div("Badges are only available for panel editing.", className="proof-muted")
    draft = editor.get("draft") or {}
    panel_id = editor.get("entity_id")
    badges = draft.get("badges", [])
    if not panel_id:
        return html.Div("Select a panel to edit badges.", className="proof-muted")
    if not badges:
        return html.Div(
            [
                html.Div("No badges yet.", className="proof-muted"),
                _btn("Add badge", "panel.badge.add", target=panel_id, className="proof-inline-btn"),
            ],
            className="proof-editor-badge-empty",
        )
    rows = []
    for idx, badge in enumerate(badges):
        rows.append(
            html.Div(
                [
                    html.Span(badge["label"], className="proof-badge", style={"background": badge["color"]}),
                    _btn("Cycle", "panel.badge.cycle",
                         target=panel_id, payload={"index": idx}, className="proof-inline-btn"),
                    _btn("Remove", "panel.badge.remove",
                         target=panel_id, payload={"index": idx}, className="proof-inline-btn proof-danger"),
                ],
                className="proof-editor-badge-row",
            )
        )
    rows.append(_btn("Add badge", "panel.badge.add", target=panel_id, className="proof-inline-btn"))
    return html.Div(rows, className="proof-editor-badges")


def build_render_summary(state: dict[str, Any] | None) -> tuple[str, str]:
    data = state or default_canvas_state()
    folder = active_folder(data)
    tab = active_tab(data)
    folder_count = len(data.get("folders", []))
    tab_count = len(folder.get("tabs", [])) if folder else 0
    panel_count = len(tab.get("panels", [])) if tab else 0
    title = active_ids_text(data)
    detail = f"{folder_count} folders · {tab_count} tabs in active folder · {panel_count} panels in active tab"
    return title, detail


# --- App construction ------------------------------------------------------

def _register_handlers() -> None:
    """Wire each pure action function in _ACTIONS into @relay.callback.

    Pure functions keep their (states_tuple, payload, event) signature so
    the test-side reduce_ui_event helper can drive them directly. The
    @relay.callback wrappers below adapt to the relay handler signature
    (event, canvas, editor) and the (canvas, editor) tuple return shape.
    """
    for action_name, pure_fn in _ACTIONS.items():
        _make_handler(action_name, pure_fn)


def _make_handler(action_name, pure_fn):
    @relay.callback(
        Output(CANVAS_STORE, "data"),
        Output(EDITOR_STORE, "data"),
        Action(action_name, bridge=UI_EVENT_BRIDGE),
        State(CANVAS_STORE, "data"),
        State(EDITOR_STORE, "data"),
    )
    def _wrapped(event, canvas, editor):
        canvas = deepcopy(canvas) if canvas is not None else default_canvas_state()
        editor = deepcopy(editor) if editor is not None else default_editor_state()
        payload = event.get("payload") or {}
        result = pure_fn((canvas, editor), payload, event)
        if result is None:
            return canvas, editor
        return result
    return _wrapped


def build_app() -> Dash:
    app = Dash(__name__, assets_folder=str(ASSETS_DIR))

    toolbar = html.Div(
        [
            _btn("Add Folder", "folder.add", className="proof-toolbar-btn"),
            _btn("Add Tab", "tab.add", className="proof-toolbar-btn"),
            _btn("Add Time Series", "panel.add", payload={"kind": "timeseries"},
                 className="proof-toolbar-btn"),
            _btn("Add Histogram", "panel.add", payload={"kind": "histogram"},
                 className="proof-toolbar-btn"),
            _btn("Add Scatter", "panel.add", payload={"kind": "scatter"},
                 className="proof-toolbar-btn"),
        ],
        className="proof-toolbar",
    )

    app.layout = html.Div(
        id="proof-shell",
        className="proof-shell",
        children=[
            dcc.Store(id=CANVAS_STORE, data=default_canvas_state()),
            dcc.Store(id=EDITOR_STORE, data=default_editor_state()),
            html.Div(
                [
                    html.Div(
                        [
                            html.Div("Dash Relay demo", className="proof-kicker"),
                            html.H1("Folders, tabs, and panels with a fixed callback graph",
                                    className="proof-title"),
                            html.P(
                                "Add, rename, delete, and switch between folders, tabs, and panels "
                                "while keeping the callback graph small and predictable.",
                                className="proof-subtitle",
                            ),
                        ]
                    ),
                    toolbar,
                    html.Div(
                        [
                            html.Div(id="workspace-title", className="proof-workspace-title"),
                            html.Div(id="workspace-detail", className="proof-subtitle"),
                        ],
                        className="proof-location-card",
                    ),
                    html.Div(id="folder-strip", className="proof-strip"),
                    html.Div(id="tab-strip", className="proof-strip"),
                ],
                className="proof-header",
            ),
            html.Div(
                [
                    html.Div(id="panel-grid", className="proof-grid"),
                    html.Div(
                        id="editor-shell",
                        className="proof-editor-shell",
                        children=[
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            html.Div("Shared editor", className="proof-kicker"),
                                            html.H2(id="editor-panel-label", className="proof-editor-title"),
                                            html.Div(id="editor-panel-id", className="proof-panel-id"),
                                        ]
                                    ),
                                    html.Button("Close", id="editor-close", className="proof-mini-btn"),
                                ],
                                className="proof-editor-topbar",
                            ),
                            html.Div(id="editor-help", className="proof-subtitle"),
                            html.Div(
                                [
                                    html.Label(id="title-label", children="Title", className="proof-label"),
                                    dcc.Input(id="edit-title", type="text", className="proof-input"),
                                ],
                                className="proof-field",
                            ),
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            html.Label("Panel kind", className="proof-label"),
                                            dcc.Dropdown(
                                                id="edit-kind",
                                                options=[{"label": KIND_META[k]["label"], "value": k} for k in PANEL_KINDS],
                                                clearable=False,
                                            ),
                                        ],
                                        className="proof-field",
                                    ),
                                    html.Div(
                                        [
                                            html.Label("Active mode", className="proof-label"),
                                            dcc.Dropdown(
                                                id="edit-mode",
                                                options=[{"label": m.title(), "value": m} for m in PANEL_MODES],
                                                clearable=False,
                                            ),
                                        ],
                                        className="proof-field",
                                    ),
                                ],
                                id="panel-meta-row",
                                className="proof-two-col",
                            ),
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            html.H3("Filter", className="proof-section-header"),
                                            html.Div([html.Label("Variable", className="proof-label"),
                                                      dcc.Dropdown(id="filter-variable",
                                                                   options=[{"label": x, "value": x}
                                                                            for x in ["altitude", "velocity", "temperature", "dynamic_pressure"]],
                                                                   clearable=False)],
                                                     className="proof-field"),
                                            html.Div([html.Label("Operator", className="proof-label"),
                                                      dcc.Dropdown(id="filter-operator",
                                                                   options=[{"label": x, "value": x}
                                                                            for x in [">", ">=", "<", "<=", "=="]],
                                                                   clearable=False)],
                                                     className="proof-field"),
                                            html.Div([html.Label("Value", className="proof-label"),
                                                      dcc.Input(id="filter-value", type="number",
                                                                className="proof-input")],
                                                     className="proof-field"),
                                            dcc.Checklist(id="filter-invert",
                                                          options=[{"label": "Invert selection", "value": "invert"}],
                                                          className="proof-checklist"),
                                        ],
                                        id="section-filter",
                                        className="proof-editor-section",
                                    ),
                                    html.Div(
                                        [
                                            html.H3("Style", className="proof-section-header"),
                                            html.Div(
                                                [
                                                    html.Div(
                                                        [
                                                            html.Label("Line width", className="proof-label"),
                                                            dcc.Input(id="line-width", type="number", className="proof-input"),
                                                            html.Label("Line style", className="proof-label"),
                                                            dcc.Dropdown(id="line-style",
                                                                         options=[{"label": x.title(), "value": x}
                                                                                  for x in ["solid", "dash", "dot"]],
                                                                         clearable=False),
                                                            dcc.Checklist(id="show-markers",
                                                                          options=[{"label": "Show markers", "value": "markers"}],
                                                                          className="proof-checklist"),
                                                            html.Label("Smoothing", className="proof-label"),
                                                            dcc.Dropdown(id="smoothing",
                                                                         options=[{"label": x.title(), "value": x}
                                                                                  for x in ["off", "low", "medium", "high"]],
                                                                         clearable=False),
                                                        ],
                                                        id="style-timeseries", className="proof-kind-subsection",
                                                    ),
                                                    html.Div(
                                                        [
                                                            html.Label("Bins", className="proof-label"),
                                                            dcc.Input(id="bins", type="number", className="proof-input"),
                                                            dcc.Checklist(id="normalize",
                                                                          options=[{"label": "Normalize", "value": "normalize"}],
                                                                          className="proof-checklist"),
                                                            dcc.Checklist(id="cumulative",
                                                                          options=[{"label": "Cumulative", "value": "cumulative"}],
                                                                          className="proof-checklist"),
                                                            dcc.Checklist(id="reference-lines",
                                                                          options=[{"label": "Reference lines", "value": "reference_lines"}],
                                                                          className="proof-checklist"),
                                                        ],
                                                        id="style-histogram", className="proof-kind-subsection",
                                                    ),
                                                    html.Div(
                                                        [
                                                            html.Label("Marker size", className="proof-label"),
                                                            dcc.Input(id="marker-size", type="number", className="proof-input"),
                                                            dcc.Checklist(id="trendline",
                                                                          options=[{"label": "Trendline", "value": "trendline"}],
                                                                          className="proof-checklist"),
                                                            dcc.Checklist(id="density-overlay",
                                                                          options=[{"label": "Density overlay", "value": "density_overlay"}],
                                                                          className="proof-checklist"),
                                                            html.Label("Palette", className="proof-label"),
                                                            dcc.Dropdown(id="palette",
                                                                         options=[{"label": x.title(), "value": x}
                                                                                  for x in ["blue", "sunset", "forest", "mono"]],
                                                                         clearable=False),
                                                        ],
                                                        id="style-scatter", className="proof-kind-subsection",
                                                    ),
                                                ]
                                            ),
                                        ],
                                        id="section-style",
                                        className="proof-editor-section",
                                    ),
                                    html.Div(
                                        [
                                            html.H3("Subplot", className="proof-section-header"),
                                            html.Div(
                                                [
                                                    html.Div([html.Label("Rows", className="proof-label"),
                                                              dcc.Input(id="subplot-rows", type="number", className="proof-input")],
                                                             className="proof-field"),
                                                    html.Div([html.Label("Cols", className="proof-label"),
                                                              dcc.Input(id="subplot-cols", type="number", className="proof-input")],
                                                             className="proof-field"),
                                                ],
                                                className="proof-two-col",
                                            ),
                                            dcc.Checklist(id="share-x",
                                                          options=[{"label": "Share X", "value": "share_x"}],
                                                          className="proof-checklist"),
                                            dcc.Checklist(id="share-y",
                                                          options=[{"label": "Share Y", "value": "share_y"}],
                                                          className="proof-checklist"),
                                        ],
                                        id="section-subplot",
                                        className="proof-editor-section",
                                    ),
                                    html.Div([html.H3("Badges", className="proof-section-header"),
                                              html.Div(id="editor-badges")],
                                             id="section-badges", className="proof-editor-section"),
                                ],
                                className="proof-editor-body",
                            ),
                            html.Div([html.Button("Apply changes", id="editor-apply", className="proof-toolbar-btn")],
                                     className="proof-editor-footer"),
                        ],
                    ),
                ],
                className="proof-main",
            ),
        ],
    )

    # Callback 1: UI events → (canvas, editor).
    # Each pure action in _ACTIONS becomes a @relay.callback entry; the
    # install() call at the end of build_app() consumes the pool and
    # registers one dispatcher Dash callback for UI_EVENT_BRIDGE.
    _register_handlers()

    # Callback 2: render workspace chrome
    @app.callback(
        Output("workspace-title", "children"),
        Output("workspace-detail", "children"),
        Output("folder-strip", "children"),
        Output("tab-strip", "children"),
        Output("panel-grid", "children"),
        Input(CANVAS_STORE, "data"),
    )
    def render_workspace(canvas_state):
        title, detail = build_render_summary(canvas_state)
        return title, detail, render_folder_strip(canvas_state), render_tab_strip(canvas_state), render_panel_grid(canvas_state)

    # Callback 3: hydrate shared editor form from editor state
    @app.callback(
        Output("editor-shell", "style"),
        Output("editor-panel-label", "children"),
        Output("editor-panel-id", "children"),
        Output("editor-help", "children"),
        Output("title-label", "children"),
        Output("edit-title", "value"),
        Output("panel-meta-row", "style"),
        Output("edit-kind", "value"),
        Output("edit-mode", "value"),
        Output("section-filter", "style"),
        Output("section-style", "style"),
        Output("section-subplot", "style"),
        Output("section-badges", "style"),
        Output("style-timeseries", "style"),
        Output("style-histogram", "style"),
        Output("style-scatter", "style"),
        Output("filter-variable", "value"),
        Output("filter-operator", "value"),
        Output("filter-value", "value"),
        Output("filter-invert", "value"),
        Output("line-width", "value"),
        Output("line-style", "value"),
        Output("show-markers", "value"),
        Output("smoothing", "value"),
        Output("bins", "value"),
        Output("normalize", "value"),
        Output("cumulative", "value"),
        Output("reference-lines", "value"),
        Output("marker-size", "value"),
        Output("trendline", "value"),
        Output("density-overlay", "value"),
        Output("palette", "value"),
        Output("subplot-rows", "value"),
        Output("subplot-cols", "value"),
        Output("share-x", "value"),
        Output("share-y", "value"),
        Output("editor-badges", "children"),
        Input(EDITOR_STORE, "data"),
    )
    def hydrate_shared_editor(editor_state):
        form = editor_form_from_state(editor_state)
        entity_type = form["entity_type"]
        is_panel = entity_type == "panel"
        mode = form["mode"]
        kind = form["kind"]
        title_label = {None: "Title", "folder": "Folder title", "tab": "Tab title", "panel": "Panel title"}[entity_type]
        help_text = {
            None: "Open a folder, tab, or panel from the dynamic surface to edit it here.",
            "folder": "Folders are lightweight containers for a set of tabs.",
            "tab": "Tabs belong to the active folder and own their own panel collections.",
            "panel": "This one shared editor handles all detailed panel configuration for any panel ID.",
        }[entity_type]
        return (
            {"display": "block"} if form["is_open"] else {"display": "none"},
            f"Editing {form['entity_label']}",
            f"ID: {form['entity_id']}",
            help_text,
            title_label,
            form["title"],
            {"display": "grid"} if is_panel else {"display": "none"},
            form["kind"],
            form["mode"],
            {"display": "block" if is_panel and mode == "filter" else "none"},
            {"display": "block" if is_panel and mode == "style" else "none"},
            {"display": "block" if is_panel and mode == "subplot" else "none"},
            {"display": "block" if is_panel and mode == "badges" else "none"},
            {"display": "block" if is_panel and kind == "timeseries" else "none"},
            {"display": "block" if is_panel and kind == "histogram" else "none"},
            {"display": "block" if is_panel and kind == "scatter" else "none"},
            form["filter_variable"], form["filter_operator"], form["filter_value"], form["filter_invert"],
            form["line_width"], form["line_style"], form["show_markers"], form["smoothing"],
            form["bins"], form["normalize"], form["cumulative"], form["reference_lines"],
            form["marker_size"], form["trendline"], form["density_overlay"], form["palette"],
            form["rows"], form["cols"], form["share_x"], form["share_y"],
            render_editor_badges(editor_state),
        )

    # Callback 4: apply editor form
    @app.callback(
        Output(CANVAS_STORE, "data", allow_duplicate=True),
        Output(EDITOR_STORE, "data", allow_duplicate=True),
        Input("editor-apply", "n_clicks"),
        State("edit-title", "value"), State("edit-kind", "value"), State("edit-mode", "value"),
        State("filter-variable", "value"), State("filter-operator", "value"),
        State("filter-value", "value"), State("filter-invert", "value"),
        State("line-width", "value"), State("line-style", "value"),
        State("show-markers", "value"), State("smoothing", "value"),
        State("bins", "value"), State("normalize", "value"),
        State("cumulative", "value"), State("reference-lines", "value"),
        State("marker-size", "value"), State("trendline", "value"),
        State("density-overlay", "value"), State("palette", "value"),
        State("subplot-rows", "value"), State("subplot-cols", "value"),
        State("share-x", "value"), State("share-y", "value"),
        State(CANVAS_STORE, "data"), State(EDITOR_STORE, "data"),
        prevent_initial_call=True,
    )
    def apply_editor(
        _n_clicks,
        title, kind, mode,
        filter_variable, filter_operator, filter_value, filter_invert,
        line_width, line_style, show_markers, smoothing,
        bins, normalize, cumulative, reference_lines,
        marker_size, trendline, density_overlay, palette,
        rows, cols, share_x, share_y,
        canvas_state, editor_state,
    ):
        if not (editor_state or {}).get("is_open"):
            return no_update, no_update
        form = build_form_payload(
            title, kind, mode,
            filter_variable, filter_operator, filter_value, filter_invert,
            line_width, line_style, show_markers, smoothing,
            bins, normalize, cumulative, reference_lines,
            marker_size, trendline, density_overlay, palette,
            rows, cols, share_x, share_y,
        )
        return apply_editor_form(canvas_state, editor_state, form)

    # Callback 5: close editor
    @app.callback(
        Output(EDITOR_STORE, "data", allow_duplicate=True),
        Input("editor-close", "n_clicks"),
        prevent_initial_call=True,
    )
    def close_editor(_n_clicks):
        return close_editor_state()

    # Drains the handler pool and registers one dispatcher per bridge.
    # Must run AFTER all @relay.callback decorators have populated the pool.
    relay.install(app)

    return app


app = build_app()


if __name__ == "__main__":
    app.run(debug=True)
