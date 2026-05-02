from pathlib import Path
from zipfile import ZipFile
from unittest.mock import MagicMock

import pytest

from epicc.formats.docx import DOCXFormat


def _make_report_payload(title: str = "Test Report") -> dict:
    return {
        "__report__": {
            "title": title,
            "sections": [
                {"type": "markdown", "content": "## Overview\nSome text here."},
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
    fmt = DOCXFormat(Path("report.docx"))
    result = fmt.write(_make_report_payload())
    assert isinstance(result, bytes)
    with ZipFile.__new__(ZipFile) as _:
        pass
    from io import BytesIO
    with ZipFile(BytesIO(result)) as zf:
        names = zf.namelist()
    assert "[Content_Types].xml" in names
    assert "word/document.xml" in names


def test_write_contains_title():
    fmt = DOCXFormat(Path("report.docx"))
    result = fmt.write(_make_report_payload("My Report"))
    from io import BytesIO
    with ZipFile(BytesIO(result)) as zf:
        doc_xml = zf.read("word/document.xml").decode()
    assert "My Report" in doc_xml


def test_write_contains_scenario_values():
    fmt = DOCXFormat(Path("report.docx"))
    result = fmt.write(_make_report_payload())
    from io import BytesIO
    with ZipFile(BytesIO(result)) as zf:
        doc_xml = zf.read("word/document.xml").decode()
    assert "Scenario A" in doc_xml
    assert "100" in doc_xml


def test_write_contains_markdown_content():
    fmt = DOCXFormat(Path("report.docx"))
    result = fmt.write(_make_report_payload())
    from io import BytesIO
    with ZipFile(BytesIO(result)) as zf:
        doc_xml = zf.read("word/document.xml").decode()
    assert "Some text here" in doc_xml


def test_read_raises_not_implemented():
    fmt = DOCXFormat(Path("report.docx"))
    with pytest.raises(NotImplementedError):
        fmt.read(b"")