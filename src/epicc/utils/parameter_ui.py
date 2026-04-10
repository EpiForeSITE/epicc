from typing import Any

import streamlit as st


def item_level(key: str) -> int:
    return len(key) - len(key.lstrip("\t"))


def _set_param_and_widget(
    widget_key: str, params_key: str, value: Any, params: dict[str, str]
) -> None:
    value_as_str = str(value)
    st.session_state[widget_key] = value_as_str
    params[params_key] = value_as_str


def reset_parameters_to_defaults(
    param_dict: dict[str, Any], params: dict[str, str], model_id: str
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
            _set_param_and_widget(f"{model_id}:{label}", label, value, params)
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
                _set_param_and_widget(
                    f"{model_id}:{label}:{sublabel}",
                    sublabel,
                    subval,
                    params,
                )
            j += 1

        i = j


def render_parameters_with_indent(
    param_dict: dict[str, Any], params: dict[str, str], model_id: str
) -> None:
    """Render flattened parameter data as top-level controls and one-level nested expanders."""

    items = list(param_dict.items())
    i = 0
    n = len(items)

    while i < n:
        key, value = items[i]
        level = item_level(key)
        label = key.strip()

        if value is not None:
            widget_key = f"{model_id}:{label}"
            if widget_key in st.session_state:
                params[label] = st.sidebar.text_input(label, key=widget_key)
                i += 1
                continue

            params[label] = st.sidebar.text_input(
                label,
                value=str(value),
                key=widget_key,
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

        with st.sidebar.expander(label, expanded=False):
            for sublabel, subval in children:
                widget_key = f"{model_id}:{label}:{sublabel}"
                if widget_key in st.session_state:
                    params[sublabel] = st.text_input(sublabel, key=widget_key)
                    continue

                params[sublabel] = st.text_input(
                    sublabel,
                    value=str(subval),
                    key=widget_key,
                )

        i = j
