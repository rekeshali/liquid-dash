"""``relay.install(app)`` — the lifecycle entry point."""
from __future__ import annotations

from importlib import resources

from dash import Input, State, dcc, html

from .callback import (
    _build_bridge_dispatcher,
    _bridge_store_id,
    _drain_pending,
    _plan_bridges,
)
from .exceptions import InstallError


_ASSET_NAME = "dash_relay.js"
_ASSET_ROUTE = "/_dash_relay/dash_relay.js"
_ENDPOINT = "_dash_relay_js"
_SCRIPT_TAG = f'<script src="{_ASSET_ROUTE}"></script>'
_SCRIPTS_PLACEHOLDER = "{%scripts%}"


def _read_asset() -> str:
    return (
        resources.files("dash_relay")
        .joinpath("assets", _ASSET_NAME)
        .read_text(encoding="utf-8")
    )


def _register_runtime(app) -> None:
    server = app.server
    if _ENDPOINT not in server.view_functions:
        js_body = _read_asset()

        def serve_dash_relay_js():
            return js_body, 200, {"Content-Type": "application/javascript"}

        server.add_url_rule(
            _ASSET_ROUTE, endpoint=_ENDPOINT, view_func=serve_dash_relay_js
        )
    if _SCRIPT_TAG not in app.index_string:
        app.index_string = app.index_string.replace(
            _SCRIPTS_PLACEHOLDER,
            _SCRIPTS_PLACEHOLDER + "\n        " + _SCRIPT_TAG,
            1,
        )


# ---------------------------------------------------------------------------
# Layout injection
# ---------------------------------------------------------------------------


def _inject_stores(app, store_components) -> None:
    if not store_components:
        return

    holder = html.Div(
        store_components,
        style={"display": "none"},
        id="_relay_bridges",
    )

    layout = app.layout
    if callable(layout):
        original = layout

        def _wrapped(*args, **kwargs):
            inner = original(*args, **kwargs)
            return _attach(inner, holder)

        try:
            _wrapped.__name__ = getattr(original, "__name__", "_wrapped")
        except (AttributeError, TypeError):
            pass

        app.layout = _wrapped
    else:
        app.layout = _attach(layout, holder)


def _attach(layout, holder):
    if isinstance(layout, list):
        return [*layout, holder]
    return html.Div([layout, holder])


# ---------------------------------------------------------------------------
# install()
# ---------------------------------------------------------------------------


def install(app, *, register_runtime: bool = True):
    """Materialize bridge stores, inject them into the layout, and wire dispatchers.

    Lifecycle contract:

      * ``app.layout`` must be set before ``install()`` is called. If it
        is ``None``, ``InstallError`` is raised.
      * ``install()`` may be called at most once per app. A second call
        raises ``InstallError``.
      * Reassigning ``app.layout`` after ``install()`` removes the bridge
        stores. The library does not re-inject. Don't do that.

    What ``install()`` does, in order:

      1. Validate the lifecycle preconditions.
      2. Inject the JS runtime ``<script>`` tag and Flask asset route.
         (Skip with ``register_runtime=False`` to vendor or CDN.)
      3. Drain the global ``@relay.callback`` pending pool.
      4. Plan one bridge per unique ``(action.bridge_id)`` mentioned in
         any handler's ``Action`` declarations. Detect duplicate
         ``(bridge, action)`` registrations and raise ``InstallError``.
      5. Mint one ``dcc.Store`` per bridge with id
         ``relay-bridge-<slug(bridge_name)>``.
      6. Inject the stores into the layout (single Component → wrap in
         Div; list → append; callable → wrap callable).
      7. Register one Dash callback per bridge:
         ``Output``s = union with ``allow_duplicate=True``,
         ``State``s = union, ``Input`` = the bridge store,
         ``prevent_initial_call=True``.

    The handler pool is cached on the app as ``_dash_relay_handlers``
    and the bridge plans as ``_dash_relay_bridge_plans`` so
    ``validate()`` and tests can introspect after install.
    """
    if getattr(app, "_dash_relay_installed", False):
        raise InstallError(
            "relay.install(app) was already called for this app. "
            "Call it once after defining handlers and assigning app.layout."
        )
    if app.layout is None:
        raise InstallError(
            "relay.install(app) called before app.layout was set. "
            "Assign app.layout = ... first, then call install()."
        )

    if register_runtime:
        _register_runtime(app)

    handlers = _drain_pending()
    plans = _plan_bridges(handlers)

    # Mint stores for every bridge in the plan.
    store_components = [
        dcc.Store(
            id=_bridge_store_id(name),
            data=None,
            storage_type="memory",
        )
        for name in sorted(plans.keys())
    ]

    _inject_stores(app, store_components)

    # Register one Dash callback per bridge.
    for bridge_name, plan in plans.items():
        dispatch_fn = _build_bridge_dispatcher(plan)
        # Cache for tests / debugging.
        plan.dispatch = dispatch_fn  # type: ignore[attr-defined]
        store_id = _bridge_store_id(bridge_name)
        outputs = [
            type(o)(o.component_id, o.component_property, allow_duplicate=True)
            for o in plan.all_outputs
        ]
        app.callback(
            *outputs,
            Input(store_id, "data"),
            *plan.all_states,
            prevent_initial_call=True,
        )(dispatch_fn)

    app._dash_relay_handlers = list(handlers)
    app._dash_relay_bridge_plans = plans
    app._dash_relay_installed = True
    return app
