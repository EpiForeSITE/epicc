import hashlib
import importlib.resources
import re
from typing import Any

import streamlit as st
from pydantic import BaseModel, ValidationError

from epicc.config import CONFIG
from epicc.formats import VALID_PARAMETER_SUFFIXES
from epicc.model.base import BaseSimulationModel
from epicc.model.models import get_all_models
from epicc.model.parameters import load_model_params
from epicc.ui.parameters import (
    item_level,
    render_parameters_with_indent,
    reset_parameters_to_defaults,
)
from epicc.ui.sections import render_sections

# ---------------------------------------------------------------------------
# Export / print state helpers (inlined)
# ---------------------------------------------------------------------------

RESULTS_PAYLOAD_KEY = "results_payload"
PRINT_REQUESTED_KEY = "print_requested"
PRINT_TRIGGER_TOKEN_KEY = "print_trigger_token"


def initialize_export_state() -> None:
    if RESULTS_PAYLOAD_KEY not in st.session_state:
        st.session_state[RESULTS_PAYLOAD_KEY] = None

    if PRINT_REQUESTED_KEY not in st.session_state:
        st.session_state[PRINT_REQUESTED_KEY] = False

    if PRINT_TRIGGER_TOKEN_KEY not in st.session_state:
        st.session_state[PRINT_TRIGGER_TOKEN_KEY] = 0


def clear_export_state() -> None:
    st.session_state[RESULTS_PAYLOAD_KEY] = None
    st.session_state[PRINT_REQUESTED_KEY] = False
    st.session_state[PRINT_TRIGGER_TOKEN_KEY] = 0


def has_results() -> bool:
    return st.session_state.get(RESULTS_PAYLOAD_KEY) is not None


def get_results_payload() -> dict[str, Any] | None:
    payload = st.session_state.get(RESULTS_PAYLOAD_KEY)
    if payload is None:
        return None

    return payload


def set_results_payload(payload: dict[str, Any] | None) -> None:
    st.session_state[RESULTS_PAYLOAD_KEY] = payload


def render_export_button() -> None:
    export_clicked = st.sidebar.button(
        "Export Results as PDF", disabled=not has_results()
    )

    if export_clicked and has_results():
        st.session_state[PRINT_REQUESTED_KEY] = True
        st.session_state[PRINT_TRIGGER_TOKEN_KEY] = (
            st.session_state.get(PRINT_TRIGGER_TOKEN_KEY, 0) + 1
        )


def trigger_print_if_requested() -> None:
    if not st.session_state.get(PRINT_REQUESTED_KEY):
        return

    if not has_results():
        st.session_state[PRINT_REQUESTED_KEY] = False
        return

    trigger_token = st.session_state.get(PRINT_TRIGGER_TOKEN_KEY, 0)
    st.html(
        (
            "<script>"
            f"window.__epiccPrintToken = {trigger_token};"
            "setTimeout(function(){ window.parent.print(); }, 0);"
            "</script>"
        ),
        unsafe_allow_javascript=True,
    )
    st.session_state[PRINT_REQUESTED_KEY] = False


def _load_styles() -> None:
    with importlib.resources.files("epicc").joinpath("web/sidebar.css").open("rb") as f:
        css_content = f.read().decode("utf-8")
        st.markdown(f"<style>{css_content}</style>", unsafe_allow_html=True)


def _sync_active_model(model_key: str) -> dict[str, Any]:
    active_model_key = st.session_state.get("active_model_key")
    if active_model_key != model_key:
        st.session_state.active_model_key = model_key
        st.session_state.params = {}
        clear_export_state()

    if "params" not in st.session_state:
        st.session_state.params = {}

    return st.session_state.params


def _render_results_panel(results_payload: dict[str, Any]) -> None:
    st.title(results_payload.get("title", CONFIG.app.title))
    st.write(results_payload.get("description", ""))
    render_sections(results_payload.get("sections", []))


