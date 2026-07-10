from __future__ import annotations

import hashlib
import re
from typing import TYPE_CHECKING, Any

import streamlit as st
from pydantic import BaseModel, ValidationError

from epicc.formats import VALID_PARAMETER_SUFFIXES
from epicc.model.base import BaseSimulationModel
from epicc.model.parameters import load_model_params, parse_preset_from_file
from epicc.model.schema import Preset, Scenario, ScenarioVars
from epicc.ui.state import (
    clear_results,
    get_active_param_identity,
    reset_params,
    set_active_param_identity,
)
from epicc.ui.preset_keys import (
    _FILE_PRESET_KEY_PREFIX,
    _PRESET_INLINE_ADD_CTR_KEY_PREFIX,
    _PRESET_INLINE_ADD_SEL_KEY_PREFIX,
    _PRESET_STACK_KEY_PREFIX,
)

# Avoid circular import — import lazily where needed
# from epicc.ui.export import render_parameter_export_modal

if TYPE_CHECKING:
    from epicc.model.schema import Parameter, ParameterGroup


def _build_help_text(spec: Parameter) -> str | None:
    """Build tooltip text from a Parameter schema object."""
    parts: list[str] = []
    if spec.description:
        parts.append(spec.description)
    if spec.type == "enum" and spec.options:
        opt_lines = "\n".join(f"- {k}: {v}" for k, v in spec.options.items())
        parts.append(f"Options:\n{opt_lines}")
    if spec.unit:
        parts.append(f"Unit: {spec.unit}")
    if spec.references:
        ref_lines = "\n".join(f"{i}. {r}" for i, r in enumerate(spec.references, 1))
        parts.append(f"References:\n{ref_lines}")
    return "\n\n".join(parts) or None


def _native_value(value: Any, spec: Parameter) -> Any:
    """Coerce a value to the native Python type declared by the spec."""
    try:
        if spec.type == "integer":
            return int(float(value))
        if spec.type == "number":
            return float(value)
        if spec.type == "boolean":
            if isinstance(value, str):
                return value.lower() not in ("false", "0", "no", "")
            return bool(value)
    except (ValueError, TypeError):
        pass
    return str(value)


def _render_spec_widget(
    param_id: str,
    spec: Parameter,
    default_value: Any,
    widget_key: str,
    params: dict[str, Any] | None,
    container: Any,
) -> None:
    """Render a typed widget for a parameter with a full schema spec.

    When *params* is not ``None`` the widget value is stored in
    ``params[param_id]``.  Pass ``None`` when the caller only needs
    Streamlit session-state (e.g. the scenario editor).
    """
    display_label = spec.label
    help_text = _build_help_text(spec)

    if spec.type == "boolean":
        native_default = _native_value(default_value, spec)
        if widget_key in st.session_state:
            result = container.checkbox(display_label, key=widget_key, help=help_text)
        else:
            result = container.checkbox(
                display_label, value=native_default, key=widget_key, help=help_text
            )

    elif spec.type in ("integer", "number"):
        is_int = spec.type == "integer"
        coerce = int if is_int else float
        native_default = coerce(_native_value(default_value, spec))

        kwargs: dict[str, Any] = {
            "label": display_label,
            "key": widget_key,
            "help": help_text,
        }
        if is_int:
            kwargs["step"] = 1
        if spec.min is not None:
            kwargs["min_value"] = coerce(spec.min)
        if spec.max is not None:
            kwargs["max_value"] = coerce(spec.max)
        if widget_key not in st.session_state:
            kwargs["value"] = native_default

        result = container.number_input(**kwargs)

    elif spec.type == "enum" and spec.options:
        option_keys = list(spec.options.keys())
        selectbox_kwargs: dict[str, Any] = {
            "label": display_label,
            "options": option_keys,
            "format_func": lambda v, _m=spec.options: _m.get(v, v),
            "key": widget_key,
            "help": help_text,
        }
        if widget_key not in st.session_state:
            try:
                selectbox_kwargs["index"] = option_keys.index(str(default_value))
            except ValueError:
                selectbox_kwargs["index"] = 0
        result = container.selectbox(**selectbox_kwargs)

    else:
        # string
        if widget_key in st.session_state:
            result = container.text_input(display_label, key=widget_key, help=help_text)
        else:
            result = container.text_input(
                display_label,
                value=str(default_value),
                key=widget_key,
                help=help_text,
            )

    if params is not None:
        params[param_id] = result


