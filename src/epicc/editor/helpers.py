"""Pure-logic helpers for the model editor.

These functions contain no Streamlit dependencies and can be tested in
plain pytest without mocking the Streamlit runtime.
"""

from __future__ import annotations

import io
from typing import Any

from epicc.formats import opaque_to_typed
from epicc.formats.yaml import YAMLFormat
from epicc.model.schema import Model

# ---------------------------------------------------------------------------
# Coercion helpers
# ---------------------------------------------------------------------------


def coerce_numeric(value: str) -> int | float | str | bool:
    """Attempt to coerce a string to a numeric type or boolean."""
    if value.lower() in ("true", "false"):
        return value.lower() == "true"
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value


def coerce_numeric_or_none(value: str) -> int | float | None:
    """Coerce to numeric or return ``None`` for empty / non-numeric strings."""
    if not value.strip():
        return None
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def parse_key_value_lines(text: str) -> dict[str, Any]:
    """Parse ``key: value`` lines into a dict, coercing numeric values."""
    result: dict[str, Any] = {}
    for line in text.strip().splitlines():
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        val = val.strip()
        try:
            result[key.strip()] = int(val)
        except ValueError:
            try:
                result[key.strip()] = float(val)
            except ValueError:
                result[key.strip()] = val
    return result


def parse_table_rows(text: str) -> list[dict[str, Any]]:
    """Parse ``label | value [| emphasis]`` lines back to dicts."""
    rows: list[dict[str, Any]] = []
    for line in text.strip().splitlines():
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 2:
            row: dict[str, Any] = {"label": parts[0], "value": parts[1]}
            if len(parts) >= 3 and parts[2]:
                row["emphasis"] = parts[2]
            rows.append(row)
    return rows


def table_row_to_str(row: dict[str, str]) -> str:
    """Serialize a table-row dict to a ``label | value [| emphasis]`` string."""
    parts = [row.get("label", ""), row.get("value", "")]
    emphasis = row.get("emphasis", "")
    if emphasis:
        parts.append(emphasis)
    return " | ".join(parts)


# ---------------------------------------------------------------------------
# YAML load → session-state dicts
# ---------------------------------------------------------------------------

# The following type alias describes the flat dict shape stored in
# ``st.session_state`` for each section of the editor form.
EditorState = dict[str, Any]

#: Default state values for a blank model document.
DEFAULT_STATE: dict[str, Any] = {
    "model_title": "",
    "model_description": "",
    "authors": [{"name": "", "email": ""}],
    "parameters": [
        {
            "id": "",
            "type": "number",
            "label": "",
            "description": "",
            "default": 0.0,
            "min": 0.0,
            "max": 100.0,
            "unit": "",
            "references": "",
            "options": "",
        }
    ],
    "equations": [{"id": "", "label": "", "unit": "", "output": "number", "compute": ""}],
    "groups": [],
    "scenarios": [{"id": "", "label": "", "vars": ""}],
    "report_blocks": [{"type": "markdown", "content": ""}],
    "figures": [],
}


