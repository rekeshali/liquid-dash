from __future__ import annotations

from importlib import resources


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

        server.add_url_rule(_ASSET_ROUTE, endpoint=_ENDPOINT, view_func=serve_dash_relay_js)

    if _SCRIPT_TAG not in app.index_string:
        app.index_string = app.index_string.replace(
            _SCRIPTS_PLACEHOLDER,
            _SCRIPTS_PLACEHOLDER + "\n        " + _SCRIPT_TAG,
            1,
        )


def install(app, *, register_runtime: bool = True):
    """Prepare a Dash app to carry Dash Relay events.

    Two side effects on ``app``:

      * A Flask route is registered at ``/_dash_relay/dash_relay.js`` that
        serves the ~130-line client-side runtime (event delegation, lazy
        listener registration, bridge writes).
      * A ``<script src="/_dash_relay/dash_relay.js">`` tag is inserted
        into ``app.index_string`` right after the ``{%scripts%}`` marker
        so the runtime loads on every page render.

    Both steps are idempotent — calling ``install()`` twice is safe.

    Pass ``register_runtime=False`` to skip both steps, e.g. if you prefer
    to vendor the asset yourself or serve it from a CDN.

    Returns the app for chaining.
    """
    if register_runtime:
        _register_runtime(app)
    return app
