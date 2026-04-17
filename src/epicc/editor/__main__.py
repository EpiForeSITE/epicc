"""
Model Editor – a Streamlit app for building and editing YAML model files.

Provides a form-based GUI for constructing model definitions that conform
to the ``epicc.model.schema.Model`` Pydantic schema.  Users can start from
scratch, upload an existing YAML file, validate the document in real time,
and download the result.
"""

from __future__ import annotations

import copy
from typing import Any

import streamlit as st
from pydantic import ValidationError

from epicc.editor.helpers import (
    DEFAULT_STATE,
    build_model_dict,
    serialize_to_yaml,
    validate_model_dict,
    yaml_to_state,
)

# ---------------------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------------------

st.set_page_config(page_title="EPICC Model Editor", layout="wide")
st.title("EPICC Model Editor")
st.markdown(
    "Build, edit, and validate YAML model files for the **EPICC Cost Calculator**."
)

# ---------------------------------------------------------------------------
# Widget-key versioning
# ---------------------------------------------------------------------------
# Streamlit caches widget values by key.  When the list of authors (or
# parameters, etc.) changes structurally (upload, add, remove), cached
# values under old keys can shadow the correct data.  We embed a version
# counter in every dynamic widget key so that a version bump forces
# Streamlit to create genuinely new widgets that honour the ``value``
# parameter from the current list state.


def _bump_version() -> None:
    """Increment the widget-key version counter."""
    st.session_state["_wv"] = st.session_state.get("_wv", 0) + 1


def _v() -> int:
    """Return the current widget-key version."""
    return int(st.session_state.get("_wv", 0))


# ---------------------------------------------------------------------------
# Callbacks – executed *before* the next script rerun
# ---------------------------------------------------------------------------


def _add_item(section: str, template: dict[str, Any]) -> None:
    st.session_state[section].append(copy.deepcopy(template))
    _bump_version()


def _remove_item(section: str, idx: int) -> None:
    items: list[Any] = st.session_state[section]
    if 0 <= idx < len(items):
        items.pop(idx)
    _bump_version()


# ---------------------------------------------------------------------------
# Session-state initialization
# ---------------------------------------------------------------------------


def _init_state() -> None:
    for key, default in DEFAULT_STATE.items():
        if key not in st.session_state:
            if isinstance(default, (list, dict)):
                st.session_state[key] = copy.deepcopy(default)
            else:
                st.session_state[key] = default


_init_state()

# ---------------------------------------------------------------------------
# Upload widget
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("Load / Save")
    uploaded = st.file_uploader("Upload a model YAML file", type=["yaml", "yml"])
    if uploaded is not None:
        file_id = f"{uploaded.name}:{uploaded.size}"
        if st.session_state.get("_uploaded_file_id") != file_id:
            st.session_state["_uploaded_file_id"] = file_id
            state = yaml_to_state(uploaded.getvalue())
            _bump_version()
            for k, v in state.items():
                st.session_state[k] = v
            st.rerun()
        st.success(f"Loaded **{uploaded.name}**")

# ---------------------------------------------------------------------------
# Sync helper – read widget values back into the canonical list
# ---------------------------------------------------------------------------


def _sync_list(
    section: str,
    widgets: list[dict[str, Any]],
) -> None:
    """Replace *section* in session state with *widgets* (values read from UI)."""
    st.session_state[section] = widgets if widgets else copy.deepcopy(
        DEFAULT_STATE.get(section, [])
    )


# ---------------------------------------------------------------------------
# Form sections
# ---------------------------------------------------------------------------

meta_tab, params_tab, eqs_tab, scenarios_tab, report_tab, figures_tab = st.tabs(
    ["Metadata", "Parameters", "Equations", "Scenarios", "Report", "Figures"]
)

# ---- Metadata ----
with meta_tab:
    st.subheader("Model Metadata")
    st.session_state["model_title"] = st.text_input(
        "Title *", st.session_state["model_title"]
    )
    st.session_state["model_description"] = st.text_area(
        "Description *", st.session_state["model_description"], height=100
    )

    st.markdown("**Authors**")
    _authors: list[dict[str, str]] = st.session_state["authors"]
    _updated_authors: list[dict[str, str]] = []
    for _i, _author in enumerate(_authors):
        _cols = st.columns([3, 3, 1])
        _name = _cols[0].text_input(
            "Name", _author["name"], key=f"author_name_{_v()}_{_i}"
        )
        _email = _cols[1].text_input(
            "Email", _author["email"], key=f"author_email_{_v()}_{_i}"
        )
        _cols[2].button(
            "✕", key=f"rm_author_{_v()}_{_i}",
            on_click=_remove_item, args=("authors", _i),
        )
        _updated_authors.append({"name": _name, "email": _email})

    st.button(
        "＋ Add author",
        on_click=_add_item,
        args=("authors", {"name": "", "email": ""}),
    )
    _sync_list("authors", _updated_authors)

