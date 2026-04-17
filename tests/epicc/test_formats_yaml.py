from io import BytesIO

import pytest

from epicc.formats.yaml import YAMLFormat


def _fmt() -> YAMLFormat:
    return YAMLFormat("test.yaml")


def _stream(text: str) -> BytesIO:
    return BytesIO(text.encode())


def test_read_simple_mapping():
    data, _ = _fmt().read(_stream("a: 1\nb: hello\n"))
    assert data == {"a": 1, "b": "hello"}


def test_read_nested_mapping():
    data, _ = _fmt().read(_stream("costs:\n  latent: 300\n  active: 500\n"))
    assert data == {"costs": {"latent": 300, "active": 500}}


def test_read_non_mapping_raises():
    with pytest.raises(ValueError, match="Expected a YAML mapping"):
        _fmt().read(_stream("- a\n- b\n"))


def test_read_invalid_yaml_raises():
    with pytest.raises(ValueError, match="Failed to parse YAML"):
        _fmt().read(_stream("key: [unclosed"))


def test_write_round_trips():
    original = {"a": 1, "b": {"c": 2}}
    result = _fmt().write(original)
    data, _ = _fmt().read(BytesIO(result))
    assert data == original


def test_write_with_template_preserves_comments():
    source = """# top comment
costs:
  # latent comment
  latent: 300
  active: 500
"""
    data, template = _fmt().read(_stream(source))
    data["costs"]["latent"] = 123

    result = _fmt().write(data, template)
    text = result.decode("utf-8")

    assert "# top comment" in text
    assert "# latent comment" in text
    assert "latent: 123" in text
