from __future__ import annotations

from typing import Any

from dash import html

from ._util import drop_none


def _tag_factory(tag: str):
    constructor = getattr(html, tag.capitalize(), None)
    if constructor is None:
        raise ValueError(f"Unsupported HTML tag: {tag}")
    return constructor


def StableRegion(
    *,
    id: str | None = None,
    children: Any = None,
    tag: str = "div",
    className: str | None = None,
    style: dict | None = None,
    role: str | None = None,
    region_name: str | None = None,
    **kwargs,
):
    """Semantic wrapper for a stable layout region."""
    constructor = _tag_factory(tag)
    return constructor(
        children=children,
        **drop_none({
            "id": id,
            "className": className,
            "style": style,
            "role": role,
            "data-ld-region": "stable",
            "data-ld-region-name": region_name or "",
            **kwargs,
        }),
    )


def DynamicRegion(
    *,
    id: str | None = None,
    children: Any = None,
    tag: str = "div",
    className: str | None = None,
    style: dict | None = None,
    role: str | None = None,
    region_name: str | None = None,
    bridge: str | None = None,
    strict: bool = False,
    **kwargs,
):
    """Semantic wrapper for a volatile layout region."""
    constructor = _tag_factory(tag)
    return constructor(
        children=children,
        **drop_none({
            "id": id,
            "className": className,
            "style": style,
            "role": role,
            "data-ld-region": "dynamic",
            "data-ld-region-name": region_name or "",
            "data-ld-default-bridge": bridge or "",
            "data-ld-strict": "true" if strict else "false",
            **kwargs,
        }),
    )