# ---- Parameters ----
with params_tab:
    st.subheader("Parameters")
    st.caption(
        "Each parameter needs a unique **ID** (used in equations), a display **label**, "
        "a **type**, and a **default** value. For enum parameters, specify options as "
        "``KEY: Label`` lines."
    )
    _params: list[dict[str, Any]] = st.session_state["parameters"]
    _updated_params: list[dict[str, Any]] = []
    for _i, _p in enumerate(_params):
        with st.expander(
            _p.get("label") or _p.get("id") or f"Parameter {_i + 1}",
            expanded=(_i == len(_params) - 1 and not _p.get("id")),
        ):
            _c1, _c2 = st.columns(2)
            _pid = _c1.text_input("ID *", _p.get("id", ""), key=f"pid_{_v()}_{_i}")
            _ptype = _c2.selectbox(
                "Type *",
                ["integer", "number", "string", "boolean", "enum"],
                index=["integer", "number", "string", "boolean", "enum"].index(
                    _p.get("type", "number")
                ),
                key=f"ptype_{_v()}_{_i}",
            )
            _plabel = st.text_input("Label *", _p.get("label", ""), key=f"plabel_{_v()}_{_i}")
            _pdesc = st.text_input(
                "Description", _p.get("description", ""), key=f"pdesc_{_v()}_{_i}"
            )

            _dc1, _dc2, _dc3 = st.columns(3)
            _pdefault_raw = _dc1.text_input(
                "Default *", str(_p.get("default", "")), key=f"pdef_{_v()}_{_i}"
            )
            _pmin_raw = _dc2.text_input(
                "Min", str(_p.get("min", "")), key=f"pmin_{_v()}_{_i}"
            )
            _pmax_raw = _dc3.text_input(
                "Max", str(_p.get("max", "")), key=f"pmax_{_v()}_{_i}"
            )
            _punit = st.text_input("Unit", _p.get("unit", ""), key=f"punit_{_v()}_{_i}")
            _prefs = st.text_area(
                "References (one per line)",
                _p.get("references", ""),
                key=f"prefs_{_v()}_{_i}",
                height=68,
            )

            _poptions = ""
            if _ptype == "enum":
                _poptions = st.text_area(
                    "Options (KEY: Label, one per line)",
                    _p.get("options", ""),
                    key=f"popts_{_v()}_{_i}",
                    height=68,
                )

            st.button(
                "Remove parameter", key=f"rm_param_{_v()}_{_i}",
                on_click=_remove_item, args=("parameters", _i),
            )
            _updated_params.append(
                {
                    "id": _pid,
                    "type": _ptype,
                    "label": _plabel,
                    "description": _pdesc,
                    "default": _pdefault_raw,
                    "min": _pmin_raw,
                    "max": _pmax_raw,
                    "unit": _punit,
                    "references": _prefs,
                    "options": _poptions,
                }
            )

    st.button(
        "＋ Add parameter",
        on_click=_add_item,
        args=(
            "parameters",
            {
                "id": "",
                "type": "number",
                "label": "",
                "description": "",
                "default": "0",
                "min": "0",
                "max": "100",
                "unit": "",
                "references": "",
                "options": "",
            },
        ),
    )
    _sync_list("parameters", _updated_params)

