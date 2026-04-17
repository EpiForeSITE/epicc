"""Tests for the non-UI helper functions in epicc.editor.helpers."""

from __future__ import annotations

import io
from typing import Any

import pytest

from epicc.editor.helpers import (
    build_model_dict,
    coerce_numeric,
    coerce_numeric_or_none,
    parse_key_value_lines,
    parse_table_rows,
    serialize_to_yaml,
    table_row_to_str,
    validate_model_dict,
    yaml_to_state,
)
from epicc.formats import opaque_to_typed
from epicc.formats.yaml import YAMLFormat
from epicc.model.schema import Model


# ---------------------------------------------------------------------------
# coerce_numeric
# ---------------------------------------------------------------------------


class TestCoerceNumeric:
    def test_integer(self) -> None:
        assert coerce_numeric("42") == 42

    def test_float(self) -> None:
        assert coerce_numeric("3.14") == pytest.approx(3.14)

    def test_bool_true(self) -> None:
        assert coerce_numeric("true") is True

    def test_bool_false(self) -> None:
        assert coerce_numeric("False") is False

    def test_string_passthrough(self) -> None:
        assert coerce_numeric("hello") == "hello"


# ---------------------------------------------------------------------------
# coerce_numeric_or_none
# ---------------------------------------------------------------------------


class TestCoerceNumericOrNone:
    def test_integer(self) -> None:
        assert coerce_numeric_or_none("10") == 10

    def test_float(self) -> None:
        assert coerce_numeric_or_none("2.5") == pytest.approx(2.5)

    def test_empty_string(self) -> None:
        assert coerce_numeric_or_none("") is None

    def test_whitespace(self) -> None:
        assert coerce_numeric_or_none("   ") is None

    def test_non_numeric(self) -> None:
        assert coerce_numeric_or_none("abc") is None


# ---------------------------------------------------------------------------
# parse_key_value_lines
# ---------------------------------------------------------------------------


class TestParseKeyValueLines:
    def test_basic(self) -> None:
        result = parse_key_value_lines("n_cases: 22\nrate: 0.5")
        assert result == {"n_cases": 22, "rate": pytest.approx(0.5)}

    def test_string_value(self) -> None:
        result = parse_key_value_lines("name: hello world")
        assert result == {"name": "hello world"}

    def test_empty(self) -> None:
        assert parse_key_value_lines("") == {}

    def test_skips_lines_without_colon(self) -> None:
        result = parse_key_value_lines("no colon here\nk: v")
        assert result == {"k": "v"}


# ---------------------------------------------------------------------------
# parse_table_rows / table_row_to_str round-trip
# ---------------------------------------------------------------------------


class TestTableRows:
    def test_round_trip_simple(self) -> None:
        text = "Hospitalization | eq_hosp"
        rows = parse_table_rows(text)
        assert len(rows) == 1
        assert rows[0] == {"label": "Hospitalization", "value": "eq_hosp"}
        assert table_row_to_str(rows[0]) == text

    def test_round_trip_with_emphasis(self) -> None:
        text = "TOTAL | eq_total | strong"
        rows = parse_table_rows(text)
        assert len(rows) == 1
        assert rows[0] == {"label": "TOTAL", "value": "eq_total", "emphasis": "strong"}
        assert table_row_to_str(rows[0]) == text

    def test_multiline(self) -> None:
        text = "A | eq_a\nB | eq_b | em"
        rows = parse_table_rows(text)
        assert len(rows) == 2

    def test_empty(self) -> None:
        assert parse_table_rows("") == []


# ---------------------------------------------------------------------------
# build_model_dict
# ---------------------------------------------------------------------------


class TestBuildModelDict:
    def _minimal_state(self) -> dict[str, Any]:
        return {
            "model_title": "Test Model",
            "model_description": "A test.",
            "authors": [{"name": "Tester", "email": ""}],
            "parameters": [
                {
                    "id": "x",
                    "type": "number",
                    "label": "X",
                    "description": "",
                    "default": "1.0",
                    "min": "0",
                    "max": "100",
                    "unit": "",
                    "references": "",
                    "options": "",
                }
            ],
            "equations": [
                {"id": "eq_x", "label": "X value", "unit": "", "output": "number", "compute": "x * 2"}
            ],
            "groups": [],
            "scenarios": [
                {"id": "base", "label": "Base", "vars": "n: 1"}
            ],
            "report_blocks": [
                {"type": "markdown", "content": "Hello"}
            ],
            "figures": [],
        }

    def test_produces_valid_dict(self) -> None:
        doc = build_model_dict(self._minimal_state())
        assert doc["title"] == "Test Model"
        assert "x" in doc["parameters"]
        assert "eq_x" in doc["equations"]

    def test_skips_empty_parameter_ids(self) -> None:
        state = self._minimal_state()
        state["parameters"].append(
            {
                "id": "",
                "type": "number",
                "label": "Y",
                "description": "",
                "default": "0",
                "min": "",
                "max": "",
                "unit": "",
                "references": "",
                "options": "",
            }
        )
        doc = build_model_dict(state)
        assert len(doc["parameters"]) == 1

    def test_enum_options_parsed(self) -> None:
        state = self._minimal_state()
        state["parameters"][0]["type"] = "enum"
        state["parameters"][0]["default"] = "A"
        state["parameters"][0]["options"] = "A: Option A\nB: Option B"
        doc = build_model_dict(state)
        assert doc["parameters"]["x"]["options"] == {"A": "Option A", "B": "Option B"}


