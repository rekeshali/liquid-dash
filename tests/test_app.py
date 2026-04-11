from dash import Dash, html

from liquid_dash import configure


def test_configure_registers_js_route_and_injects_script_tag() -> None:
    app = Dash(__name__)
    app.layout = html.Div()
    configure(app)

    assert '<script src="/_liquid_dash/liquid_dash.js"></script>' in app.index_string

    client = app.server.test_client()
    response = client.get("/_liquid_dash/liquid_dash.js")
    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith("application/javascript")
    assert "__liquidDashInstalled" in response.get_data(as_text=True)


def test_configure_is_idempotent() -> None:
    app = Dash(__name__)
    configure(app)
    configure(app)

    assert app.index_string.count('src="/_liquid_dash/liquid_dash.js"') == 1
