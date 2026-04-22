from __future__ import annotations

from dash import dcc


DEFAULT_BRIDGE_ID = "bridge"

# Module-level set of bridge ids registered via ``relay.bridge(id)`` since
# the last ``install(app)`` flush. ``install()`` reads this to know which
# bridges to wire dispatchers for, then clears it.
_REGISTERED_BRIDGE_IDS: set[str] = set()


def bridge(id: str = DEFAULT_BRIDGE_ID) -> dcc.Store:
    """Return a dcc.Store that acts as the event sink for Dash Relay.

    Drop this component into your layout once per bridge you need. The
    default id ``"bridge"`` matches what ``emitter()`` and ``handle()``
    target by default.

    Calling ``bridge(id)`` records the id in a module-level pool so
    ``install(app)`` knows to register a dispatcher for it.
    """
    _REGISTERED_BRIDGE_IDS.add(id)
    return dcc.Store(id=id, data=None, storage_type="memory")


def _registered_bridge_ids() -> frozenset[str]:
    return frozenset(_REGISTERED_BRIDGE_IDS)


def _reset_bridge_pool() -> None:
    """Clear the registered-bridge pool. Called after ``install()`` flushes."""
    _REGISTERED_BRIDGE_IDS.clear()
