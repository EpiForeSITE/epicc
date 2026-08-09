"""Tests for epicc.ui.url_params encode/decode logic."""

import base64
import json

from streamlit.testing.v1 import AppTest

from epicc.model.schema import Scenario, ScenarioVars
from epicc.ui.url_params import decode_params, encode_params


def test_roundtrip_simple() -> None:
    model = "Test Model"
    values = {"rate": 0.5, "count": 100, "label": "hello"}
    encoded = encode_params(model, values)
    result = decode_params(encoded)
    assert result is not None
    assert result[0] == model
    assert result[1] == values
    assert result[2] is None


def test_roundtrip_empty_params() -> None:
    encoded = encode_params("M", {})
    result = decode_params(encoded)
    assert result == ("M", {}, None)


def test_roundtrip_scenarios() -> None:
    scenarios = [
        Scenario(
            id="test_1",
            label="Test 1",
            vars=ScenarioVars(n_cases=1000),
        ),
        Scenario(
            id="baseline",
            label="100 Cases",
            vars=ScenarioVars(n_cases=100),
        ),
    ]

    result = decode_params(encode_params("Measles", {"rate": 0.5}, scenarios))

    assert result == ("Measles", {"rate": 0.5}, scenarios)


def test_decode_legacy_parameter_only_payload() -> None:
    raw = json.dumps({"model": "Legacy", "values": {"count": 22}})
    encoded = base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")

    assert decode_params(encoded) == ("Legacy", {"count": 22}, None)


def test_decode_invalid_returns_none() -> None:
    assert decode_params("not-valid-base64!!!") is None
    assert decode_params("") is None


def test_decode_wrong_shape_returns_none() -> None:
    # Missing 'model' key
    raw = json.dumps({"values": {}})
    encoded = base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")
    assert decode_params(encoded) is None


def test_decode_invalid_scenario_returns_none() -> None:
    raw = json.dumps(
        {
            "model": "M",
            "values": {},
            "scenarios": [{"id": "missing-label-and-vars"}],
        }
    )
    encoded = base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")

    assert decode_params(encoded) is None


def test_app_restores_and_rewrites_complete_simulator_state() -> None:
    model = "Measles Outbreak Cost Estimation"
    scenarios = [
        Scenario(id="22_cases", label="Test 1", vars=ScenarioVars(n_cases=1000)),
        Scenario(id="100_cases", label="100 Cases", vars=ScenarioVars(n_cases=100)),
        Scenario(id="803_cases", label="803 Cases", vars=ScenarioVars(n_cases=803)),
    ]
    app = AppTest.from_file("app.py")
    app.query_params["params"] = encode_params(
        model,
        {"contacts_per_case": 200.0},
        scenarios,
    )

    app.run(timeout=30)

    assert not app.exception
    assert app.session_state["model_selector"] == model
    assert app.session_state[f"{model}:contacts_per_case"] == 200.0
    assert app.session_state[f"{model}:scen_0:label"] == "Test 1"
    assert app.session_state[f"{model}:scen_0:n_cases"] == 1000

    rewritten = decode_params(app.query_params["params"][0])
    assert rewritten is not None
    assert rewritten[2] == scenarios
