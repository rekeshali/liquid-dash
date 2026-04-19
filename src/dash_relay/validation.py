from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from .exceptions import UnsafeLayoutError


@dataclass
class ValidationIssue:
    """One finding from ``relay.validate()``.

    Fields:
        level: "warning" today (reserved for future "error" / "info").
        code: stable short identifier (e.g. "duplicate-id",
            "orphan-emitter") — safe to match against in tooling.
        message: human-readable description of the issue.
        component_id: id of the offending component when known. ``None``
            for issues that aren't tied to a specific component
            (e.g. orphan-handler, which points at a registered handler
            with no corresponding emitter).
    """

    level: str
    code: str
    message: str
    component_id: str | None = None


@dataclass
class ValidationReport:
    """Result of a ``relay.validate()`` run.

    ``report.issues`` is the list of findings (empty on a clean layout).
    ``report.ok`` is a convenience property — ``True`` iff ``issues`` is
    empty — so the common "fail the build on any issue" path stays terse.
    """

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


def validate(layout, *, strict: bool = False, registry: Any = None) -> ValidationReport:
    """Walk a Dash layout for common Dash Relay mistakes.

    Reports:
      - duplicate-id: two components share an id
      - empty-action: an element has data-relay-action set to empty string
      - missing-bridge: an element targets a bridge id that is not present
        as a dcc.Store in the layout
      - empty-event: an element has data-relay-on set to empty string
      - orphan-emitter: an emitter's action has no matching handler on the
        supplied registry (a user click that lands nowhere).
        Only reported when ``registry=`` is provided.
      - orphan-handler: a registered handler has no emitter in the layout
        using its action name. Only reported when ``registry=`` is provided.
        Note: this may be a false positive for apps that render emitters
        dynamically inside callbacks — the initial layout won't contain them.

    Pass ``registry=events`` (the ``Registry`` returned by
    ``relay.registry(app, state=...)``) to enable the orphan checks. The
    registry only needs to expose ``.actions() -> Iterable[str]``.

    If `strict=True`, raises UnsafeLayoutError when any issue is found.
    """
    report = ValidationReport()
    seen_ids: set[str] = set()
    store_ids: set[str] = set()
    scopes: set[str] = set()
    action_targets: list[tuple[str, str | None]] = []  # (bridge_or_scope, component_id)
    emitter_actions: set[str] = set()

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

        scope = props.get("data-relay-default-bridge")
        if scope:
            scopes.add(scope)

        action = props.get("data-relay-action")
        if action is not None:
            action_str = str(action)
            if not action_str.strip():
                report.issues.append(
                    ValidationIssue(
                        level="warning",
                        code="empty-action",
                        message="Element has empty data-relay-action.",
                        component_id=cid,
                    )
                )
            else:
                emitter_actions.add(action_str)
            own_bridge = props.get("data-relay-bridge") or ""
            action_targets.append((own_bridge, cid))

            ev = props.get("data-relay-on")
            if ev is not None and not str(ev).strip():
                report.issues.append(
                    ValidationIssue(
                        level="warning",
                        code="empty-event",
                        message="Element has empty data-relay-on.",
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

    # Cross-check emitter actions against the registry's handlers, if one
    # was supplied. Action names are string-linked between emitter and
    # handler; this catches typos on either side at load time.
    if registry is not None:
        try:
            handler_actions = frozenset(registry.actions())
        except AttributeError as exc:
            raise TypeError(
                "validate(registry=...) requires an object with an "
                ".actions() method returning the registered action names."
            ) from exc
        orphan_emitters = emitter_actions - handler_actions
        orphan_handlers = handler_actions - emitter_actions
        for action in sorted(orphan_emitters):
            report.issues.append(
                ValidationIssue(
                    level="warning",
                    code="orphan-emitter",
                    message=(
                        f"Emitter action '{action}' has no matching handler "
                        "on the registry — clicking this element is a no-op."
                    ),
                )
            )
        for action in sorted(orphan_handlers):
            report.issues.append(
                ValidationIssue(
                    level="warning",
                    code="orphan-handler",
                    message=(
                        f"Handler registered for '{action}' but no emitter "
                        "in the layout uses this action. (If emitters are "
                        "rendered dynamically from callbacks, this is expected.)"
                    ),
                )
            )

    if strict and report.issues:
        lines = "\n".join(f"[{i.code}] {i.message}" for i in report.issues)
        raise UnsafeLayoutError(lines)

    return report