def _render_param(
    param_id: str,
    default_value: Any,
    widget_key: str,
    params: dict[str, Any],
    container: Any,
    spec: Parameter | None,
) -> None:
    """Render a single parameter widget, with or without a spec."""
    if spec is not None:
        _render_spec_widget(
            param_id, spec, default_value, widget_key, params, container
        )
    elif widget_key in st.session_state:
        params[param_id] = container.text_input(param_id, key=widget_key)
    else:
        params[param_id] = container.text_input(
            param_id,
            value=str(default_value) if default_value is not None else "",
            key=widget_key,
        )


def _collect_group_param_ids(nodes: list) -> set[str]:
    """Recursively collect all param IDs in a group tree."""
    ids: set[str] = set()
    for node in nodes:
        if isinstance(node, str):
            ids.add(node)
        else:
            ids.update(_collect_group_param_ids(node.children))
    return ids


def _render_group_node(
    node: str | ParameterGroup,
    param_specs: dict[str, Parameter],
    param_defaults: dict[str, Any],
    params: dict[str, Any],
    model_id: str,
    container: Any,
    depth: int,
) -> None:
    """Recursively render a group node or a leaf param ID."""
    if isinstance(node, str):
        param_id = node
        if param_id not in param_defaults:
            return
        default_value = param_defaults[param_id]
        widget_key = f"{model_id}:{param_id}"
        spec = param_specs.get(param_id)
        _render_param(param_id, default_value, widget_key, params, container, spec)
    else:
        # It's a ParameterGroup
        if depth == 0:
            # Top-level groups become sidebar expanders
            child_container = container.expander(
                node.label,
                expanded=False,
                key=f"{model_id}:expander:{node.label}",
            )
        else:
            # Nested groups: Streamlit doesn't support nested expanders, so render
            # a bold markdown sub-header inside the current container instead
            container.markdown(f"**{node.label}**")
            child_container = container

        for child in node.children:
            _render_group_node(
                child,
                param_specs,
                param_defaults,
                params,
                model_id,
                child_container,
                depth + 1,
            )


def _set_param_widget_state(
    widget_key: str,
    param_id: str,
    value: Any,
    params: dict[str, Any],
    spec: Parameter | None = None,
) -> None:
    native = _native_value(value, spec) if spec is not None else str(value)
    st.session_state[widget_key] = native
    params[param_id] = native


def reset_parameters_to_defaults(
    param_dict: dict[str, Any],
    params: dict[str, Any],
    model_id: str,
    param_specs: dict[str, Parameter] | None = None,
) -> None:
    for param_id, value in param_dict.items():
        spec = param_specs.get(param_id) if param_specs else None
        _set_param_widget_state(f"{model_id}:{param_id}", param_id, value, params, spec)


def render_parameters_with_indent(
    param_dict: dict[str, Any],
    params: dict[str, Any],
    model_id: str,
    param_specs: dict[str, Parameter] | None = None,
    param_groups: list,
    container: Any = None,
) -> None:
    rc = container if container is not None else st
    specs = param_specs or {}
    grouped_ids = _collect_group_param_ids(param_groups)
    for param_id, default_value in param_dict.items():
        if param_id not in grouped_ids:
            widget_key = f"{model_id}:{param_id}"
            spec = specs.get(param_id)
            _render_param(param_id, default_value, widget_key, params, rc, spec)
    for node in param_groups:
        _render_group_node(node, specs, param_dict, params, model_id, rc, depth=0)


