"""Tests for epicc.ui.url_params human-readable query-string encoding."""

from typing import Any

import pytest
from streamlit.testing.v1 import AppTest

from epicc.model.base import BaseSimulationModel
from epicc.model.models import get_all_models
from epicc.model.schema import Scenario, ScenarioVars
from epicc.ui.url_params import (
    RESERVED_KEYS,
    build_slug_registry,
    decode_state,
    encode_state,
    model_slug,
)

MEASLES_LABEL = "Measles Outbreak Cost Estimation"
TB_LABEL = "TB Isolation Cost Estimation"


@pytest.fixture(scope="module")
def registry() -> dict[str, BaseSimulationModel]:
    return {m.human_name(): m for m in get_all_models()}


@pytest.fixture
def measles(registry: dict[str, BaseSimulationModel]) -> BaseSimulationModel:
    return registry[MEASLES_LABEL]


@pytest.fixture
def tb(registry: dict[str, BaseSimulationModel]) -> BaseSimulationModel:
    return registry[TB_LABEL]


def defaults_of(model: BaseSimulationModel) -> dict[str, Any]:
    """The model's equation-parameter defaults, as the sidebar would report them."""
    return {pid: spec.default for pid, spec in (model.parameter_specs or {}).items()}


def roundtrip(model: BaseSimulationModel, query: dict[str, str]) -> dict[str, str]:
    """Decode *query* then re-encode it, as the app does on every rerun."""
    values, scenarios, _ = decode_state(model, query)
    return encode_state(model, {**defaults_of(model), **values}, scenarios)


# --------------------------------------------------------------------------
# Slugs
# --------------------------------------------------------------------------


def test_slugs_come_from_the_yaml_file_stem(
    measles: BaseSimulationModel, tb: BaseSimulationModel
) -> None:
    assert model_slug(measles) == "measles"
    assert model_slug(tb) == "tb_isolation"


def test_slug_registry_maps_back_to_labels(
    registry: dict[str, BaseSimulationModel],
) -> None:
    assert build_slug_registry(registry) == {
        "measles": MEASLES_LABEL,
        "tb_isolation": TB_LABEL,
    }


def test_shipped_models_avoid_reserved_parameter_names(
    registry: dict[str, BaseSimulationModel],
) -> None:
    for model in registry.values():
        names = set(model.parameter_specs or {}) | set(
            model.scenario_parameter_specs or {}
        )
        assert not (names & RESERVED_KEYS), model.human_name()


# --------------------------------------------------------------------------
# Encoding
# --------------------------------------------------------------------------


def test_default_state_encodes_to_the_model_alone(measles: BaseSimulationModel) -> None:
    query = encode_state(measles, defaults_of(measles), measles.default_scenarios)

    assert query == {"model": "measles"}


def test_only_changed_parameters_appear(measles: BaseSimulationModel) -> None:
    params = {**defaults_of(measles), "vaccination_rate": 0.9}

    query = encode_state(measles, params, measles.default_scenarios)

    assert query == {"model": "measles", "vaccination_rate": "0.9"}


def test_whole_floats_lose_their_trailing_zero(measles: BaseSimulationModel) -> None:
    params = {**defaults_of(measles), "contacts_per_case": 200.0}

    query = encode_state(measles, params, measles.default_scenarios)

    assert query["contacts_per_case"] == "200"


def test_scenario_overrides_are_keyed_by_scenario_id(
    measles: BaseSimulationModel,
) -> None:
    scenarios = [
        Scenario(id="22_cases", label="Small outbreak", vars=ScenarioVars(n_cases=30)),
        Scenario(id="100_cases", label="100 Cases", vars=ScenarioVars(n_cases=100)),
        Scenario(id="803_cases", label="803 Cases", vars=ScenarioVars(n_cases=803)),
    ]

    query = encode_state(measles, defaults_of(measles), scenarios)

    assert query == {
        "model": "measles",
        "scen.22_cases.label": "Small outbreak",
        "scen.22_cases.n_cases": "30",
    }


