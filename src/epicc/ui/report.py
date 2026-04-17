from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import uuid
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from epicc.model.parameters import format_value
from epicc.model.schema import Figure, FigureBlock, GraphBlock, MarkdownBlock, Scenario, TableBlock


def _callout(summary: str, detail: str | None = None) -> None:
    """A muted informational callout used for skeletons and errors."""

    detail_html = (
        f"<br><span style='font-size:0.75rem;'>{detail}</span>" if detail else ""
    )

    st.markdown(
        f"<div style='border:1px solid #e0e0e0; border-radius:4px; "
        f"padding:0.75rem 1rem; color:#999; background:#fafafa; "
        f"font-size:0.85rem;'>{summary}{detail_html}</div>",
        unsafe_allow_html=True,
    )


class BlockRenderer(ABC):
    """Some sort of block in the report."""

    @abstractmethod
    def render(self, run_results: dict[str, Any] | None) -> None:
        ... 


class MarkdownBlockRenderer(BlockRenderer):
    def __init__(self, block: MarkdownBlock) -> None:
        self._block = block

    def render(self, run_results: dict[str, Any] | None) -> None:
        st.markdown(self._block.content, unsafe_allow_html=True)


class TableBlockRenderer(BlockRenderer):
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
        if run_results is None:
            labels = [r.label for r in self._block.rows]
            preview = ", ".join(labels[:3]) + ("..." if len(labels) > 3 else "")
            _callout(
                f"Table - {len(labels)} rows ({preview})" if labels else "Table",
                "Run simulation to see results",
            )

            return

        try:
            st.dataframe(self._build_df(run_results), width='stretch')
        except Exception as exc:
            _callout("Table could not be rendered", str(exc))

        if self._block.caption:
            st.caption(self._block.caption)

    def _build_df(self, run_results: dict[str, Any]) -> pd.DataFrame:
        scenarios = run_results.get("scenarios", self._scenarios)
        by_id: dict[str, dict] = run_results.get("scenario_results_by_id", {})
        overrides: dict[str, str] = run_results.get("label_overrides", {})

        # Determine column order
        if self._block.columns is not None:
            col_pairs = [
                (sid, next((s for s in scenarios if s.id == sid), None))
                for sid in self._block.columns
                if sid in by_id
            ]
        else:
            col_pairs = [(s.id, s) for s in scenarios]

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
                data[lbl].append(format_value(val, self._equations.get(row.value)))

        df = pd.DataFrame(data).set_index("label")
        df.index.name = None
        return df


class FigureBlockRenderer(BlockRenderer):
    def __init__(self, block: FigureBlock, figure: Figure | None) -> None:
        self._block = block
        self._figure = figure

    def render(self, run_results: dict[str, Any] | None) -> None:
        if self._figure is None:
            _callout(
                "Figure not found",
                f"No figure with id '{self._block.id}'",
            )
            return

        if run_results is None:
            _callout(
                f"Figure - {self._figure.title}",
                "Run simulation to see results",
            )
            return

        # TODO: execute py_code when figure rendering is implemented
        st.subheader(self._figure.title)
        _callout("Figure rendering not yet implemented")


class GraphBlockRenderer(BlockRenderer):
    _KIND_LABELS = {
        "bar": "Bar chart",
        "stacked_bar": "Stacked bar chart",
        "line": "Line chart",
        "pie": "Pie chart",
    }

    def __init__(
        self,
        block: GraphBlock,
        equations: dict[str, Any],
        scenarios: list[Scenario],
    ) -> None:
        self._block = block
        self._equations = equations
        self._scenarios = scenarios
        self._uuid = str(uuid.uuid4())

    def render(self, run_results: dict[str, Any] | None) -> None:
        if run_results is None:
            kind_label = self._KIND_LABELS.get(self._block.kind, self._block.kind)
            _callout(
                f"{kind_label}" + (f" - {self._block.title}" if self._block.title else ""),
                "Run simulation to see results",
            )
            return

        try:
            fig = self._build_figure(run_results)
        except Exception as exc:
            _callout("Graph could not be rendered", str(exc))
            return

        # Chart!
        with st.container(key=f'graph-block-{self._uuid}'):
            if self._block.title:
                st.markdown(
                    f"<div style='text-align: center; margin-bottom: 0.5rem;'>"
                    f"<span style='font-size: 1.1rem; font-weight: 600; color: #1f1f1f;'>"
                    f"{self._block.title}</span></div>",
                    unsafe_allow_html=True,
                )

            if self._block.caption:
                st.markdown(
                    f"<div style='text-align: center; margin-bottom: 0.5rem;'>"
                    f"<span style='font-size: 0.9rem; color: #6c757d;'>"
                    f"{self._block.caption}</span></div>",
                    unsafe_allow_html=True
                )

            st.plotly_chart(fig, width='stretch', key=f'plotly-{self._uuid}')

    def _resolve_columns(
        self, run_results: dict[str, Any]
    ) -> tuple[list[str], list[str], list[dict[str, Any]]]:
        """Return (scenario_ids, scenario_labels, eq_results_per_scenario)."""
        scenarios = run_results.get("scenarios", self._scenarios)
        by_id: dict[str, dict] = run_results.get("scenario_results_by_id", {})
        overrides: dict[str, str] = run_results.get("label_overrides", {})

        if self._block.columns is not None:
            pairs = [
                (sid, next((s for s in scenarios if s.id == sid), None))
                for sid in self._block.columns
                if sid in by_id
            ]
        else:
            pairs = [(s.id, s) for s in scenarios]

        ids = [sid for sid, _ in pairs]
        labels = [overrides.get(sid, s.label if s else sid) for sid, s in pairs]
        results = [by_id.get(sid, {}) for sid, _ in pairs]
        return ids, labels, results

    def _build_figure(self, run_results: dict[str, Any]) -> go.Figure:
        _, col_labels, col_results = self._resolve_columns(run_results)
        rows = self._block.rows
        row_labels = [r.label for r in rows]

        kind = self._block.kind

        if kind == "bar":
            # One trace per row-equation; scenarios on x-axis
            fig = go.Figure()
            for row in rows:
                values = [
                    _raw_value(res.get(row.value, 0)) for res in col_results
                ]
                fig.add_trace(go.Bar(name=row.label, x=col_labels, y=values))
            fig.update_layout(barmode="group", legend_title_text="Component")

        elif kind == "stacked_bar":
            fig = go.Figure()
            for row in rows:
                values = [
                    _raw_value(res.get(row.value, 0)) for res in col_results
                ]
                fig.add_trace(go.Bar(name=row.label, x=col_labels, y=values))
            fig.update_layout(barmode="stack", legend_title_text="Component")

        elif kind == "line":
            fig = go.Figure()
            for row in rows:
                values = [
                    _raw_value(res.get(row.value, 0)) for res in col_results
                ]
                fig.add_trace(go.Scatter(
                    name=row.label, x=col_labels, y=values, mode="lines+markers"
                ))
            fig.update_layout(legend_title_text="Component")

        elif kind == "pie":
            # Use the first scenario column; rows become pie slices
            first_results = col_results[0] if col_results else {}
            values = [
                _raw_value(first_results.get(row.value, 0)) for row in rows
            ]
            scenario_label = col_labels[0] if col_labels else ""
            fig = go.Figure(go.Pie(
                labels=row_labels,
                values=values,
                hole=0.3,
            ))
            fig.update_layout(title_text=scenario_label)

        else:
            raise ValueError(f"Unknown graph kind: {kind!r}")

        fig.update_layout(
            margin={"t": 40, "b": 20, "l": 0, "r": 0},
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
        )
        return fig


def _raw_value(value: Any) -> float:
    """Coerce an equation result to a plain float for Plotly, the picky."""

    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


class ReportRenderer:
    """Render full report."""

    def __init__(
        self,
        model_title: str,
        model_description: str,
        block_renderers: list[BlockRenderer],
    ) -> None:
        self._title = model_title
        self._description = model_description
        self._block_renderers = block_renderers

    def render(self, run_results: dict[str, Any] | None, *, hint: str | None = None) -> None:
        st.title(self._title)
        st.write(self._description)
        if run_results is None and hint:
            st.info(hint)
        for i, renderer in enumerate(self._block_renderers):
            renderer.render(run_results)
            if i < len(self._block_renderers) - 1:
                st.markdown(
                    '<div class="section-divider"></div>', unsafe_allow_html=True
                )


def get_report_renderer(model: Any) -> ReportRenderer:
    model_def = model.get_model_definition()
    figures_by_id = {fig.id: fig for fig in model_def.figures}
    block_renderers: list[BlockRenderer] = []

    for block in model_def.report:
        if isinstance(block, MarkdownBlock):
            block_renderers.append(MarkdownBlockRenderer(block))
            
        elif isinstance(block, TableBlock):
            block_renderers.append(
                TableBlockRenderer(
                    block, model_def.equations, model_def.resolved_scenarios()
                )
            )

        elif isinstance(block, GraphBlock):
            block_renderers.append(
                GraphBlockRenderer(
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
