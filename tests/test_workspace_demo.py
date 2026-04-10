from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


EXAMPLE_PATH = Path(__file__).resolve().parents[1] / "examples" / "workspace_demo" / "app.py"


def _load_demo_module():
    spec = spec_from_file_location("liquid_dash_workspace_demo", EXAMPLE_PATH)
    module = module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module



def _panel_ids(state):
    ids = []
    for folder in state["folders"]:
        for tab in folder["tabs"]:
            ids.extend(panel["id"] for panel in tab["panels"])
    return ids



def _tab_ids(state):
    ids = []
    for folder in state["folders"]:
        ids.extend(tab["id"] for tab in folder["tabs"])
    return ids



def test_workspace_like_nested_navigation_without_caps():
    demo = _load_demo_module()
    state = demo.default_canvas_state()
    editor = demo.default_editor_state()

    assert len(state["folders"]) == 2
    assert demo.active_folder(state)["title"] == "Workspace 1"
    assert demo.active_tab(state)["title"] == "Overview"

    state, editor = demo.reduce_ui_event(state, editor, {"action": "folder.add"})
    state, editor = demo.reduce_ui_event(state, editor, {"action": "folder.add"})
    assert len(state["folders"]) == 4
    assert demo.active_folder(state)["id"] == "folder-4"

    state, editor = demo.reduce_ui_event(state, editor, {"action": "folder.rename.open", "target": "folder-4"})
    assert editor["entity_type"] == "folder"
    state, editor = demo.apply_editor_form(state, editor, {"title": "Research"})
    assert demo.find_folder(state, "folder-4")["title"] == "Research"

    state, editor = demo.reduce_ui_event(state, editor, {"action": "tab.add"})
    state, editor = demo.reduce_ui_event(state, editor, {"action": "tab.add"})
    folder = demo.active_folder(state)
    assert folder is not None
    assert len(folder["tabs"]) == 3
    newest_tab_id = folder["active_tab_id"]

    state, editor = demo.reduce_ui_event(state, editor, {"action": "tab.rename.open", "target": newest_tab_id})
    assert editor["entity_type"] == "tab"
    state, editor = demo.apply_editor_form(state, editor, {"title": "Comparisons"})
    assert demo.find_tab(state, newest_tab_id)["title"] == "Comparisons"

    state, editor = demo.reduce_ui_event(state, editor, {"action": "panel.add", "payload": {"kind": "scatter"}})
    state, editor = demo.reduce_ui_event(state, editor, {"action": "panel.add", "payload": {"kind": "histogram"}})

    target_tab = demo.active_tab(state)
    assert target_tab is not None
    assert len(target_tab["panels"]) == 2
    target_panel_id = target_tab["panels"][-1]["id"]

    state, editor = demo.reduce_ui_event(state, editor, {"action": "panel.settings.open", "target": target_panel_id})
    assert editor["entity_type"] == "panel"
    state, editor = demo.reduce_ui_event(state, editor, {"action": "panel.badge.add", "target": target_panel_id})
    state, editor = demo.reduce_ui_event(
        state,
        editor,
        {"action": "panel.badge.cycle", "target": target_panel_id, "payload": {"index": 0}},
    )

    state, editor = demo.apply_editor_form(
        state,
        editor,
        {
            "title": "Scatter Study",
            "kind": "scatter",
            "mode": "subplot",
            "filter_variable": "temperature",
            "filter_operator": "<=",
            "filter_value": 42,
            "filter_invert": ["invert"],
            "line_width": 2,
            "line_style": "solid",
            "show_markers": [],
            "smoothing": "off",
            "bins": 12,
            "normalize": [],
            "cumulative": [],
            "reference_lines": [],
            "marker_size": 12,
            "trendline": [],
            "density_overlay": ["density_overlay"],
            "palette": "forest",
            "rows": 2,
            "cols": 3,
            "share_x": [],
            "share_y": ["share_y"],
        },
    )

    panel = demo.find_panel(state, target_panel_id)
    assert panel is not None
    assert panel["title"] == "Scatter Study"
    assert panel["kind"] == "scatter"
    assert panel["active_mode"] == "subplot"
    assert panel["filter"]["variable"] == "temperature"
    assert panel["subplot"]["rows"] == 2
    assert panel["subplot"]["share_y"] is True
    assert len(panel["badges"]) >= 2

    state, editor = demo.reduce_ui_event(state, editor, {"action": "panel.duplicate", "target": target_panel_id})
    duplicated = demo.active_tab(state)["panels"][-1]
    assert duplicated["title"].endswith("Copy")
    assert duplicated["id"] != target_panel_id

    prior_first_folder_tab = demo.find_folder(state, "folder-1")["tabs"][1]["id"]
    state, editor = demo.reduce_ui_event(state, editor, {"action": "folder.activate", "target": "folder-1"})
    state, editor = demo.reduce_ui_event(state, editor, {"action": "tab.activate", "target": prior_first_folder_tab})
    assert demo.active_folder(state)["id"] == "folder-1"
    assert demo.active_tab(state)["id"] == prior_first_folder_tab
    state, editor = demo.reduce_ui_event(state, editor, {"action": "panel.add", "payload": {"kind": "timeseries"}})
    assert len(demo.active_tab(state)["panels"]) == 2

    state, editor = demo.reduce_ui_event(state, editor, {"action": "folder.activate", "target": "folder-4"})
    state, editor = demo.reduce_ui_event(state, editor, {"action": "tab.delete", "target": newest_tab_id})
    assert demo.find_tab(state, newest_tab_id) is None
    state, editor = demo.reduce_ui_event(state, editor, {"action": "folder.delete", "target": "folder-3"})
    assert demo.find_folder(state, "folder-3") is None

    panel_ids = _panel_ids(state)
    tab_ids = _tab_ids(state)
    folder_ids = [folder["id"] for folder in state["folders"]]
    assert len(panel_ids) == len(set(panel_ids))
    assert len(tab_ids) == len(set(tab_ids))
    assert len(folder_ids) == len(set(folder_ids))
    assert len(state["folders"]) >= 1
    assert demo.active_folder(state) is not None
    assert demo.active_tab(state) is not None



def test_workspace_demo_has_small_fixed_callback_graph():
    demo = _load_demo_module()
    app = demo.build_app()

    assert len(app.callback_map) == 5

    state = demo.default_canvas_state()
    editor = demo.default_editor_state()

    for _ in range(12):
        state, editor = demo.reduce_ui_event(state, editor, {"action": "folder.add"})
        for _ in range(2):
            state, editor = demo.reduce_ui_event(state, editor, {"action": "tab.add"})
        for tab in demo.active_folder(state)["tabs"]:
            state, editor = demo.reduce_ui_event(state, editor, {"action": "tab.activate", "target": tab["id"]})
            for kind in ["timeseries", "histogram", "scatter", "timeseries"]:
                state, editor = demo.reduce_ui_event(state, editor, {"action": "panel.add", "payload": {"kind": kind}})

    folder_count = len(state["folders"])
    tab_count = sum(len(folder["tabs"]) for folder in state["folders"])
    panel_count = sum(len(tab["panels"]) for folder in state["folders"] for tab in folder["tabs"])

    assert folder_count == 14
    assert tab_count >= 38
    assert panel_count >= 52
    assert len(app.callback_map) == 5
