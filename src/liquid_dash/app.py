from __future__ import annotations

import shutil
from pathlib import Path

from importlib import resources

from .validation import validate_layout


_ASSET_NAME = "liquid_dash.js"


def _copy_asset_to_dash(app) -> Path:
    assets_folder = Path(app.config.assets_folder)
    assets_folder.mkdir(parents=True, exist_ok=True)
    target = assets_folder / _ASSET_NAME

    with resources.as_file(resources.files("liquid_dash").joinpath("assets", _ASSET_NAME)) as source:
        source_path = Path(source)
        if not target.exists() or target.read_text(encoding="utf-8") != source_path.read_text(encoding="utf-8"):
            shutil.copyfile(source_path, target)

    return target


def configure(app, *, copy_assets: bool = True, validate: bool = False):
    """Prepare a Dash app to use liquid_dash helpers."""
    if copy_assets:
        _copy_asset_to_dash(app)
    if validate and getattr(app, "layout", None) is not None:
        validate_layout(app.layout)
    return app
