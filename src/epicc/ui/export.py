"""PDF export button, browser-print trigger, and parameter export."""

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


def render_parameter_export_inline(
    model_name: str,
    param_data: dict[str, Any],
    *,
    pydantic_model: type[BaseModel] | None = None,
    container: Any = None,
) -> None:
    """Render inline parameter download buttons for every registered writable format.

    Intended to be placed directly below the parameter file uploader so that
    the load/save relationship is obvious from proximity alone.
    """
    rc = container if container is not None else st
    safe_name = model_name.lower().replace(" ", "_")

    # Collect unique format classes in registration order.
    seen: set[type[BaseFormat]] = set()
    unique: list[tuple[str, type[BaseFormat]]] = []
    for suffix, cls in iter_formats():
        if cls not in seen:
            seen.add(cls)
            unique.append((suffix.lstrip("."), cls))

    rc.caption("Save current parameters")
    cols = rc.columns(len(unique))
    for col, (suffix, fmt_cls) in zip(cols, unique):
        try:
            fmt = get_format(Path(f"params.{suffix}"))
            kwargs: dict[str, Any] = {}
            if pydantic_model is not None:
                kwargs["pydantic_model"] = pydantic_model
            data = fmt.write(param_data, **kwargs)
            col.download_button(
                label=f"Save as {fmt_cls.label}",
                data=data,
                file_name=f"{safe_name}_params.{suffix}",
                mime=fmt_cls.mime_type,
                width='stretch',
                key=f"inline_param_export_{safe_name}_{suffix}",
            )
        except Exception as exc:
            col.error(f"Could not generate {fmt_cls.label}: {exc}")


def render_pdf_export_button(container: Any = None) -> None:
    """Render a direct Save report as PDF button.

    Disabled until results are available. Intended for placement in the
    results column so it is visible without any extra navigation.
    """
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
