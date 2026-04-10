from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, TypedDict

IssueLevel = Literal["warning", "error"]


class EventPayload(TypedDict, total=False):
    action: str
    target: str | None
    payload: Any
    source: str | None
    bridge: str | None
    event_type: str | None
    timestamp: float | None


@dataclass(slots=True)
class ValidationIssue:
    level: IssueLevel
    code: str
    message: str
    component_id: str | None = None
    region_name: str | None = None


@dataclass(slots=True)
class ValidationReport:
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return any(issue.level == "error" for issue in self.issues)

    @property
    def has_warnings(self) -> bool:
        return any(issue.level == "warning" for issue in self.issues)
