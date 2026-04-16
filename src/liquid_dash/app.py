from __future__ import annotations

from importlib import resources


_ASSET_NAME = "liquid_dash.js"
_ASSET_ROUTE = "/_liquid_dash/liquid_dash.js"
_ENDPOINT = "_liquid_dash_js"
_SCRIPT_TAG = f'<script src="{_ASSET_ROUTE}"></script>'
_SCRIPTS_PLACEHOLDER = "{%scripts%}"


def _read_asset() -> str:
    return (
        resources.files("liquid_dash")
        .joinpath("assets", _ASSET_NAME)
        .read_text(encoding="utf-8")
    )


def _register_asset(app) -> None:
    server = app.server

    if _ENDPOINT not in server.view_functions:
        js_body = _read_asset()

        def serve_liquid_dash_js():
            return js_body, 200, {"Content-Type": "application/javascript"}

        server.add_url_rule(_ASSET_ROUTE, endpoint=_ENDPOINT, view_func=serve_liquid_dash_js)

    if _SCRIPT_TAG not in app.index_string:
        app.index_string = app.index_string.replace(
            _SCRIPTS_PLACEHOLDER,
            _SCRIPTS_PLACEHOLDER + "\n        " + _SCRIPT_TAG,
            1,
        )


def melt(app, *, register_asset: bool = True):
    """Prepare a Dash app to carry Liquid Dash events.

    Installs the client-side event handler and returns the app.
    """
    if register_asset:
        _register_asset(app)
    return app