def test_changed_scenario_set_emits_an_order_key(measles: BaseSimulationModel) -> None:
    scenarios = [
        Scenario(id="22_cases", label="22 Cases", vars=ScenarioVars(n_cases=22)),
        Scenario(id="custom_3", label="Scenario 2", vars=ScenarioVars(n_cases=7)),
    ]

    query = encode_state(measles, defaults_of(measles), scenarios)

    assert query == {
        "model": "measles",
        "scenarios": "22_cases,custom_3",
        "scen.custom_3.n_cases": "7",
    }


def test_slug_override_names_a_different_model(measles: BaseSimulationModel) -> None:
    query = encode_state(measles, defaults_of(measles), None, slug="elsewhere")

    assert query["model"] == "elsewhere"


# --------------------------------------------------------------------------
# Decoding
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("param_id", "text", "expected"),
    [
        ("contacts_per_case", "200", 200.0),
        ("contacts_per_case", "141.5", 141.5),
        ("quarantine_days", "10", 10),
        ("vaccination_rate", "0.9", 0.9),
    ],
)
def test_values_decode_to_native_types(
    measles: BaseSimulationModel, param_id: str, text: str, expected: Any
) -> None:
    values, _, warnings = decode_state(measles, {"model": "measles", param_id: text})

    assert values == {param_id: expected}
    assert type(values[param_id]) is type(expected)
    assert warnings == []


def test_enum_value_decodes(tb: BaseSimulationModel) -> None:
    values, _, warnings = decode_state(
        tb, {"model": "tb_isolation", "isolation_type": "MOTEL_ISO"}
    )

    assert values == {"isolation_type": "MOTEL_ISO"}
    assert warnings == []


def test_unknown_keys_are_ignored(measles: BaseSimulationModel) -> None:
    values, scenarios, warnings = decode_state(
        measles, {"model": "measles", "embed": "true", "not_a_param": "9"}
    )

    assert values == {}
    assert scenarios is None
    assert warnings == []


def test_untouched_scenarios_decode_to_none(measles: BaseSimulationModel) -> None:
    _, scenarios, _ = decode_state(measles, {"model": "measles"})

    assert scenarios is None


def test_scenario_label_and_var_decode_by_id(measles: BaseSimulationModel) -> None:
    _, scenarios, warnings = decode_state(
        measles,
        {
            "model": "measles",
            "scen.22_cases.label": "Small outbreak",
            "scen.22_cases.n_cases": "30",
        },
    )

    assert scenarios is not None
    assert [(s.id, s.label, s.vars.model_dump()) for s in scenarios] == [
        ("22_cases", "Small outbreak", {"n_cases": 30}),
        ("100_cases", "100 Cases", {"n_cases": 100}),
        ("803_cases", "803 Cases", {"n_cases": 803}),
    ]
    assert warnings == []


def test_scenario_order_key_selects_membership(measles: BaseSimulationModel) -> None:
    _, scenarios, warnings = decode_state(
        measles,
        {"model": "measles", "scenarios": "803_cases,22_cases"},
    )

    assert scenarios is not None
    assert [s.id for s in scenarios] == ["803_cases", "22_cases"]
    assert warnings == []


# --------------------------------------------------------------------------
# Bad input
# --------------------------------------------------------------------------


def test_value_above_maximum_is_clamped_with_a_warning(
    measles: BaseSimulationModel,
) -> None:
    values, _, warnings = decode_state(
        measles, {"model": "measles", "vaccination_rate": "5"}
    )

    assert values == {"vaccination_rate": 1.0}
    assert len(warnings) == 1
    assert "above the maximum" in warnings[0]


def test_value_below_minimum_is_clamped_with_a_warning(
    measles: BaseSimulationModel,
) -> None:
    values, _, warnings = decode_state(
        measles, {"model": "measles", "hourly_wage_worker": "-3"}
    )

    assert values == {"hourly_wage_worker": 0.0}
    assert len(warnings) == 1
    assert "below the minimum" in warnings[0]


def test_unparseable_number_is_dropped_with_a_warning(
    measles: BaseSimulationModel,
) -> None:
    values, _, warnings = decode_state(
        measles, {"model": "measles", "vaccination_rate": "abc"}
    )

    assert values == {}
    assert warnings == ["Ignored `vaccination_rate=abc`: expected a number."]


