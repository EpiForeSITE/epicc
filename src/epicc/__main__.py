from typing import cast

import streamlit as st
from pydantic import ValidationError

from epicc import __version__
from epicc.config import CONFIG
from epicc.model.base import BaseSimulationModel
from epicc.model.factory import create_model_instance
from epicc.model.models import get_all_models
from epicc.model.parameters import load_model_params
from epicc.model.schema import Model
from epicc.ui.about import render_whats_new_button
from epicc.ui.editor import get_current_doc, render_model_editor, validate_doc
from epicc.ui.export import (
    render_parameter_export_modal,
    render_pdf_export_button,
    trigger_print_if_requested,
)
from epicc.ui.model_loader import (
    consume_pending_model_selection,
    render_load_model_button,
)
from epicc.ui.parameters import (
    build_typed_params,
    render_sidebar_parameters,
    render_validation_error,
    reset_parameters_to_defaults,
    reset_scenario_state,
)
from epicc.ui.report import get_report_renderer
from epicc.ui.state import (
    DEFAULT_PARAM_IDENTITY,
    get_custom_models,
    get_run_output,
    has_results,
    initialize_state,
    set_run_output,
    set_active_param_identity,
    sync_active_model,
)
from epicc.ui.styles import load_styles, render_brand_header
from epicc.ui.url_params import read_url_params, write_url_params

st.set_page_config(page_title=CONFIG.app.title, layout="wide")
load_styles(CONFIG.brand)
initialize_state()

all_models = get_all_models()
model_registry: dict[str, BaseSimulationModel] = {m.human_name(): m for m in all_models}
model_registry.update(get_custom_models())

# Restore model selection and parameters from URL query string on first load.
_URL_APPLIED_KEY = "_url_params_applied"
if not st.session_state.get(_URL_APPLIED_KEY):
    _url_result = read_url_params()
    if _url_result is not None:
        _url_model, _url_values, _url_scenarios = _url_result
        if _url_model in model_registry:
            st.session_state[_URL_APPLIED_KEY] = True
            st.session_state["model_selector"] = _url_model
            # Activate the model and populate its keyed widgets before they render.
            _url_params = sync_active_model(_url_model)
            set_active_param_identity(DEFAULT_PARAM_IDENTITY)
            _url_active_model = model_registry[_url_model]
            reset_parameters_to_defaults(
                _url_values,
                _url_params,
                _url_model,
                param_specs=_url_active_model.parameter_specs,
            )
            if _url_scenarios:
                reset_scenario_state(
                    _url_model,
                    _url_scenarios,
                    _url_active_model.scenario_parameter_specs or {},
                )
    else:
        st.session_state[_URL_APPLIED_KEY] = True

_EDITOR_MODE_KEY = "epicc_editor_mode"
_MODEL_SELECT_KEY = "model_selector"
_PREVIEW_MODEL_KEY = "epicc_editor_preview_model"
_PREVIEW_LABEL_KEY = "epicc_editor_preview_label"


def _activate_preview(model_label: str) -> bool:
    """Compile the in-progress editor doc and switch the Calculator to it.

    Returns False (and leaves the editor open) if the doc doesn't validate.
    """
    doc = get_current_doc()
    result = validate_doc(doc) if doc is not None else None
    if not isinstance(result, Model):
        return False
    preview_model = create_model_instance(result)
    st.session_state[_PREVIEW_MODEL_KEY] = preview_model
    st.session_state[_PREVIEW_LABEL_KEY] = model_label
    model_defaults = load_model_params(preview_model)
    reset_parameters_to_defaults(
        model_defaults, {}, model_label, param_specs=preview_model.parameter_specs
    )
    default_scenarios = preview_model.default_scenarios
    if default_scenarios:
        reset_scenario_state(
            model_label, default_scenarios, preview_model.scenario_parameter_specs or {}
        )
    return True


def _discard_preview() -> None:
    st.session_state.pop(_PREVIEW_MODEL_KEY, None)
    st.session_state.pop(_PREVIEW_LABEL_KEY, None)


pending_label = consume_pending_model_selection()
if pending_label is not None and pending_label in model_registry:
    st.session_state[_MODEL_SELECT_KEY] = pending_label

hdr_title, hdr_right, hdr_editor = st.columns([3, 3, 1.25])
render_brand_header(
    CONFIG.brand, CONFIG.app.title, version=__version__, container=hdr_title
)

with hdr_right:
    col_model, col_load = st.columns([4, 1], vertical_alignment="center")
    selected_label: str | None = col_model.selectbox(
        "Model",
        list(model_registry),
        key=_MODEL_SELECT_KEY,
        index=None,
        placeholder="Select a model...",
        label_visibility="collapsed",
    )
    render_load_model_button(container=col_load)

in_editor = selected_label is not None and bool(st.session_state.get(_EDITOR_MODE_KEY))
if in_editor:
    try_button_slot = hdr_editor.empty()
elif selected_label is not None:
    if hdr_editor.button(
        "Open Model Editor",
        use_container_width=True,
        key="open_editor_btn",
    ):
        st.session_state[_EDITOR_MODE_KEY] = True
        st.rerun()

render_whats_new_button(CONFIG.app.releases_url, container=hdr_editor)

st.divider()

