from typing import Literal

from pydantic import BaseModel, Field


class AppConfig(BaseModel):
    title: str = Field(description="Display title of the application.")

    description: str = Field(
        description="Brief description of the application and its purpose."
    )


class DefaultsConfig(BaseModel):
    decimal_precision: int = Field(
        default=4,  # This used to be 28, not sure why, since that's very large.
        ge=1,
        le=16,
        description="Number of decimal places used in cost and probability calculations.",
    )

    ui_theme: Literal["light", "dark"] = Field(
        default="light",
        description="UI theme. One of 'light' or 'dark'.",
    )


class LogoConfig(BaseModel):
    """The approved logo artwork used in the application header."""

    path: str = Field(description="Package-relative path to the logo artwork.")
    dark_path: str | None = Field(
        default=None,
        description="Optional package-relative logo artwork for dark backgrounds.",
    )
    alt_text: str = Field(description="Accessible description of the logo.")
    mime_type: str = Field(
        default="image/png", description="MIME type of the logo artwork."
    )
    width_px: int = Field(
        default=220,
        ge=72,
        le=480,
        description="Rendered logo width in pixels.",
    )


class BrandColorsConfig(BaseModel):
    """Semantic color tokens used by the web interface."""

    primary: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    on_primary: str = Field(
        default="#FFFFFF",
        pattern=r"^#[0-9A-Fa-f]{6}$",
        description="Text and icon color displayed on the primary color.",
    )
    accent: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    text: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    muted_text: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    canvas: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    surface: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    border: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    chart_palette: list[str] = Field(
        min_length=1,
        description="Ordered colors for report charts.",
    )


class BrandConfig(BaseModel):
    """Configurable visual identity for the application."""

    name: str = Field(description="Organization or center name.")
    font_family: str = Field(description="CSS font stack used by the application.")
    logo: LogoConfig
    colors: BrandColorsConfig
    dark_colors: BrandColorsConfig | None = Field(
        default=None,
        description="Semantic color tokens used when Streamlit is in dark mode.",
    )


class Config(BaseModel):
    app: AppConfig
    defaults: DefaultsConfig
    brand: BrandConfig


__all__ = ["Config"]
