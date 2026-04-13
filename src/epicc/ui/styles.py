"""Load package CSS assets into the Streamlit page."""

from __future__ import annotations

import importlib.resources

import streamlit as st


def load_styles() -> None:
    with importlib.resources.files("epicc").joinpath("web/sidebar.css").open("rb") as f:
        css = f.read().decode("utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
