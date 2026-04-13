from __future__ import annotations

import hashlib
import re
from typing import TYPE_CHECKING, Any

import streamlit as st
from pydantic import BaseModel, ValidationError

from epicc.formats import VALID_PARAMETER_SUFFIXES
from epicc.model.base import BaseSimulationModel
from epicc.model.parameters import load_model_params
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
        opt_lines = "\n".join(f"\u2022 {k}: {v}" for k, v in spec.options.items())
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
    """Recursively collect all param IDs referenced in a group tree."""
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
    """Reset session-state widgets and params to defaults from flattened parameter data."""
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
) -> None:
    """Render flattened parameter data as sidebar widgets.

    When *param_groups* is provided the parameters are arranged according to
    the group tree (arbitrary depth).  Top-level groups become sidebar
    expanders; deeper sub-groups render as bold sub-headers inside the
    containing expander.  Any parameters not referenced by the tree are
    rendered flat above the groups.

    When *param_groups* is None the parameters are rendered flat (legacy
    tab-indent behaviour is preserved for uploaded parameter files).
    """
    if param_groups is not None:
        specs = param_specs or {}
        # Render params not mentioned in any group first (safety-net)
        grouped_ids = _collect_group_param_ids(param_groups)
        for param_id, default_value in param_dict.items():
            if param_id not in grouped_ids:
                widget_key = f"{model_id}:{param_id}"
                spec = specs.get(param_id)
                _render_param(param_id, default_value, widget_key, params, st.sidebar, spec)

        # Render the group tree
        for node in param_groups:
            _render_group_node(node, specs, param_dict, params, model_id, st.sidebar, depth=0)
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
                _render_spec_widget(label, spec, value, widget_key, params, st.sidebar)
            elif widget_key in st.session_state:
                params[label] = st.sidebar.text_input(label, key=widget_key)
            else:
                params[label] = st.sidebar.text_input(
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

        expander = st.sidebar.expander(label, expanded=False)
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


# ---------------------------------------------------------------------------
# Validation error display
# ---------------------------------------------------------------------------

def render_validation_error(
    model_name: str, exc: ValidationError, *, sidebar: bool
) -> None:
    target = st.sidebar if sidebar else st
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
        scope = "sidebar" if sidebar else "main"
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


# ---------------------------------------------------------------------------
# Parameter flattening / merging helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Sidebar parameter panel (file upload + reset + group widgets)
# ---------------------------------------------------------------------------

def render_sidebar_parameters(
    model: BaseSimulationModel,
    model_key: str,
    params: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, str], dict[str, Any], bool]:
    """Render the full sidebar parameter panel for *model*.

    Returns ``(params, label_overrides, model_defaults_flat, has_errors)``.
    ``has_errors`` is ``True`` when the sidebar should block the Run button.
    """
    label_overrides: dict[str, str] = {}

    # --- file upload --------------------------------------------------------
    uploaded = st.sidebar.file_uploader(
        "Optional parameter file",
        type=sorted(VALID_PARAMETER_SUFFIXES),
        help="If omitted, model defaults are used.",
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

    # --- load defaults ------------------------------------------------------
    try:
        model_defaults = load_model_params(
            model,
            uploaded_params=uploaded or None,
            uploaded_name=uploaded.name if uploaded else None,
        )
    except ValidationError as exc:
        render_validation_error(model.human_name(), exc, sidebar=True)
        return params, label_overrides, {}, True
    except ValueError as exc:
        st.sidebar.error(f"Could not read parameter file for {model.human_name()}: {exc}")
        return params, label_overrides, {}, True

    if not model_defaults:
        st.sidebar.info("No default parameters defined for this model.")
        return params, label_overrides, {}, True

    # --- reset callback -----------------------------------------------------
    current_headers = model.scenario_labels

    def _handle_reset() -> None:
        reset_parameters_to_defaults(
            model_defaults, params, model_key, param_specs=model.parameter_specs
        )
        for key, default_text in (current_headers or {}).items():
            st.session_state[f"py_label_{model_key}_{key}"] = default_text

    if should_refresh:
        _handle_reset()

    st.sidebar.button("Reset Parameters", on_click=_handle_reset)

    # --- scenario label overrides -------------------------------------------
    if current_headers:
        with st.sidebar.expander("Output Scenario Headers", expanded=False):
            st.caption("Rename the output headers")
            for key, default_text in current_headers.items():
                widget_key = f"py_label_{model_key}_{key}"
                default_label = str(default_text)
                if widget_key not in st.session_state:
                    label_overrides[key] = st.text_input(
                        f"Label for '{default_label}'",
                        value=default_label,
                        key=widget_key,
                    )
                else:
                    label_overrides[key] = st.text_input(
                        f"Label for '{default_label}'", key=widget_key
                    )

    # --- parameter widgets --------------------------------------------------
    render_parameters_with_indent(
        model_defaults,
        params,
        model_id=model_key,
        param_specs=model.parameter_specs,
        param_groups=model.parameter_groups,
    )
    return params, label_overrides, model_defaults, False

