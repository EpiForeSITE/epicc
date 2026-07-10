from zipfile import ZipFile

from epicc.ui.report_exports import build_report_docx_bytes


def _make_report_payload(title: str = "Test Report") -> dict:
    return {
        "__report__": {
            "title": title,
            "description": "Summary paragraph",
            "sections": [
                {
                    "type": "markdown",
                    "content": "## Overview\n- **Strong point**\n$$\\LaTeX \\text{ test.}$$\nSome text here.",
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
    with ZipFile.__new__(ZipFile) as _:
        pass
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


def test_write_contains_markdown_content():
    result = build_report_docx_bytes(_make_report_payload())
    from io import BytesIO
    with ZipFile(BytesIO(result)) as zf:
        doc_xml = zf.read("word/document.xml").decode()
    assert "Some text here" in doc_xml
    assert "Strong point" in doc_xml
    assert "LaTeX test." in doc_xml
    assert "**" not in doc_xml
    assert "$$" not in doc_xml
    assert "Chart type: bar" in doc_xml