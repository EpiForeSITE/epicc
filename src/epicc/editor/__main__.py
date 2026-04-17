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
# Session-state initialization
# ---------------------------------------------------------------------------


def _init_state() -> None:
    for key, default in DEFAULT_STATE.items():
        if key not in st.session_state:
            if isinstance(default, list):
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
        state = yaml_to_state(uploaded.getvalue())
        for k, v in state.items():
            st.session_state[k] = v
        st.success(f"Loaded **{uploaded.name}**")

# ---------------------------------------------------------------------------
# Form sections
# ---------------------------------------------------------------------------

meta_tab, params_tab, eqs_tab, scenarios_tab, report_tab, figures_tab = st.tabs(
    ["Metadata", "Parameters", "Equations", "Scenarios", "Report", "Figures"]
)

# ---- Metadata ----
with meta_tab:
    st.subheader("Model Metadata")
    st.session_state["model_title"] = st.text_input("Title *", st.session_state["model_title"])
    st.session_state["model_description"] = st.text_area(
        "Description *", st.session_state["model_description"], height=100
    )

    st.markdown("**Authors**")
    authors: list[dict[str, str]] = st.session_state["authors"]
    updated_authors: list[dict[str, str]] = []
    for i, author in enumerate(authors):
        cols = st.columns([3, 3, 1])
        name = cols[0].text_input("Name", author["name"], key=f"author_name_{i}")
        email = cols[1].text_input("Email", author["email"], key=f"author_email_{i}")
        remove = cols[2].button("✕", key=f"rm_author_{i}")
        if not remove:
            updated_authors.append({"name": name, "email": email})
    if st.button("＋ Add author"):
        updated_authors.append({"name": "", "email": ""})
    st.session_state["authors"] = updated_authors or [{"name": "", "email": ""}]

# ---- Parameters ----
with params_tab:
    st.subheader("Parameters")
    st.caption(
        "Each parameter needs a unique **ID** (used in equations), a display **label**, "
        "a **type**, and a **default** value. For enum parameters, specify options as "
        "``KEY: Label`` lines."
    )
    params: list[dict[str, Any]] = st.session_state["parameters"]
    updated_params: list[dict[str, Any]] = []
    for i, p in enumerate(params):
        with st.expander(
            p.get("label") or p.get("id") or f"Parameter {i + 1}",
            expanded=(i == len(params) - 1 and not p.get("id")),
        ):
            c1, c2 = st.columns(2)
            pid = c1.text_input("ID *", p.get("id", ""), key=f"pid_{i}")
            ptype = c2.selectbox(
                "Type *",
                ["integer", "number", "string", "boolean", "enum"],
                index=["integer", "number", "string", "boolean", "enum"].index(
                    p.get("type", "number")
                ),
                key=f"ptype_{i}",
            )
            plabel = st.text_input("Label *", p.get("label", ""), key=f"plabel_{i}")
            pdesc = st.text_input("Description", p.get("description", ""), key=f"pdesc_{i}")

            dc1, dc2, dc3 = st.columns(3)
            pdefault_raw = dc1.text_input(
                "Default *", str(p.get("default", "")), key=f"pdef_{i}"
            )
            pmin_raw = dc2.text_input("Min", str(p.get("min", "")), key=f"pmin_{i}")
            pmax_raw = dc3.text_input("Max", str(p.get("max", "")), key=f"pmax_{i}")
            punit = st.text_input("Unit", p.get("unit", ""), key=f"punit_{i}")
            prefs = st.text_area(
                "References (one per line)",
                p.get("references", ""),
                key=f"prefs_{i}",
                height=68,
            )

            poptions = ""
            if ptype == "enum":
                poptions = st.text_area(
                    "Options (KEY: Label, one per line)",
                    p.get("options", ""),
                    key=f"popts_{i}",
                    height=68,
                )

            remove = st.button("Remove parameter", key=f"rm_param_{i}")
            if not remove:
                updated_params.append(
                    {
                        "id": pid,
                        "type": ptype,
                        "label": plabel,
                        "description": pdesc,
                        "default": pdefault_raw,
                        "min": pmin_raw,
                        "max": pmax_raw,
                        "unit": punit,
                        "references": prefs,
                        "options": poptions,
                    }
                )

    if st.button("＋ Add parameter"):
        updated_params.append(
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
            }
        )
    st.session_state["parameters"] = updated_params

