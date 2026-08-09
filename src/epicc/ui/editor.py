from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

import pandas as pd
import streamlit as st
from pydantic import ValidationError

from epicc.formats import opaque_to_typed
from epicc.formats.yaml import YAMLFormat
from epicc.model.schema import Model


_DOC_KEY = "editor_doc"
_SOURCE_KEY = "editor_source_label"
_WELCOME_SEEN_KEY = "editor_welcome_seen"
_ADD_FORM_REVISION_KEY = "editor_add_form_revision"
_GROUP_EDITOR_EXPANDED_KEY = "editor_group_editor_expanded"


_BLANK: dict[str, Any] = {
    "title": "",
    "description": "",
    "authors": [],
    "parameters": {},
    "equations": {},
    "groups": [],
    "scenarios": [],
    "report": [],
    "figures": [],
    "presets": [],
}

_YAML_MIME = "text/yaml"
_YAML_SUFFIX = "yaml"


@dataclass(frozen=True)
class ValidationIssue:
    """A validation problem phrased for model-editor users."""

    location: str
    message: str
    technical_detail: str


_FIELD_LABELS = {
    "authors": "Authors",
    "description": "Description",
    "equations": "Equations",
    "figures": "Figures",
    "groups": "Parameter groups",
    "parameters": "Parameters",
    "presets": "Presets",
    "report": "Report",
    "scenarios": "Scenarios",
    "title": "Model title",
}




def _doc() -> dict[str, Any]:
    return st.session_state[_DOC_KEY]


_WIDGET_KEY_PREFIXES = (
    "author_",
    "block_",
    "eq_",
    "grp_",
    "param_",
    "preset_",
    "scen_",
    "new_",
)


def _clear_widget_state() -> None:
    """Drop cached per-field widget values from a previous document.

    Widgets below are keyed by list index (e.g. ``scen_label_0``) and pass a
    fresh ``value=`` on every render, but Streamlit ignores ``value`` once a
    key already exists in session-state. Without this, switching documents
    (a new model, a fresh upload, "Reset to blank") leaves stale values
    attached to those indices, which then show up as repeated/incorrect
    labels for the new document's items.
    """
    for key in list(st.session_state.keys()):
        if isinstance(key, str) and key.startswith(_WIDGET_KEY_PREFIXES):
            del st.session_state[key]


def _set_doc(doc: dict[str, Any], source_label: str | None = None) -> None:
    st.session_state[_DOC_KEY] = doc
    st.session_state[_SOURCE_KEY] = source_label
    _clear_widget_state()


def _add_form_key(name: str) -> str:
    """Return a new widget key after each successful add action."""
    revision = st.session_state.get(_ADD_FORM_REVISION_KEY, 0)
    return f"{name}_{revision}"


def _reset_add_forms() -> None:
    """Give all add forms fresh widget identities on the next render."""
    st.session_state[_ADD_FORM_REVISION_KEY] = (
        st.session_state.get(_ADD_FORM_REVISION_KEY, 0) + 1
    )


def _init_state(
    initial_doc: dict[str, Any] | None = None,
    source_label: str | None = None,
) -> None:
    """Initialise editor state.

    If *source_label* differs from the currently loaded source the doc is
    replaced with *initial_doc* so stale edits from a previous model are not
    shown.
    """
    current_source = st.session_state.get(_SOURCE_KEY)
    if _DOC_KEY not in st.session_state or (
        source_label is not None and current_source != source_label
    ):
        _set_doc(
            deepcopy(initial_doc) if initial_doc is not None else deepcopy(_BLANK),
            source_label=source_label,
        )




def get_current_doc() -> dict[str, Any] | None:
    """Return the in-progress editor document, if the editor has been opened."""
    return st.session_state.get(_DOC_KEY)


def validate_doc(doc: dict[str, Any]) -> Model | list[ValidationIssue]:
    """Public wrapper around the editor's document validation."""
    return _validate(doc)


def _validate(doc: dict[str, Any]) -> Model | list[ValidationIssue]:
    """Return a validated ``Model`` or a list of human-readable error strings."""
    try:
        return opaque_to_typed(doc, Model)
    except ValidationError as exc:
        issues: list[ValidationIssue] = []
        for err in exc.errors():
            path = tuple(str(part) for part in err["loc"])
            field = (
                _FIELD_LABELS.get(path[0], path[0].replace("_", " ").title())
                if path
                else "Model"
            )
            location = " > ".join((field, *path[1:]))
            message = err["msg"]
            if path == ("groups",) and err["type"] == "list_type":
                message = "No parameter groups are required. Use an empty list (`[]`) or add a group."
            technical_location = " > ".join(path) if path else "(root)"
            issues.append(
                ValidationIssue(
                    location=location,
                    message=message,
                    technical_detail=f"{technical_location}: {err['msg']} [{err['type']}]",
                )
            )
        return issues
    except Exception as exc:
        return [
            ValidationIssue(
                location="Model",
                message="Could not validate this model.",
                technical_detail=str(exc),
            )
        ]




def _groups_list(doc: dict[str, Any]) -> list[Any]:
    """Return the groups list, coercing ``None`` to ``[]``."""
    return doc.get("groups") or []


