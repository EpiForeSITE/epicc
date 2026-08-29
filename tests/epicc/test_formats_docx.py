from zipfile import ZipFile

from epicc.config import CONFIG
from epicc.ui.report_exports import (
    _build_plotly_figure_from_rows,
    build_report_docx_bytes,
    docx_chart_images_supported,
    report_contains_graph_sections,
)


def _make_report_payload(title: str = "Test Report") -> dict:
    return {
        "__report__": {
            "title": title,
            "description": "Summary paragraph",
            "sections": [
                {
                    "type": "markdown",
                    "content": "## Overview\n- **Strong point**\nSee [CDC guidance](https://cdc.gov).\n$$\\LaTeX \\text{ test.}$$\nSome text here.",
                },
                {
                    "type": "graph",
                    "kind": "bar",
                    "title": "Outcomes",
                    "caption": "Chart caption",
                    "rows": [
                        {"label": "Cases", "values": {"Scenario A": 5, "Scenario B": 3}},
                    ],
                },
                {
                    "type": "table",
                    "title": "Results",
                    "caption": "Scenario comparison",
                    "rows": [
                        {"label": "Cost", "values": {"Scenario A": 100, "Scenario B": 200}},
                        {"label": "Cases", "values": {"Scenario A": 5, "Scenario B": 3}},
                    ],
                },
            ],
        }
    }


def test_write_produces_valid_zip():
    result = build_report_docx_bytes(_make_report_payload())
    assert isinstance(result, bytes)
    from io import BytesIO
    with ZipFile(BytesIO(result)) as zf:
        names = zf.namelist()
    assert "[Content_Types].xml" in names
    assert "word/document.xml" in names


def test_write_contains_title():
    result = build_report_docx_bytes(_make_report_payload("My Report"))
    from io import BytesIO
    with ZipFile(BytesIO(result)) as zf:
        doc_xml = zf.read("word/document.xml").decode()
    assert "My Report" in doc_xml
    assert "Summary paragraph" in doc_xml


def test_write_contains_scenario_values():
    result = build_report_docx_bytes(_make_report_payload())
    from io import BytesIO
    with ZipFile(BytesIO(result)) as zf:
        doc_xml = zf.read("word/document.xml").decode()
    assert "Scenario A" in doc_xml
    assert "100" in doc_xml
    assert "<w:tbl" in doc_xml
    assert "TableGrid" in doc_xml


def test_write_contains_markdown_content():
    result = build_report_docx_bytes(_make_report_payload())
    from io import BytesIO
    with ZipFile(BytesIO(result)) as zf:
        doc_xml = zf.read("word/document.xml").decode()
    assert "Some text here" in doc_xml
    assert "Strong point" in doc_xml
    assert "CDC guidance" in doc_xml
    assert "[CDC guidance](https://cdc.gov)" not in doc_xml
    assert "<m:oMath>" in doc_xml
    assert "LaTeX test." in doc_xml
    assert "\\text{" not in doc_xml
    assert "**" not in doc_xml
    assert "Chart type: bar" not in doc_xml


def test_write_contains_chart_image_or_fallback_note():
    result = build_report_docx_bytes(_make_report_payload())
    from io import BytesIO
    with ZipFile(BytesIO(result)) as zf:
        doc_xml = zf.read("word/document.xml").decode()
        names = zf.namelist()

    has_image = any(name.startswith("word/media/") and name.endswith(".png") for name in names)
    has_fallback = "Chart image export unavailable in this runtime" in doc_xml
    assert has_image or has_fallback


def test_chart_images_supported_for_current_runtime():
    assert docx_chart_images_supported() is True


def test_report_contains_graph_sections_true_for_graph_payload():
    assert report_contains_graph_sections(_make_report_payload()) is True


def test_report_contains_graph_sections_false_for_non_graph_payload():
    payload = _make_report_payload()
    payload["__report__"]["sections"] = [
        s for s in payload["__report__"]["sections"] if s.get("type") != "graph"
    ]
    assert report_contains_graph_sections(payload) is False


def test_export_figure_uses_matching_color_palette():
    fig = _build_plotly_figure_from_rows(
        {
            "kind": "bar",
            "title": "Outcomes",
            "caption": "Chart caption",
            "rows": [
                {"label": "Cases", "raw_values": {"Scenario A": 5, "Scenario B": 3}},
            ],
        }
    )
    assert fig is not None
    assert fig.data[0].marker.color == CONFIG.brand.colors.chart_palette[0]


def test_export_image_xml_does_not_emit_visible_label_text():
    result = build_report_docx_bytes(_make_report_payload())
    from io import BytesIO
    with ZipFile(BytesIO(result)) as zf:
        doc_xml = zf.read("word/document.xml").decode()
    assert 'name="Chart"' not in doc_xml
    assert 'descr="Chart"' not in doc_xml