def render_validation_error(
    model_name: str, exc: ValidationError, *, container: Any = None
) -> None:
    target = container if container is not None else st
    issues = exc.errors()
    issue_count = len(issues)
    target.error(f"Parameters do not match {model_name} schema ({issue_count} issues).")

    with target.expander("Validation details", expanded=False):
        preview_count = 8
        for issue in issues[:preview_count]:
            loc_parts = issue.get("loc", [])
            path = " > ".join(str(p) for p in loc_parts) if loc_parts else "(root)"
            st.write(f"- {path}: {issue.get('msg', 'Invalid value')}")
        if issue_count > preview_count:
            st.caption(f"...and {issue_count - preview_count} more.")

        safe_name = re.sub(r"[^a-z0-9]+", "_", model_name.lower()).strip("_")
        full_details = exc.json(indent=2)
        digest = hashlib.sha1(full_details.encode()).hexdigest()[:10]
        scope = "panel" if container is not None else "main"
        st.text_area(
            "Full details (copyable)",
            value=full_details,
            height=180,
            key=f"{safe_name}_{scope}_validation_text_{digest}",
        )
        st.download_button(
            "Download full error details",
            data=full_details,
            file_name=f"{safe_name}_validation_error.json",
            mime="application/json",
            key=f"{safe_name}_{scope}_validation_download_{digest}",
        )


def build_typed_params(
    model: BaseSimulationModel,
    model_defaults_flat: dict[str, Any],
    params: dict[str, Any],
) -> BaseModel:
    payload = {key: params.get(key, value) for key, value in model_defaults_flat.items()}
    return model.parameter_model().model_validate(payload)


_MAX_SCENARIOS = 10
_MIN_SCENARIOS = 1


def _scenario_count_key(model_key: str) -> str:
    return f"{model_key}__scen_count"


def _scenario_ids_key(model_key: str) -> str:
    return f"{model_key}__scen_ids"


def _scenario_label_key(model_key: str, idx: int) -> str:
    return f"{model_key}:scen_{idx}:label"


def _scenario_var_key(model_key: str, idx: int, var_name: str) -> str:
    return f"{model_key}:scen_{idx}:{var_name}"


def _init_scenario_state(
    model_key: str,
    defaults: list[Scenario],
    specs: dict[str, Parameter],
) -> None:
    """Populate session-state entries for the scenario editor from defaults."""
    cnt_key = _scenario_count_key(model_key)
    ids_key = _scenario_ids_key(model_key)
    st.session_state[cnt_key] = len(defaults)
    st.session_state[ids_key] = [s.id for s in defaults]
    for i, scen in enumerate(defaults):
        st.session_state[_scenario_label_key(model_key, i)] = scen.label
        vars_dict = scen.vars.model_dump()
        for var_name, spec in specs.items():
            val = vars_dict.get(var_name, spec.default)
            st.session_state[_scenario_var_key(model_key, i, var_name)] = _native_value(
                val, spec
            )


def reset_scenario_state(
    model_key: str,
    defaults: list[Scenario],
    specs: dict[str, Parameter],
) -> None:
    """Reset scenario editor back to model defaults (clearing any extra scenarios)."""
    # Clear all existing scenario widget keys
    prefix = f"{model_key}:scen_"
    for key in list(st.session_state.keys()):
        if isinstance(key, str) and key.startswith(prefix):
            del st.session_state[key]
    _init_scenario_state(model_key, defaults, specs)


def _collect_scenario_overrides(
    model_key: str,
    specs: dict[str, Parameter],
) -> list[Scenario]:
    """Build Scenario objects from current session-state widget values."""
    count = st.session_state.get(_scenario_count_key(model_key), 0)
    ids = st.session_state.get(_scenario_ids_key(model_key), [])
    overrides: list[Scenario] = []
    for i in range(count):
        label = st.session_state.get(
            _scenario_label_key(model_key, i), f"Scenario {i + 1}"
        )
        scen_id = ids[i] if i < len(ids) else f"custom_{i}"
        var_dict: dict[str, Any] = {}
        for var_name, spec in specs.items():
            var_dict[var_name] = st.session_state.get(
                _scenario_var_key(model_key, i, var_name), spec.default
            )
        overrides.append(
            Scenario(id=scen_id, label=label, vars=ScenarioVars(**var_dict))
        )
    return overrides