# ---- Equations ----
with eqs_tab:
    st.subheader("Equations")
    st.caption(
        "Each equation has a unique **ID**, a **label**, and a **compute** expression "
        "that may reference parameter IDs, scenario variable names, or other equation IDs."
    )
    _eqs: list[dict[str, Any]] = st.session_state["equations"]
    _updated_eqs: list[dict[str, Any]] = []
    for _i, _eq in enumerate(_eqs):
        with st.expander(
            _eq.get("label") or _eq.get("id") or f"Equation {_i + 1}",
            expanded=(_i == len(_eqs) - 1 and not _eq.get("id")),
        ):
            _c1, _c2 = st.columns(2)
            _eid = _c1.text_input("ID *", _eq.get("id", ""), key=f"eid_{_v()}_{_i}")
            _elabel = _c2.text_input(
                "Label *", _eq.get("label", ""), key=f"elabel_{_v()}_{_i}"
            )
            _ec1, _ec2 = st.columns(2)
            _eunit = _ec1.text_input("Unit", _eq.get("unit", ""), key=f"eunit_{_v()}_{_i}")
            _eoutput = _ec2.selectbox(
                "Output type",
                ["number", "integer"],
                index=["number", "integer"].index(
                    _eq.get("output", "number") or "number"
                ),
                key=f"eoutput_{_v()}_{_i}",
            )
            _ecompute = st.text_area(
                "Compute expression *",
                _eq.get("compute", ""),
                key=f"ecomp_{_v()}_{_i}",
                height=80,
            )

            st.button(
                "Remove equation", key=f"rm_eq_{_v()}_{_i}",
                on_click=_remove_item, args=("equations", _i),
            )
            _updated_eqs.append(
                {
                    "id": _eid,
                    "label": _elabel,
                    "unit": _eunit,
                    "output": _eoutput,
                    "compute": _ecompute,
                }
            )

    st.button(
        "＋ Add equation",
        on_click=_add_item,
        args=(
            "equations",
            {"id": "", "label": "", "unit": "", "output": "number", "compute": ""},
        ),
    )
    _sync_list("equations", _updated_eqs)

# ---- Scenarios ----
with scenarios_tab:
    st.subheader("Scenarios")
    st.caption(
        "Define scenarios with a unique **ID**, a **label**, and scenario **variables** "
        "as ``name: value`` lines (one per line)."
    )
    _scenarios: list[dict[str, Any]] = st.session_state["scenarios"]
    _updated_scenarios: list[dict[str, Any]] = []
    for _i, _sc in enumerate(_scenarios):
        with st.expander(
            _sc.get("label") or _sc.get("id") or f"Scenario {_i + 1}",
            expanded=(_i == len(_scenarios) - 1 and not _sc.get("id")),
        ):
            _c1, _c2 = st.columns(2)
            _sid = _c1.text_input("ID *", _sc.get("id", ""), key=f"sid_{_v()}_{_i}")
            _slabel = _c2.text_input(
                "Label *", _sc.get("label", ""), key=f"slabel_{_v()}_{_i}"
            )
            _svars = st.text_area(
                "Variables (name: value, one per line) *",
                _sc.get("vars", ""),
                key=f"svars_{_v()}_{_i}",
                height=80,
            )

            st.button(
                "Remove scenario", key=f"rm_sc_{_v()}_{_i}",
                on_click=_remove_item, args=("scenarios", _i),
            )
            _updated_scenarios.append(
                {"id": _sid, "label": _slabel, "vars": _svars}
            )

    st.button(
        "＋ Add scenario",
        on_click=_add_item,
        args=("scenarios", {"id": "", "label": "", "vars": ""}),
    )
    _sync_list("scenarios", _updated_scenarios)

# ---- Report ----
with report_tab:
    st.subheader("Report Blocks")
    st.caption(
        "Build the report from blocks. **Markdown** blocks hold free-form text. "
        "**Table** and **Graph** blocks reference equation IDs. "
        "Row format: ``Label | equation_id [| emphasis]``."
    )
    _blocks: list[dict[str, Any]] = st.session_state["report_blocks"]
    _updated_blocks: list[dict[str, Any]] = []
    for _i, _blk in enumerate(_blocks):
        _btype = _blk.get("type", "markdown")
        with st.expander(
            f"{_btype.title()} block {_i + 1}", expanded=(_i == len(_blocks) - 1)
        ):
            _new_type = st.selectbox(
                "Block type",
                ["markdown", "table", "figure", "graph"],
                index=["markdown", "table", "figure", "graph"].index(_btype),
                key=f"btype_{_v()}_{_i}",
            )
            _entry: dict[str, Any] = {"type": _new_type}

            if _new_type == "markdown":
                _entry["content"] = st.text_area(
                    "Content (Markdown)",
                    _blk.get("content", ""),
                    key=f"bcontent_{_v()}_{_i}",
                    height=150,
                )
            elif _new_type == "table":
                _entry["caption"] = st.text_input(
                    "Caption", _blk.get("caption", ""), key=f"tcap_{_v()}_{_i}"
                )
                _entry["columns"] = st.text_input(
                    "Columns (comma-separated scenario IDs, blank = all)",
                    _blk.get("columns", ""),
                    key=f"tcols_{_v()}_{_i}",
                )
                _entry["rows"] = st.text_area(
                    "Rows (Label | equation_id [| emphasis])",
                    _blk.get("rows", ""),
                    key=f"trows_{_v()}_{_i}",
                    height=120,
                )
            elif _new_type == "figure":
                _entry["id"] = st.text_input(
                    "Figure ID", _blk.get("id", ""), key=f"fid_{_v()}_{_i}"
                )
            elif _new_type == "graph":
                _entry["kind"] = st.selectbox(
                    "Graph kind",
                    ["bar", "stacked_bar", "line", "pie"],
                    index=["bar", "stacked_bar", "line", "pie"].index(
                        _blk.get("kind", "bar")
                    ),
                    key=f"gkind_{_v()}_{_i}",
                )
                _entry["title"] = st.text_input(
                    "Title", _blk.get("title", ""), key=f"gtitle_{_v()}_{_i}"
                )
                _entry["caption"] = st.text_input(
                    "Caption", _blk.get("caption", ""), key=f"gcap_{_v()}_{_i}"
                )
                _entry["columns"] = st.text_input(
                    "Columns (comma-separated scenario IDs, blank = all)",
                    _blk.get("columns", ""),
                    key=f"gcols_{_v()}_{_i}",
                )
                _entry["rows"] = st.text_area(
                    "Rows (Label | equation_id [| emphasis])",
                    _blk.get("rows", ""),
                    key=f"grows_{_v()}_{_i}",
                    height=120,
                )

            st.button(
                "Remove block", key=f"rm_blk_{_v()}_{_i}",
                on_click=_remove_item, args=("report_blocks", _i),
            )
            _updated_blocks.append(_entry)

    st.button(
        "＋ Add report block",
        on_click=_add_item,
        args=("report_blocks", {"type": "markdown", "content": ""}),
    )
    _sync_list("report_blocks", _updated_blocks)

