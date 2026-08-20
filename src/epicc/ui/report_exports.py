from __future__ import annotations

import html
from io import BytesIO
import importlib.util
import math
import re
import sys
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

import plotly.colors as plotly_colors
import plotly.graph_objects as go
import plotly.io as pio

from epicc.model.base import BaseSimulationModel
from epicc.model.parameters import format_value


def docx_chart_images_supported() -> bool:
    """Return True when Plotly PNG export can actually render in this runtime."""
    if sys.platform == "emscripten":
        return False

    if importlib.util.find_spec("kaleido") is None:
        return False

    try:
        fig = go.Figure(go.Bar(x=["A", "B"], y=[1, 2]))
        pio.to_image(fig, format="png", width=200, height=120, scale=1)
        return True
    except Exception:
        return False


def report_contains_graph_sections(report_payload: dict[str, Any]) -> bool:
    """Return True when the structured report payload has graph sections."""
    report = report_payload.get("__report__", {})
    sections = report.get("sections", [])
    if not isinstance(sections, list):
        return False

    for section in sections:
        if isinstance(section, dict) and str(section.get("type", "")).lower() == "graph":
            return True
    return False


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
                raw_values: dict[str, Any] = {}
                for sid in selected_scenario_ids:
                    eqs = scenario_results.get(sid, {})
                    raw_value = (eqs or {}).get(eq_key, "N/A")
                    scenario_label = scenario_labels.get(sid, sid)
                    raw_values[scenario_label] = raw_value
                    values[scenario_label] = format_value(
                        raw_value,
                        model_def.equations.get(eq_key),
                    )
                rows_out.append(
                    {
                        "label": getattr(r, "label", eq_key),
                        "values": values,
                        "raw_values": raw_values,
                    }
                )

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

    media_parts: dict[str, bytes] = {}
    doc_relationships: list[tuple[str, str, str]] = []
    next_image_id = 1
    chart_images_supported = docx_chart_images_supported()

    content_types_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
    <Default Extension="png" ContentType="image/png"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>'''

    rels_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>'''

    body_parts: list[str] = []

    title = str(report.get("title", "Report"))
    body_parts.append(_w_paragraph(title, bold=True))
    body_parts.append(_w_paragraph(" "))

    description = str(report.get("description", "")).strip()
    if description:
        body_parts.append(_w_paragraph(description))
        body_parts.append(_w_paragraph(" "))

    sections = report.get("sections", [])
    if isinstance(sections, list):
        has_rendered_section = False
        for section in sections:
            if not isinstance(section, dict):
                continue

            if has_rendered_section:
                body_parts.append(_w_paragraph(" "))

            sec_type = str(section.get("type", "")).lower()

            if sec_type == "markdown":
                content = str(section.get("content", ""))
                has_rendered_markdown_line = False
                for line in content.splitlines():
                    line = line.strip()
                    if not line or line == "$$":
                        continue

                    if line.startswith("### "):
                        if has_rendered_markdown_line:
                            body_parts.append(_w_paragraph(" "))
                        body_parts.append(_w_paragraph(_strip_markdown_inline(line[4:]), bold=True))
                        has_rendered_markdown_line = True
                    elif line.startswith("## "):
                        if has_rendered_markdown_line:
                            body_parts.append(_w_paragraph(" "))
                        body_parts.append(_w_paragraph(_strip_markdown_inline(line[3:]), bold=True))
                        has_rendered_markdown_line = True
                    elif line.startswith("# "):
                        if has_rendered_markdown_line:
                            body_parts.append(_w_paragraph(" "))
                        body_parts.append(_w_paragraph(_strip_markdown_inline(line[2:]), bold=True))
                        has_rendered_markdown_line = True
                    elif line.startswith("- "):
                        body_parts.append(_w_paragraph(f"• {_strip_markdown_inline(line[2:])}"))
                        has_rendered_markdown_line = True
                    elif re.match(r"^\d+\.\s+", line):
                        match = re.match(r"^(\d+)\.\s+(.*)$", line)
                        if match:
                            idx, content_line = match.groups()
                            body_parts.append(_w_paragraph(f"{idx}. {_strip_markdown_inline(content_line)}"))
                        else:
                            body_parts.append(_w_paragraph(_strip_markdown_inline(line)))
                        has_rendered_markdown_line = True
                    else:
                        body_parts.append(_w_paragraph(_strip_markdown_inline(_latex_to_text(line))))
                        has_rendered_markdown_line = True
                has_rendered_section = True

            elif sec_type in {"table", "graph"}:
                sec_title = str(section.get("title", "")).strip()
                caption = str(section.get("caption", "")).strip()

                if sec_type == "table" and sec_title:
                    body_parts.append(_w_paragraph(sec_title, bold=True))

                rows = section.get("rows", [])
                if isinstance(rows, list):
                    headers, table_rows = _rows_to_table(rows)
                    if headers and table_rows:
                        body_parts.append(_w_table(headers, table_rows))
                    else:
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

                    if sec_type == "graph":
                        png_bytes = _render_graph_png(section) if chart_images_supported else None
                        if png_bytes is not None:
                            rid = f"rId{next_image_id}"
                            next_image_id += 1
                            media_name = f"image{len(media_parts) + 1}.png"
                            media_parts[f"word/media/{media_name}"] = png_bytes
                            doc_relationships.append(
                                (
                                    rid,
                                    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image",
                                    f"media/{media_name}",
                                )
                            )
                            body_parts.append(_w_paragraph(" "))
                            body_parts.append(
                                _w_image(
                                    relationship_id=rid,
                                    name=sec_title or "Chart",
                                    width_px=820,
                                    height_px=460,
                                )
                            )
                            body_parts.append(_w_paragraph(" "))
                        else:
                            body_parts.append(
                                _w_paragraph(
                                    "Chart image export unavailable in this runtime; included chart data table above."
                                )
                            )
                has_rendered_section = True

    document_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document
  xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
  xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
  xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
  xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
  xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">
  <w:body>
    {''.join(body_parts)}
    <w:sectPr/>
  </w:body>
