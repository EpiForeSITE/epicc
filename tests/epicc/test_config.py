import importlib.resources

import pytest
from pydantic import ValidationError

from epicc.config import CONFIG
from epicc.config.schema import BrandColorsConfig


def test_default_brand_configuration_references_packaged_logo() -> None:
    """The configured logo must be present for both Streamlit and stlite builds."""
    logo = importlib.resources.files("epicc").joinpath(CONFIG.brand.logo.path)

    assert CONFIG.brand.name == "ForeSITE"
    assert logo.is_file()
    if CONFIG.brand.logo.dark_path:
        dark_logo = importlib.resources.files("epicc").joinpath(
            CONFIG.brand.logo.dark_path
        )
        assert dark_logo.is_file()
    assert CONFIG.brand.logo.mime_type == "image/png"
    assert CONFIG.brand.colors.chart_palette[:2] == ["#A60F2D", "#FDB921"]
    assert CONFIG.brand.dark_colors is not None
    assert CONFIG.brand.dark_colors.canvas == "#171717"
    assert CONFIG.brand.dark_colors.primary == "#FDB921"


def test_brand_colors_require_hex_values() -> None:
    with pytest.raises(ValidationError):
        BrandColorsConfig.model_validate(
            {
                "primary": "crimson",
                "on_primary": "#FFFFFF",
                "accent": "#FDB921",
                "text": "#4E4E4E",
                "muted_text": "#6B6E72",
                "canvas": "#F7F7F5",
                "surface": "#FFFFFF",
                "border": "#D9D9D6",
                "chart_palette": ["#A60F2D"],
            }
        )

    with pytest.raises(ValidationError):
        BrandColorsConfig.model_validate(
            {
                "primary": "#A60F2D",
                "on_primary": "#FFFFFF",
                "accent": "#FDB921",
                "text": "#4E4E4E",
                "muted_text": "#6B6E72",
                "canvas": "#F7F7F5",
                "surface": "#FFFFFF",
                "border": "#D9D9D6",
                "chart_palette": ["not-a-hex-color"],
            }
        )