def test_unknown_enum_constant_is_dropped_with_a_warning(
    tb: BaseSimulationModel,
) -> None:
    values, _, warnings = decode_state(
        tb, {"model": "tb_isolation", "isolation_type": "motel"}
    )

    assert values == {}
    assert len(warnings) == 1
    assert "HOSP_ISO, MOTEL_ISO, HOME_ISO" in warnings[0]


def test_scenario_variable_at_top_level_is_explained(
    measles: BaseSimulationModel,
) -> None:
    values, scenarios, warnings = decode_state(
        measles, {"model": "measles", "n_cases": "50"}
    )

    assert values == {}
    assert scenarios is None
    assert len(warnings) == 1
    assert "scen.<scenario>.n_cases" in warnings[0]


def test_override_for_an_absent_scenario_is_reported(
    measles: BaseSimulationModel,
) -> None:
    _, _, warnings = decode_state(
        measles, {"model": "measles", "scen.nope.n_cases": "5"}
    )

    assert warnings == ["Ignored `scen.nope.n_cases`: no scenario with id `nope`."]


def test_too_many_scenarios_are_truncated(measles: BaseSimulationModel) -> None:
    ids = ",".join(f"s{i}" for i in range(12))

    _, scenarios, warnings = decode_state(
        measles, {"model": "measles", "scenarios": ids}
    )

    assert scenarios is not None
    assert len(scenarios) == 10
    assert any("only the first 10" in w for w in warnings)


# --------------------------------------------------------------------------
# Idempotency -- the URL is rewritten on every rerun, so it must be stable.
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "query",
    [
        {"model": "measles"},
        {"model": "measles", "vaccination_rate": "0.9", "contacts_per_case": "200"},
        {
            "model": "measles",
            "scen.22_cases.label": "Small outbreak",
            "scen.22_cases.n_cases": "30",
        },
        {
            "model": "measles",
            "scenarios": "22_cases,custom_3",
            "scen.custom_3.n_cases": "7",
        },
    ],
)
def test_roundtrip_is_stable(
    measles: BaseSimulationModel, query: dict[str, str]
) -> None:
    assert roundtrip(measles, query) == query


def test_roundtrip_is_stable_for_the_enum_model(tb: BaseSimulationModel) -> None:
    query = {
        "model": "tb_isolation",
        "isolation_type": "MOTEL_ISO",
        "discount_rate": "0.05",
        "scen.5_day.label": "Short isolation",
    }

    assert roundtrip(tb, query) == query


def test_clamped_value_settles_after_one_roundtrip(
    measles: BaseSimulationModel,
) -> None:
    once = roundtrip(measles, {"model": "measles", "vaccination_rate": "5"})

    assert once == {"model": "measles", "vaccination_rate": "1"}
    assert roundtrip(measles, once) == once


# --------------------------------------------------------------------------
# End-to-end through the app
# --------------------------------------------------------------------------


def test_app_restores_and_rewrites_complete_simulator_state() -> None:
    app = AppTest.from_file("app.py")
    app.query_params.update(
        {
            "model": "measles",
            "contacts_per_case": "200",
            "scen.22_cases.label": "Test 1",
            "scen.22_cases.n_cases": "1000",
        }
    )

    app.run(timeout=30)

    assert not app.exception
    assert app.session_state["model_selector"] == MEASLES_LABEL
    assert app.session_state[f"{MEASLES_LABEL}:contacts_per_case"] == 200.0
    assert app.session_state[f"{MEASLES_LABEL}:scen_0:label"] == "Test 1"
    assert app.session_state[f"{MEASLES_LABEL}:scen_0:n_cases"] == 1000

    # AppTest exposes query values as single-item lists.
    assert app.query_params["model"][0] == "measles"
    assert app.query_params["contacts_per_case"][0] == "200"
    assert app.query_params["scen.22_cases.label"][0] == "Test 1"
    assert app.query_params["scen.22_cases.n_cases"][0] == "1000"


def test_app_warns_when_the_link_names_an_unknown_model() -> None:
    app = AppTest.from_file("app.py")
    app.query_params["model"] = "no_such_model"

    app.run(timeout=30)

    assert not app.exception
    assert app.session_state["model_selector"] is None
    assert any("no_such_model" in w.value for w in app.warning)