def _collect_grouped_ids(groups: list[Any]) -> set[str]:
    """Recursively collect all parameter IDs referenced in a group tree."""
    ids: set[str] = set()
    for node in groups:
        if isinstance(node, str):
            ids.add(node)
        elif isinstance(node, dict):
            ids.update(_collect_grouped_ids(node.get("children", [])))
    return ids


def _group_has_marked(nodes: list[Any], marked_ids: set[str]) -> bool:
    """Return True if any leaf param ID in *nodes* is in *marked_ids*."""
    for node in nodes:
        if isinstance(node, str):
            if node in marked_ids:
                return True
        elif isinstance(node, dict):
            if _group_has_marked(node.get("children", []), marked_ids):
                return True
    return False


def _render_grouped_params(
    groups: list[Any],
    all_params: dict[str, Any],
    render_fn: Callable[[str, dict[str, Any]], None],
    depth: int = 0,
    marked_ids: set[str] | None = None,
) -> None:
    """Recursively render parameter widgets inside group containers.

    ``render_fn(param_id, params_dict)`` is called for each leaf param ID.
    """
    _marked = marked_ids or set()
    for node in groups:
        if isinstance(node, str):
            if node in all_params:
                render_fn(node, all_params)
        elif isinstance(node, dict):
            label = node.get("label", "Group")
            children = node.get("children", [])
            group_marked = _group_has_marked(children, _marked)
            display_label = f"{label} [*]" if group_marked else label
            if depth == 0:
                with st.expander(display_label, expanded=False):
                    _render_grouped_params(children, all_params, render_fn, depth + 1, marked_ids)
            else:
                st.markdown(f"**{display_label}**")
                _render_grouped_params(children, all_params, render_fn, depth + 1, marked_ids)




def _render_metadata_tab(doc: dict[str, Any]) -> None:
    doc["title"] = st.text_input("Title", value=doc.get("title", ""))
    doc["description"] = st.text_area(
        "Description", value=doc.get("description", ""), height=100
    )

    st.markdown("**Authors**")
    authors: list[dict[str, Any]] = doc.setdefault("authors", [])

    for i, author in enumerate(authors):
        c1, c2, c3 = st.columns([3, 3, 1])
        author["name"] = c1.text_input(
            "Name", value=author.get("name", ""), key=f"author_name_{i}"
        )
        author["email"] = (
            c2.text_input(
                "Email (optional)",
                value=author.get("email", "") or "",
                key=f"author_email_{i}",
            )
            or None
        )
        if c3.button("Remove", key=f"author_remove_{i}"):
            authors.pop(i)
            st.rerun()

    ac1, ac2, ac3 = st.columns([3, 3, 1])
    new_author_name = ac1.text_input(
        "Name",
        key=_add_form_key("new_author_name"),
        placeholder="e.g. Jane Doe",
        label_visibility="collapsed",
    )
    new_author_email = ac2.text_input(
        "Email (optional)",
        key=_add_form_key("new_author_email"),
        placeholder="e.g. jane@law.net",
        label_visibility="collapsed",
    )
    if ac3.button("Add", key="author_add"):
        name = new_author_name.strip()
        if name:
            authors.append({"name": name, "email": new_author_email.strip() or None})
            _reset_add_forms()
            st.rerun()




def _render_parameters_tab(doc: dict[str, Any]) -> None:
    params: dict[str, Any] = doc.setdefault("parameters", {})
    groups = _groups_list(doc)

    st.caption(
        "Each parameter needs a unique ID used in equations and scenario vars. "
        "Equation-context parameters appear in the sidebar; scenario-context "
        "parameters are set per scenario."
    )

    with st.expander("Add new parameter", expanded=False):
        new_id = st.text_input(
            "Parameter ID",
            key=_add_form_key("new_param_id"),
            placeholder="e.g. cost_per_case",
        )
        new_label = st.text_input(
            "Label (optional)",
            key=_add_form_key("new_param_label"),
            placeholder="e.g. Cost per case",
        )
        
        if st.button("Add parameter", key="param_add_btn"):
            new_id = new_id.strip()
            if not new_id:
                st.error("Parameter ID cannot be empty.")
            elif new_id in params:
                st.error(f"Parameter ID '{new_id}' already exists.")
            else:
                params[new_id] = {
                    "type": "number",
                    "label": new_label.strip(),
                    "description": None,
                    "default": 0.0,
                    "context": "equation",
                }
                _reset_add_forms()
                st.rerun()

    if groups:
        grouped_ids = _collect_grouped_ids(groups)
        ungrouped = [pid for pid in params if pid not in grouped_ids]
        if ungrouped:
            st.caption("Ungrouped parameters")
            for pid in ungrouped:
                _param_expander(params, pid)
        _render_grouped_params(
            groups,
            params,
            lambda pid, p: _param_expander(p, pid),
        )
    else:
        for pid in list(params.keys()):
            _param_expander(params, pid)

    _render_groups_editor(doc)


def _param_expander(params: dict[str, Any], param_id: str) -> None:
    spec = params[param_id]
    label = spec.get("label") or param_id
    with st.expander(f"{param_id} — {label}", expanded=False):
        _render_single_parameter(params, param_id, spec)


