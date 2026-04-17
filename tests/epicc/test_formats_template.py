from io import BytesIO
from typing import Literal

import openpyxl
from pydantic import BaseModel, Field

from epicc.formats.template import generate_template
from epicc.formats.xlsx import XLSXFormat
from epicc.formats.yaml import YAMLFormat


class _Inner(BaseModel):
    rate: float
    label: str = Field(default="default label", description="A label.")


class _Outer(BaseModel):
    name: str = Field(description="The name.")
    count: int = 5
    inner: _Inner
    theme: Literal["light", "dark"] = "light"
    note: str | None = None


def test_yaml_template_contains_defaults():
    result = generate_template(_Outer, YAMLFormat("template.yaml"))
    data, _ = YAMLFormat("template.yaml").read(BytesIO(result))

    assert data["count"] == 5
    assert data["theme"] == "light"
    assert data["note"] is None


def test_yaml_template_nested_model():
    result = generate_template(_Outer, YAMLFormat("template.yaml"))
    data, _ = YAMLFormat("template.yaml").read(BytesIO(result))

    assert isinstance(data["inner"], dict)
    assert data["inner"]["label"] == "default label"


def test_yaml_template_placeholder_for_required_fields():
    result = generate_template(_Outer, YAMLFormat("template.yaml"))
    data, _ = YAMLFormat("template.yaml").read(BytesIO(result))

    assert data["name"] == ""
    assert data["inner"]["rate"] == 0.0


def _read_xlsx_rows(data: bytes) -> dict[str, tuple]:
    """Parse an XLSX template into {key: (value, description)}."""
    wb = openpyxl.load_workbook(BytesIO(data))
    assert wb.active

    rows = list(wb.active.iter_rows(values_only=True))
    return {str(r[0]): (r[1], r[2]) for r in rows[1:] if r[0] is not None}


def test_xlsx_template_flattens_nested():
    result = generate_template(_Outer, XLSXFormat("template.xlsx"))
    rows = _read_xlsx_rows(result)

    assert "inner.rate" in rows
    assert "inner.label" in rows


def test_xlsx_template_includes_descriptions():
    result = generate_template(_Outer, XLSXFormat("template.xlsx"))
    rows = _read_xlsx_rows(result)

    assert rows["name"][1] == "The name."
    assert rows["inner.label"][1] == "A label."


def test_xlsx_template_values_match_defaults():
    result = generate_template(_Outer, XLSXFormat("template.xlsx"))
    rows = _read_xlsx_rows(result)

    assert rows["count"][0] == 5
    assert rows["theme"][0] == "light"
    assert rows["inner.label"][0] == "default label"
