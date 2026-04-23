"""Dash Relay — client-side event bridge for Dash.

Public surface:

    import dash_relay as relay
    from dash_relay import Action, Emitter, DEFAULT_BRIDGE
    from dash import Output, State

    relay.install(app)                                       # lifecycle entry
    relay.validate(layout=None, *, strict=False, app=None)   # correctness checks

    Emitter(action=..., bridge=..., target=..., ...)         # template
        .wrap(component, **overrides) -> Component
        .attrs(**overrides) -> dict[str, str]

    @relay.callback(Output(...), Action(...), State(...))    # decorator
    def handler(event, *state_values): ...

The handler signature mirrors plain Dash callbacks: arguments appear in
declaration order with ``Output``s skipped (response targets, not
inputs). Each ``Action`` slot becomes a positional arg receiving the
event envelope dict; each ``State`` slot becomes a positional arg
receiving the current store value.
"""

from .action import Action, DEFAULT_BRIDGE
from .app import install
from .callback import callback
from .emitter import Emitter
from .exceptions import (
    DashRelayError,
    InstallError,
    InvalidEventError,
    UnsafeLayoutError,
)
from .validation import validate, ValidationIssue, ValidationReport

__all__ = [
    "Action",
    "DEFAULT_BRIDGE",
    "DashRelayError",
    "Emitter",
    "InstallError",
    "InvalidEventError",
    "UnsafeLayoutError",
    "ValidationIssue",
    "ValidationReport",
    "callback",
    "install",
    "validate",
]
