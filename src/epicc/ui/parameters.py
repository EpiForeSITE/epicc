from __future__ import annotations

import hashlib
import re
from typing import TYPE_CHECKING, Any

import streamlit as st
from pydantic import BaseModel, ValidationError

from epicc.formats import VALID_PARAMETER_SUFFIXES
from epicc.model.base import BaseSimulationModel
from epicc.model.parameters import load_model_params
from epicc.model.schema import Scenario, ScenarioVars
from epicc.ui.state import (
    clear_results,
    get_active_param_identity,
    get_upload_hash_cache,
    reset_params,
    set_active_param_identity,
    set_upload_hash_cache,
)

if TYPE_CHECKING:
    from epicc.model.schema import Parameter, ParameterGroup


def item_level(key: str) -> int:
    return len(key) - len(key.lstrip("\t"))


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
        ref_lines = "\n".join(
            f"{i}. {r}" for i, r in enumerate(spec.references, 1)
        )
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
    params: dict[str, Any],
    container: Any,
) -> None:
    """Render a typed widget for a parameter with a full schema spec."""
    display_label = spec.label
    help_text = _build_help_text(spec)

    if spec.type == "boolean":
        native_default = _native_value(default_value, spec)
        if widget_key in st.session_state:
            params[param_id] = container.checkbox(
                display_label, key=widget_key, help=help_text
            )
        else:
            params[param_id] = container.checkbox(
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

        params[param_id] = container.number_input(**kwargs)

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
        params[param_id] = container.selectbox(**selectbox_kwargs)

    else:
        # string
        if widget_key in st.session_state:
            params[param_id] = container.text_input(
                display_label, key=widget_key, help=help_text
            )
        else:
            params[param_id] = container.text_input(
                display_label,
                value=str(default_value),
                key=widget_key,
                help=help_text,
            )


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
        _render_spec_widget(param_id, spec, default_value, widget_key, params, container)
    elif widget_key in st.session_state:
        params[param_id] = container.text_input(param_id, key=widget_key)
    else:
        params[param_id] = container.text_input(
            param_id, value=str(default_value) if default_value is not None else "", key=widget_key
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
            child_container = container.expander(node.label, expanded=False)
        else:
            # Nested groups: Streamlit doesn't support nested expanders, so render
            # a bold markdown sub-header inside the current container instead
            container.markdown(f"**{node.label}**")
            child_container = container

        for child in node.children:
            _render_group_node(
                child, param_specs, param_defaults, params, model_id, child_container, depth + 1
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
    """Reset session-state widgets and params to defaults."""
    items = list(param_dict.items())
    i = 0
    n = len(items)

    while i < n:
        key, value = items[i]
        level = item_level(key)
        label = key.strip()

        if value is not None:
            spec = param_specs.get(label) if param_specs else None
            _set_param_widget_state(f"{model_id}:{label}", label, value, params, spec)
            i += 1
            continue

        j = i + 1
        while j < n:
            subkey, subval = items[j]
            sublevel = item_level(subkey)
            if sublevel <= level:
                break
            if sublevel == level + 1 and subval is not None:
                sublabel = subkey.strip()
                spec = param_specs.get(sublabel) if param_specs else None
                _set_param_widget_state(
                    f"{model_id}:{label}:{sublabel}",
                    sublabel,
                    subval,
                    params,
                    spec,
                )
            j += 1

        i = j


def render_parameters_with_indent(
    param_dict: dict[str, Any],
    params: dict[str, Any],
    model_id: str,
    param_specs: dict[str, Parameter] | None = None,
    param_groups: list | None = None,
    container: Any = None,
) -> None:
    """Render flattened parameter data as widgets inside container."""
    rc = container if container is not None else st
    if param_groups is not None:
        specs = param_specs or {}
        # Render params not mentioned in any group first (safety-net)
        grouped_ids = _collect_group_param_ids(param_groups)
        for param_id, default_value in param_dict.items():
            if param_id not in grouped_ids:
                widget_key = f"{model_id}:{param_id}"
                spec = specs.get(param_id)
                _render_param(param_id, default_value, widget_key, params, rc, spec)

        # Render the group tree
        for node in param_groups:
            _render_group_node(node, specs, param_dict, params, model_id, rc, depth=0)
        return

    # --- Legacy flat / tab-indented rendering (no groups defined) ---
    items = list(param_dict.items())
    i = 0
    n = len(items)

    while i < n:
        key, value = items[i]
        level = item_level(key)
        label = key.strip()

        if value is not None:
            widget_key = f"{model_id}:{label}"
            spec = param_specs.get(label) if param_specs else None
            if spec is not None:
                _render_spec_widget(label, spec, value, widget_key, params, rc)
            elif widget_key in st.session_state:
                params[label] = rc.text_input(label, key=widget_key)
            else:
                params[label] = rc.text_input(
                    label, value=str(value), key=widget_key
                )
            i += 1
            continue

        children: list[tuple[str, Any]] = []
        j = i + 1
        while j < n:
            subkey, subval = items[j]
            sublevel = item_level(subkey)
            if sublevel <= level:
                break
            if sublevel == level + 1 and subval is not None:
                children.append((subkey.strip(), subval))
            j += 1

        expander = rc.expander(label, expanded=False)
        for sublabel, subval in children:
            widget_key = f"{model_id}:{label}:{sublabel}"
            spec = param_specs.get(sublabel) if param_specs else None
            if spec is not None:
                _render_spec_widget(sublabel, spec, subval, widget_key, params, expander)
            elif widget_key in st.session_state:
                params[sublabel] = expander.text_input(sublabel, key=widget_key)
            else:
                params[sublabel] = expander.text_input(
                    sublabel, value=str(subval), key=widget_key
                )

        i = j


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
        else:
            parent[label] = value
    return root


def _merge_sidebar_values(
    nested_defaults: dict[str, Any], params: dict[str, Any]
) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for key, value in nested_defaults.items():
        if isinstance(value, dict):
            merged[key] = _merge_sidebar_values(value, params)
        else:
            merged[key] = params.get(key, value)
    return merged


def build_typed_params(
    model: BaseSimulationModel,
    model_defaults_flat: dict[str, Any],
    params: dict[str, Any],
) -> BaseModel:
    nested = _unflatten_indented_params(model_defaults_flat)
    payload = _merge_sidebar_values(nested, params)
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
            st.session_state[_scenario_var_key(model_key, i, var_name)] = (
                _native_value(val, spec)
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

    # First-time initialisation
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
                throwaway: dict[str, Any] = {}
                _render_spec_widget(
                    var_name, spec, spec.default, var_key, throwaway, st
                )

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
                    if isinstance(key, str) and key.startswith(f"{model_key}:scen_{last}:"):
                        del st.session_state[key]
                st.rerun()

    return _collect_scenario_overrides(model_key, specs)


def render_sidebar_parameters(
    model: BaseSimulationModel,
    model_key: str,
    params: dict[str, Any],
    *,
    container: Any = None,
) -> tuple[dict[str, Any], list[Scenario] | None, dict[str, Any], bool]:
    """Render the full parameter panel for model inside container."""
    ct = container if container is not None else st

    uploaded = ct.file_uploader(
        "Load parameters from file",
        type=sorted(VALID_PARAMETER_SUFFIXES),
        accept_multiple_files=False,
    )

    if uploaded:
        cheap_id = (uploaded.name, uploaded.size)
        cached = get_upload_hash_cache()
        if cached is not None and cached[0] == cheap_id:
            upload_hash = cached[1]
        else:
            upload_hash = hashlib.sha1(uploaded.getvalue()).hexdigest()
            set_upload_hash_cache((cheap_id, upload_hash))
        param_identity: tuple = ("upload", uploaded.name, uploaded.size, upload_hash)
    else:
        param_identity = ("default", None, 0, None)

    should_refresh = False
    if get_active_param_identity() != param_identity:
        set_active_param_identity(param_identity)
        params = reset_params()
        clear_results()
        should_refresh = True

    try:
        model_defaults = load_model_params(
            model,
            uploaded_params=uploaded or None,
            uploaded_name=uploaded.name if uploaded else None,
        )
    except ValidationError as exc:
        render_validation_error(model.human_name(), exc, container=ct)
        return params, None, {}, True
    except ValueError as exc:
        ct.error(f"Could not read parameter file for {model.human_name()}: {exc}")
        return params, None, {}, True

    if not model_defaults:
        ct.info("No default parameters defined for this model.")
        return params, None, {}, True

    # Handle refresh when new file uploaded - reset parameters to defaults
    if should_refresh:
        reset_parameters_to_defaults(
            model_defaults, params, model_key, param_specs=model.parameter_specs
        )
        # Reset scenarios back to model defaults
        default_scenarios = model.default_scenarios
        if default_scenarios:
            specs: dict[str, Parameter] = model.scenario_parameter_specs or {}
            reset_scenario_state(model_key, default_scenarios, specs)

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

    return params, scenario_overrides, model_defaults, False

