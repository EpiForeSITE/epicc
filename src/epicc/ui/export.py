"""PDF export button and browser-print trigger."""

from __future__ import annotations

import streamlit as st

from epicc.ui.state import has_results, _PRINT_REQUESTED_KEY, _PRINT_TOKEN_KEY


def render_export_button() -> None:
    export_clicked = st.sidebar.button(
        "Export Results as PDF", disabled=not has_results()
    )
    if export_clicked and has_results():
        st.session_state[_PRINT_REQUESTED_KEY] = True
        st.session_state[_PRINT_TOKEN_KEY] = (
            st.session_state.get(_PRINT_TOKEN_KEY, 0) + 1
        )


def trigger_print_if_requested() -> None:
    if not st.session_state.get(_PRINT_REQUESTED_KEY):
        return

    if not has_results():
        st.session_state[_PRINT_REQUESTED_KEY] = False
        return

    trigger_token = st.session_state.get(_PRINT_TOKEN_KEY, 0)
    st.html(
        (
            "<script>"
            f"window.__epiccPrintToken = {trigger_token};"
            "setTimeout(function(){ window.parent.print(); }, 0);"
            "</script>"
        ),
        unsafe_allow_javascript=True,
    )
    st.session_state[_PRINT_REQUESTED_KEY] = False
