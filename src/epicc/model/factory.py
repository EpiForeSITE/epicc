from __future__ import annotations

import re
from typing import Any, Literal

import pandas as pd
from pydantic import BaseModel, Field, create_model

from epicc.model.base import BaseSimulationModel
from epicc.model.evaluator import EquationEvaluator
from epicc.model.parameters import format_value
from epicc.model.schema import FigureBlock, MarkdownBlock, Model, Scenario, TableBlock


def _make_parameter_model(model_def: Model) -> type[BaseModel]:
    """
    This will dynamically create a Pydantic model class for the parameters of a
    given Model definition. Neat!

    Only equation-context parameters are included; scenario-context parameters
    are handled separately via scenario overrides.
    """

    fields: dict[str, Any] = {}
    for param_id, param in model_def.parameters.items():
        if param.context == "scenario":
            continue
        base_description = param.description or param.label
        default = param.default

        if param.type == "integer":
            kwargs: dict[str, Any] = {}
            if param.min is not None:
                kwargs["ge"] = int(param.min)

            if param.max is not None:
                kwargs["le"] = int(param.max)

            constraint_hint = _range_hint(param.min, param.max, param.unit)
            description = f"{base_description}\n\n{constraint_hint}" if constraint_hint else base_description
            fields[param_id] = (int, Field(int(default), description=description, **kwargs))

        elif param.type == "number":
            kwargs = {}
            if param.min is not None:
                kwargs["ge"] = float(param.min)

            if param.max is not None:
                kwargs["le"] = float(param.max)

            constraint_hint = _range_hint(param.min, param.max, param.unit)
            description = f"{base_description}\n\n{constraint_hint}" if constraint_hint else base_description
            fields[param_id] = (float, Field(float(default), description=description, **kwargs))

        elif param.type == "boolean":
            fields[param_id] = (bool, Field(bool(default), description=base_description))

        elif param.type == "enum" and param.options:
            keys = tuple(param.options.keys())
            literal_type = Literal[keys]  # type: ignore[valid-type]
            options_hint = "Options: " + ", ".join(
                f"{k} ({v})" for k, v in param.options.items()
            )
            description = f"{base_description}\n\n{options_hint}"
            fields[param_id] = (literal_type, Field(str(default), description=description))

        else:
            fields[param_id] = (str, Field(str(default), description=base_description))

    return create_model("GeneratedParams", __config__={"extra": "forbid"}, **fields)


def _range_hint(
    min_val: int | float | None,
    max_val: int | float | None,
    unit: str | None,
) -> str:
    parts: list[str] = []
    if min_val is not None:
        parts.append(f"min {min_val}")

    if max_val is not None:
        parts.append(f"max {max_val}")

    if unit:
        parts.append(unit)

    return f"Range: {', '.join(parts)}" if parts else ""


def _sanitize_class_name(title: str) -> str:
    """
    Convert a model title into a valid Python class name.
    """

    sanitized = re.sub(r"[^a-zA-Z0-9]+", "_", title)
    sanitized = sanitized.strip("_")

    if sanitized and not sanitized[0].isalpha():
        sanitized = "Model_" + sanitized

    parts = sanitized.split("_")
    class_name = "".join(part.capitalize() for part in parts if part)

    if not class_name:
        class_name = "InterpretedModel_" + str(abs(hash(title)))

    return class_name


