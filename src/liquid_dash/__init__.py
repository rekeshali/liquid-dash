"""Liquid Dash — minimal client-side event delegation for Dash.

Canonical import:

    import liquid_dash as ld

Surface:

    ld.melt(app)                                # install the runtime
    ld.bridge(id="bridge")                      # event sink (a dcc.Store)
    ld.on(component, action, ...)               # attach event to a component
    ld.on(action, ...)                          # reusable emitter factory
    ld.handler(app, state="state_id") -> .on    # receiver-side registry
    ld.validate(layout)                         # optional linter
"""

from .app import melt
from .bridge import bridge
from .on import on
from .handler import handler, Registry
from .validation import validate, ValidationIssue, ValidationReport

__all__ = [
    "melt",
    "bridge",
    "on",
    "handler",
    "Registry",
    "validate",
    "ValidationIssue",
    "ValidationReport",
]