def _render_python_parameter_inputs(
    model: BaseSimulationModel,
    model_key: str,
    params: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, str], dict[str, Any], bool]:
    label_overrides: dict[str, str] = {}

    sorted_suffixes = sorted(VALID_PARAMETER_SUFFIXES)
    uploaded_params = st.sidebar.file_uploader(
        "Optional parameter file",
        type=sorted_suffixes,
        help="If omitted, model defaults are used.",
        accept_multiple_files=False,
    )

    if uploaded_params:
        cheap_id = (uploaded_params.name, uploaded_params.size)
        cached = st.session_state.get("_upload_hash_cache")
        if cached is not None and cached[0] == cheap_id:
            upload_hash = cached[1]
        else:
            upload_hash = hashlib.sha1(uploaded_params.getvalue()).hexdigest()
            st.session_state["_upload_hash_cache"] = (cheap_id, upload_hash)
        param_identity = (
            "upload",
            uploaded_params.name,
            uploaded_params.size,
            upload_hash,
        )
    else:
        param_identity = ("default", None, 0, None)
    should_refresh_params = False
    if st.session_state.get("active_param_identity") != param_identity:
        st.session_state.active_param_identity = param_identity
        st.session_state.params = {}
        clear_export_state()
        params = st.session_state.params
        should_refresh_params = True

    try:
        model_defaults = load_model_params(
            model,
            uploaded_params=uploaded_params or None,
            uploaded_name=uploaded_params.name if uploaded_params else None,
        )
    except ValidationError as exc:
        _render_validation_error_details(model.human_name(), exc, sidebar=True)
        return params, label_overrides, {}, True
    except ValueError as exc:
        st.sidebar.error(
            f"Could not read parameter file for {model.human_name()}: {exc}"
        )
        return params, label_overrides, {}, True

    if not model_defaults:
        st.sidebar.info("No default parameters defined for this model.")
        return params, label_overrides, {}, True

    current_headers = model.scenario_labels

    def handle_reset_python() -> None:
        reset_parameters_to_defaults(
            model_defaults, params, model_key, param_specs=model.parameter_specs
        )
        if not current_headers:
            return

        for key, default_text in current_headers.items():
            st.session_state[f"py_label_{model_key}_{key}"] = default_text

    if should_refresh_params:
        handle_reset_python()

    st.sidebar.button("Reset Parameters", on_click=handle_reset_python)

    if current_headers:
        with st.sidebar.expander("Output Scenario Headers", expanded=False):
            st.caption("Rename the output headers")
            for key, default_text in current_headers.items():
                widget_key = f"py_label_{model_key}_{key}"
                default_label = str(default_text)
                if widget_key in st.session_state:
                    label_overrides[key] = st.text_input(
                        f"Label for '{default_label}'", key=widget_key
                    )
                    continue

                label_overrides[key] = st.text_input(
                    f"Label for '{default_label}'",
                    value=default_label,
                    key=widget_key,
                )

    render_parameters_with_indent(
        model_defaults,
        params,
        model_id=model_key,
        param_specs=model.parameter_specs,
        param_groups=model.parameter_groups,
    )
    return params, label_overrides, model_defaults, False


def _unflatten_indented_params(flat_params: dict[str, Any]) -> dict[str, Any]:
    root: dict[str, Any] = {}
    stack: list[dict[str, Any]] = [root]

    for raw_key, value in flat_params.items():
        level = item_level(raw_key)
        label = raw_key.strip()

        while len(stack) > level + 1:
            stack.pop()

        parent = stack[-1]
        if value is None:
            node: dict[str, Any] = {}
            parent[label] = node
            stack.append(node)
            continue

        parent[label] = value

    return root


def _merge_sidebar_values(
    nested_defaults: dict[str, Any], params: dict[str, Any]
) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for key, value in nested_defaults.items():
        if isinstance(value, dict):
            merged[key] = _merge_sidebar_values(value, params)
            continue

        merged[key] = params.get(key, value)

    return merged


def _build_typed_params(
    model: BaseSimulationModel,
    model_defaults_flat: dict[str, Any],
    params: dict[str, Any],
) -> BaseModel:
    nested_defaults = _unflatten_indented_params(model_defaults_flat)
    payload = _merge_sidebar_values(nested_defaults, params)
    return model.parameter_model().model_validate(payload)