</w:document>'''

    doc_rels_xml = _build_document_relationships_xml(doc_relationships)

    buf = BytesIO()
    with ZipFile(buf, "w", ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types_xml)
        zf.writestr("_rels/.rels", rels_xml)
        zf.writestr("word/document.xml", document_xml)
        zf.writestr("word/_rels/document.xml.rels", doc_rels_xml)
        for part_name, payload in media_parts.items():
            zf.writestr(part_name, payload)

    return buf.getvalue()


def _build_document_relationships_xml(
    relationships: list[tuple[str, str, str]],
) -> str:
    rel_parts = [
        f'<Relationship Id="{_escape_xml(rid)}" Type="{_escape_xml(rel_type)}" Target="{_escape_xml(target)}"/>'
        for rid, rel_type, target in relationships
    ]
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f"{''.join(rel_parts)}"
        '</Relationships>'
    )


def _rows_to_table(rows: list[Any]) -> tuple[list[str], list[list[str]]]:
    scenario_headers: list[str] = []
    seen_headers: set[str] = set()
    table_rows: list[list[str]] = []

    for row in rows:
        if not isinstance(row, dict):
            continue
        values = row.get("values")
        if isinstance(values, dict):
            for scenario in values:
                scenario_name = str(scenario)
                if scenario_name not in seen_headers:
                    seen_headers.add(scenario_name)
                    scenario_headers.append(scenario_name)

    headers = ["Metric", *scenario_headers]

    for row in rows:
        if not isinstance(row, dict):
            continue
        label = str(row.get("label", "")).strip()
        values = row.get("values")
        if isinstance(values, dict) and scenario_headers:
            table_rows.append([label, *[str(values.get(h, "N/A")) for h in scenario_headers]])
        else:
            table_rows.append([label, str(row.get("value", ""))])

    if not table_rows:
        return [], []

    if len(headers) < len(table_rows[0]):
        headers = ["Metric", "Value"]
    return headers, table_rows


def _w_table(headers: list[str], rows: list[list[str]]) -> str:
    header_cells = "".join(_w_table_cell(h, header=True) for h in headers)
    header_row = f"<w:tr>{header_cells}</w:tr>"

    body_rows: list[str] = []
    for row in rows:
        cells: list[str] = []
        for index, value in enumerate(row):
            cells.append(_w_table_cell(value, header=(index == 0)))
        body_rows.append(f"<w:tr>{''.join(cells)}</w:tr>")

    return (
        "<w:tbl>"
        "<w:tblPr>"
        "<w:tblStyle w:val=\"TableGrid\"/>"
        "<w:tblW w:w=\"0\" w:type=\"auto\"/>"
        "<w:tblBorders>"
        "<w:top w:val=\"single\" w:sz=\"6\" w:space=\"0\" w:color=\"808080\"/>"
        "<w:left w:val=\"single\" w:sz=\"6\" w:space=\"0\" w:color=\"808080\"/>"
        "<w:bottom w:val=\"single\" w:sz=\"6\" w:space=\"0\" w:color=\"808080\"/>"
        "<w:right w:val=\"single\" w:sz=\"6\" w:space=\"0\" w:color=\"808080\"/>"
        "<w:insideH w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"BFBFBF\"/>"
        "<w:insideV w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"BFBFBF\"/>"
        "</w:tblBorders>"
        "</w:tblPr>"
        f"{header_row}{''.join(body_rows)}"
        "</w:tbl>"
    )


def _w_table_cell(text: Any, *, header: bool = False) -> str:
    t = _escape_xml(str(text))
    run_pr = "<w:rPr><w:b/></w:rPr>" if header else ""
    cell_shading = '<w:shd w:val="clear" w:color="auto" w:fill="F2F2F2"/>' if header else ""
    return (
        "<w:tc>"
        "<w:tcPr>"
        f"{cell_shading}"
        "</w:tcPr>"
        "<w:p><w:r>"
        f"{run_pr}"
        f"<w:t xml:space=\"preserve\">{t}</w:t>"
        "</w:r></w:p>"
        "</w:tc>"
    )


def _w_image(
    *,
    relationship_id: str,
    name: str,
    width_px: int,
    height_px: int,
) -> str:
    # Keep exported DOCX charts at a fixed page-friendly width (17 cm),
    # while preserving the original aspect ratio.
    width_emu = 17 * 360000
    height_emu = int(width_emu * (height_px / max(width_px, 1)))
    safe_name = _escape_xml(name)
    return (
        "<w:p><w:pPr><w:jc w:val=\"center\"/></w:pPr><w:r>"
        "<w:drawing>"
        "<wp:inline distT=\"0\" distB=\"0\" distL=\"0\" distR=\"0\">"
        f"<wp:extent cx=\"{width_emu}\" cy=\"{height_emu}\"/>"
        "<wp:effectExtent l=\"0\" t=\"0\" r=\"0\" b=\"0\"/>"
        "<wp:docPr id=\"1\" name=\"\" descr=\"\"/>"
        "<wp:cNvGraphicFramePr/>"
        "<a:graphic>"
        "<a:graphicData uri=\"http://schemas.openxmlformats.org/drawingml/2006/picture\">"
        "<pic:pic>"
        "<pic:nvPicPr>"
        "<pic:cNvPr id=\"0\" name=\"\"/>"
        "<pic:cNvPicPr/>"
        "</pic:nvPicPr>"
        "<pic:blipFill>"
        f"<a:blip r:embed=\"{_escape_xml(relationship_id)}\"/>"
        "<a:stretch><a:fillRect/></a:stretch>"
        "</pic:blipFill>"
        "<pic:spPr>"
        "<a:xfrm>"
        "<a:off x=\"0\" y=\"0\"/>"
        f"<a:ext cx=\"{width_emu}\" cy=\"{height_emu}\"/>"
        "</a:xfrm>"
        "<a:prstGeom prst=\"rect\"><a:avLst/></a:prstGeom>"
        "</pic:spPr>"
        "</pic:pic>"
        "</a:graphicData>"
        "</a:graphic>"
        "</wp:inline>"
        "</w:drawing>"
        "</w:r>"
        "</w:p>"
    )


def _render_graph_png(section: dict[str, Any]) -> bytes | None:
    rows = section.get("rows")
    if not isinstance(rows, list) or not rows:
        return None

    fig = _build_plotly_figure_from_rows(section)
    if fig is None:
        return None

    try:
        # Requires Kaleido in CPython. WASM/stlite environments do not currently support this path.
        return pio.to_image(fig, format="png", width=700, height=390, scale=2)
    except Exception:
        return None


def _build_plotly_figure_from_rows(section: dict[str, Any]) -> go.Figure | None:
    rows = section.get("rows")
    if not isinstance(rows, list) or not rows:
        return None

    kind = str(section.get("kind", "bar")).strip().lower()
    scenario_names: list[str] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        raw_values = row.get("raw_values")
        values = raw_values if isinstance(raw_values, dict) else row.get("values")
        if isinstance(values, dict):
            for scenario_name in values:
                scenario_text = str(scenario_name)
                if scenario_text not in seen:
                    seen.add(scenario_text)
                    scenario_names.append(scenario_text)

    if not scenario_names:
        return None

    fig = go.Figure()

    if kind in {"bar", "stacked_bar", "line"}:
        for row in rows:
            if not isinstance(row, dict):
                continue
            label = str(row.get("label", "")).strip()
            raw_values = row.get("raw_values")
            values_map = raw_values if isinstance(raw_values, dict) else row.get("values", {})
            if not isinstance(values_map, dict):
                continue
            values = [_coerce_float(values_map.get(s, 0)) for s in scenario_names]
            if kind in {"bar", "stacked_bar"}:
                fig.add_trace(
                    go.Bar(
                        name=label,
                        x=scenario_names,
                        y=values,
                        marker={"color": list(plotly_colors.qualitative.Plotly)[len(fig.data) % len(plotly_colors.qualitative.Plotly)]},
                    )
                )
            else:
                fig.add_trace(
                    go.Scatter(
                        name=label,
                        x=scenario_names,
                        y=values,
                        mode="lines+markers",
                        line={"color": list(plotly_colors.qualitative.Plotly)[len(fig.data) % len(plotly_colors.qualitative.Plotly)]},
                        marker={"color": list(plotly_colors.qualitative.Plotly)[len(fig.data) % len(plotly_colors.qualitative.Plotly)]},
                    )
                )

        if kind == "bar":
            fig.update_layout(barmode="group")
            _apply_yaxis_ticks(fig, [
                _coerce_float(values_map.get(s, 0))
                for row in rows
                if isinstance(row, dict)
                for values_map in [row.get("raw_values") if isinstance(row.get("raw_values"), dict) else row.get("values", {})]
                if isinstance(values_map, dict)
                for s in scenario_names
            ])
        elif kind == "stacked_bar":
            fig.update_layout(barmode="stack")
            _apply_yaxis_ticks(fig, [
                _coerce_float(values_map.get(s, 0))
                for row in rows
                if isinstance(row, dict)
                for values_map in [row.get("raw_values") if isinstance(row.get("raw_values"), dict) else row.get("values", {})]
                if isinstance(values_map, dict)
                for s in scenario_names
            ])

    elif kind == "pie":
        first_scenario = scenario_names[0]
        labels: list[str] = []
        values: list[float] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            labels.append(str(row.get("label", "")))
            raw_values = row.get("raw_values")
            values_map = raw_values if isinstance(raw_values, dict) else row.get("values", {})
            if isinstance(values_map, dict):
                values.append(_coerce_float(values_map.get(first_scenario, 0)))
            else:
                values.append(0.0)
        fig.add_trace(
            go.Pie(
                labels=labels,
                values=values,
                hole=0.3,
                marker={"colors": [list(plotly_colors.qualitative.Plotly)[i % len(plotly_colors.qualitative.Plotly)] for i in range(len(labels))]},
            )
        )
        default_title = first_scenario

    else:
        return None

    section_title = str(section.get("title", "")).strip()
    section_subtitle = str(section.get("caption", "")).strip()
    if kind == "pie":
        title_main = section_title or default_title
    else:
        title_main = section_title

    title_html = html.escape(title_main)
    if section_subtitle:
        title_html = f"{title_html}<br><sup>{html.escape(section_subtitle)}</sup>"

    palette = list(plotly_colors.qualitative.Plotly)
    chart_top_margin = 132 if kind in {"bar", "stacked_bar", "line"} else 92
    fig.update_layout(
        title={"text": title_html, "x": 0.5, "xanchor": "center", "y": 0.90, "yanchor": "top"},
        margin={"t": chart_top_margin, "b": 24, "l": 24, "r": 16},
        # Use an opaque white canvas for exported images so labels remain
        # readable when DOCX viewers are in dark mode.
        plot_bgcolor="white",
        paper_bgcolor="white",
        template="plotly",
        colorway=palette,
        legend_title_text="Component",
        font={"family": "Arial", "size": 12, "color": "#1f2937"},
        hovermode="x unified",
    )
    return fig


def _apply_yaxis_ticks(fig: go.Figure, values: list[float]) -> None:
    positive_values = [abs(v) for v in values if v is not None]
    if not positive_values:
        return

    max_value = max(positive_values)
    dtick = _nice_dtick(max_value, target_ticks=8)
    tickformat = ",.2f" if dtick < 0.1 else (",.1f" if dtick < 1 else ",.0f")
    fig.update_yaxes(tickmode="linear", dtick=dtick, tickformat=tickformat)


def _nice_dtick(max_value: float, target_ticks: int = 8) -> float:
    if max_value <= 0:
        return 1.0

    raw_step = max_value / max(target_ticks, 1)
    magnitude = 10 ** math.floor(math.log10(raw_step))
    normalized = raw_step / magnitude

    if normalized <= 1:
        nice = 1
    elif normalized <= 2:
        nice = 2
    elif normalized <= 2.5:
        nice = 2.5
    elif normalized <= 5:
        nice = 5
    else:
        nice = 10

    return nice * magnitude


def _coerce_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        if isinstance(value, str):
            cleaned = re.sub(r"[^0-9eE+\-.]", "", value)
            try:
                return float(cleaned)
            except (TypeError, ValueError):
                return 0.0
        return 0.0


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