def _render_groups_editor(doc: dict[str, Any]) -> None:
    groups: list[Any] = doc.get("groups") or []

    with st.expander(
        "Edit parameter groups",
        expanded=st.session_state.pop(_GROUP_EDITOR_EXPANDED_KEY, False),
    ):
        st.caption(
            "Groups control how parameters are visually organised in the sidebar. "
            "Each top-level group becomes an expander. Children are parameter IDs "
            "or nested groups."
        )
        params: dict[str, Any] = doc.get("parameters", {})
        all_param_ids = list(params.keys())

        for gi, node in enumerate(groups):
            if isinstance(node, str):
                # Bare param ID at top level
                nc1, nc2 = st.columns([4, 1])
                nc1.text(f"(bare) {node}")
                if nc2.button("Remove", key=f"grp_bare_rm_{gi}"):
                    groups.pop(gi)
                    doc["groups"] = groups
                    st.session_state[_GROUP_EDITOR_EXPANDED_KEY] = True
                    st.rerun()

            elif isinstance(node, dict):
                with st.expander(node.get("label", f"Group {gi + 1}"), expanded=True):
                    if _render_group_node(node, str(gi), all_param_ids):
                        groups.pop(gi)
                        doc["groups"] = groups
                        st.session_state[_GROUP_EDITOR_EXPANDED_KEY] = True
                        st.rerun()

        gc1, gc2 = st.columns([3, 1])
        new_grp_label = gc1.text_input(
            "Group label",
            key=_add_form_key("new_grp_label"),
            placeholder="e.g. Cost parameters",
            label_visibility="collapsed",
        )
        if gc2.button("Add group", key="grp_add"):
            label = new_grp_label.strip() or "New group"
            groups.append({"label": label, "children": []})
            doc["groups"] = groups
            _reset_add_forms()
            st.session_state[_GROUP_EDITOR_EXPANDED_KEY] = True
            st.rerun()


def _render_group_node(
    group: dict[str, Any], path: str, all_param_ids: list[str]
) -> bool:
    """Render a group and return whether the caller should delete it."""
    group["label"] = st.text_input(
        "Group label", value=group.get("label", ""), key=f"grp_label_{path}"
    )
    children: list[Any] = group.setdefault("children", [])

    for child_index, child in enumerate(children):
        child_path = f"{path}_{child_index}"
        if isinstance(child, str):
            child_col, remove_col = st.columns([4, 1])
            child_col.text(child)
            if remove_col.button("Remove", key=f"grp_child_rm_{child_path}"):
                children.pop(child_index)
                st.session_state[_GROUP_EDITOR_EXPANDED_KEY] = True
                st.rerun()

        elif isinstance(child, dict):
            with st.expander(child.get("label", "Nested group"), expanded=True):
                if _render_group_node(child, child_path, all_param_ids):
                    children.pop(child_index)
                    st.session_state[_GROUP_EDITOR_EXPANDED_KEY] = True
                    st.rerun()

    direct_parameter_ids = {child for child in children if isinstance(child, str)}
    available = [pid for pid in all_param_ids if pid not in direct_parameter_ids]
    if available:
        add_param_col, add_param_btn_col = st.columns([3, 1])
        add_pid = add_param_col.selectbox(
            "Add parameter",
            available,
            key=_add_form_key(f"grp_add_pid_{path}"),
            label_visibility="collapsed",
        )
        if add_param_btn_col.button("Add parameter", key=f"grp_add_btn_{path}"):
            children.append(add_pid)
            _reset_add_forms()
            st.session_state[_GROUP_EDITOR_EXPANDED_KEY] = True
            st.rerun()

    nested_label_col, nested_add_col = st.columns([3, 1])
    nested_label = nested_label_col.text_input(
        "Nested group label",
        key=_add_form_key(f"grp_nested_label_{path}"),
        placeholder="e.g. Treatment costs",
        label_visibility="collapsed",
    )
    if nested_add_col.button("Add nested group", key=f"grp_nested_add_{path}"):
        children.append({"label": nested_label.strip() or "New group", "children": []})
        _reset_add_forms()
        st.session_state[_GROUP_EDITOR_EXPANDED_KEY] = True
        st.rerun()

    return st.button("Delete group", key=f"grp_delete_{path}", type="secondary")


