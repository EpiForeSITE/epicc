from __future__ import annotations

from pathlib import Path
from typing import Any
import base64
import importlib.resources

import streamlit as st
from pydantic import BaseModel

from epicc.formats import get_format, iter_formats
from epicc.formats.base import BaseFormat
from epicc.formats.docx import DOCXFormat
from epicc.model.base import BaseSimulationModel
from epicc.ui.state import has_results, _PRINT_REQUESTED_KEY, _PRINT_TOKEN_KEY


def build_report_payload(
    model: BaseSimulationModel,
    run_output: dict[str, Any],
) -> dict[str, Any]:
    """Build a structured report payload from model definition and run output.

    This is the shared abstraction used by both PDF and DOCX export paths
    to keep report content in sync.
    """
    model_def = model.get_model_definition()
    scenario_results = run_output.get("scenario_results_by_id", {})
    label_overrides = run_output.get("label_overrides", {})

    scenario_labels: dict[str, str] = {}
    for s in getattr(model_def, "scenarios", []) or []:
        sid = getattr(s, "id", None)
        lbl = getattr(s, "label", None)
        if sid:
            scenario_labels[sid] = label_overrides.get(sid, lbl or sid)

    sections: list[dict[str, Any]] = []
    for item in getattr(model_def, "report", []) or []:
        kind = getattr(item, "type", None)

        if kind == "markdown":
            sections.append({"type": "markdown", "content": getattr(item, "content", "")})
            continue

        if kind in {"table", "graph"}:
            rows_out: list[dict[str, Any]] = []
            for r in getattr(item, "rows", []) or []:
                eq_key = getattr(r, "value", "")
                values: dict[str, Any] = {}
                for sid, eqs in scenario_results.items():
                    values[scenario_labels.get(sid, sid)] = (eqs or {}).get(eq_key)
                rows_out.append({"label": getattr(r, "label", eq_key), "values": values})

            sections.append({
                "type": "table",
                "title": getattr(item, "title", ""),
                "caption": getattr(item, "caption", ""),
                "rows": rows_out,
            })

    return {"__report__": {"title": model_def.title, "sections": sections}}


@st.dialog("Save Parameters")
def _export_dialog(
    model_name: str,
    param_data: dict[str, Any],
    unique_formats: list[tuple[str, type[BaseFormat]]],
    pydantic_model: type[BaseModel] | None = None
) -> None:
    safe_name = model_name.lower().replace(" ", "_")

    st.markdown("""
    **EPICC** supports a variety of formats for exporting your parameter settings, each with its own advantages:

    - **Excel (XLSX)**: A familiar spreadsheet format that opens in Microsoft Excel, Google Sheets, or other spreadsheet applications.
    - **YAML**: A text-based format, ideal for easy sharing. Can be edited in any text editor.

    If you are unsure, YAML is a good default choice for its simplicity and readability.
    """)

    format_options = [cls.label for _, cls in unique_formats]
    default_index = 0
    if "YAML" in format_options:
        default_index = format_options.index("YAML")

    selected_format = st.selectbox(
        "Select file format:",
        options=format_options,
        index=default_index,
        help="Choose how you'd like to save your parameters"
    )

    selected_cls = None
    selected_suffix = None
    for suffix, cls in unique_formats:
        if cls.label == selected_format:
            selected_cls = cls
            selected_suffix = suffix
            break

    if selected_cls and selected_suffix:
        try:
            fmt = get_format(Path(f"params.{selected_suffix}"))
            kwargs: dict[str, Any] = {}
            if pydantic_model is not None:
                kwargs["pydantic_model"] = pydantic_model
            data = fmt.write(param_data, **kwargs)

            st.download_button(
                label=f"Download {selected_format} file",
                data=data,
                file_name=f"{safe_name}_params.{selected_suffix}",
                mime=selected_cls.mime_type,
                type="primary",
                use_container_width=True
            )
        except Exception as exc:
            st.error(f"Could not generate {selected_format} file: {exc}")


def render_parameter_export_modal(
    model_name: str,
    param_data: dict[str, Any],
    *,
    pydantic_model: type[BaseModel] | None = None,
    container: Any = None,
) -> None:
    rc = container if container is not None else st

    seen: set[type[BaseFormat]] = set()
    unique: list[tuple[str, type[BaseFormat]]] = []
    for suffix, cls in iter_formats():
        if cls not in seen:
            seen.add(cls)
            unique.append((suffix.lstrip("."), cls))

    model_key = model_name.lower().replace(" ", "_")
    if rc.button("Save Parameters", width="stretch", key=f"save_params_btn_{model_key}"):
        _export_dialog(model_name, param_data, unique, pydantic_model)


def render_pdf_export_button(container: Any = None) -> None:
    rc = container if container is not None else st
    clicked = rc.button(
        "Save report as PDF",
        disabled=not has_results(),
        width="stretch",
        type="primary",
    )

    if clicked and has_results():
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

    # What the hell is this, Streamlit? Why can't I just run JS without this nonsense? Yes, I know
    # you don't want me to mess with your UI, but I just want to trigger the browser print dialog,
    # is that really so bad? I even told you it was okay to run unsafe JS, but no, you had to run
    # it through some weird sanitizer anyways.
    #
    # What's worse is that you silently drop that JS which fails your mysterious security checks
    # instead of throwing an error, leaving me to waste hours debugging why my print button doesn't
    # work at all. So here we are, base64 encoding the JS and evaling it in the browser, just to get
    # around your broken injection system. I hope you're proud of yourselves.
    #
    # Seriously!?!? This works?
    #
    # This is an alternative implementation to something like:
    #
    #   https://github.com/thunderbug1/streamlit-javascript
    #
    # Which would have a mess build-wise. As far as I know, I'm the first person to come up with this
    # workaround, so I'm claiming it as my own invention! Don't tell Streamlit.

    with importlib.resources.files("epicc").joinpath("js/print_results.js").open("rb") as f:
        js = f.read().decode()
        js64 = base64.b64encode(js.encode()).decode()

    print_assign = f"window.__epiccPrintToken = {trigger_token}"
    looks_malicious = f"eval(atob('{js64}'))"

    st.html(
        f"<script>{print_assign}; {looks_malicious}</script>",
        unsafe_allow_javascript=True,
    )

    st.session_state[_PRINT_REQUESTED_KEY] = False


def render_docx_export_button(
    model: BaseSimulationModel,
    run_output: dict[str, Any] | None,
    container: Any = None,
) -> None:
    """Render a direct Save report as DOCX button."""
    rc = container if container is not None else st

    if run_output is None or not has_results():
        rc.button("Save report as DOCX", disabled=True, width="stretch")
        return

    try:
        fmt = DOCXFormat(Path("report.docx"))
        data = fmt.write(build_report_payload(model, run_output))
        rc.download_button(
            label="Save report as DOCX",
            data=data,
            file_name=f"{model.human_name().lower().replace(' ', '_')}_report.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            type="primary",
            use_container_width=True,
        )
    except Exception as exc:
        rc.error(f"Could not generate DOCX report: {exc}")