def yaml_to_state(raw: bytes) -> EditorState:
    """Parse raw YAML bytes into a flat *state* dict for the editor form.

    Returns a dict whose keys match :data:`DEFAULT_STATE`.
    """
    fmt = YAMLFormat("upload.yaml")
    data, _ = fmt.read(io.BytesIO(raw))

    state: EditorState = {}

    state["model_title"] = data.get("title", "")
    state["model_description"] = data.get("description", "")

    # Authors
    authors_raw = data.get("authors", [])
    state["authors"] = [
        {"name": a.get("name", ""), "email": a.get("email", "")} for a in authors_raw
    ] or [{"name": "", "email": ""}]

    # Parameters
    params_raw: dict = data.get("parameters", {})
    state["parameters"] = [
        {
            "id": pid,
            "type": p.get("type", "number"),
            "label": p.get("label", ""),
            "description": p.get("description", ""),
            "default": p.get("default", 0),
            "min": p.get("min") if p.get("min") is not None else "0",
            "max": p.get("max") if p.get("max") is not None else "100",
            "unit": p.get("unit", ""),
            "references": "\n".join(p.get("references") or []),
            "options": "\n".join(
                f"{k}: {v}" for k, v in (p.get("options") or {}).items()
            ),
        }
        for pid, p in params_raw.items()
    ] or DEFAULT_STATE["parameters"]

    # Equations
    eqs_raw: dict = data.get("equations", {})
    state["equations"] = [
        {
            "id": eid,
            "label": e.get("label", ""),
            "unit": e.get("unit", ""),
            "output": e.get("output", "number") or "number",
            "compute": e.get("compute", "").strip(),
        }
        for eid, e in eqs_raw.items()
    ] or DEFAULT_STATE["equations"]

    # Groups (pass through)
    state["groups"] = data.get("groups", [])

    # Scenarios
    scenarios_raw = data.get("scenarios", [])
    state["scenarios"] = [
        {
            "id": s.get("id", ""),
            "label": s.get("label", ""),
            "vars": "\n".join(f"{k}: {v}" for k, v in (s.get("vars") or {}).items()),
        }
        for s in scenarios_raw
    ] or DEFAULT_STATE["scenarios"]

    # Report blocks
    blocks_raw = data.get("report", [])
    report_blocks: list[dict[str, Any]] = []
    for b in blocks_raw:
        btype = b.get("type", "markdown")
        entry: dict[str, Any] = {"type": btype}
        if btype == "markdown":
            entry["content"] = b.get("content", "")
        elif btype == "table":
            entry["caption"] = b.get("caption", "")
            entry["columns"] = ", ".join(b.get("columns") or [])
            entry["rows"] = "\n".join(
                table_row_to_str(r) for r in b.get("rows", [])
            )
        elif btype == "figure":
            entry["id"] = b.get("id", "")
        elif btype == "graph":
            entry["kind"] = b.get("kind", "bar")
            entry["title"] = b.get("title", "")
            entry["caption"] = b.get("caption", "")
            entry["columns"] = ", ".join(b.get("columns") or [])
            entry["rows"] = "\n".join(
                table_row_to_str(r) for r in b.get("rows", [])
            )
        report_blocks.append(entry)
    state["report_blocks"] = report_blocks or DEFAULT_STATE["report_blocks"]

    # Figures
    figs_raw = data.get("figures", [])
    state["figures"] = [
        {
            "id": f.get("id", ""),
            "title": f.get("title", ""),
            "alt_text": f.get("alt-text", f.get("alt_text", "")),
            "py_code": f.get("py-code", f.get("py_code", "")),
        }
        for f in figs_raw
    ] or []

    return state


# ---------------------------------------------------------------------------
# Session-state → model document dict
# ---------------------------------------------------------------------------


