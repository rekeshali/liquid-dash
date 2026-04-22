"""Dash Relay — client-side event bridge for Dash with action-based dispatch.

Canonical import:

    import dash_relay as relay
    from dash_relay import Action

Surface:

    relay.install(app)                                        # install runtime + wire dispatchers
    relay.bridge(id="bridge")                                 # event sink (a dcc.Store)
    relay.emitter(component, action, ...)                     # wrap a component as an event emitter
    relay.handle(Output(...), Action("..."), State(...))      # handler decorator
    relay.validate(layout)                                    # optional linter

Handlers register globally via the ``@relay.handle`` decorator and look
like Dash callbacks: ``Output``, ``Action`` (substituting for ``Input``),
and ``State`` declared positionally; the wrapped function receives
``event`` for the action and current values for each ``State``.
"""

from .action import Action
from .app import install
from .bridge import bridge
from .emitter import emitter
from .handle import handle
from .validation import validate, ValidationIssue, ValidationReport

__all__ = [
    "install",
    "bridge",
    "emitter",
    "handle",
    "Action",
    "validate",
    "ValidationIssue",
    "ValidationReport",
]
