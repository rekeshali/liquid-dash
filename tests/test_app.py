from dash import Dash, html

import liquid_dash as ld


def test_melt_registers_js_route_and_injects_script_tag() -> None:
    app = Dash(__name__)
    app.layout = html.Div()
    ld.melt(app)

    assert '<script src="/_liquid_dash/liquid_dash.js"></script>' in app.index_string

    client = app.server.test_client()
    response = client.get("/_liquid_dash/liquid_dash.js")
    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith("application/javascript")
    assert "__liquidDashInstalled" in response.get_data(as_text=True)


def test_melt_is_idempotent() -> None:
    app = Dash(__name__)
    ld.melt(app)
    ld.melt(app)

    assert app.index_string.count('src="/_liquid_dash/liquid_dash.js"') == 1
