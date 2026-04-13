"""Integration tests for interpreted models."""

from io import BytesIO

import pandas as pd
import pytest

from epicc.model import create_model_class, create_model_instance
from epicc.model.base import BaseSimulationModel
from epicc.model.schema import (
    Equation,
    Model,
    Parameter,
    Scenario,
    ScenarioVars,
    Table,
    TableRow,
)


@pytest.fixture
def simple_model_def():
    """Create a simple model definition for testing."""
    return Model(
        title="Simple Cost Model",
        description="A basic cost calculation model",
        parameters={
            "unit_cost": Parameter(
                type="number",
                label="Unit Cost",
                default=10.0,
                min=0.0,
            ),
            "quantity": Parameter(
                type="integer",
                label="Quantity",
                default=5,
                min=0,
            ),
        },
        equations={
            "eq_subtotal": Equation(
                label="Subtotal",
                compute="unit_cost * quantity",
            ),
            "eq_tax": Equation(
                label="Tax",
                compute="eq_subtotal * tax_rate",
            ),
            "eq_total": Equation(
                label="Total",
                compute="eq_subtotal + eq_tax",
            ),
        },
        table=Table(
            scenarios=[
                Scenario(
                    id="low_tax",
                    label="Low Tax (5%)",
                    vars=ScenarioVars(tax_rate=0.05),  # type: ignore
                ),
                Scenario(
                    id="high_tax",
                    label="High Tax (10%)",
                    vars=ScenarioVars(tax_rate=0.10),  # type: ignore
                ),
            ],
            rows=[
                TableRow(label="Subtotal", value="eq_subtotal"),
                TableRow(label="Tax", value="eq_tax"),
                TableRow(label="Total", value="eq_total", emphasis="strong"),
            ],
        ),
    )


class TestModelCreation:
    """Test dynamic model class creation."""

    def test_create_model_class_returns_class(self, simple_model_def):
        """Test that create_model_class returns a class."""
        model_class = create_model_class(simple_model_def)
        assert isinstance(model_class, type)
        assert issubclass(model_class, BaseSimulationModel)

    def test_model_class_has_name(self, simple_model_def):
        """Test that generated class has a name."""
        model_class = create_model_class(simple_model_def)
        assert model_class.__name__ == "SimpleCostModel"

    def test_model_class_can_be_instantiated(self, simple_model_def):
        """Test that the generated class can be instantiated."""
        model_class = create_model_class(simple_model_def)
        instance = model_class()
        assert isinstance(instance, BaseSimulationModel)


class TestModelInterface:
    """Test that generated models implement BaseSimulationModel interface."""

    def test_human_name(self, simple_model_def):
        """Test human_name method."""
        model = create_model_instance(simple_model_def)
        assert model.human_name() == "Simple Cost Model"

    def test_model_title(self, simple_model_def):
        """Test model_title property."""
        model = create_model_instance(simple_model_def)
        assert model.model_title == "Simple Cost Model"

    def test_scenario_labels(self, simple_model_def):
        """Test scenario_labels property."""
        model = create_model_instance(simple_model_def)
        labels = model.scenario_labels
        assert labels == {
            "low_tax": "Low Tax (5%)",
            "high_tax": "High Tax (10%)",
        }

    def test_default_params(self, simple_model_def):
        """Test default_params method."""
        model = create_model_instance(simple_model_def)
        defaults = model.default_params()
        assert defaults == {"unit_cost": 10.0, "quantity": 5}


class TestModelExecution:
    """Test model execution."""

    def test_run_simple_model(self, simple_model_def):
        """Test running a simple model."""
        model = create_model_instance(simple_model_def)
        param_model = model.parameter_model()
        params = param_model(unit_cost=10.0, quantity=5)

        results = model.run(params)

        assert "scenario_results" in results
        assert "Low Tax (5%)" in results["scenario_results"]
        assert "High Tax (10%)" in results["scenario_results"]

    def test_run_evaluates_equations_correctly(self, simple_model_def):
        """Test that equations are evaluated correctly."""
        model = create_model_instance(simple_model_def)
        param_model = model.parameter_model()
        params = param_model(unit_cost=10.0, quantity=5)

        results = model.run(params)

        low_tax = results["scenario_results"]["Low Tax (5%)"]
        assert low_tax["eq_subtotal"] == 50.0
        assert low_tax["eq_tax"] == 2.5
        assert low_tax["eq_total"] == 52.5

        high_tax = results["scenario_results"]["High Tax (10%)"]
        assert high_tax["eq_subtotal"] == 50.0
        assert high_tax["eq_tax"] == 5.0
        assert high_tax["eq_total"] == 55.0

    def test_run_with_different_parameters(self, simple_model_def):
        """Test running with different parameter values."""
        model = create_model_instance(simple_model_def)
        param_model = model.parameter_model()
        params = param_model(unit_cost=20.0, quantity=10)

        results = model.run(params)

        low_tax = results["scenario_results"]["Low Tax (5%)"]
        assert low_tax["eq_subtotal"] == 200.0
        assert low_tax["eq_tax"] == 10.0
        assert low_tax["eq_total"] == 210.0


class TestSectionBuilding:
    """Test build_sections() method."""

    def test_build_sections_returns_list(self, simple_model_def):
        """Test that build_sections returns a list."""
        model = create_model_instance(simple_model_def)
        param_model = model.parameter_model()
        params = param_model(unit_cost=10.0, quantity=5)

        results = model.run(params)
        sections = model.build_sections(results)

        assert isinstance(sections, list)
        assert len(sections) > 0

    def test_sections_contain_dataframe(self, simple_model_def):
        """Test that sections contain DataFrame."""
        model = create_model_instance(simple_model_def)
        param_model = model.parameter_model()
        params = param_model(unit_cost=10.0, quantity=5)

        results = model.run(params)
        sections = model.build_sections(results)

        # Find DataFrame in sections
        found_df = False
        for section in sections:
            for content in section.get("content", []):
                if isinstance(content, pd.DataFrame):
                    found_df = True
                    break

        assert found_df


class TestErrorHandling:
    """Test error handling."""

    def test_invalid_equation_syntax(self):
        """Test that invalid equation syntax is caught."""
        model_def = Model(
            title="Bad Model",
            description="Has bad equation",
            parameters={"x": Parameter(type="number", label="X", default=1.0)},
            equations={"bad": Equation(label="Bad", compute="1 + (2")},
            table=Table(
                scenarios=[Scenario(id="s1", label="S1", vars=ScenarioVars())],
                rows=[TableRow(label="Bad", value="bad")],
            ),
        )

        with pytest.raises(ValueError, match="Failed to build equation evaluator"):
            create_model_instance(model_def)

    def test_circular_dependency_detected(self):
        """Test that circular dependencies are detected."""
        model_def = Model(
            title="Circular",
            description="Has cycle",
            parameters={},
            equations={
                "a": Equation(label="A", compute="b + 1"),
                "b": Equation(label="B", compute="a + 1"),
            },
            table=Table(
                scenarios=[Scenario(id="s1", label="S1", vars=ScenarioVars())],
                rows=[TableRow(label="A", value="a")],
            ),
        )

        with pytest.raises(ValueError, match="Circular dependency"):
            create_model_instance(model_def)