def create_model_class(
    model_def: Model,
    source_path: str | None = None,
) -> type[BaseSimulationModel]:
    """
    To avoid passing around user data, we dynamically create a new class for each model definition that
    implements the BaseSimulationModel interface. This function does that dynamic class creation.
    """

    _typed_param_model = _make_parameter_model(model_def)
    equations_dict = {eq_id: eq.compute for eq_id, eq in model_def.equations.items()}
    class_name = _sanitize_class_name(model_def.title)

    try:
        evaluator = EquationEvaluator(equations_dict)
    except Exception as e:
        raise ValueError(f"Failed to build equation evaluator: {e}") from e

    # Create method implementations using closures to capture model_def and evaluator

    def human_name(self) -> str:
        return model_def.title

    def model_title(self) -> str:
        return model_def.title

    def model_description(self) -> str:
        return model_def.description

    def scenario_labels(self) -> dict[str, str]:
        return {scenario.id: scenario.label for scenario in model_def.resolved_scenarios()}

    def default_params(self) -> dict[str, Any]:
        return {
            param_id: param.default
            for param_id, param in model_def.parameters.items()
            if param.context != "scenario"
        }

    def parameter_model(self) -> type[BaseModel]:
        return _typed_param_model

    def run(
        self,
        params: BaseModel,
        label_overrides: dict[str, str] | None = None,
        scenario_overrides: list[Scenario] | None = None,
    ) -> dict[str, Any]:
        """Execute the model for all scenarios."""

        if label_overrides is None:
            label_overrides = {}

        # Ensure params are of the correct typed model
        if not isinstance(params, _typed_param_model):
            raise TypeError(
                f"Expected parameters of type {_typed_param_model.__name__}, "
                f"got {type(params).__name__}"
            )

        param_dict = params.model_dump()

        # Use scenario overrides if provided, otherwise use model defaults
        if scenario_overrides is not None:
            scenarios = scenario_overrides
        else:
            scenarios = model_def.resolved_scenarios()

        # Evaluate for each scenario
        scenario_results: dict[str, dict[str, Any]] = {}
        scenario_results_by_id: dict[str, dict[str, Any]] = {}
        for scenario in scenarios:
            context = {**param_dict, **scenario.vars.model_dump()}

            try:
                eq_results = evaluator.evaluate_all(context)
            except Exception as e:
                raise RuntimeError(
                    f"Error evaluating scenario '{scenario.label}': {e}"
                ) from e

            label = label_overrides.get(scenario.id, scenario.label)
            scenario_results[label] = eq_results
            scenario_results_by_id[scenario.id] = eq_results

        return {
            "scenario_results": scenario_results,
            "scenario_results_by_id": scenario_results_by_id,
            "scenarios": scenarios,
            "label_overrides": label_overrides,
        }

    def build_sections(self, results: dict[str, Any]) -> list[dict[str, Any]]:
        """Build output sections from scenario results."""

        scenario_results: dict[str, dict[str, Any]] = results["scenario_results"]
        scenario_results_by_id: dict[str, dict[str, Any]] = results.get(
            "scenario_results_by_id", {}
        )
        label_overrides: dict[str, str] = results.get("label_overrides", {})
        scenarios = results["scenarios"]
        figures_by_id = {fig.id: fig for fig in model_def.figures}

        def _build_table_df(
            rows_spec: list[Any],
            column_ids: list[str] | None,
        ) -> pd.DataFrame:
            """DataFrame from table."""

            # Determine column labels and corresponding results based on column_ids or all scenarios.
            if column_ids is not None:
                col_labels = [
                    label_overrides.get(sid, next(
                        (s.label for s in scenarios if s.id == sid), sid
                    ))
                    for sid in column_ids
                    if sid in scenario_results_by_id
                ]

                col_eq_results = [
                    scenario_results_by_id[sid]
                    for sid in column_ids
                    if sid in scenario_results_by_id
                ]

            else:
                col_labels = list(scenario_results.keys())
                col_eq_results = list(scenario_results.values())

            # Build table data by iterating over rows_spec and pulling values from the appropriate scenario results.
            table_data: dict[str, list[Any]] = {"label": []}
            for col_label in col_labels:
                table_data[col_label] = []

            # For each row spec, pull the corresponding value from each scenario's equation results and format it.
            for row_spec in rows_spec:
                table_data["label"].append(row_spec.label)
                for col_label, eq_results in zip(col_labels, col_eq_results):
                    value = eq_results.get(row_spec.value, "N/A")
                    eq_spec = model_def.equations.get(row_spec.value)
                    table_data[col_label].append(format_value(value, eq_spec))

            df = pd.DataFrame(table_data)
            df = df.set_index("label")
            df.index.name = None
            return df

        # Build sections based on the report specification, using scenario results and figures as needed.
        sections: list[dict[str, Any]] = []
        for block in model_def.report:
            if isinstance(block, MarkdownBlock):
                sections.append({"type": "markdown", "content": block.content})

            elif isinstance(block, TableBlock):
                df = _build_table_df(block.rows, block.columns)
                sections.append(
                    {
                        "type": "table",
                        "caption": block.caption,
                        "content": df,
                    }
                )

            elif isinstance(block, FigureBlock):
                fig = figures_by_id.get(block.id)
                if fig is not None:
                    sections.append(
                        {
                            "type": "figure",
                            "title": fig.title,
                            "content": f"Figure: {fig.alt_text or 'Visualization'}",
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

    def parameter_specs(self) -> dict[str, Any]:
        """Return the Parameter schema objects keyed by param_id (equation-context only)."""
        return {
            k: v
            for k, v in model_def.parameters.items()
            if v.context != "scenario"
        }

    def scenario_parameter_specs(self) -> dict[str, Any]:
        """Return the Parameter schema objects for scenario-context params."""
        return {
            k: v
            for k, v in model_def.parameters.items()
            if v.context == "scenario"
        }

    def default_scenarios(self) -> list:
        """Return the model's default scenario list."""
        return list(model_def.resolved_scenarios())

    def parameter_groups(self) -> list | None:
        """Return the parameter group tree, or None if not defined."""
        return model_def.groups

    methods = {
        "human_name": human_name,
        "model_title": property(model_title),
        "model_description": property(model_description),
        "scenario_labels": property(scenario_labels),
        "default_params": default_params,
        "parameter_model": parameter_model,
        "run": run,
        # Additional metadata
        "get_source_path": get_source_path,
        "get_model_definition": get_model_definition,
        "parameter_specs": property(parameter_specs),
        "scenario_parameter_specs": property(scenario_parameter_specs),
        "default_scenarios": property(default_scenarios),
        "parameter_groups": property(parameter_groups),
        # Class metadata
        "__module__": "epicc.model.factory",
        "__doc__": f"Dynamically generated model class for '{model_def.title}'",
    }

    # Dyncreate
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
    # Create the model class and then instantiate it. 
    model_class = create_model_class(model_def, source_path)
    return model_class()


__all__ = [
    "create_model_class",
    "create_model_instance",
]