# ---- Equations ----
with eqs_tab:
    st.subheader("Equations")
    st.caption(
        "Each equation has a unique **ID**, a **label**, and a **compute** expression "
        "that may reference parameter IDs, scenario variable names, or other equation IDs."
    )
    eqs: list[dict[str, Any]] = st.session_state["equations"]
    updated_eqs: list[dict[str, Any]] = []
    for i, eq in enumerate(eqs):
        with st.expander(
            eq.get("label") or eq.get("id") or f"Equation {i + 1}",
            expanded=(i == len(eqs) - 1 and not eq.get("id")),
        ):
            c1, c2 = st.columns(2)
            eid = c1.text_input("ID *", eq.get("id", ""), key=f"eid_{i}")
            elabel = c2.text_input("Label *", eq.get("label", ""), key=f"elabel_{i}")
            ec1, ec2 = st.columns(2)
            eunit = ec1.text_input("Unit", eq.get("unit", ""), key=f"eunit_{i}")
            eoutput = ec2.selectbox(
                "Output type",
                ["number", "integer"],
                index=["number", "integer"].index(eq.get("output", "number") or "number"),
                key=f"eoutput_{i}",
            )
            ecompute = st.text_area(
                "Compute expression *",
                eq.get("compute", ""),
                key=f"ecomp_{i}",
                height=80,
            )

            remove = st.button("Remove equation", key=f"rm_eq_{i}")
            if not remove:
                updated_eqs.append(
                    {
                        "id": eid,
                        "label": elabel,
                        "unit": eunit,
                        "output": eoutput,
                        "compute": ecompute,
                    }
                )

    if st.button("＋ Add equation"):
        updated_eqs.append(
            {"id": "", "label": "", "unit": "", "output": "number", "compute": ""}
        )
    st.session_state["equations"] = updated_eqs

# ---- Scenarios ----
with scenarios_tab:
    st.subheader("Scenarios")
    st.caption(
        "Define scenarios with a unique **ID**, a **label**, and scenario **variables** "
        "as ``name: value`` lines (one per line)."
    )
    scenarios: list[dict[str, Any]] = st.session_state["scenarios"]
    updated_scenarios: list[dict[str, Any]] = []
    for i, sc in enumerate(scenarios):
        with st.expander(
            sc.get("label") or sc.get("id") or f"Scenario {i + 1}",
            expanded=(i == len(scenarios) - 1 and not sc.get("id")),
        ):
            c1, c2 = st.columns(2)
            sid = c1.text_input("ID *", sc.get("id", ""), key=f"sid_{i}")
            slabel = c2.text_input("Label *", sc.get("label", ""), key=f"slabel_{i}")
            svars = st.text_area(
                "Variables (name: value, one per line) *",
                sc.get("vars", ""),
                key=f"svars_{i}",
                height=80,
            )

            remove = st.button("Remove scenario", key=f"rm_sc_{i}")
            if not remove:
                updated_scenarios.append({"id": sid, "label": slabel, "vars": svars})

    if st.button("＋ Add scenario"):
        updated_scenarios.append({"id": "", "label": "", "vars": ""})
    st.session_state["scenarios"] = updated_scenarios

# ---- Report ----
with report_tab:
    st.subheader("Report Blocks")
    st.caption(
        "Build the report from blocks. **Markdown** blocks hold free-form text. "
        "**Table** and **Graph** blocks reference equation IDs. "
        "Row format: ``Label | equation_id [| emphasis]``."
    )
    blocks: list[dict[str, Any]] = st.session_state["report_blocks"]
    updated_blocks: list[dict[str, Any]] = []
    for i, blk in enumerate(blocks):
        btype = blk.get("type", "markdown")
        with st.expander(f"{btype.title()} block {i + 1}", expanded=(i == len(blocks) - 1)):
            new_type = st.selectbox(
                "Block type",
                ["markdown", "table", "figure", "graph"],
                index=["markdown", "table", "figure", "graph"].index(btype),
                key=f"btype_{i}",
            )
            entry: dict[str, Any] = {"type": new_type}

            if new_type == "markdown":
                entry["content"] = st.text_area(
                    "Content (Markdown)",
                    blk.get("content", ""),
                    key=f"bcontent_{i}",
                    height=150,
                )
            elif new_type == "table":
                entry["caption"] = st.text_input(
                    "Caption", blk.get("caption", ""), key=f"tcap_{i}"
                )
                entry["columns"] = st.text_input(
                    "Columns (comma-separated scenario IDs, blank = all)",
                    blk.get("columns", ""),
                    key=f"tcols_{i}",
                )
                entry["rows"] = st.text_area(
                    "Rows (Label | equation_id [| emphasis])",
                    blk.get("rows", ""),
                    key=f"trows_{i}",
                    height=120,
                )
            elif new_type == "figure":
                entry["id"] = st.text_input(
                    "Figure ID", blk.get("id", ""), key=f"fid_{i}"
                )
            elif new_type == "graph":
                entry["kind"] = st.selectbox(
                    "Graph kind",
                    ["bar", "stacked_bar", "line", "pie"],
                    index=["bar", "stacked_bar", "line", "pie"].index(
                        blk.get("kind", "bar")
                    ),
                    key=f"gkind_{i}",
                )
                entry["title"] = st.text_input(
                    "Title", blk.get("title", ""), key=f"gtitle_{i}"
                )
                entry["caption"] = st.text_input(
                    "Caption", blk.get("caption", ""), key=f"gcap_{i}"
                )
                entry["columns"] = st.text_input(
                    "Columns (comma-separated scenario IDs, blank = all)",
                    blk.get("columns", ""),
                    key=f"gcols_{i}",
                )
                entry["rows"] = st.text_area(
                    "Rows (Label | equation_id [| emphasis])",
                    blk.get("rows", ""),
                    key=f"grows_{i}",
                    height=120,
                )

            remove = st.button("Remove block", key=f"rm_blk_{i}")
            if not remove:
                updated_blocks.append(entry)

    if st.button("＋ Add report block"):
        updated_blocks.append({"type": "markdown", "content": ""})
    st.session_state["report_blocks"] = updated_blocks

# ---- Figures ----
with figures_tab:
    st.subheader("Figures")
    st.caption(
        "Define custom figures with Python code. These are referenced from "
        "**figure** report blocks by their **ID**."
    )
    figs: list[dict[str, Any]] = st.session_state["figures"]
    updated_figs: list[dict[str, Any]] = []
    for i, fig in enumerate(figs):
        with st.expander(
            fig.get("title") or fig.get("id") or f"Figure {i + 1}", expanded=True
        ):
            c1, c2 = st.columns(2)
            fid = c1.text_input("ID *", fig.get("id", ""), key=f"figid_{i}")
            ftitle = c2.text_input("Title *", fig.get("title", ""), key=f"figtitle_{i}")
            falt = st.text_input(
                "Alt text", fig.get("alt_text", "") or "", key=f"figalt_{i}"
            )
            fcode = st.text_area(
                "Python code",
                fig.get("py_code", "") or "",
                key=f"figcode_{i}",
                height=120,
            )

            remove = st.button("Remove figure", key=f"rm_fig_{i}")
            if not remove:
                updated_figs.append(
                    {"id": fid, "title": ftitle, "alt_text": falt, "py_code": fcode}
                )

    if st.button("＋ Add figure"):
        updated_figs.append({"id": "", "title": "", "alt_text": "", "py_code": ""})
    st.session_state["figures"] = updated_figs

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
