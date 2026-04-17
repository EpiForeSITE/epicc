from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator


class Author(BaseModel):
    name: str
    email: str | None = None


class Parameter(BaseModel):
    type: Literal["integer", "number", "string", "boolean", "enum"]
    label: str
    description: str | None = None
    default: int | float | str | bool
    min: int | float | None = None
    max: int | float | None = None
    unit: str | None = None
    references: list[str] = Field(default_factory=list)
    options: dict[str, str] | None = Field(
        None,
        description="Ordered mapping of constant->display label for enum parameters. Required when type='enum'.",
    )
    context: Literal["equation", "scenario"] = Field(
        "equation",
        description=(
            "Whether this parameter belongs to the equation context "
            "(rendered in the normal parameter sidebar) or the scenario "
            "context (rendered inside each scenario block)."
        ),
    )
    
    @model_validator(mode='after')
    def validate_enum_options(self) -> 'Parameter':
        """Ensure enum parameters have options and non-enum parameters don't."""
        if self.type == 'enum':
            if not self.options:
                raise ValueError("Parameter with type='enum' must have 'options' defined")
        else:
            if self.options is not None:
                raise ValueError(f"Parameter with type='{self.type}' cannot have 'options' (only enum parameters can)")
        return self


class ParameterGroup(BaseModel):
    """A named visual group of parameters or nested sub-groups."""

    label: str
    children: list["str | ParameterGroup"] = Field(default_factory=list)


ParameterGroup.model_rebuild()


class Equation(BaseModel):
    label: str
    unit: str | None = None
    output: Literal["integer", "number"] | None = None
    compute: str = Field(
        ...,
        description="Python-evaluable expression referencing parameter/scenario variable names.",
    )


class ScenarioVars(BaseModel):
    model_config = {"extra": "allow"}  # arbitrary vars like n_cases


class Scenario(BaseModel):
    id: str
    label: str
    vars: ScenarioVars


class TableRow(BaseModel):
    label: str
    value: str = Field(..., description="Key into the equations dict.")
    emphasis: Literal["strong", "em"] | None = None


class MarkdownBlock(BaseModel):
    type: Literal["markdown"]
    content: str


class TableBlock(BaseModel):
    type: Literal["table"]
    caption: str | None = None
    columns: list[str] | None = Field(
        None,
        description="Scenario IDs to display as columns. Defaults to all scenarios in order.",
    )
    rows: list[TableRow] = Field(default_factory=list)


class FigureBlock(BaseModel):
    type: Literal["figure"]
    id: str = Field(..., description="References an entry in the top-level figures list.")


class GraphBlock(BaseModel):
    type: Literal["graph"]
    kind: Literal["bar", "stacked_bar", "line", "pie"] = "bar"
    title: str | None = None
    caption: str | None = None
    columns: list[str] | None = Field(
        None,
        description="Scenario IDs to include. Defaults to all scenarios in order.",
    )
    rows: list[TableRow] = Field(default_factory=list)


ReportBlock = Annotated[
    MarkdownBlock | TableBlock | FigureBlock | GraphBlock,
    Field(discriminator="type"),
]


class Figure(BaseModel):
    id: str
    title: str
    alt_text: str | None = Field(None, alias="alt-text")
    py_code: str | None = Field(None, alias="py-code")

    model_config = {"populate_by_name": True}


class Model(BaseModel):
    title: str
    description: str
    authors: list[Author] = Field(default_factory=list)

    parameters: dict[str, Parameter]
    equations: dict[str, Equation]

    groups: list[str | ParameterGroup] | None = None

    scenarios: list[Scenario]
    report: list[ReportBlock]
    figures: list[Figure] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_scenario_vars(self) -> "Model":
        """Validate that scenario vars match corresponding scenario-context parameters."""
        scenario_params = {
            pid: p for pid, p in self.parameters.items() if p.context == "scenario"
        }
        if not scenario_params:
            return self

        for scenario in self.scenarios:
            vars_dict = scenario.vars.model_dump()
            for var_name, spec in scenario_params.items():
                if var_name not in vars_dict:
                    continue
                value = vars_dict[var_name]
                coerced_value = value

                if spec.type == "integer":
                    if isinstance(value, bool):
                        raise ValueError(
                            f"Scenario '{scenario.id}' var '{var_name}' must be an integer, "
                            f"got {value!r}"
                        )
                    try:
                        coerced_value = int(value)
                    except (TypeError, ValueError):
                        raise ValueError(
                            f"Scenario '{scenario.id}' var '{var_name}' must be an integer, "
                            f"got {value!r}"
                        ) from None
                elif spec.type == "number":
                    if isinstance(value, bool):
                        raise ValueError(
                            f"Scenario '{scenario.id}' var '{var_name}' must be a number, "
                            f"got {value!r}"
                        )
                    try:
                        coerced_value = float(value)
                    except (TypeError, ValueError):
                        raise ValueError(
                            f"Scenario '{scenario.id}' var '{var_name}' must be a number, "
                            f"got {value!r}"
                        ) from None

                if spec.type in ("number", "integer"):
                    if spec.min is not None and coerced_value < spec.min:
                        raise ValueError(
                            f"Scenario '{scenario.id}' var '{var_name}' value "
                            f"{coerced_value} is below minimum {spec.min}"
                        )
                    if spec.max is not None and coerced_value > spec.max:
                        raise ValueError(
                            f"Scenario '{scenario.id}' var '{var_name}' value "
                            f"{coerced_value} exceeds maximum {spec.max}"
                        )
        return self

    def resolved_scenarios(self) -> list[Scenario]:
        return self.scenarios


__all__ = ["Model", "ParameterGroup", "TableRow", "TableBlock", "MarkdownBlock", "FigureBlock", "GraphBlock", "ReportBlock"]
