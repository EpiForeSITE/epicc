"""Tests for the scenario-context parameter feature.

Covers:
- Parameter context field (equation vs scenario)
- Schema-level scenario var validation
- Factory filtering of scenario params
- Scenario overrides in model run()
- New model properties (scenario_parameter_specs, default_scenarios)
"""

import pytest

from epicc.model import create_model_instance
from epicc.model.schema import (
    Equation,
    Model,
    Parameter,
    Scenario,
    ScenarioVars,
    TableBlock,
    TableRow,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def model_with_scenario_params():
    """Model where one parameter has context='scenario'."""
    return Model(
        title="Scenario Param Model",
        description="A model with scenario-context parameters",
        parameters={
            "unit_cost": Parameter(
                type="number",
                label="Unit Cost",
                default=10.0,
                min=0.0,
            ),
            "n_items": Parameter(
                type="integer",
                label="Number of items",
                description="Number of items in each scenario",
                default=5,
                min=1,
                max=1000,
                context="scenario",
            ),
        },
        equations={
            "eq_total": Equation(
                label="Total Cost",
                compute="unit_cost * n_items",
            ),
        },
        scenarios=[
            Scenario(
                id="small",
                label="Small Order",
                vars=ScenarioVars(n_items=5),
            ),
            Scenario(
                id="large",
                label="Large Order",
                vars=ScenarioVars(n_items=100),
            ),
        ],
        report=[
            TableBlock(
                type="table",
                rows=[TableRow(label="Total", value="eq_total")],
            ),
        ],
    )


# ---------------------------------------------------------------------------
# Tests: Parameter context field
# ---------------------------------------------------------------------------

class TestParameterContext:
    """Test the context field on the Parameter schema."""

    def test_default_context_is_equation(self):
        p = Parameter(type="number", label="X", default=1.0)
        assert p.context == "equation"

    def test_explicit_equation_context(self):
        p = Parameter(type="number", label="X", default=1.0, context="equation")
        assert p.context == "equation"

    def test_scenario_context(self):
        p = Parameter(type="integer", label="N", default=5, context="scenario")
        assert p.context == "scenario"


# ---------------------------------------------------------------------------
# Tests: Schema-level scenario var validation
# ---------------------------------------------------------------------------

class TestScenarioVarValidation:
    """Test that Model validates scenario vars against scenario-context parameter specs."""

    def test_valid_scenario_vars_accepted(self, model_with_scenario_params):
        """Model with valid scenario vars should be created without errors."""
        assert len(model_with_scenario_params.scenarios) == 2

    def test_scenario_var_below_min_rejected(self):
        """Scenario var below the parameter min should be rejected."""
        with pytest.raises(ValueError, match="below minimum"):
            Model(
                title="Bad",
                description="",
                parameters={
                    "x": Parameter(
                        type="integer", label="X", default=5, min=1, max=100, context="scenario"
                    ),
                },
                equations={"eq": Equation(label="E", compute="x")},
                scenarios=[
                    Scenario(id="s1", label="S1", vars=ScenarioVars(x=0)),
                ],
                report=[TableBlock(type="table", rows=[TableRow(label="E", value="eq")])],
            )

    def test_scenario_var_above_max_rejected(self):
        """Scenario var above the parameter max should be rejected."""
        with pytest.raises(ValueError, match="exceeds maximum"):
            Model(
                title="Bad",
                description="",
                parameters={
                    "x": Parameter(
                        type="number", label="X", default=5.0, min=0, max=10, context="scenario"
                    ),
                },
                equations={"eq": Equation(label="E", compute="x")},
                scenarios=[
                    Scenario(id="s1", label="S1", vars=ScenarioVars(x=11.0)),
                ],
                report=[TableBlock(type="table", rows=[TableRow(label="E", value="eq")])],
            )

    def test_equation_context_params_not_validated_in_scenario_vars(self):
        """Equation-context params should NOT trigger validation on scenario vars."""
        # x has context="equation" (default), so it shouldn't enforce min/max on scenario vars.
        m = Model(
            title="OK",
            description="",
            parameters={
                "x": Parameter(type="number", label="X", default=5.0, min=0, max=10),
            },
            equations={"eq": Equation(label="E", compute="x")},
            scenarios=[
                Scenario(id="s1", label="S1", vars=ScenarioVars(x=999.0)),
            ],
            report=[TableBlock(type="table", rows=[TableRow(label="E", value="eq")])],
        )
        assert m.scenarios[0].vars.model_dump()["x"] == 999.0

    def test_scenario_var_boolean_rejected_for_integer(self):
        """A boolean value for an integer scenario parameter should be rejected."""
        with pytest.raises(ValueError, match="must be an integer"):
            Model(
                title="Bad",
                description="",
                parameters={
                    "x": Parameter(
                        type="integer", label="X", default=5, min=1, max=100, context="scenario"
                    ),
                },
                equations={"eq": Equation(label="E", compute="x")},
                scenarios=[
                    Scenario(id="s1", label="S1", vars=ScenarioVars(x=True)),
                ],
                report=[TableBlock(type="table", rows=[TableRow(label="E", value="eq")])],
            )

    def test_scenario_var_boolean_rejected_for_number(self):
        """A boolean value for a number scenario parameter should be rejected."""
        with pytest.raises(ValueError, match="must be a number"):
            Model(
                title="Bad",
                description="",
                parameters={
                    "x": Parameter(
                        type="number", label="X", default=5.0, min=0, max=10, context="scenario"
                    ),
                },
                equations={"eq": Equation(label="E", compute="x")},
                scenarios=[
                    Scenario(id="s1", label="S1", vars=ScenarioVars(x=False)),
                ],
                report=[TableBlock(type="table", rows=[TableRow(label="E", value="eq")])],
            )

    def test_scenario_var_string_coerced_for_integer(self):
        """A string-encoded integer should be coerced and validated."""
        with pytest.raises(ValueError, match="below minimum"):
            Model(
                title="Bad",
                description="",
                parameters={
                    "x": Parameter(
                        type="integer", label="X", default=5, min=1, max=100, context="scenario"
                    ),
                },
                equations={"eq": Equation(label="E", compute="x")},
                scenarios=[
                    Scenario(id="s1", label="S1", vars=ScenarioVars(x="0")),
                ],
                report=[TableBlock(type="table", rows=[TableRow(label="E", value="eq")])],
            )

    def test_scenario_var_non_numeric_string_rejected_for_integer(self):
        """A non-numeric string for an integer scenario parameter should be rejected."""
        with pytest.raises(ValueError, match="must be an integer"):
            Model(
                title="Bad",
                description="",
                parameters={
                    "x": Parameter(
                        type="integer", label="X", default=5, min=1, max=100, context="scenario"
                    ),
                },
                equations={"eq": Equation(label="E", compute="x")},
                scenarios=[
                    Scenario(id="s1", label="S1", vars=ScenarioVars(x="abc")),
                ],
                report=[TableBlock(type="table", rows=[TableRow(label="E", value="eq")])],
            )


# ---------------------------------------------------------------------------
# Tests: Factory filtering
# ---------------------------------------------------------------------------

class TestFactoryFiltering:
    """Test that factory correctly separates equation and scenario params."""

    def test_default_params_excludes_scenario_params(self, model_with_scenario_params):
        model = create_model_instance(model_with_scenario_params)
        defaults = model.default_params()
        assert "unit_cost" in defaults
        assert "n_items" not in defaults

    def test_parameter_model_excludes_scenario_params(self, model_with_scenario_params):
        model = create_model_instance(model_with_scenario_params)
        param_cls = model.parameter_model()
        field_names = set(param_cls.model_fields.keys())
        assert "unit_cost" in field_names
        assert "n_items" not in field_names

    def test_parameter_specs_excludes_scenario_params(self, model_with_scenario_params):
        model = create_model_instance(model_with_scenario_params)
        specs = model.parameter_specs
        assert "unit_cost" in specs
        assert "n_items" not in specs

    def test_scenario_parameter_specs_includes_only_scenario_params(
        self, model_with_scenario_params
    ):
        model = create_model_instance(model_with_scenario_params)
        scen_specs = model.scenario_parameter_specs
        assert "n_items" in scen_specs
        assert "unit_cost" not in scen_specs

    def test_default_scenarios_returns_model_scenarios(self, model_with_scenario_params):
        model = create_model_instance(model_with_scenario_params)
        defaults = model.default_scenarios
        assert len(defaults) == 2
        assert defaults[0].id == "small"
        assert defaults[1].id == "large"


# ---------------------------------------------------------------------------
# Tests: Scenario overrides in run()
# ---------------------------------------------------------------------------

class TestScenarioOverrides:
    """Test that run() respects scenario_overrides."""

    def test_run_with_default_scenarios(self, model_with_scenario_params):
        """Run with no overrides should use model defaults."""
        model = create_model_instance(model_with_scenario_params)
        params = model.parameter_model()(unit_cost=10.0)
        results = model.run(params)

        assert "Small Order" in results["scenario_results"]
        assert "Large Order" in results["scenario_results"]
        assert results["scenario_results"]["Small Order"]["eq_total"] == 50.0
        assert results["scenario_results"]["Large Order"]["eq_total"] == 1000.0

    def test_run_with_scenario_overrides(self, model_with_scenario_params):
        """Run with overrides should use the provided scenarios."""
        model = create_model_instance(model_with_scenario_params)
        params = model.parameter_model()(unit_cost=10.0)

        custom_scenarios = [
            Scenario(id="custom", label="Custom", vars=ScenarioVars(n_items=50)),
        ]
        results = model.run(params, scenario_overrides=custom_scenarios)

        assert "Custom" in results["scenario_results"]
        assert results["scenario_results"]["Custom"]["eq_total"] == 500.0
        assert len(results["scenarios"]) == 1

    def test_run_with_modified_scenario_values(self, model_with_scenario_params):
        """Run with different var values should compute accordingly."""
        model = create_model_instance(model_with_scenario_params)
        params = model.parameter_model()(unit_cost=5.0)

        overrides = [
            Scenario(id="s1", label="Ten Items", vars=ScenarioVars(n_items=10)),
            Scenario(id="s2", label="Twenty Items", vars=ScenarioVars(n_items=20)),
        ]
        results = model.run(params, scenario_overrides=overrides)

        assert results["scenario_results"]["Ten Items"]["eq_total"] == 50.0
        assert results["scenario_results"]["Twenty Items"]["eq_total"] == 100.0

    def test_run_backward_compat_label_overrides(self, model_with_scenario_params):
        """label_overrides should still work when scenario_overrides is None."""
        model = create_model_instance(model_with_scenario_params)
        params = model.parameter_model()(unit_cost=10.0)

        results = model.run(params, label_overrides={"small": "Tiny"})

        assert "Tiny" in results["scenario_results"]
        assert "Large Order" in results["scenario_results"]


# ---------------------------------------------------------------------------
# Tests: Loaded YAML models have scenario params
# ---------------------------------------------------------------------------

class TestYamlModelsHaveScenarioParams:
    """Verify that the YAML models we updated actually have scenario params."""

    def test_measles_model_has_scenario_params(self):
        from epicc.model.models import get_all_models

        models = get_all_models()
        measles = next(m for m in models if "measles" in m.human_name().lower())
        scen_specs = measles.scenario_parameter_specs
        assert scen_specs is not None
        assert "n_cases" in scen_specs

    def test_tb_model_has_scenario_params(self):
        from epicc.model.models import get_all_models

        models = get_all_models()
        tb = next(m for m in models if "tb" in m.human_name().lower())
        scen_specs = tb.scenario_parameter_specs
        assert scen_specs is not None
        assert "isolation_days" in scen_specs
        assert "latent_multiplier" in scen_specs

    def test_measles_n_cases_not_in_equation_params(self):
        from epicc.model.models import get_all_models

        models = get_all_models()
        measles = next(m for m in models if "measles" in m.human_name().lower())
        assert "n_cases" not in measles.default_params()
        assert "n_cases" not in (measles.parameter_specs or {})

    def test_measles_default_scenarios_correct(self):
        from epicc.model.models import get_all_models

        models = get_all_models()
        measles = next(m for m in models if "measles" in m.human_name().lower())
        defaults = measles.default_scenarios
        assert defaults is not None
        assert len(defaults) == 3
        ids = [s.id for s in defaults]
        assert "22_cases" in ids
        assert "100_cases" in ids
        assert "803_cases" in ids