def _render_single_parameter(
    params: dict[str, Any], param_id: str, spec: dict[str, Any]
) -> None:
    k = param_id

    col1, col2 = st.columns([3, 1])
    new_id = col1.text_input("ID", value=param_id, key=f"param_id_{k}")
    param_type = col2.selectbox(
        "Type",
        ["number", "integer", "boolean", "string", "enum"],
        index=["number", "integer", "boolean", "string", "enum"].index(
            spec.get("type", "number")
        ),
        key=f"param_type_{k}",
    )

    spec["type"] = param_type
    spec["label"] = st.text_input(
        "Label", value=spec.get("label", ""), key=f"param_label_{k}"
    )
    spec["description"] = (
        st.text_area(
            "Description (optional)",
            value=spec.get("description", "") or "",
            height=68,
            key=f"param_desc_{k}",
        )
        or None
    )

    c1, c2 = st.columns(2)
    spec["context"] = c1.selectbox(
        "Context",
        ["equation", "scenario"],
        index=0 if spec.get("context", "equation") == "equation" else 1,
        key=f"param_ctx_{k}",
        help=(
            "Use **equation** for one shared value, entered in the calculator "
            "sidebar and available to every scenario. Use **scenario** when "
            "each scenario needs its own value; it is entered within each "
            "scenario definition."
        ),
    )
    spec["unit"] = (
        c2.text_input(
            "Unit (optional)", value=spec.get("unit", "") or "", key=f"param_unit_{k}"
        )
        or None
    )

    if param_type in ("number", "integer"):
        mc1, mc2, mc3 = st.columns(3)
        default_val = spec.get("default", 0)
        try:
            default_val = (
                int(default_val) if param_type == "integer" else float(default_val)
            )
        except (TypeError, ValueError):
            default_val = 0 if param_type == "integer" else 0.0

        spec["default"] = mc1.number_input(
            "Default",
            value=default_val,
            step=1 if param_type == "integer" else 0.01,
            format="%d" if param_type == "integer" else "%g",
            key=f"param_default_{k}",
        )
        min_raw = spec.get("min")
        max_raw = spec.get("max")
        min_val = mc2.number_input(
            "Min (optional)",
            value=float(min_raw) if min_raw is not None else 0.0,
            key=f"param_min_{k}",
        )
        max_val = mc3.number_input(
            "Max (optional)",
            value=float(max_raw) if max_raw is not None else 0.0,
            key=f"param_max_{k}",
        )
        has_min = mc2.checkbox(
            "Set min", value=min_raw is not None, key=f"param_hasmin_{k}"
        )
        has_max = mc3.checkbox(
            "Set max", value=max_raw is not None, key=f"param_hasmax_{k}"
        )
        spec["min"] = min_val if has_min else None
        spec["max"] = max_val if has_max else None

    elif param_type == "boolean":
        spec["default"] = st.checkbox(
            "Default value",
            value=bool(spec.get("default", False)),
            key=f"param_default_{k}",
        )
        spec.pop("min", None)
        spec.pop("max", None)

    elif param_type == "string":
        spec["default"] = st.text_input(
            "Default value",
            value=str(spec.get("default", "")),
            key=f"param_default_{k}",
        )
        spec.pop("min", None)
        spec.pop("max", None)

    elif param_type == "enum":
        st.markdown("**Options**")
        options: dict[str, str] = spec.get("options") or {}
        spec["options"] = options

        opts_df = pd.DataFrame(
            [{"key": ok, "label": ov} for ok, ov in options.items()]
            if options
            else [{"key": "", "label": ""}],
            columns=["key", "label"],
        )
        edited_opts = st.data_editor(
            opts_df,
            num_rows="dynamic",
            key=f"param_opts_{k}",
            column_config={
                "key": st.column_config.TextColumn("Key", required=True),
                "label": st.column_config.TextColumn("Label"),
            },
            hide_index=True,
        )
        options.clear()
        for _, row in edited_opts.iterrows():
            key_val = str(row["key"]).strip() if row["key"] else ""
            if key_val:
                options[key_val] = str(row["label"]) if row["label"] else ""

        default_opts = list(options.keys())
        current_default = str(spec.get("default", default_opts[0] if default_opts else ""))
        try:
            default_idx = default_opts.index(current_default)
        except ValueError:
            default_idx = 0
        if default_opts:
            spec["default"] = st.selectbox(
                "Default",
                options=default_opts,
                index=default_idx,
                key=f"param_default_{k}",
            )
        spec.pop("min", None)
        spec.pop("max", None)

    st.markdown("**References** (optional)")
    refs: list[str] = spec.get("references") or []
    refs_df = pd.DataFrame(
        {"reference": refs} if refs else {"reference": pd.Series([], dtype=str)}
    )
    edited_refs = st.data_editor(
        refs_df,
        num_rows="dynamic",
        key=f"param_refs_{k}",
        column_config={
            "reference": st.column_config.TextColumn("Reference"),
        },
        hide_index=True,
    )
    spec["references"] = [
        r for r in edited_refs["reference"].tolist() if r and str(r).strip()
    ]

    st.divider()
    c_rename, c_delete = st.columns([3, 1])
    if c_rename.button("Rename / apply ID change", key=f"param_rename_{k}"):
        new_id = new_id.strip()
        if not new_id:
            st.error("ID cannot be empty.")
        elif new_id != param_id and new_id in params:
            st.error(f"ID '{new_id}' already exists.")
        elif new_id != param_id:
            items = list(params.items())
            idx = next(i for i, (pk, _) in enumerate(items) if pk == param_id)
            items[idx] = (new_id, spec)
            params.clear()
            params.update(items)
            st.rerun()

    if c_delete.button("Delete parameter", key=f"param_delete_{k}", type="secondary"):
        del params[param_id]
        st.rerun()




