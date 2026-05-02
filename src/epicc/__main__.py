from typing import cast

import streamlit as st
from pydantic import ValidationError

from epicc.model.base import BaseSimulationModel
from epicc.model.models import get_all_models
from epicc.ui.export import (
    render_parameter_export_modal,
    render_pdf_export_button,
    render_docx_export_button,
    trigger_print_if_requested,
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
    has_results,
    get_run_output,
    initialize_state,
    set_run_output,
    sync_active_model,
)
from epicc.ui.styles import load_styles

st.set_page_config(page_title="EPICC Cost Calculator", layout="wide")
load_styles()
initialize_state()

all_models = get_all_models()
model_registry: dict[str, BaseSimulationModel] = {m.human_name(): m for m in all_models}

hdr_title, hdr_model = st.columns([3, 3])
hdr_title.title("EPICC Cost Calculator")
selected_label: str | None = hdr_model.selectbox(
    "Model",
    list(model_registry),
    index=None,
    placeholder="Select a model...",
    label_visibility="collapsed",
)

st.divider()

if selected_label is None:
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
params = sync_active_model(selected_label)

param_col, result_col = st.columns([2, 3], gap="large")

with param_col:
    params, scenario_overrides, model_defaults_flat, has_input_errors = render_sidebar_parameters(
        active_model, selected_label, params, container=param_col
    )

    typed_params = None
    if not has_input_errors:
        try:
            typed_params = build_typed_params(active_model, model_defaults_flat, params)
        except ValidationError as exc:
            render_validation_error(selected_label, exc, container=param_col)
            has_input_errors = True

    # Reset and Save Parameters buttons side by side 
    button_col1, button_col2 = st.columns(2)
    
    # Reset Parameters button
    def _handle_reset() -> None:
        model_label = cast(str, selected_label)  # Safe because we checked above
        reset_parameters_to_defaults(
            model_defaults_flat, params, model_label, param_specs=active_model.parameter_specs
        )
        # Reset scenarios back to model defaults
        default_scenarios = active_model.default_scenarios
        if default_scenarios:
            reset_scenario_state(
                model_label,
                default_scenarios,
                active_model.scenario_parameter_specs or {},
            )
    
    with button_col1:
        st.button("Reset Parameters", on_click=_handle_reset, width='stretch')
    
    # Save Parameters button (only enabled when parameters are valid)
    with button_col2:
        if typed_params is not None:
            render_parameter_export_modal(
                active_model.human_name(),
                typed_params.model_dump(),
                pydantic_model=type(typed_params),
                container=button_col2,
            )
        else:
            st.button("Save Parameters", disabled=True, width='stretch', help="Fix parameter errors first")

    st.divider()
    run_clicked = st.button(
        "Run Simulation", disabled=has_input_errors, width='stretch', type='primary'
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

    with st.container(key='results-report'):
        if has_results():
            renderer.render(get_run_output())
        else:
            renderer.render(None, hint=_HINT)

    st.divider()
    render_pdf_export_button(container=result_col)
    render_docx_export_button(
        active_model,  # pass model object, not title string
        get_run_output() if has_results() else None,
        container=result_col,
    )

