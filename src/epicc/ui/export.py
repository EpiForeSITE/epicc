from __future__ import annotations

from pathlib import Path
from typing import Any
import base64
import importlib.resources

import streamlit as st
from pydantic import BaseModel

from epicc.formats import get_format, iter_formats
from epicc.formats.base import BaseFormat
from epicc.ui.state import has_results, _PRINT_REQUESTED_KEY, _PRINT_TOKEN_KEY


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
    
    # Prepare format options
    format_options = [cls.label for _, cls in unique_formats]
    default_index = 0  # YAML is default
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
    
    # Collect unique format classes in registration order.
    seen: set[type[BaseFormat]] = set()
    unique: list[tuple[str, type[BaseFormat]]] = []
    
    for suffix, cls in iter_formats():
        if cls not in seen:
            seen.add(cls)
            unique.append((suffix.lstrip("."), cls))
    
    if rc.button("Save Parameters", width='stretch', key=f"save_params_btn_{model_name.lower().replace(' ', '_')}"):
        _export_dialog(model_name, param_data, unique, pydantic_model)


def render_pdf_export_button(container: Any = None) -> None:
    # Render a direct Save report as PDF button.

    rc = container if container is not None else st
    clicked = rc.button(
        "Save report as PDF",
        disabled=not has_results(),
        width='stretch',
        type='primary',
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
