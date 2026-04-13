from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Author(BaseModel):
    name: str
    email: str | None = None


class Parameter(BaseModel):
    type: Literal["integer", "number", "string", "boolean"]
    label: str
    description: str | None = None
    default: int | float | str | bool
    min: int | float | None = None
    max: int | float | None = None
    unit: str | None = None
    references: list[str] = Field(default_factory=list)


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


class Table(BaseModel):
    scenarios: list[Scenario] = Field(default_factory=list)
    rows: list[TableRow] = Field(default_factory=list)


class Figure(BaseModel):
    title: str
    alt_text: str | None = Field(None, alias="alt-text")
    py_code: str | None = Field(None, alias="py-code")

    model_config = {"populate_by_name": True}


class Model(BaseModel):
    title: str
    description: str
    authors: list[Author] = Field(default_factory=list)
    introduction: str | None = None

    parameters: dict[str, Parameter]
    equations: dict[str, Equation]

    table: Table
    figures: list[Figure] = Field(default_factory=list)


__all__ = ["Model"]
