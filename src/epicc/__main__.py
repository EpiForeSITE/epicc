import streamlit as st
from pydantic import ValidationError

from epicc.model.base import BaseSimulationModel
from epicc.model.models import get_all_models
from epicc.ui.export import render_export_button, trigger_print_if_requested
from epicc.ui.parameters import (
    build_typed_params,
    render_sidebar_parameters,
    render_validation_error,
)
from epicc.ui.report import get_report_renderer
from epicc.ui.sections import render_sections
from epicc.ui.state import (
    has_results,
    get_run_output,
    initialize_state,
    set_run_output,
    sync_active_model,
)
from epicc.ui.styles import load_styles

# ---------------------------------------------------------------------------
# One-time setup
# ---------------------------------------------------------------------------

load_styles()
initialize_state()

# ---------------------------------------------------------------------------
# Model registry
# ---------------------------------------------------------------------------

all_models = get_all_models()
model_registry: dict[str, BaseSimulationModel] = {m.human_name(): m for m in all_models}

# ---------------------------------------------------------------------------
# Sidebar — model selector
# ---------------------------------------------------------------------------

st.sidebar.title("epicc Cost Calculator")
st.sidebar.header("Simulation Controls")

selected_label: str = st.sidebar.selectbox("Select Model", list(model_registry), index=0)  # type: ignore[assignment]
active_model = model_registry[selected_label]

params = sync_active_model(selected_label)

# ---------------------------------------------------------------------------
# Sidebar — parameter panel
# ---------------------------------------------------------------------------

st.sidebar.subheader("Input Parameters")

params, label_overrides, model_defaults_flat, has_input_errors = render_sidebar_parameters(
    active_model, selected_label, params
)

typed_params = None
if not has_input_errors:
    try:
        typed_params = build_typed_params(active_model, model_defaults_flat, params)
    except ValidationError as exc:
        render_validation_error(selected_label, exc, sidebar=True)
        has_input_errors = True

run_clicked = st.sidebar.button("Run Simulation", disabled=has_input_errors)
render_export_button()

# ---------------------------------------------------------------------------
# Guard: block rendering if params are invalid
# ---------------------------------------------------------------------------

if typed_params is None:
    st.error("Cannot run simulation until parameter validation errors are fixed.")
    st.stop()

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if run_clicked:
    with st.spinner(f"Running {selected_label}..."):
        run_output = active_model.run(typed_params, label_overrides=label_overrides)
    set_run_output(run_output)
    st.rerun()

# ---------------------------------------------------------------------------
# Render report
# ---------------------------------------------------------------------------

renderer = get_report_renderer(active_model)

if has_results():
    if renderer:
        renderer.render(get_run_output())
    else:
        sections = active_model.build_sections(get_run_output())
        st.title(active_model.model_title)
        render_sections(sections)
else:
    if renderer:
        renderer.render(None)
    else:
        st.info("Configure parameters in the sidebar, then click **Run Simulation**.")
    st.stop()

trigger_print_if_requested()