def _render_equations_tab(doc: dict[str, Any]) -> None:
    eqs: dict[str, Any] = doc.setdefault("equations", {})

    st.caption(
        "Equations are Python-evaluable expressions. Each equation's key is "
        "referenced in report tables and graphs via its row 'value' field."
    )

    with st.expander("Add new equation", expanded=False):
        new_id = st.text_input(
            "Equation ID",
            key=_add_form_key("new_eq_id"),
            placeholder="e.g. total_cost",
        )
        if st.button("Add equation", key="eq_add_btn"):
            new_id = new_id.strip()
            if not new_id:
                st.error("Equation ID cannot be empty.")
            elif new_id in eqs:
                st.error(f"Equation ID '{new_id}' already exists.")
            else:
                eqs[new_id] = {"label": "", "compute": ""}
                _reset_add_forms()
                st.rerun()

    for eq_id in list(eqs.keys()):
        eq = eqs[eq_id]
        label = eq.get("label") or eq_id
        with st.expander(f"{eq_id} — {label}", expanded=False):
            _render_single_equation(eqs, eq_id, eq)


def _render_single_equation(
    eqs: dict[str, Any], eq_id: str, eq: dict[str, Any]
) -> None:
    k = eq_id
    c1, c2 = st.columns([3, 1])
    new_id = c1.text_input("ID", value=eq_id, key=f"eq_id_{k}")
    output_options = ["(none)", "number", "integer"]
    current_output = eq.get("output") or "(none)"
    output_idx = (
        output_options.index(current_output)
        if current_output in output_options
        else 0
    )
    selected_output = c2.selectbox(
        "Output type",
        output_options,
        index=output_idx,
        key=f"eq_output_{k}",
        help=(
            "Use **number** for values that may include decimals, such as costs "
            "or rates. Use **integer** for whole-number counts, such as cases. "
            "This does not round or convert the equation result."
        ),
    )
    eq["output"] = None if selected_output == "(none)" else selected_output

    eq["label"] = st.text_input(
        "Label", value=eq.get("label", ""), key=f"eq_label_{k}"
    )
    eq["unit"] = (
        st.text_input(
            "Unit (optional)", value=eq.get("unit", "") or "", key=f"eq_unit_{k}"
        )
        or None
    )
    eq["compute"] = st.text_area(
        "Compute expression",
        value=eq.get("compute", ""),
        height=80,
        key=f"eq_compute_{k}",
        help="Python-evaluable expression referencing parameter/scenario variable names.",
    )

    st.divider()
    c_rename, c_delete = st.columns([3, 1])
    if c_rename.button("Rename / apply ID change", key=f"eq_rename_{k}"):
        new_id = new_id.strip()
        if not new_id:
            st.error("ID cannot be empty.")
        elif new_id != eq_id and new_id in eqs:
            st.error(f"ID '{new_id}' already exists.")
        elif new_id != eq_id:
            items = list(eqs.items())
            idx = next(i for i, (ek, _) in enumerate(items) if ek == eq_id)
            items[idx] = (new_id, eq)
            eqs.clear()
            eqs.update(items)
            st.rerun()

    if c_delete.button("Delete equation", key=f"eq_delete_{k}", type="secondary"):
        del eqs[eq_id]
        st.rerun()




def _render_scenarios_tab(doc: dict[str, Any]) -> None:
    scenarios: list[dict[str, Any]] = doc.setdefault("scenarios", [])
    params: dict[str, Any] = doc.get("parameters", {})
    scenario_param_ids = [
        pid for pid, p in params.items() if p.get("context") == "scenario"
    ]

    st.caption(
        "Each scenario represents a distinct intervention or comparison point. "
        "Scenario vars supply values for parameters marked with context='scenario'."
    )

    with st.expander("Add scenario", expanded=False):
        ns_id = st.text_input(
            "ID",
            key=_add_form_key("new_scen_id"),
            placeholder=f"e.g. scenario_{len(scenarios) + 1}",
        )
        ns_label = st.text_input(
            "Label",
            key=_add_form_key("new_scen_label"),
            placeholder="e.g. Low intervention",
        )
        if st.button("Add scenario", key="scenario_add_btn"):
            scen_id = ns_id.strip() or f"scenario_{len(scenarios) + 1}"
            scenarios.append({"id": scen_id, "label": ns_label.strip(), "vars": {}})
            _reset_add_forms()
            st.rerun()

    for i, scenario in enumerate(scenarios):
        label = scenario.get("label") or scenario.get("id", f"Scenario {i + 1}")
        with st.expander(f"Scenario {i + 1}: {label}", expanded=False):
            _render_single_scenario(scenarios, i, scenario, scenario_param_ids)


