from __future__ import annotations

import base64
import html
import importlib.resources
from typing import Any

import streamlit as st

from epicc.config.schema import BrandColorsConfig, BrandConfig


def load_styles(brand: BrandConfig) -> None:
    """Load the stylesheet and synchronize it with Streamlit's active theme."""
    with importlib.resources.files("epicc").joinpath("web/sidebar.css").open("rb") as f:
        css = f.read().decode("utf-8")

    def render_tokens(colors: BrandColorsConfig) -> str:
        return f"""
        --brand-primary: {colors.primary};
        --brand-on-primary: {colors.on_primary};
        --brand-accent: {colors.accent};
        --brand-text: {colors.text};
        --brand-muted-text: {colors.muted_text};
        --brand-canvas: {colors.canvas};
        --brand-surface: {colors.surface};
        --brand-border: {colors.border};
        """

    dark_colors = brand.dark_colors or brand.colors
    tokens = f"""
    :root {{
        {render_tokens(brand.colors)}
        --brand-font-family: {brand.font_family};
    }}

    :root[data-epicc-theme="dark"] {{
        {render_tokens(dark_colors)}
    }}
    """
    st.markdown(f"<style>{tokens}\n{css}</style>", unsafe_allow_html=True)

    with (
        importlib.resources.files("epicc").joinpath("js/theme_sync.js").open("rb") as f
    ):
        theme_sync = f.read().decode("utf-8")
    theme_sync64 = base64.b64encode(theme_sync.encode()).decode()
    st.html(
        f"<script>eval(atob('{theme_sync64}'))</script>",
        unsafe_allow_javascript=True,
    )


def render_brand_header(brand: BrandConfig, title: str, *, container: Any = st) -> None:
    """Render a compact header using the configured logo artwork and title."""
    logo_resource = importlib.resources.files("epicc").joinpath(brand.logo.path)
    logo_data = base64.b64encode(logo_resource.read_bytes()).decode("ascii")
    logo_source = f"data:{brand.logo.mime_type};base64,{logo_data}"

    dark_logo = ""
    if brand.logo.dark_path:
        dark_resource = importlib.resources.files("epicc").joinpath(
            brand.logo.dark_path
        )
        dark_data = base64.b64encode(dark_resource.read_bytes()).decode("ascii")
        dark_source = f"data:{brand.logo.mime_type};base64,{dark_data}"
        dark_logo = f"""
          <img class="brand-header__logo brand-header__logo--dark"
               src="{dark_source}" alt="{html.escape(brand.logo.alt_text)}"
               style="width: {brand.logo.width_px}px;" />
        """

    container.markdown(
        f"""
        <div class="brand-header" aria-label="{html.escape(brand.name)}">
          <img class="brand-header__logo brand-header__logo--light"
               src="{logo_source}"
               alt="{html.escape(brand.logo.alt_text)}"
               style="width: {brand.logo.width_px}px;" />
          {dark_logo}
          <div class="brand-header__title">{html.escape(title)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