def _render_scenario_editor(
    model: BaseSimulationModel,
    model_key: str,
    container: Any,
) -> list[Scenario] | None:
    """Render the scenario editor and return the current scenario list."""
    default_scenarios = model.default_scenarios
    if not default_scenarios:
        return None

    specs: dict[str, Parameter] = model.scenario_parameter_specs or {}

    cnt_key = _scenario_count_key(model_key)
    ids_key = _scenario_ids_key(model_key)

    # First-time initialization
    if cnt_key not in st.session_state:
        _init_scenario_state(model_key, default_scenarios, specs)

    count: int = st.session_state[cnt_key]
    ids: list[str] = st.session_state[ids_key]

    with container.expander("Scenarios", expanded=False):
        st.caption("Configure scenario labels and parameters")

        for i in range(count):
            st.markdown(f"**Scenario {i + 1}**")

            # Label input
            lbl_key = _scenario_label_key(model_key, i)
            st.text_input("Label", key=lbl_key)

            # Variable inputs (using the same typed widgets as parameters)
            for var_name, spec in specs.items():
                var_key = _scenario_var_key(model_key, i, var_name)
                _render_spec_widget(var_name, spec, spec.default, var_key, None, st)

            if i < count - 1:
                st.divider()

        # Add / Remove buttons
        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            if st.button(
                "➕ Add Scenario",
                disabled=count >= _MAX_SCENARIOS,
                key=f"{model_key}__add_scen",
            ):
                new_idx = count
                new_id = f"custom_{new_idx}"
                st.session_state[cnt_key] = count + 1
                st.session_state[ids_key] = ids + [new_id]
                st.session_state[_scenario_label_key(model_key, new_idx)] = (
                    f"Scenario {new_idx + 1}"
                )
                for var_name, spec in specs.items():
                    st.session_state[
                        _scenario_var_key(model_key, new_idx, var_name)
                    ] = _native_value(spec.default, spec)
                st.rerun()
        with btn_col2:
            if st.button(
                "➖ Remove Scenario",
                disabled=count <= _MIN_SCENARIOS,
                key=f"{model_key}__rm_scen",
            ):
                last = count - 1
                st.session_state[cnt_key] = last
                st.session_state[ids_key] = ids[:last]
                # Clear widget keys for the removed scenario
                for key in list(st.session_state.keys()):
                    if isinstance(key, str) and key.startswith(
                        f"{model_key}:scen_{last}:"
                    ):
                        del st.session_state[key]
                st.rerun()

    return _collect_scenario_overrides(model_key, specs)


def _compute_dirty_state(
    model_defaults: dict[str, Any],
    model_id: str,
    param_specs: dict[str, Parameter] | None,
) -> bool:
    """Return True if any widget in session state differs from its model default."""
    specs = param_specs or {}
    for key, default_val in model_defaults.items():
        widget_key = f"{model_id}:{key}"
        if widget_key not in st.session_state:
            continue
        current = st.session_state[widget_key]
        spec = specs.get(key)
        native_default = (
            _native_value(default_val, spec)
            if spec is not None
            else (str(default_val) if default_val is not None else "")
        )
        if current != native_default:
            return True
    return False


def _compute_scenario_dirty_state(
    model_id: str,
    defaults: list[Scenario],
    specs: dict[str, Parameter],
) -> bool:
    """Return True if scenario count, labels, or vars differ from defaults."""
    count = st.session_state.get(_scenario_count_key(model_id), 0)
    if count != len(defaults):
        return True
    for i, scen in enumerate(defaults):
        if st.session_state.get(_scenario_label_key(model_id, i)) != scen.label:
            return True
        vars_dict = scen.vars.model_dump()
        for var_name, spec in specs.items():
            default_val = _native_value(vars_dict.get(var_name, spec.default), spec)
            if st.session_state.get(_scenario_var_key(model_id, i, var_name)) != default_val:
                return True
    return False