def _render_single_scenario(
    scenarios: list[dict[str, Any]],
    idx: int,
    scenario: dict[str, Any],
    scenario_param_ids: list[str],
) -> None:
    k = str(idx)
    c1, c2 = st.columns(2)
    scenario["id"] = c1.text_input(
        "ID", value=scenario.get("id", ""), key=f"scen_id_{k}"
    )
    scenario["label"] = c2.text_input(
        "Label", value=scenario.get("label", ""), key=f"scen_label_{k}"
    )

    vars_dict: dict[str, Any] = scenario.setdefault("vars", {})

    if scenario_param_ids:
        st.markdown("**Scenario vars** (from scenario-context parameters)")
        for param_id in scenario_param_ids:
            current_val = vars_dict.get(param_id, "")
            vars_dict[param_id] = st.text_input(
                param_id,
                value=str(current_val),
                key=f"scen_var_{k}_{param_id}",
                help=f"Value for scenario parameter '{param_id}'",
            )
    else:
        st.caption(
            "No scenario-context parameters defined. "
            "Add parameters with context='scenario' to enable per-scenario variable editing."
        )

    st.markdown("**Additional vars**")
    extra_keys = [vk for vk in vars_dict if vk not in scenario_param_ids]
    for vk in extra_keys:
        vc1, vc2, vc3 = st.columns([2, 3, 1])
        new_vk = vc1.text_input(
            "Key", value=vk, key=f"scen_extra_k_{k}_{vk}"
        )
        new_vv = vc2.text_input(
            "Value", value=str(vars_dict[vk]), key=f"scen_extra_v_{k}_{vk}"
        )
        if vc3.button("Remove", key=f"scen_extra_rm_{k}_{vk}"):
            del vars_dict[vk]
            st.rerun()
        if new_vk != vk:
            vars_dict[new_vk] = vars_dict.pop(vk)
        else:
            vars_dict[vk] = new_vv

    ek1, ek2, ek3 = st.columns([2, 3, 1])
    new_extra_k = ek1.text_input(
        "New key", key=_add_form_key(f"scen_new_extra_k_{k}"), placeholder="var_name"
    )
    new_extra_v = ek2.text_input(
        "New value", key=_add_form_key(f"scen_new_extra_v_{k}"), placeholder="value"
    )
    if ek3.button("Add var", key=f"scen_extra_add_{k}"):
        if new_extra_k and new_extra_k not in vars_dict:
            vars_dict[new_extra_k] = new_extra_v
            _reset_add_forms()
            st.rerun()

    st.divider()
    if st.button("Delete scenario", key=f"scen_delete_{k}", type="secondary"):
        scenarios.pop(idx)
        st.rerun()




def _render_report_tab(doc: dict[str, Any]) -> None:
    report: list[dict[str, Any]] = doc.setdefault("report", [])
    eqs: dict[str, Any] = doc.get("equations", {})
    scenarios: list[dict[str, Any]] = doc.get("scenarios", [])
    scenario_ids = [s.get("id", "") for s in scenarios]
    eq_ids = list(eqs.keys())

    st.caption(
        "Report blocks are rendered in order after a simulation run. "
        "Table and graph blocks reference equation IDs and scenario IDs defined above."
    )

    with st.expander("Add block", expanded=False):
        new_type = st.selectbox(
            "Block type",
            ["markdown", "table", "graph"],
            key=_add_form_key("report_new_block_type"),
        )
        if st.button("Add block", key="report_add_block"):
            report.append(_blank_block(new_type))
            _reset_add_forms()
            st.rerun()

    for i, block in enumerate(report):
        block_type = block.get("type", "?")
        summary = _block_summary(block)
        with st.expander(
            f"Block {i + 1}: [{block_type}] {summary}", expanded=False
        ):
            _render_single_report_block(report, i, block, eq_ids, scenario_ids)


def _blank_block(block_type: str) -> dict[str, Any]:
    if block_type == "markdown":
        return {"type": "markdown", "content": ""}
    if block_type == "table":
        return {"type": "table", "caption": None, "columns": None, "rows": []}
    if block_type == "graph":
        return {
            "type": "graph",
            "kind": "bar",
            "title": None,
            "caption": None,
            "columns": None,
            "rows": [],
        }
    return {"type": block_type}


def _block_summary(block: dict[str, Any]) -> str:
    btype = block.get("type", "")
    if btype == "markdown":
        content = block.get("content", "")
        return content[:60].replace("\n", " ") + ("..." if len(content) > 60 else "")
    if btype in ("table", "graph"):
        rows = block.get("rows", [])
        return f"{len(rows)} row(s)"
    return ""


