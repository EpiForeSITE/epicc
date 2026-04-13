from __future__ import annotations

from typing import TYPE_CHECKING, Any

import streamlit as st

if TYPE_CHECKING:
    from epicc.model.schema import Parameter, ParameterGroup


def item_level(key: str) -> int:
    return len(key) - len(key.lstrip("\t"))


def _build_help_text(spec: Parameter) -> str | None:
    """Build tooltip text from a Parameter schema object."""
    parts: list[str] = []
    if spec.description:
        parts.append(spec.description)
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
