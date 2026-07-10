from __future__ import annotations

import base64
import io
import lzma
import urllib.error
import urllib.request
from typing import Any

import streamlit as st

from epicc.model.models import load_model_from_stream
from epicc.ui.state import add_custom_model

_PENDING_MODEL_KEY = "_pending_model_selection"


def _infer_filename_from_url(url: str) -> str:
    base = url.split("?")[0].split("#")[0].rstrip("/")
    filename = base.rsplit("/", 1)[-1] if "/" in base else base
    if not filename:
        filename = "model.yaml"
    elif not filename.lower().endswith((".yaml", ".yml")):
        filename += ".yaml"
    return filename


def _decode_model_code(code: str) -> bytes:
    """Decode a base64-encoded, LZMA-compressed YAML model code into raw YAML bytes."""
    compressed = base64.b64decode(code.strip())
    return lzma.decompress(compressed)


@st.dialog("Load Custom Model", width="large")
def _load_model_dialog() -> None:
    st.markdown(
        "Load a model from a local YAML file, from a URL, or by pasting a model code. "
        "Custom models are available for the rest of this browser session."
    )

    tab_file, tab_url, tab_code = st.tabs(
        ["Upload File", "Load from URL", "Use a Model Code"]
    )

    with tab_file:
        uploaded = st.file_uploader(
            "YAML model file",
            type=["yaml", "yml"],
            label_visibility="collapsed",
        )

        load_file_btn = st.button(
            "Load",
            key="load_model_file_btn",
            type="primary",
            disabled=uploaded is None,
        )

        if load_file_btn and uploaded is not None:
            try:
                with st.spinner("Parsing model..."):
                    model = load_model_from_stream(
                        uploaded.name, io.BytesIO(uploaded.read())
                    )
                add_custom_model(model.human_name(), model)
                st.session_state[_PENDING_MODEL_KEY] = model.human_name()
                st.rerun()
            except Exception as exc:
                st.error(f"Could not load model: {exc}")

    with tab_url:
        url = st.text_input(
            "Model URL",
            placeholder="https://example.com/model.yaml",
            label_visibility="collapsed",
        )

        load_url_btn = st.button(
            "Load",
            key="load_model_url_btn",
            type="primary",
            disabled=not bool(url),
        )

        if load_url_btn and url:
            try:
                with st.spinner("Fetching model..."):
                    if not url.lower().startswith(("http://", "https://")):
                        raise ValueError("Only http(s) URLs are supported")
                    req = urllib.request.Request(
                        url,
                        headers={"User-Agent": "epicc/0.1"},
                    )
                    with urllib.request.urlopen(req, timeout=15) as response:  # noqa: S310
                        max_bytes = 2 * 1024 * 1024  # 2 MiB safety cap
                        raw = response.read(max_bytes + 1)
                        if len(raw) > max_bytes:
                            raise ValueError("Model file is too large (max 2 MiB)")

                filename = _infer_filename_from_url(url)
                model = load_model_from_stream(filename, io.BytesIO(raw))
                add_custom_model(model.human_name(), model)
                st.session_state[_PENDING_MODEL_KEY] = model.human_name()
                st.rerun()
            except urllib.error.URLError as exc:
                reason = exc.reason if hasattr(exc, "reason") else str(exc)
                st.error(f"Could not fetch URL: {reason}")
            except Exception as exc:
                st.error(f"Could not load model: {exc}")

    with tab_code:
        code = st.text_area(
            "Model code",
            placeholder="Paste your model code here...",
            label_visibility="collapsed",
            height=160,
        )

        load_code_btn = st.button(
            "Load",
            key="load_model_code_btn",
            type="primary",
            disabled=not bool(code),
        )

        if load_code_btn and code:
            try:
                with st.spinner("Decoding model..."):
                    model = load_model_from_stream(
                        "model.yaml", io.BytesIO(_decode_model_code(code))
                    )
                add_custom_model(model.human_name(), model)
                st.session_state[_PENDING_MODEL_KEY] = model.human_name()
                st.rerun()
            except Exception as exc:
                st.error(f"Could not load model: {exc}")


def render_load_model_button(container: Any = None) -> None:
    rc = container if container is not None else st
    if rc.button(
        "Other...",
        key="open_load_model_dialog",
        help="Load a model from a local YAML file or from a URL",
        use_container_width=True,
    ):
        _load_model_dialog()


def consume_pending_model_selection() -> str | None:
    return st.session_state.pop(_PENDING_MODEL_KEY, None)