def build_model_dict(state: EditorState) -> dict[str, Any]:
    """Assemble a model document dict from the flat editor *state*."""
    doc: dict[str, Any] = {
        "title": state.get("model_title", ""),
        "description": state.get("model_description", ""),
    }

    # Authors (omit empty entries)
    doc["authors"] = [
        {k: v for k, v in a.items() if v}
        for a in state.get("authors", [])
        if a.get("name")
    ]

    # Parameters
    parameters: dict[str, Any] = {}
    for p in state.get("parameters", []):
        pid = p["id"].strip()
        if not pid:
            continue
        param: dict[str, Any] = {
            "type": p["type"],
            "label": p["label"],
            "default": coerce_numeric(str(p["default"])),
        }
        if p.get("description"):
            param["description"] = p["description"]
        pmin = coerce_numeric_or_none(str(p.get("min", "")))
        pmax = coerce_numeric_or_none(str(p.get("max", "")))
        if pmin is not None:
            param["min"] = pmin
        if pmax is not None:
            param["max"] = pmax
        if p.get("unit"):
            param["unit"] = p["unit"]
        refs = [r.strip() for r in p.get("references", "").splitlines() if r.strip()]
        if refs:
            param["references"] = refs
        if p["type"] == "enum" and p.get("options"):
            options = parse_key_value_lines(p["options"])
            param["options"] = {str(k): str(v) for k, v in options.items()}
        parameters[pid] = param
    doc["parameters"] = parameters

    # Equations
    equations: dict[str, Any] = {}
    for eq in state.get("equations", []):
        eid = eq["id"].strip()
        if not eid:
            continue
        entry: dict[str, Any] = {"label": eq["label"], "compute": eq["compute"]}
        if eq.get("unit"):
            entry["unit"] = eq["unit"]
        if eq.get("output"):
            entry["output"] = eq["output"]
        equations[eid] = entry
    doc["equations"] = equations

    # Groups (pass through)
    groups = state.get("groups")
    if groups:
        doc["groups"] = groups

    # Scenarios
    scenarios: list[dict[str, Any]] = []
    for sc in state.get("scenarios", []):
        sid = sc["id"].strip()
        if not sid:
            continue
        scenarios.append(
            {
                "id": sid,
                "label": sc["label"],
                "vars": parse_key_value_lines(sc.get("vars", "")),
            }
        )
    doc["scenarios"] = scenarios

    # Report blocks
    report: list[dict[str, Any]] = []
    for blk in state.get("report_blocks", []):
        btype = blk["type"]
        if btype == "markdown":
            report.append({"type": "markdown", "content": blk.get("content", "")})
        elif btype == "table":
            entry_t: dict[str, Any] = {"type": "table"}
            if blk.get("caption"):
                entry_t["caption"] = blk["caption"]
            cols = [c.strip() for c in blk.get("columns", "").split(",") if c.strip()]
            if cols:
                entry_t["columns"] = cols
            entry_t["rows"] = parse_table_rows(blk.get("rows", ""))
            report.append(entry_t)
        elif btype == "figure":
            report.append({"type": "figure", "id": blk.get("id", "")})
        elif btype == "graph":
            entry_g: dict[str, Any] = {
                "type": "graph",
                "kind": blk.get("kind", "bar"),
            }
            if blk.get("title"):
                entry_g["title"] = blk["title"]
            if blk.get("caption"):
                entry_g["caption"] = blk["caption"]
            cols_g = [c.strip() for c in blk.get("columns", "").split(",") if c.strip()]
            if cols_g:
                entry_g["columns"] = cols_g
            entry_g["rows"] = parse_table_rows(blk.get("rows", ""))
            report.append(entry_g)
    doc["report"] = report

    # Figures
    figures: list[dict[str, Any]] = []
    for fig in state.get("figures", []):
        fid = fig["id"].strip()
        if not fid:
            continue
        entry_f: dict[str, Any] = {"id": fid, "title": fig["title"]}
        if fig.get("alt_text"):
            entry_f["alt-text"] = fig["alt_text"]
        if fig.get("py_code"):
            entry_f["py-code"] = fig["py_code"]
        figures.append(entry_f)
    doc["figures"] = figures

    return doc


def validate_model_dict(doc: dict[str, Any]) -> Model:
    """Validate a model document dict against the ``Model`` schema.

    Raises :class:`ValueError` on validation failure.
    """
    return opaque_to_typed(doc, Model)


def serialize_to_yaml(doc: dict[str, Any]) -> bytes:
    """Serialize a model document dict to YAML bytes."""
    fmt = YAMLFormat("model.yaml")
    return fmt.write(doc)


__all__ = [
    "DEFAULT_STATE",
    "EditorState",
    "build_model_dict",
    "coerce_numeric",
    "coerce_numeric_or_none",
    "parse_key_value_lines",
    "parse_table_rows",
    "serialize_to_yaml",
    "table_row_to_str",
    "validate_model_dict",
    "yaml_to_state",
]