# ---- Figures ----
with figures_tab:
    st.subheader("Figures")
    st.caption(
        "Define custom figures with Python code. These are referenced from "
        "**figure** report blocks by their **ID**."
    )
    _figs: list[dict[str, Any]] = st.session_state["figures"]
    _updated_figs: list[dict[str, Any]] = []
    for _i, _fig in enumerate(_figs):
        with st.expander(
            _fig.get("title") or _fig.get("id") or f"Figure {_i + 1}",
            expanded=True,
        ):
            _c1, _c2 = st.columns(2)
            _fid = _c1.text_input(
                "ID *", _fig.get("id", ""), key=f"figid_{_v()}_{_i}"
            )
            _ftitle = _c2.text_input(
                "Title *", _fig.get("title", ""), key=f"figtitle_{_v()}_{_i}"
            )
            _falt = st.text_input(
                "Alt text", _fig.get("alt_text", "") or "", key=f"figalt_{_v()}_{_i}"
            )
            _fcode = st.text_area(
                "Python code",
                _fig.get("py_code", "") or "",
                key=f"figcode_{_v()}_{_i}",
                height=120,
            )

            st.button(
                "Remove figure", key=f"rm_fig_{_v()}_{_i}",
                on_click=_remove_item, args=("figures", _i),
            )
            _updated_figs.append(
                {
                    "id": _fid,
                    "title": _ftitle,
                    "alt_text": _falt,
                    "py_code": _fcode,
                }
            )

    st.button(
        "＋ Add figure",
        on_click=_add_item,
        args=(
            "figures",
            {"id": "", "title": "", "alt_text": "", "py_code": ""},
        ),
    )
    _sync_list("figures", _updated_figs)

# ---------------------------------------------------------------------------
# Validate & Download
# ---------------------------------------------------------------------------

st.divider()
val_col, dl_col = st.columns([1, 1])

with val_col:
    if st.button("✔ Validate model", type="primary", use_container_width=True):
        doc = build_model_dict({str(k): v for k, v in st.session_state.items()})
        try:
            validate_model_dict(doc)
            st.success("Model is valid! ✅")
        except (ValidationError, ValueError) as exc:
            st.error("Validation failed ❌")
            st.code(str(exc))

with dl_col:
    doc = build_model_dict({str(k): v for k, v in st.session_state.items()})
    try:
        yaml_bytes = serialize_to_yaml(doc)
    except Exception:
        yaml_bytes = b""

    if yaml_bytes:
        st.download_button(
            "⬇ Download YAML",
            data=yaml_bytes,
            file_name="model.yaml",
            mime="text/yaml",
            use_container_width=True,
        )

# Show a live YAML preview in a collapsed section
with st.expander("YAML Preview"):
    if yaml_bytes:
        st.code(yaml_bytes.decode("utf-8"), language="yaml")
    else:
        st.info("Fill in the form fields above to see a preview.")
