"""
Dynamic model class factory.

This module provides functions to dynamically create BaseSimulationModel subclasses
from Model schema instances loaded from YAML/XLSX files.
"""

from __future__ import annotations

import re
from typing import Any

import pandas as pd
from pydantic import BaseModel

from epicc.model.base import BaseSimulationModel
from epicc.model.evaluator import EquationEvaluator
from epicc.model.schema import Model


class InterpretedModelParams(BaseModel):
    """
    Dynamic parameter model that accepts any parameters defined in the schema.
    """

    model_config = {"extra": "allow"}


def _sanitize_class_name(title: str) -> str:
    """
    Convert a model title into a valid Python class name.

    Args:
        title: Human-readable model title

    Returns:
        Valid Python identifier suitable for a class name
    """
    # Remove non-alphanumeric characters and replace with underscores
    sanitized = re.sub(r"[^a-zA-Z0-9]+", "_", title)

    # Remove leading/trailing underscores
    sanitized = sanitized.strip("_")

    # Ensure it starts with a letter
    if sanitized and not sanitized[0].isalpha():
        sanitized = "Model_" + sanitized

    # Convert to PascalCase
    parts = sanitized.split("_")
    class_name = "".join(part.capitalize() for part in parts if part)

    # Ensure we have a valid name
    if not class_name:
        class_name = "InterpretedModel"

    return class_name


def _format_value(value: Any, equation_spec: Any = None) -> str:
    """
    Format a computed value for display in tables.

    Args:
        value: The value to format
        equation_spec: Optional equation specification with unit/output type info

    Returns:
        Formatted string representation
    """
    if isinstance(value, (int, float)):
        # Check for currency indicators
        is_currency = False
        if equation_spec and hasattr(equation_spec, "unit"):
            is_currency = equation_spec.unit in ("USD", "dollars", "$")

        # Format based on magnitude
        if abs(value) >= 1000:
            formatted = f"{value:,.0f}"
        elif abs(value) >= 100:
            formatted = f"{value:,.2f}"
        elif abs(value) >= 1:
            formatted = f"{value:.2f}"
        else:
            formatted = f"{value:.4f}"

        # Add currency symbol if appropriate
        if is_currency:
            formatted = f"${formatted}"

        return formatted
    else:
        return str(value)


def create_model_class(
    model_def: Model,
    source_path: str | None = None,
) -> type[BaseSimulationModel]:
    """
    Dynamically create a BaseSimulationModel subclass from a Model schema.

    This function generates a new class at runtime that implements the
    BaseSimulationModel interface. Each generated class is unique and has
    its own identity in the type system.

    Args:
        model_def: Validated Model schema instance
        source_path: Optional path to the source file (for debugging/metadata)

    Returns:
        A new class (not instance) that inherits from BaseSimulationModel

    Raises:
        ValueError: If the model definition is invalid
    """
    # Build equation evaluator
    equations_dict = {eq_id: eq.compute for eq_id, eq in model_def.equations.items()}

    try:
        evaluator = EquationEvaluator(equations_dict)
    except Exception as e:
        raise ValueError(f"Failed to build equation evaluator: {e}") from e

    # Generate class name from model title
    class_name = _sanitize_class_name(model_def.title)

    # Create method implementations using closures to capture model_def and evaluator

    def human_name(self) -> str:
        return model_def.title

    def model_title(self) -> str:
        return model_def.title

    def model_description(self) -> str:
        return model_def.description

    def scenario_labels(self) -> dict[str, str]:
        return {scenario.id: scenario.label for scenario in model_def.table.scenarios}

    def default_params(self) -> dict[str, Any]:
        return {
            param_id: param.default for param_id, param in model_def.parameters.items()
        }

    def parameter_model(self) -> type[InterpretedModelParams]:
        return InterpretedModelParams

    def run(
        self,
        params: InterpretedModelParams,
        label_overrides: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Execute the model for all scenarios."""
        if label_overrides is None:
            label_overrides = {}

        # Convert params to dict
        param_dict = params.model_dump()

        # Evaluate for each scenario
        scenario_results = {}
        for scenario in model_def.table.scenarios:
            # Merge params + scenario vars
            context = {**param_dict, **scenario.vars.model_dump()}

            # Evaluate all equations
            try:
                results = evaluator.evaluate_all(context)
            except Exception as e:
                raise RuntimeError(
                    f"Error evaluating scenario '{scenario.label}': {e}"
                ) from e

            # Store with label
            label = label_overrides.get(scenario.id, scenario.label)
            scenario_results[label] = results

        return {
            "scenario_results": scenario_results,
            "scenarios": model_def.table.scenarios,
            "rows": model_def.table.rows,
        }

    def build_sections(self, results: dict[str, Any]) -> list[dict[str, Any]]:
        """Build output sections from scenario results."""
        scenario_results = results["scenario_results"]
        rows_spec = results["rows"]

        # Build DataFrame for main results table
        table_data: dict[str, list[Any]] = {"": []}  # First column for row labels
        for label in scenario_results.keys():
            table_data[label] = []

        # Populate rows
        for row_spec in rows_spec:
            table_data[""].append(row_spec.label)

            for scenario_label, eq_results in scenario_results.items():
                value = eq_results.get(row_spec.value, "N/A")

                # Get equation spec for formatting hints
                eq_spec = model_def.equations.get(row_spec.value)
                formatted = _format_value(value, eq_spec)

                table_data[scenario_label].append(formatted)

        df = pd.DataFrame(table_data)

        # Build sections list
        sections: list[dict[str, Any]] = []

        # Add introduction section if present
        if model_def.introduction:
            sections.append(
                {
                    "title": "Introduction",
                    "content": [model_def.introduction],
                }
            )

        # Add main results table
        sections.append(
            {
                "title": model_def.title,
                "content": [df],
            }
        )

        # Add figures if any
        for figure in model_def.figures:
            sections.append(
                {
                    "title": figure.title,
                    "content": [f"Figure: {figure.alt_text or 'Visualization'}"],
                }
            )

        return sections

    # Add metadata as class attributes
    def get_source_path(self) -> str | None:
        """Return the path to the source file, if available."""
        return source_path

    def get_model_definition(self) -> Model:
        """Return the underlying Model schema definition."""
        return model_def

    # Build the methods dictionary for the class
    methods = {
        "human_name": human_name,
        "model_title": property(model_title),
        "model_description": property(model_description),
        "scenario_labels": property(scenario_labels),
        "default_params": default_params,
        "parameter_model": parameter_model,
        "run": run,
        "build_sections": build_sections,
        # Additional metadata methods
        "get_source_path": get_source_path,
        "get_model_definition": get_model_definition,
        # Class metadata
        "__module__": "epicc.model.factory",
        "__doc__": f"Dynamically generated model class for '{model_def.title}'",
    }

    # Create the class dynamically using type()
    # type(name, bases, dict) -> new type
    model_class = type(
        class_name,
        (BaseSimulationModel,),
        methods,
    )

    return model_class


def create_model_instance(
    model_def: Model,
    source_path: str | None = None,
) -> BaseSimulationModel:
    """
    Create a BaseSimulationModel instance from a Model schema.

    This is a convenience function that creates the class and instantiates it.

    Args:
        model_def: Validated Model schema instance
        source_path: Optional path to the source file

    Returns:
        An instance of the dynamically created model class
    """
    model_class = create_model_class(model_def, source_path)
    return model_class()


__all__ = [
    "InterpretedModelParams",
    "create_model_class",
    "create_model_instance",
]
