from io import BytesIO

import pytest
from pydantic import BaseModel

from epicc.formats import (
    XLSXFormat,
    YAMLFormat,
    get_format,
    read_from_format,
)


class _Simple(BaseModel):
    x: int
    y: str


def test_get_format_yaml_returns_yaml_format():
    assert isinstance(get_format("params.yaml"), YAMLFormat)


def test_get_format_xlsx_returns_xlsx_format():
    assert isinstance(get_format("params.xlsx"), XLSXFormat)


def test_get_format_unsupported_raises():
    with pytest.raises(ValueError, match="Unsupported file format"):
        get_format("params.csv")


def test_read_from_format_yaml():
    model, _ = read_from_format("params.yaml", BytesIO(b"x: 10\ny: hello\n"), _Simple)
    assert model.x == 10
    assert model.y == "hello"
