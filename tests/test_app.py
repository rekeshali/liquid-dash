from dash import Dash

from liquid_dash import configure


def test_configure_copies_js_asset(tmp_path) -> None:
    app = Dash(__name__, assets_folder=str(tmp_path / "assets"))
    configure(app)
    asset = tmp_path / "assets" / "liquid_dash.js"
    assert asset.exists()
    assert "__liquidDashInstalled" in asset.read_text(encoding="utf-8")