def _render_single_report_block(
    report: list[dict[str, Any]],
    idx: int,
    block: dict[str, Any],
    eq_ids: list[str],
    scenario_ids: list[str],
) -> None:
    k = str(idx)
    block_type = block.get("type", "markdown")

    c1, c2 = st.columns([1, 4])
    move_up = c1.button("Move up", key=f"block_up_{k}", disabled=idx == 0)
    move_dn = c1.button(
        "Move down", key=f"block_dn_{k}", disabled=idx == len(report) - 1
    )

    if move_up:
        report[idx - 1], report[idx] = report[idx], report[idx - 1]
        st.rerun()
    if move_dn:
        report[idx + 1], report[idx] = report[idx], report[idx + 1]
        st.rerun()

    if block_type == "markdown":
        block["content"] = c2.text_area(
            "Markdown content",
            value=block.get("content", ""),
            height=120,
            key=f"block_md_{k}",
        )

    elif block_type in ("table", "graph"):
        if block_type == "graph":
            block["kind"] = c2.selectbox(
                "Graph kind",
                ["bar", "stacked_bar", "line", "pie"],
                index=["bar", "stacked_bar", "line", "pie"].index(
                    block.get("kind", "bar")
                ),
                key=f"block_gkind_{k}",
            )
            block["title"] = (
                c2.text_input(
                    "Title (optional)",
                    value=block.get("title", "") or "",
                    key=f"block_gtitle_{k}",
                )
                or None
            )

        block["caption"] = (
            st.text_input(
                "Caption (optional)",
                value=block.get("caption", "") or "",
                key=f"block_cap_{k}",
            )
            or None
        )

        col_input = st.text_input(
            "Column scenario IDs (comma-separated, leave blank for all)",
            value=", ".join(block.get("columns") or []),
            key=f"block_cols_{k}",
            help=f"Available: {', '.join(scenario_ids) or 'none yet'}",
        )
        block["columns"] = (
            [c.strip() for c in col_input.split(",") if c.strip()] or None
        )

        st.markdown("**Rows**")
        rows: list[dict[str, Any]] = block.setdefault("rows", [])
        rows_df = pd.DataFrame(
            [
                {
                    "label": r.get("label", ""),
                    "value": r.get("value", ""),
                    "emphasis": r.get("emphasis") or "",
                }
                for r in rows
            ]
            if rows
            else pd.DataFrame(columns=["label", "value", "emphasis"]),
        )
        edited_rows = st.data_editor(
            rows_df,
            num_rows="dynamic",
            key=f"block_rows_{k}",
            column_config={
                "label": st.column_config.TextColumn("Label"),
                "value": st.column_config.TextColumn(
                    "Equation ID",
                    help=f"Available: {', '.join(eq_ids) or 'none yet'}",
                ),
                "emphasis": st.column_config.SelectboxColumn(
                    "Emphasis", options=["", "strong", "em"]
                ),
            },
            hide_index=True,
        )
        block["rows"] = [
            {
                "label": str(row["label"]) if row["label"] else "",
                "value": str(row["value"]) if row["value"] else "",
                "emphasis": str(row["emphasis"]) if row["emphasis"] else None,
            }
            for _, row in edited_rows.iterrows()
        ]

    st.divider()
    if st.button("Delete block", key=f"block_delete_{k}", type="secondary"):
        report.pop(idx)
        st.rerun()




def _render_presets_tab(doc: dict[str, Any]) -> None:
    presets: list[dict[str, Any]] = doc.setdefault("presets", [])
    params: dict[str, Any] = doc.get("parameters", {})
    eq_params = [
        pid
        for pid, p in params.items()
        if p.get("context", "equation") == "equation"
    ]
    groups = _groups_list(doc)

    st.caption(
        "Presets bundle parameter values that can be loaded from the main calculator. "
        "Each preset overrides a subset of the model's equation-context parameters."
    )

    with st.expander("Add preset", expanded=False):
        np_id = st.text_input(
            "ID",
            key=_add_form_key("new_preset_id"),
            placeholder=f"e.g. preset_{len(presets) + 1}",
        )
        np_label = st.text_input(
            "Label",
            key=_add_form_key("new_preset_label"),
            placeholder="e.g. High cost scenario",
        )
        if st.button("Add preset", key="preset_add_btn"):
            preset_id = np_id.strip() or f"preset_{len(presets) + 1}"
            presets.append({"id": preset_id, "label": np_label.strip(), "params": {}})
            _reset_add_forms()
            st.rerun()

    for i, preset in enumerate(presets):
        label = preset.get("label") or preset.get("id", f"Preset {i + 1}")
        with st.expander(f"Preset {i + 1}: {label}", expanded=False):
            _render_single_preset(presets, i, preset, eq_params, params, groups)


def _render_single_preset(
    presets: list[dict[str, Any]],
    idx: int,
    preset: dict[str, Any],
    eq_params: list[str],
    all_params: dict[str, Any],
    groups: list[Any],
) -> None:
    k = str(idx)
    c1, c2 = st.columns(2)
    preset["id"] = c1.text_input(
        "ID", value=preset.get("id", ""), key=f"preset_id_{k}"
    )
    preset["label"] = c2.text_input(
        "Label", value=preset.get("label", ""), key=f"preset_label_{k}"
    )

    preset_params: dict[str, Any] = preset.setdefault("params", {})

    if eq_params:
        st.markdown("**Parameter values** (leave blank to exclude from preset)")

        def _render_preset_field(pid: str, _: dict[str, Any]) -> None:
            if pid not in eq_params:
                return
            val_str = str(preset_params[pid]) if pid in preset_params else ""
            param_spec = all_params.get(pid, {})
            base_label = param_spec.get("label") or pid
            label = f"{base_label} [*]" if pid in preset_params else base_label
            new_val = st.text_input(
                label,
                value=val_str,
                key=f"preset_param_{k}_{pid}",
                help="Leave blank to exclude this parameter from the preset.",
            )
            if new_val.strip():
                try:
                    preset_params[pid] = (
                        float(new_val) if "." in new_val else int(new_val)
                    )
                except ValueError:
                    preset_params[pid] = new_val
            else:
                preset_params.pop(pid, None)

        marked_ids: set[str] = set(preset_params.keys())
        if groups:
            grouped_ids = _collect_grouped_ids(groups)
            ungrouped_eq = [pid for pid in eq_params if pid not in grouped_ids]
            if ungrouped_eq:
                for pid in ungrouped_eq:
                    _render_preset_field(pid, all_params)
            _render_grouped_params(groups, all_params, _render_preset_field, marked_ids=marked_ids)
        else:
            for pid in eq_params:
                _render_preset_field(pid, all_params)
    else:
        st.caption(
            "Define equation-context parameters first to edit preset values here."
        )

    st.divider()
    if st.button("Delete preset", key=f"preset_delete_{k}", type="secondary"):
        presets.pop(idx)
        st.rerun()




