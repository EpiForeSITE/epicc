"""DOCX (Microsoft Word) format support for parameter and report export."""

from __future__ import annotations

from io import BytesIO
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

from epicc.formats.base import BaseFormat
from pydantic import BaseModel


class DOCXFormat(BaseFormat):
    """DOCX format reader/writer using minimal OOXML structure."""

    label = "Word (DOCX)"
    mime_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    def read(self, data) -> tuple[dict[str, Any], Any]:
        """DOCX read not yet supported; raise NotImplementedError."""
        raise NotImplementedError("DOCX parameter import is not yet supported.")

    def write(self, data: dict[str, Any], template: Any | None = None) -> bytes:
        """Serialize dict to DOCX using minimal OOXML structure."""
        report = data.get("__report__")
        if isinstance(report, dict):
            return _build_docx_from_report(report)
        return _build_docx_from_dict(data)

    def write_template(self, model: BaseModel) -> bytes:
        """Generate a template DOCX with placeholder parameter structure."""
        template_data = {
            "parameter_name_1": "value_1",
            "parameter_name_2": "value_2",
        }
        return _build_docx_from_dict(template_data)


def _build_docx_from_dict(data: dict[str, Any]) -> bytes:
    """Build minimal DOCX package from flat parameter dict."""

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

    # Build document body from parameters
    body_parts = []
    for key, value in data.items():
        # Basic XML escape
        key_safe = _escape_xml(str(key))
        val_safe = _escape_xml(str(value))
        body_parts.append(
            f'<w:p><w:r><w:t>{key_safe}: {val_safe}</w:t></w:r></w:p>'
        )

    document_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    {''.join(body_parts)}
    <w:sectPr/>
  </w:body>
</w:document>'''

    # Pack into ZIP
    buf = BytesIO()
    with ZipFile(buf, "w", ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types_xml)
        zf.writestr("_rels/.rels", rels_xml)
        zf.writestr("word/document.xml", document_xml)

    return buf.getvalue()


def _build_docx_from_report(report: dict[str, Any]) -> bytes:
    """Build minimal DOCX package from structured report dict."""

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
                    if line:
                        body_parts.append(_w_paragraph(line))

            elif sec_type in {"table", "graph"}:
                sec_title = str(section.get("title", "")).strip()
                caption = str(section.get("caption", "")).strip()

                if sec_title:
                    body_parts.append(_w_paragraph(sec_title, bold=True))
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
                            # fallback if payload is simple row/value
                            val = row.get("value", "")
                            body_parts.append(_w_paragraph(f"{label}: {val}"))

            else:
                # fallback for unknown section types
                body_parts.append(_w_paragraph(str(section)))

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
    """Minimal XML entity escaping."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )