"""
OO report rendering pipeline.

Each block type has a dedicated renderer subclass that handles three states
transparently through a single render(run_results) call:

  - run_results is None  → skeleton placeholder
  - run_results is set   → live computed data
  - data is missing/bad  → error callout (same visual language as skeleton)

The public entry point is get_report_renderer(model), which constructs a
ReportRenderer from a model instance without importing anything from the
model layer (model layer stays clean; UI layer may depend on model types).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import pandas as pd
import streamlit as st

from epicc.model.schema import Figure, FigureBlock, MarkdownBlock, Scenario, TableBlock


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _format_value(value: Any, equation_spec: Any = None) -> str:
    """Format a computed value for display in tables."""
    if isinstance(value, (int, float)):
        is_currency = equation_spec and getattr(equation_spec, "unit", None) in (
            "USD",
            "dollars",
            "$",
        )
        if abs(value) >= 1000:
            formatted = f"{value:,.0f}"
        elif abs(value) >= 100:
            formatted = f"{value:,.2f}"
        elif abs(value) >= 1:
            formatted = f"{value:.2f}"
        else:
            formatted = f"{value:.4f}"
        return f"${formatted}" if is_currency else formatted
    return str(value)


def _callout(icon: str, summary: str, detail: str | None = None) -> None:
    """Render a muted informational callout used for skeletons and errors."""
    detail_html = (
        f"<br><span style='font-size:0.75rem;'>{detail}</span>" if detail else ""
    )
    st.markdown(
        f"<div style='border:1px solid #e0e0e0; border-radius:4px; "
        f"padding:0.75rem 1rem; color:#999; background:#fafafa; "
        f"font-size:0.85rem;'>{icon} {summary}{detail_html}</div>",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Block renderer base + subclasses
# ---------------------------------------------------------------------------

class BlockRenderer(ABC):
    """Renders one report block — with live data, as a skeleton, or as an error."""

    @abstractmethod
    def render(self, run_results: dict[str, Any] | None) -> None:
        """Render the block.

        Args:
            run_results: The raw dict returned by model.run(), or None if the
                         simulation has not been executed yet.
        """


class MarkdownBlockRenderer(BlockRenderer):
    """Always renders immediately; no data dependency."""

    def __init__(self, block: MarkdownBlock) -> None:
        self._block = block

    def render(self, run_results: dict[str, Any] | None) -> None:
        st.markdown(self._block.content, unsafe_allow_html=True)


class TableBlockRenderer(BlockRenderer):
    """Renders a scenario comparison table, or a skeleton before the run."""

    def __init__(
        self,
        block: TableBlock,
        equations: dict[str, Any],
        scenarios: list[Scenario],
    ) -> None:
        self._block = block
        self._equations = equations
        self._scenarios = scenarios

    def render(self, run_results: dict[str, Any] | None) -> None:
        if self._block.caption:
            st.caption(self._block.caption)

        if run_results is None:
            labels = [r.label for r in self._block.rows]
            preview = ", ".join(labels[:3]) + ("…" if len(labels) > 3 else "")
            _callout(
                "📊",
                f"Table — {len(labels)} rows ({preview})" if labels else "Table",
                "Run simulation to see results",
            )
            return

        try:
            st.dataframe(self._build_df(run_results), width='stretch')
        except Exception as exc:
            _callout("⚠️", "Table could not be rendered", str(exc))

    def _build_df(self, run_results: dict[str, Any]) -> pd.DataFrame:
        by_id: dict[str, dict] = run_results.get("scenario_results_by_id", {})
        overrides: dict[str, str] = run_results.get("label_overrides", {})

        # Determine column order
        if self._block.columns is not None:
            col_pairs = [
                (sid, next((s for s in self._scenarios if s.id == sid), None))
                for sid in self._block.columns
                if sid in by_id
            ]
        else:
            col_pairs = [(s.id, s) for s in self._scenarios]

        col_labels = [
            overrides.get(sid, s.label if s else sid) for sid, s in col_pairs
        ]
        col_results = [by_id.get(sid, {}) for sid, _ in col_pairs]

        data: dict[str, list] = {"label": []}
        for lbl in col_labels:
            data[lbl] = []

        for row in self._block.rows:
            data["label"].append(row.label)
            for lbl, eq_res in zip(col_labels, col_results):
                val = eq_res.get(row.value, "N/A")
                data[lbl].append(_format_value(val, self._equations.get(row.value)))

        df = pd.DataFrame(data).set_index("label")
        df.index.name = None
        return df


class FigureBlockRenderer(BlockRenderer):
    """Renders a figure asset, or a skeleton/error when unavailable."""

    def __init__(self, block: FigureBlock, figure: Figure | None) -> None:
        self._block = block
        self._figure = figure

    def render(self, run_results: dict[str, Any] | None) -> None:
        if self._figure is None:
            _callout(
                "⚠️",
                "Figure not found",
                f"No figure with id '{self._block.id}'",
            )
            return

        if run_results is None:
            _callout(
                "📈",
                f"Figure — {self._figure.title}",
                "Run simulation to see results",
            )
            return

        # TODO: execute py_code when figure rendering is implemented
        st.subheader(self._figure.title)
        _callout("📈", "Figure rendering not yet implemented")


# ---------------------------------------------------------------------------
# Root renderer
# ---------------------------------------------------------------------------

class ReportRenderer:
    """Renders a full model report with title, description, and all blocks."""

    def __init__(
        self,
        model_title: str,
        model_description: str,
        block_renderers: list[BlockRenderer],
    ) -> None:
        self._title = model_title
        self._description = model_description
        self._block_renderers = block_renderers

    def render(self, run_results: dict[str, Any] | None) -> None:
        """Render the report.

        Args:
            run_results: Raw output of model.run(), or None for skeleton mode.
        """
        st.title(self._title)
        st.write(self._description)
        for i, renderer in enumerate(self._block_renderers):
            renderer.render(run_results)
            if i < len(self._block_renderers) - 1:
                st.markdown(
                    '<div class="section-divider"></div>', unsafe_allow_html=True
                )


# ---------------------------------------------------------------------------
# Public factory
# ---------------------------------------------------------------------------

def _build_synthetic_report(model_def: Any) -> list:
    """Synthesise a report block list from legacy introduction + table fields."""
    blocks: list = []
    if model_def.introduction:
        blocks.append(MarkdownBlock(type="markdown", content=model_def.introduction))
    if model_def.table and model_def.table.rows:
        blocks.append(TableBlock(type="table", columns=None, rows=model_def.table.rows))
    return blocks


def get_report_renderer(model: Any) -> ReportRenderer | None:
    """Construct a ReportRenderer for a model instance.

    Returns None if the model does not expose get_model_definition() (e.g.
    hand-written Python models that have not been migrated).
    """
    if not hasattr(model, "get_model_definition"):
        return None

    model_def = model.get_model_definition()
    report = model_def.report if model_def.report is not None else _build_synthetic_report(model_def)

    if not report:
        return None

    figures_by_id = {fig.id: fig for fig in model_def.figures}
    block_renderers: list[BlockRenderer] = []

    for block in report:
        if isinstance(block, MarkdownBlock):
            block_renderers.append(MarkdownBlockRenderer(block))
        elif isinstance(block, TableBlock):
            block_renderers.append(
                TableBlockRenderer(
                    block, model_def.equations, model_def.resolved_scenarios()
                )
            )
        elif isinstance(block, FigureBlock):
            block_renderers.append(
                FigureBlockRenderer(block, figures_by_id.get(block.id))
            )

    return ReportRenderer(model_def.title, model_def.description, block_renderers)


__all__ = [
    "BlockRenderer",
    "FigureBlockRenderer",
    "MarkdownBlockRenderer",
    "ReportRenderer",
    "TableBlockRenderer",
    "get_report_renderer",
]