def _render_preset_controls_inline(
    model: BaseSimulationModel,
    model_key: str,
    ct: Any,
) -> tuple[list[str], Preset | None]:
    """Render inline (non-modal) preset controls inside *ct*.

    Returns ``(active_stack, file_preset)`` reflecting the current state.
    All mutations write directly to session state and trigger ``st.rerun()``.
    """
    stack_key = _PRESET_STACK_KEY_PREFIX + model_key
    file_preset_key = _FILE_PRESET_KEY_PREFIX + model_key
    add_ctr_key = _PRESET_INLINE_ADD_CTR_KEY_PREFIX + model_key

    model_presets: list[Preset] = model.presets or []

    file_preset_data: dict[str, Any] | None = st.session_state.get(file_preset_key)
    file_preset: Preset | None = (
        Preset(
            id="_file_",
            label=file_preset_data["label"],
            params=file_preset_data["params"],
        )
        if file_preset_data is not None
        else None
    )

    all_presets: list[Preset] = (
        [file_preset] if file_preset is not None else []
    ) + model_presets
    all_preset_by_id: dict[str, Preset] = {p.id: p for p in all_presets}

    active_stack: list[str] = [
        pid
        for pid in st.session_state.get(stack_key, [])
        if pid in all_preset_by_id
    ]

    has_anything = bool(all_presets)
    if not has_anything:
        return active_stack, file_preset

    with ct.container():
        st.caption("Presets")

        # --- Add preset selectbox ---
        available = [p for p in all_presets if p.id not in active_stack]
        if available:
            add_ctr: int = st.session_state.get(add_ctr_key, 0)
            add_sel_key = f"{_PRESET_INLINE_ADD_SEL_KEY_PREFIX}{model_key}_{add_ctr}"

            chosen = st.selectbox(
                "Add preset",
                options=[None] + [p.id for p in available],
                format_func=lambda x: "Select..."
                if x is None
                else all_preset_by_id[x].label,
                index=0,
                key=add_sel_key,
            )
            if chosen is not None:
                st.session_state[stack_key] = active_stack + [chosen]
                st.session_state[add_ctr_key] = add_ctr + 1
                del st.session_state[add_sel_key]
                st.rerun()

        # --- File uploader (load a preset from a saved file) ---
        uploaded = st.file_uploader(
            "Add preset from file",
            type=sorted(VALID_PARAMETER_SUFFIXES),
            key=f"_file_up_{model_key}",
            label_visibility="collapsed",
        )
        if uploaded is not None:
            new_hash = hashlib.sha1(uploaded.getvalue()).hexdigest()
            existing = st.session_state.get(file_preset_key)
            if existing is None or existing["hash"] != new_hash:
                try:
                    parsed = parse_preset_from_file(
                        uploaded.name, uploaded, model.parameter_model()
                    )
                    st.session_state[file_preset_key] = {
                        "label": uploaded.name,
                        "params": parsed,
                        "hash": new_hash,
                    }
                    st.rerun()
                except (ValidationError, ValueError) as exc:
                    st.error(f"Could not read file: {exc}")

        if file_preset is not None:
            col_info, col_add = st.columns([3, 2])
            col_info.caption(f"File: {file_preset.label}")
            if "_file_" not in active_stack:
                if col_add.button(
                    "Add to stack", key=f"_file_add_{model_key}", use_container_width=True
                ):
                    st.session_state[stack_key] = ["_file_"] + active_stack
                    st.rerun()

        # --- Active stack list ---
        if active_stack:
            st.caption("Preset stack")
            for i, pid in enumerate(active_stack):
                preset = all_preset_by_id.get(pid)
                if preset is None:
                    continue
                col_lbl, col_up, col_dn, col_rm = st.columns([4, 1, 1, 1])
                col_lbl.write(preset.label)
                if col_up.button(
                    "↑",
                    key=f"_pup_{model_key}_{pid}",
                    disabled=(i == 0),
                ):
                    new = list(active_stack)
                    new[i], new[i - 1] = new[i - 1], new[i]
                    st.session_state[stack_key] = new
                    st.rerun()
                if col_dn.button(
                    "↓",
                    key=f"_pdn_{model_key}_{pid}",
                    disabled=(i == len(active_stack) - 1),
                ):
                    new = list(active_stack)
                    new[i], new[i + 1] = new[i + 1], new[i]
                    st.session_state[stack_key] = new
                    st.rerun()
                if col_rm.button("×", key=f"_prm_{model_key}_{pid}"):
                    st.session_state[stack_key] = [
                        p for p in active_stack if p != pid
                    ]
                    st.rerun()

    return active_stack, file_preset