if selected_label is None:
    if in_editor:

        def _close_editor() -> None:
            st.session_state.pop(_EDITOR_MODE_KEY, None)

        render_model_editor(
            initial_doc=None,
            source_label=None,
            on_close=_close_editor,
        )
        st.stop()

    st.markdown(
        """
## Welcome to EPICC

**EPICC** (or *EP*idemiological *C*ost *C*alculator) is a tool for quickly running arbitrary
epidemiological models directly inside your browser. Select a disease model, adjust
the parameters to match your setting, and run the simulation to explore the cost
implications of different policy scenarios.

### What you can do

 - **Compare scenarios:** Each model defines multiple intervention points so you can
   quantify the cost implications of different policy choices within the same run.

 - **Understand the assumptions:** Every model documents the equations and default
   values it uses. Read the parameter descriptions before you run, and treat outputs
   with the caveats in mind.

 - **Save and share your work:** Export your current parameters and send them to a
   colleague, so they can pick up exactly where you left off, or reload them yourself
   any time you want to revisit the analysis.

 - **Generate a report:** Once you've run a simulation, save the results page as a PDF
   to share directly with stakeholders.

### A note on interpretation

This tool is designed as a decision-support aid, not a definitive forecast. Results
depend on the assumptions baked into each model and the parameter values you supply.
Always review the model assumptions before sharing outputs externally.

### Get started

Choose a model from the combobox above to get started. Edit its parameters on the
left, run the simulation, and see the results on the right. Happy exploring!

"""
    )

    st.stop()

active_model = model_registry[selected_label]
assert selected_label is not None  # Type narrowing for mypy

if st.session_state.get(_EDITOR_MODE_KEY):
    model_def = active_model.get_model_definition()
    initial_doc = model_def.model_dump(mode="json", by_alias=True)

    def _close_editor() -> None:
        st.session_state.pop(_EDITOR_MODE_KEY, None)
        _discard_preview()

    render_model_editor(
        initial_doc=initial_doc,
        source_label=selected_label,
        on_close=_close_editor,
    )

    doc = get_current_doc()
    can_try = isinstance(validate_doc(doc), Model) if doc is not None else False
    if try_button_slot.button(
        "Try in Calculator",
        use_container_width=True,
        key="try_in_calculator_btn",
        disabled=not can_try,
        help=(
            "Try your in-progress changes in the Calculator. Nothing is saved."
            if can_try
            else "Fix the validation errors below before trying this model."
        ),
    ):
        if _activate_preview(selected_label):
            st.session_state.pop(_EDITOR_MODE_KEY, None)
            st.rerun()

    st.stop()

preview_model = st.session_state.get(_PREVIEW_MODEL_KEY)
preview_label = st.session_state.get(_PREVIEW_LABEL_KEY)
using_preview = preview_model is not None and preview_label == selected_label
if using_preview and preview_model is not None:
    active_model = preview_model
    st.warning(
        "You're trying an unsaved, edited version of this model. Nothing is saved yet."
    )

params = sync_active_model(selected_label)

param_col, result_col = st.columns([2, 3], gap="large")

with param_col:
    with st.container(key="parameter-panel") as parameter_panel:
        params, scenario_overrides, model_defaults_flat, has_input_errors, is_dirty = (
            render_sidebar_parameters(
                active_model,
                selected_label,
                params,
                container=parameter_panel,
            )
        )

        # Keep the URL in sync with current parameter values.
        write_url_params(selected_label, params, scenario_overrides)

        typed_params = None
        if not has_input_errors:
            try:
                typed_params = build_typed_params(
                    active_model, model_defaults_flat, params
                )
            except ValidationError as exc:
                render_validation_error(selected_label, exc, container=parameter_panel)
                has_input_errors = True

        # Keep both preset actions in the same keyed row so sidebar CSS can align them.
        with st.container(key="param-actions-row"):
            btn_col1, btn_col2 = st.columns(2, gap="small", vertical_alignment="top")

        with btn_col1:
            if typed_params is not None:
                render_parameter_export_modal(
                    active_model.human_name(),
                    typed_params.model_dump(),
                    label="Save Changes as Preset",
                    disabled=not is_dirty,
                    pydantic_model=type(typed_params),
                    container=btn_col1,
                )
            else:
                st.button(
                    "Save Changes as Preset", disabled=True, use_container_width=True
                )

        def _handle_reset() -> None:
            model_label = cast(str, selected_label)  # Safe: checked above
            reset_parameters_to_defaults(
                model_defaults_flat,
                params,
                model_label,
                param_specs=active_model.parameter_specs,
            )
            default_scenarios = active_model.default_scenarios
            if default_scenarios:
                reset_scenario_state(
                    model_label,
                    default_scenarios,
                    active_model.scenario_parameter_specs or {},
                )

        btn_col2.button(
            "Reset to Preset",
            on_click=_handle_reset,
            use_container_width=True,
            disabled=not is_dirty,
        )

        st.divider()
        run_clicked = st.button(
            "Run Simulation", disabled=has_input_errors, width="stretch", type="primary"
        )

with result_col:
    trigger_print_if_requested()

    if typed_params is None:
        st.warning("Fix parameter errors to enable simulation.")
        st.stop()

    if run_clicked:
        with st.spinner(f"Running {selected_label}..."):
            run_output = active_model.run(
                typed_params, scenario_overrides=scenario_overrides
            )
        set_run_output(run_output)
        st.rerun()

    renderer = get_report_renderer(active_model)
    _HINT = "This report has not been filled, since your simulation has not been run. Run the simulation to see the results here."

    with st.container(key="results-report"):
        if has_results():
            renderer.render(get_run_output())
        else:
            renderer.render(None, hint=_HINT)

    st.divider()
    render_pdf_export_button(container=result_col)