def _render_validation_error_details(
    model_name: str, exc: ValidationError, sidebar: bool
) -> None:
    target = st.sidebar if sidebar else st
    issues = exc.errors()
    issue_count = len(issues)
    target.error(f"Parameters do not match {model_name} schema ({issue_count} issues).")

    details = target.expander("Validation details", expanded=False)
    with details:
        preview_count = 8
        for issue in issues[:preview_count]:
            loc_parts = issue.get("loc", [])
            path = " > ".join(str(p) for p in loc_parts) if loc_parts else "(root)"
            msg = issue.get("msg", "Invalid value")
            st.write(f"- {path}: {msg}")

        if issue_count > preview_count:
            st.caption(f"...and {issue_count - preview_count} more.")

        safe_model_name = re.sub(r"[^a-z0-9]+", "_", model_name.lower()).strip("_")
        full_details = exc.json(indent=2)
        detail_digest = hashlib.sha1(full_details.encode("utf-8")).hexdigest()[:10]
        st.text_area(
            "Full details (copyable)",
            value=full_details,
            height=180,
            key=f"{safe_model_name}_{'sidebar' if sidebar else 'main'}_validation_text_{detail_digest}",
        )
        st.download_button(
            "Download full error details",
            data=full_details,
            file_name=f"{safe_model_name}_validation_error.json",
            mime="application/json",
            key=f"{safe_model_name}_{'sidebar' if sidebar else 'main'}_validation_download_{detail_digest}",
        )


def _run_python_simulation(
    selected_label: str,
    model: BaseSimulationModel,
    typed_params: BaseModel,
    label_overrides: dict[str, str],
) -> dict[str, Any]:
    # NOTE: Previously this function rendered results directly with st.* calls and
    # returned None implicitly. That meant set_results_payload(None) was always
    # called, has_results() was always False, and the PDF export button was
    # permanently disabled. It now returns a payload dict stored in session state;
    # rendering is deferred to _render_results_panel after st.rerun().
    with st.spinner(f"Running {selected_label}..."):
        results = model.run(typed_params, label_overrides=label_overrides)
        sections = model.build_sections(results)
    return {
        "title": model.model_title or CONFIG.app.title,
        "description": model.model_description or CONFIG.app.description,
        "sections": sections,
    }


_load_styles()

st.sidebar.title("epicc Cost Calculator")
st.sidebar.header("Simulation Controls")

all_models = get_all_models()
model_registry: dict[str, BaseSimulationModel] = {m.human_name(): m for m in all_models}
model_labels = list(model_registry.keys())

selected_label = st.sidebar.selectbox("Select Model", model_labels, index=0)
model_key = selected_label

params = _sync_active_model(model_key)
initialize_export_state()

st.sidebar.subheader("Input Parameters")

has_input_errors = False
typed_params: BaseModel | None = None

params, label_overrides, model_defaults_flat, has_input_errors = (
    _render_python_parameter_inputs(
        model_registry[selected_label],
        model_key,
        params,
    )
)

if not has_input_errors:
    try:
        typed_params = _build_typed_params(
            model_registry[selected_label], model_defaults_flat, params
        )
    except ValidationError as exc:
        _render_validation_error_details(selected_label, exc, sidebar=True)
        has_input_errors = True

run_clicked = st.sidebar.button("Run Simulation", disabled=has_input_errors)
render_export_button()

if typed_params is None:
    st.error("Cannot run simulation until parameter validation errors are fixed.")
    st.stop()

if run_clicked:
    assert typed_params is not None  # guaranteed by the st.stop() guard above
    set_results_payload(
        _run_python_simulation(
            selected_label,
            model_registry[selected_label],
            typed_params,
            label_overrides,
        )
    )

    # Always rerun after a successful run so the export button reflects the new
    # state (has_results() == True) and _render_results_panel is reached below.
    if has_results():
        st.rerun()

elif not has_results():
    # No run was clicked and no stored results exist yet; nothing to display.
    st.stop()


results_payload = get_results_payload()
if results_payload:
    _render_results_panel(results_payload)

trigger_print_if_requested()
