"""Dash Relay — client-side event bridge for Dash with a per-action handler registry.

Canonical import:

    import dash_relay as relay

Surface:

    relay.install(app)                               # install the client runtime
    relay.bridge(id="bridge")                        # event sink (a dcc.Store)
    relay.emitter(component, action, ...)            # wrap a component as an event emitter
    relay.emitter(action, ...)                       # reusable emitter factory
    relay.registry(app, state="state_id") -> .handle # receiver-side handler registry
    relay.validate(layout)                           # optional linter
"""

from .app import install
from .bridge import bridge
from .emitter import emitter
from .registry import registry, Registry
from .validation import validate, ValidationIssue, ValidationReport

__all__ = [
    "install",
    "bridge",
    "emitter",
    "registry",
    "Registry",
    "validate",
    "ValidationIssue",
    "ValidationReport",
]
