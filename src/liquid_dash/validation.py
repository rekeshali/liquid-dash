from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from .exceptions import UnsafeLayoutError


@dataclass
class ValidationIssue:
    level: str
    code: str
    message: str
    component_id: str | None = None


@dataclass
class ValidationReport:
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.issues


def _component_name(component: Any) -> str:
    return type(component).__name__


def _props(component: Any) -> dict[str, Any]:
    if hasattr(component, "to_plotly_json"):
        return component.to_plotly_json().get("props", {})
    return {}


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


def validate(layout, *, strict: bool = False) -> ValidationReport:
    """Walk a Dash layout for common liquid-dash mistakes.

    Reports:
      - duplicate-id: two components share an id
      - empty-action: an element has data-ld-action set to empty string
      - missing-bridge: an element targets a bridge id that is not present
        as a dcc.Store in the layout
      - empty-event: an element has data-ld-event set to empty string

    If `strict=True`, raises UnsafeLayoutError when any issue is found.
    """
    report = ValidationReport()
    seen_ids: set[str] = set()
    store_ids: set[str] = set()
    scopes: set[str] = set()
    action_targets: list[tuple[str, str | None]] = []  # (bridge_or_scope, component_id)

    def walk(component: Any):
        if component is None or isinstance(component, (str, int, float, bool)):
            return

        props = _props(component)
        cid = props.get("id")

        if isinstance(cid, str):
            if cid in seen_ids:
                report.issues.append(
                    ValidationIssue(
                        level="warning",
                        code="duplicate-id",
                        message=f"Duplicate component id: {cid}",
                        component_id=cid,
                    )
                )
            seen_ids.add(cid)

        if _component_name(component) == "Store" and isinstance(cid, str):
            store_ids.add(cid)

        scope = props.get("data-ld-default-bridge")
        if scope:
            scopes.add(scope)

        action = props.get("data-ld-action")
        if action is not None:
            if not str(action).strip():
                report.issues.append(
                    ValidationIssue(
                        level="warning",
                        code="empty-action",
                        message="Element has empty data-ld-action.",
                        component_id=cid,
                    )
                )
            own_bridge = props.get("data-ld-bridge") or ""
            action_targets.append((own_bridge, cid))

            ev = props.get("data-ld-event")
            if ev is not None and not str(ev).strip():
                report.issues.append(
                    ValidationIssue(
                        level="warning",
                        code="empty-event",
                        message="Element has empty data-ld-event.",
                        component_id=cid,
                    )
                )

        for child in _iter_children(props.get("children")):
            walk(child)

    walk(layout)

    # Check bridges referenced by actions exist as Stores
    reachable_bridges = store_ids | scopes
    for own_bridge, cid in action_targets:
        target = own_bridge if own_bridge else None
        if target and target not in reachable_bridges:
            report.issues.append(
                ValidationIssue(
                    level="warning",
                    code="missing-bridge",
                    message=(
                        f"Action targets bridge '{target}' but no dcc.Store "
                        "with that id was found in the layout."
                    ),
                    component_id=cid,
                )
            )
        elif not target and not reachable_bridges:
            report.issues.append(
                ValidationIssue(
                    level="warning",
                    code="missing-bridge",
                    message="Action has no bridge and no bridge is present in the layout.",
                    component_id=cid,
                )
            )

    if strict and report.issues:
        lines = "\n".join(f"[{i.code}] {i.message}" for i in report.issues)
        raise UnsafeLayoutError(lines)

    return report
