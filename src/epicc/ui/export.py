"""PDF export button, browser-print trigger, and parameter export."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st
from pydantic import BaseModel

from epicc.formats import get_format
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


def render_parameter_export(
    model_name: str,
    param_data: dict[str, Any],
    *,
    pydantic_model: type[BaseModel] | None = None,
) -> None:
    """Render a sidebar section for exporting the current parameter values.

    *param_data* should be the unflattened (nested) parameter dict — the same
    structure that would be accepted by an uploaded parameter file.
    Two download buttons are offered: YAML and XLSX.

    *pydantic_model*, if provided, is passed through to the XLSX writer so that
    field descriptions are emitted as column C comments.
    """
    safe_name = model_name.lower().replace(" ", "_")

    with st.sidebar.expander("Export Parameters", expanded=False):
        for suffix, label, mime in (
            ("yaml", "YAML (.yaml)", "text/yaml"),
            ("xlsx", "Excel (.xlsx)", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        ):
            try:
                fmt = get_format(Path(f"params.{suffix}"))
                kwargs: dict[str, Any] = {}
                if pydantic_model is not None:
                    kwargs["pydantic_model"] = pydantic_model
                data = fmt.write(param_data, **kwargs)
                st.download_button(
                    label=f"Download as {label}",
                    data=data,
                    file_name=f"{safe_name}_params.{suffix}",
                    mime=mime,
                    use_container_width=True,
                    key=f"param_export_{safe_name}_{suffix}",
                )
            except Exception as exc:
                st.error(f"Could not generate {suffix.upper()}: {exc}")