# ---------------------------------------------------------------------------
# End-to-end: build + validate
# ---------------------------------------------------------------------------


class TestValidateModelDict:
    def _minimal_doc(self) -> dict[str, Any]:
        return {
            "title": "Test Model",
            "description": "A test.",
            "authors": [{"name": "Tester"}],
            "parameters": {
                "x": {"type": "number", "label": "X", "default": 1.0}
            },
            "equations": {
                "eq_x": {"label": "X value", "compute": "x * 2"}
            },
            "scenarios": [{"id": "base", "label": "Base", "vars": {"n": 1}}],
            "report": [{"type": "markdown", "content": "Hello"}],
            "figures": [],
        }

    def test_valid_minimal_doc(self) -> None:
        model = validate_model_dict(self._minimal_doc())
        assert model.title == "Test Model"

    def test_missing_title_fails(self) -> None:
        doc = self._minimal_doc()
        del doc["title"]
        with pytest.raises(ValueError):
            validate_model_dict(doc)

    def test_invalid_parameter_type_fails(self) -> None:
        doc = self._minimal_doc()
        doc["parameters"]["x"]["type"] = "invalid_type"
        with pytest.raises(ValueError):
            validate_model_dict(doc)

    def test_enum_without_options_fails(self) -> None:
        doc = self._minimal_doc()
        doc["parameters"]["x"]["type"] = "enum"
        with pytest.raises(ValueError):
            validate_model_dict(doc)

    def test_enum_with_options_valid(self) -> None:
        doc = self._minimal_doc()
        doc["parameters"]["x"]["type"] = "enum"
        doc["parameters"]["x"]["default"] = "A"
        doc["parameters"]["x"]["options"] = {"A": "Option A", "B": "Option B"}
        model = validate_model_dict(doc)
        assert model.parameters["x"].type == "enum"


# ---------------------------------------------------------------------------
# YAML serialization round-trip
# ---------------------------------------------------------------------------


class TestYAMLRoundTrip:
    def test_write_and_read(self) -> None:
        doc: dict[str, Any] = {
            "title": "RT Model",
            "description": "round-trip test",
            "authors": [],
            "parameters": {
                "p": {"type": "number", "label": "P", "default": 5.0}
            },
            "equations": {"eq": {"label": "E", "compute": "p + 1"}},
            "scenarios": [{"id": "s1", "label": "S1", "vars": {"n": 10}}],
            "report": [{"type": "markdown", "content": "hi"}],
            "figures": [],
        }

        yaml_bytes = serialize_to_yaml(doc)
        fmt = YAMLFormat("test.yaml")
        data, _ = fmt.read(io.BytesIO(yaml_bytes))

        validated = opaque_to_typed(data, Model)
        assert validated.title == "RT Model"
        assert "p" in validated.parameters


# ---------------------------------------------------------------------------
# yaml_to_state round-trip
# ---------------------------------------------------------------------------


class TestYAMLToState:
    def test_loads_measles_yaml(self) -> None:
        import importlib.resources

        measles_res = importlib.resources.files("epicc.model.models").joinpath("measles.yaml")
        raw = measles_res.read_bytes()
        state = yaml_to_state(raw)

        assert state["model_title"] == "Measles Outbreak Cost Estimation"
        assert len(state["parameters"]) > 0
        assert len(state["equations"]) > 0
        assert len(state["scenarios"]) > 0

    def test_state_to_dict_validates(self) -> None:
        """Load a real model, convert through state, rebuild, and validate."""
        import importlib.resources

        measles_res = importlib.resources.files("epicc.model.models").joinpath("measles.yaml")
        raw = measles_res.read_bytes()
        state = yaml_to_state(raw)

        doc = build_model_dict(state)
        model = validate_model_dict(doc)
        assert model.title == "Measles Outbreak Cost Estimation"
