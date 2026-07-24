from __future__ import annotations

from io import BytesIO
import re
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

from epicc.model.base import BaseSimulationModel
from epicc.model.parameters import format_value


def build_report_payload(
    model: BaseSimulationModel,
    run_output: dict[str, Any],
) -> dict[str, Any]:
    """Build a shared structured report payload for DOCX/PDF exports."""
    model_def = model.get_model_definition()
    scenario_results: dict[str, dict[str, Any]] = run_output.get("scenario_results_by_id", {})
    label_overrides: dict[str, str] = run_output.get("label_overrides", {}) 
    scenarios = run_output.get("scenarios", getattr(model_def, "scenarios", []) or [])

    scenario_labels: dict[str, str] = {}
    for s in scenarios or []:
        sid = getattr(s, "id", None)
        lbl = getattr(s, "label", None)
        if sid:
            scenario_labels[sid] = label_overrides.get(sid, lbl or sid)
    sections: list[dict[str, Any]] = []
    for item in getattr(model_def, "report", []) or []:
        kind = getattr(item, "type", None)

        if kind == "markdown":
            sections.append({"type": "markdown", "content": getattr(item, "content", "")})
            continue

        if kind in {"table", "graph"}:
            item_columns = getattr(item, "columns", None) or []
            if item_columns:
                selected_scenario_ids = [sid for sid in item_columns if sid in scenario_results]
            else:
                selected_scenario_ids = [
                    getattr(s, "id", None)
                    for s in scenarios or []
                    if getattr(s, "id", None) in scenario_results
                ]
                if not selected_scenario_ids:
                    selected_scenario_ids = list(scenario_results.keys())

            rows_out: list[dict[str, Any]] = []
            for r in getattr(item, "rows", []) or []:
                eq_key = getattr(r, "value", "")
                values: dict[str, Any] = {}
                for sid in selected_scenario_ids:
                    eqs = scenario_results.get(sid, {})
                    raw_value = (eqs or {}).get(eq_key, "N/A")
                    values[scenario_labels.get(sid, sid)] = format_value(
                        raw_value,
                        model_def.equations.get(eq_key),
                    )
                rows_out.append({"label": getattr(r, "label", eq_key), "values": values})

            if kind == "graph":
                sections.append(
                    {
                        "type": "graph",
                        "kind": getattr(item, "kind", "bar"),
                        "title": getattr(item, "title", ""),
                        "caption": getattr(item, "caption", ""),
                        "rows": rows_out,
                    }
                )
            else:
                sections.append(
                    {
                        "type": "table",
                        "title": getattr(item, "title", ""),
                        "caption": getattr(item, "caption", ""),
                        "rows": rows_out,
                    }
                )

    return {
        "__report__": {
            "title": model_def.title,
            "description": getattr(model_def, "description", ""),
            "sections": sections,
        }
    }


def build_report_docx_bytes(report_payload: dict[str, Any]) -> bytes:
    """Build minimal DOCX package from a structured report payload."""
    report = report_payload.get("__report__", {})

    content_types_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>'''

    rels_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>'''

    body_parts: list[str] = []

    title = str(report.get("title", "Report"))
    body_parts.append(_w_paragraph(title, bold=True))

    description = str(report.get("description", "")).strip()
    if description:
        body_parts.append(_w_paragraph(description))

    sections = report.get("sections", [])
    if isinstance(sections, list):
        for section in sections:
            if not isinstance(section, dict):
                continue

            sec_type = str(section.get("type", "")).lower()

            if sec_type == "markdown":
                content = str(section.get("content", ""))
                for line in content.splitlines():
                    line = line.strip()
                    if not line or line == "$$":
                        continue

                    if line.startswith("### "):
                        body_parts.append(_w_paragraph(_strip_markdown_inline(line[4:]), bold=True))
                    elif line.startswith("## "):
                        body_parts.append(_w_paragraph(_strip_markdown_inline(line[3:]), bold=True))
                    elif line.startswith("# "):
                        body_parts.append(_w_paragraph(_strip_markdown_inline(line[2:]), bold=True))
                    elif line.startswith("- "):
                        body_parts.append(_w_paragraph(f"• {_strip_markdown_inline(line[2:])}"))
                    elif re.match(r"^\d+\.\s+", line):
                        match = re.match(r"^(\d+)\.\s+(.*)$", line)
                        if match:
                            idx, content_line = match.groups()
                            body_parts.append(_w_paragraph(f"{idx}. {_strip_markdown_inline(content_line)}"))
                        else:
                            body_parts.append(_w_paragraph(_strip_markdown_inline(line)))
                    else:
                        body_parts.append(_w_paragraph(_strip_markdown_inline(_latex_to_text(line))))

            elif sec_type in {"table", "graph"}:
                sec_title = str(section.get("title", "")).strip()
                caption = str(section.get("caption", "")).strip()
                graph_kind = str(section.get("kind", "")).strip()

                if sec_title:
                    body_parts.append(_w_paragraph(sec_title, bold=True))
                if sec_type == "graph" and graph_kind:
                    body_parts.append(_w_paragraph(f"Chart type: {graph_kind}"))
                if caption:
                    body_parts.append(_w_paragraph(caption))

                rows = section.get("rows", [])
                if isinstance(rows, list):
                    for row in rows:
                        if not isinstance(row, dict):
                            continue
                        label = str(row.get("label", "")).strip()
                        values = row.get("values", {})

                        if isinstance(values, dict) and values:
                            body_parts.append(_w_paragraph(label, bold=True))
                            for scen, val in values.items():
                                body_parts.append(_w_paragraph(f"  {scen}: {val}"))
                        else:
                            val = row.get("value", "")
                            body_parts.append(_w_paragraph(f"{label}: {val}"))

    document_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    {''.join(body_parts)}
    <w:sectPr/>
  </w:body>
</w:document>'''

    buf = BytesIO()
    with ZipFile(buf, "w", ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types_xml)
        zf.writestr("_rels/.rels", rels_xml)
        zf.writestr("word/document.xml", document_xml)

    return buf.getvalue()


def _w_paragraph(text: str, *, bold: bool = False) -> str:
    t = _escape_xml(text)
    if bold:
        return f'<w:p><w:r><w:rPr><w:b/></w:rPr><w:t xml:space="preserve">{t}</w:t></w:r></w:p>'
    return f'<w:p><w:r><w:t xml:space="preserve">{t}</w:t></w:r></w:p>'


def _escape_xml(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _strip_markdown_inline(text: str) -> str:
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"__(.*?)__", r"\1", text)
    text = re.sub(r"\*(.*?)\*", r"\1", text)
    text = re.sub(r"_(.*?)_", r"\1", text)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    return " ".join(text.split())


def _latex_to_text(text: str) -> str:
    text = text.replace("\\LaTeX", "LaTeX")
    text = re.sub(r"\\text\s*\{([^}]*)\}", r"\1", text)
    text = re.sub(r"\\[a-zA-Z]+", "", text)
    text = text.replace("{", "").replace("}", "")
    text = text.replace("$$", "")
    return " ".join(text.split())