def render_sidebar_parameters(
    model: BaseSimulationModel,
    model_key: str,
    params: dict[str, Any],
    *,
    container: Any = None,
) -> tuple[dict[str, Any], list[Scenario] | None, dict[str, Any], bool, bool]:
    """Render the full parameter panel for model inside container.

    Returns ``(params, scenario_overrides, model_defaults, has_input_errors, is_dirty)``.
    """
    ct = container if container is not None else st

    # --- Inline preset section (above parameters) ---
    active_stack, file_preset = _render_preset_controls_inline(model, model_key, ct)

    file_preset_data: dict[str, Any] | None = st.session_state.get(
        _FILE_PRESET_KEY_PREFIX + model_key
    )
    all_presets: list[Preset] = (
        [file_preset] if file_preset is not None else []
    ) + (model.presets or [])
    all_preset_by_id: dict[str, Preset] = {p.id: p for p in all_presets}

    file_hash_in_stack = (
        file_preset_data["hash"]
        if file_preset_data is not None and "_file_" in active_stack
        else None
    )
    if active_stack:
        param_identity: tuple = (
            "preset_stack",
            tuple(active_stack),
            file_hash_in_stack,
        )
    else:
        param_identity = ("default", None, 0, None)

    should_refresh = False
    if get_active_param_identity() != param_identity:
        set_active_param_identity(param_identity)
        params = reset_params()
        clear_results()
        should_refresh = True

    try:
        merged_preset_params: dict[str, Any] | None = None
        if active_stack:
            _merged: dict[str, Any] = {}
            for _pid in reversed(active_stack):
                _p = all_preset_by_id.get(_pid)
                if _p is not None:
                    _merged = {**_merged, **_p.params}
            merged_preset_params = _merged
        model_defaults = load_model_params(
            model,
            preset_params=merged_preset_params,
        )
    except ValidationError as exc:
        render_validation_error(model.human_name(), exc, container=ct)
        return params, None, {}, True, False
    except ValueError as exc:
        ct.error(f"Could not read parameter file for {model.human_name()}: {exc}")
        return params, None, {}, True, False

    if not model_defaults:
        ct.info("No default parameters defined for this model.")
        return params, None, {}, True, False

    # Handle refresh when preset changes — reset parameters and scenarios to defaults
    if should_refresh:
        reset_parameters_to_defaults(
            model_defaults, params, model_key, param_specs=model.parameter_specs
        )
        default_scenarios = model.default_scenarios
        if default_scenarios:
            specs: dict[str, Parameter] = model.scenario_parameter_specs or {}
            reset_scenario_state(model_key, default_scenarios, specs)

    ct.divider()
    ct.caption("Parameters")

    # Scenario editor (replaces the old label-only "Output Scenario Headers")
    scenario_overrides = _render_scenario_editor(model, model_key, ct)

    render_parameters_with_indent(
        model_defaults,
        params,
        model_id=model_key,
        param_specs=model.parameter_specs,
        param_groups=model.parameter_groups,
        container=ct,
    )

    is_dirty = _compute_dirty_state(model_defaults, model_key, model.parameter_specs)
    default_scenarios = model.default_scenarios
    if not is_dirty and default_scenarios and model.scenario_parameter_specs:
        is_dirty = _compute_scenario_dirty_state(
            model_key, default_scenarios, model.scenario_parameter_specs
        )
    return params, scenario_overrides, model_defaults, False, is_dirty
