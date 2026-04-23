"""``relay.validate()`` — correctness-only checks for relay-using layouts.

Scope:
  * Pre-install duplicate-handler detection.
  * Unreachable-handler detection (handler on a bridge no emitter
    targets).
  * In strict mode with a layout, missing-handler emitter detection
    (emitter targets a bridge with no registered handler).

Performance is deployment-specific (state union size, wire cost) and
out of scope.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from .callback import _PENDING_CALLBACKS
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


def _walk_emitters(layout) -> tuple[set[str], set[tuple[str, str]]]:
    """Return (bridges_targeted, (bridge, action) pairs) found in the layout."""
    bridges: set[str] = set()
    pairs: set[tuple[str, str]] = set()

    def walk(component):
        if component is None or isinstance(component, (str, int, float, bool)):
            return
        props = _props(component)
        action = props.get("data-relay-action")
        bridge = props.get("data-relay-bridge")
        if action and bridge:
            bridges.add(bridge)
            pairs.add((bridge, str(action)))
        for child in _iter_children(props.get("children")):
            walk(child)

    walk(layout)
    return bridges, pairs


def _handler_keys(app: Any | None) -> set[tuple[str, str]]:
    """Collect (bridge, action) keys from app handlers (post-install) or pool."""
    keys: set[tuple[str, str]] = set()
    if app is not None and getattr(app, "_dash_relay_handlers", None) is not None:
        for h in app._dash_relay_handlers:
            for a in h.actions:
                keys.add((a.bridge_id, a.name))
    else:
        for h in _PENDING_CALLBACKS:
            for a in h.actions:
                keys.add((a.bridge_id, a.name))
    return keys


def validate(
    layout=None,
    *,
    strict: bool = False,
    app: Any = None,
) -> ValidationReport:
    """Walk handlers (and optionally a layout) for relay-correctness issues.

    Codes:

      * ``duplicate-handler`` — two handlers register the same
        ``(bridge, action)`` key. Same condition that causes
        ``InstallError`` at ``install()`` time; this is the pre-flight.
      * ``unreachable-handler`` — a handler exists for a bridge that no
        emitter in the supplied layout writes to. Only reported when a
        layout is given.
      * ``missing-handler`` — an emitter targets a ``(bridge, action)``
        key that no handler is registered for. Only reported when a
        layout is given.

    With ``strict=True``, raises ``UnsafeLayoutError`` if any issues are
    found.

    The handler set comes from the ``app`` argument's installed
    handlers when given (post-install); otherwise from the global
    pending pool (pre-install).
    """
    report = ValidationReport()

    # Duplicate-handler check across the registered set.
    seen: dict[tuple[str, str], int] = {}
    handlers = (
        list(getattr(app, "_dash_relay_handlers", []))
        if app is not None and getattr(app, "_dash_relay_handlers", None) is not None
        else list(_PENDING_CALLBACKS)
    )
    for h in handlers:
        for a in h.actions:
            key = (a.bridge_id, a.name)
            seen[key] = seen.get(key, 0) + 1
    for (bridge, action_name), count in sorted(seen.items()):
        if count > 1:
            report.issues.append(
                ValidationIssue(
                    level="error",
                    code="duplicate-handler",
                    message=(
                        f"{count} handlers registered for "
                        f"(bridge={bridge!r}, action={action_name!r}). "
                        "Each (bridge, action) key must have at most one handler."
                    ),
                )
            )

    if layout is not None:
        emitter_bridges, emitter_pairs = _walk_emitters(layout)
        handler_bridges = {bridge for (bridge, _name) in seen.keys()}
        handler_pairs = set(seen.keys())

        for bridge in sorted(handler_bridges - emitter_bridges):
            report.issues.append(
                ValidationIssue(
                    level="warning",
                    code="unreachable-handler",
                    message=(
                        f"Handler(s) registered for bridge {bridge!r} but no "
                        "emitter in the layout targets that bridge — handler "
                        "will never fire."
                    ),
                )
            )
        for bridge, action_name in sorted(emitter_pairs - handler_pairs):
            report.issues.append(
                ValidationIssue(
                    level="warning",
                    code="missing-handler",
                    message=(
                        f"Emitter on bridge {bridge!r} fires action "
                        f"{action_name!r} but no handler is registered — "
                        "click is a no-op."
                    ),
                )
            )

    if strict and report.issues:
        lines = "\n".join(f"[{i.code}] {i.message}" for i in report.issues)
        raise UnsafeLayoutError(lines)

    return report