def _render_import_section(
    doc: dict[str, Any], source_label: str | None
) -> None:
    with st.expander("Load a different model file", expanded=False):
        uploaded = st.file_uploader(
            "Upload a model YAML file",
            type=["yaml", "yml"],
            key="editor_upload",
            help="Replace the current document with an uploaded model YAML file.",
        )
        if uploaded is not None:
            try:
                fmt = YAMLFormat(uploaded.name)
                raw_data, _ = fmt.read(uploaded)
                result = _validate(raw_data)
                if isinstance(result, list):
                    st.warning(
                        f"The file has {len(result)} validation issue(s). "
                        "You can still load and edit it."
                    )
                else:
                    st.success("File is valid.")
                if st.button("Load into editor", key="editor_load_btn"):
                    _set_doc(raw_data, source_label=source_label)
                    st.rerun()
            except Exception as exc:
                st.error(f"Could not read file: {exc}")

        if st.button("New from empty", key="editor_reset_btn"):
            # Keep the selected model as the editor source marker.  Otherwise
            # _init_state interprets the next rerun as a model switch and
            # restores that model's definition over this empty document.
            _set_doc(deepcopy(_BLANK), source_label=source_label)
            st.rerun()




def _render_validation_errors(errors: list[ValidationIssue]) -> None:
    issue_word = "issue" if len(errors) == 1 else "issues"
    st.error(f"Fix {len(errors)} {issue_word} before exporting your model.")
    for issue in errors:
        st.markdown(f"- **{issue.location}** — {issue.message}")

    with st.expander("Technical details", expanded=False):
        st.code("\n".join(issue.technical_detail for issue in errors))




def _build_yaml_bytes(doc: dict[str, Any]) -> bytes:
    fmt = YAMLFormat("model.yaml")
    return fmt.write(doc)


@st.dialog("Welcome to the Model Editor")
def _render_welcome_dialog() -> None:
    st.markdown(
        """
The **Model Editor** lets you build or modify an EPICC model definition directly
in the browser: metadata, parameters, equations, scenarios, report layout, and
presets.

- Changes here only affect this in-progress document — nothing is saved until
  you export it as a model file.
- Use **Cancel** at any point to return to the Calculator without exporting.
- You can load an existing model file to start from, or reset to a blank model.

"""
    )
    if st.button("Got it", type="primary", key="editor_welcome_dismiss"):
        st.session_state[_WELCOME_SEEN_KEY] = True
        st.rerun()




def render_model_editor(
    initial_doc: dict[str, Any] | None = None,
    source_label: str | None = None,
    on_close: Callable[[], None] | None = None,
) -> None:
    """Render the full model editor.

    Args:
        initial_doc: Pre-populated document dict (e.g. serialised from an
            existing ``Model``). Only applied when the editor is first opened
            for this *source_label*; subsequent renders keep in-progress edits.
        source_label: Stable identifier for the source model (e.g. the model
            title). Used to detect model switches so the doc can be refreshed.
            Pass ``None`` when opening a blank editor.
        on_close: Zero-argument callable invoked when the user clicks Cancel,
            after the in-progress document has been discarded,
            e.g. ``lambda: st.session_state.pop('editor_mode')``.
    """
    _init_state(initial_doc=initial_doc, source_label=source_label)

    if not st.session_state.get(_WELCOME_SEEN_KEY):
        _render_welcome_dialog()

    doc = _doc()

    # Run validation every render so results are available for both the header
    # and the pre-export error section.
    vresult = _validate(doc)
    is_valid = isinstance(vresult, Model)

    safe_title = (doc.get("title") or "model").lower().replace(" ", "_")

    _render_import_section(doc, source_label)

    tab_meta, tab_params, tab_eqs, tab_scenarios, tab_report, tab_presets = st.tabs(
        ["Metadata", "Parameters", "Equations", "Scenarios", "Report", "Presets"]
    )

    with tab_meta:
        _render_metadata_tab(doc)

    with tab_params:
        _render_parameters_tab(doc)

    with tab_eqs:
        _render_equations_tab(doc)

    with tab_scenarios:
        _render_scenarios_tab(doc)

    with tab_report:
        _render_report_tab(doc)

    with tab_presets:
        _render_presets_tab(doc)

    st.divider()
    if not is_valid:
        _render_validation_errors(vresult)  # type: ignore[arg-type]

    export_col: Any = st
    if on_close is not None:
        cancel_col, export_col = st.columns([1, 3])
        if cancel_col.button(
            "Cancel",
            use_container_width=True,
            key="editor_cancel",
            help="Discard your changes and return to the Calculator.",
        ):
            st.session_state.pop(_DOC_KEY, None)
            st.session_state.pop(_SOURCE_KEY, None)
            _clear_widget_state()
            on_close()
            st.rerun()

    try:
        yaml_bytes = _build_yaml_bytes(doc)
        export_col.download_button(
            label="Export as Model File",
            data=yaml_bytes,
            file_name=f"{safe_title}.yaml",
            mime=_YAML_MIME,
            use_container_width=True,
            key="editor_export_footer",
            type='primary'
        )
    except Exception as exc:
        st.error(f"Export failed: {exc}")
