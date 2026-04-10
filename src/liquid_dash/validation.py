from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .exceptions import UnsafeLayoutError
from .types import ValidationIssue, ValidationReport


_INTERACTIVE_NAMES = {
    "Button",
    "A",
    "Input",
    "Textarea",
    "Select",
    "Checklist",
    "RadioItems",
    "Dropdown",
    "Slider",
    "RangeSlider",
    "Tab",
}


def _component_name(component: Any) -> str:
    return getattr(component, "__class__", type(component)).__name__


def _props(component: Any) -> dict[str, Any]:
    if hasattr(component, "to_plotly_json"):
        return component.to_plotly_json().get("props", {})
    return {}


def _children_of(component: Any):
    props = _props(component)
    return props.get("children")


def _iter_children(children: Any):
    if children is None:
        return
    if isinstance(children, (str, int, float, bool)):
        return
    if isinstance(children, Iterable) and not hasattr(children, "to_plotly_json"):
        for child in children:
            yield child
        return
    yield children


def validate_layout(
    layout,
    *,
    strict: bool = False,
    require_bridge_for_actions: bool = True,
    warn_on_interactive_in_dynamic: bool = True,
    return_report: bool = False,
):
    """Validate a Dash layout tree for a few common liquid_dash pitfalls."""
    report = ValidationReport()
    seen_ids: set[str] = set()

    def walk(
        component: Any,
        *,
        in_dynamic: bool,
        inherited_bridge: str | None,
        region_name: str | None,
    ) -> None:
        if component is None or isinstance(component, (str, int, float, bool)):
            return

        props = _props(component)
        component_id = props.get("id")
        name = _component_name(component)

        if isinstance(component_id, str):
            if component_id in seen_ids:
                report.issues.append(
                    ValidationIssue(
                        level="warning",
                        code="duplicate-id",
                        message=f"Duplicate component id found: {component_id}",
                        component_id=component_id,
                        region_name=region_name,
                    )
                )
            seen_ids.add(component_id)

        region_kind = props.get("data-ld-region")
        current_region_name = props.get("data-ld-region-name") or region_name
        current_bridge = props.get("data-ld-default-bridge") or inherited_bridge

        if region_kind == "dynamic":
            in_dynamic = True
        elif region_kind == "stable" and in_dynamic:
            report.issues.append(
                ValidationIssue(
                    level="warning",
                    code="stable-inside-dynamic",
                    message="StableRegion appears inside a dynamic region.",
                    component_id=component_id,
                    region_name=current_region_name,
                )
            )

        action_name = props.get("data-ld-action")
        own_bridge = props.get("data-ld-bridge") or current_bridge
        if action_name is not None:
            if require_bridge_for_actions and not own_bridge:
                report.issues.append(
                    ValidationIssue(
                        level="warning",
                        code="missing-bridge",
                        message="Delegated action element does not have a bridge.",
                        component_id=component_id,
                        region_name=current_region_name,
                    )
                )
            if not str(action_name).strip():
                report.issues.append(
                    ValidationIssue(
                        level="warning",
                        code="empty-action",
                        message="Delegated action element has an empty action.",
                        component_id=component_id,
                        region_name=current_region_name,
                    )
                )

        if in_dynamic and warn_on_interactive_in_dynamic:
            if name in _INTERACTIVE_NAMES and action_name is None:
                report.issues.append(
                    ValidationIssue(
                        level="warning",
                        code="raw-interactive-in-dynamic",
                        message=(
                            "Interactive component found inside DynamicRegion without delegated action metadata."
                        ),
                        component_id=component_id,
                        region_name=current_region_name,
                    )
                )

        for child in _iter_children(_children_of(component)):
            walk(
                child,
                in_dynamic=in_dynamic,
                inherited_bridge=current_bridge,
                region_name=current_region_name,
            )

    walk(layout, in_dynamic=False, inherited_bridge=None, region_name=None)

    if strict and report.issues:
        messages = "\n".join(f"[{i.code}] {i.message}" for i in report.issues)
        raise UnsafeLayoutError(messages)

    if return_report:
        return report
    return None
