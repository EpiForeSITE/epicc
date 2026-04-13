from __future__ import annotations

from typing import Annotated, Literal

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


# ---------------------------------------------------------------------------
# Report block types
# ---------------------------------------------------------------------------

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


ReportBlock = Annotated[
    MarkdownBlock | TableBlock | FigureBlock,
    Field(discriminator="type"),
]


# ---------------------------------------------------------------------------
# Top-level figure asset
# ---------------------------------------------------------------------------

class Figure(BaseModel):
    id: str
    title: str
    alt_text: str | None = Field(None, alias="alt-text")
    py_code: str | None = Field(None, alias="py-code")

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Legacy table container — kept for backward compatibility
# ---------------------------------------------------------------------------

class _LegacyTable(BaseModel):
    """Deprecated. Use top-level scenarios: and report: instead."""
    scenarios: list[Scenario] = Field(default_factory=list)
    rows: list[TableRow] = Field(default_factory=list)


# Keep the public name for code that still imports Table
Table = _LegacyTable


class Model(BaseModel):
    title: str
    description: str
    authors: list[Author] = Field(default_factory=list)
    introduction: str | None = None

    parameters: dict[str, Parameter]
    equations: dict[str, Equation]

    groups: list[str | ParameterGroup] | None = None

    # New top-level scenario list (preferred)
    scenarios: list[Scenario] | None = None

    # New report block list (preferred)
    report: list[ReportBlock] | None = None

    # Legacy combined table block — honoured when scenarios/report are absent
    table: _LegacyTable | None = None

    figures: list[Figure] = Field(default_factory=list)

    def resolved_scenarios(self) -> list[Scenario]:
        """Return scenarios from the preferred location or fall back to legacy table."""
        if self.scenarios is not None:
            return self.scenarios
        if self.table is not None:
            return self.table.scenarios
        return []


__all__ = ["Model", "ParameterGroup", "Table", "TableRow", "TableBlock", "MarkdownBlock", "FigureBlock", "ReportBlock"]
