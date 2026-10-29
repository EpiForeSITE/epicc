"""Generate one documentation page per bundled model from its YAML.

Every model already carries what its page needs: a title and description, each
parameter's label, default, range, unit and references, its scenarios, presets and
equations, and the prose of its report. This renders that into Markdown under
`docs/models/` (git-ignored) so the website documents every model, and stays in step
with it, without anyone writing the pages by hand.

Usage:
    uv run scripts/build_model_docs.py                  # -> docs/models/
    uv run scripts/build_model_docs.py --out somewhere

`make docs` runs this before building the site.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from epicc.formats import read_from_format  # noqa: E402
from epicc.model.models import MODEL_REGISTRY  # noqa: E402
from epicc.model.schema import MarkdownBlock, Model, ParameterGroup  # noqa: E402

MODELS_DIR = SRC_DIR / "epicc" / "model" / "models"
DEFAULT_OUT = PROJECT_ROOT / "docs" / "models"


def cli() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help="Directory to write the pages to (replaced). Default: docs/models.",
    )
    return parser


def load(stem: str) -> Model:
    path = MODELS_DIR / f"{stem}.yaml"
    with path.open("rb") as fh:
        model, _ = read_from_format(path.name, fh, Model)
    return model


def cell(value: Any) -> str:
    """Make a value safe inside a Markdown table cell."""
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ").strip()


def number(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return cell(value)
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return f"{value:,}" if isinstance(value, int) else f"{value:,.6g}"


def value_range(low: Any, high: Any) -> str:
    if low is None and high is None:
        return ""
    return f"{number(low) if low is not None else ''} to {number(high) if high is not None else ''}"


def flatten_groups(groups: list[Any]) -> list[tuple[str, list[str]]]:
    """[(section label, [parameter ids])], with sub-group labels folded into parents."""
    out: list[tuple[str, list[str]]] = []

    def walk(children: list[Any], label: str) -> None:
        direct = [child for child in children if isinstance(child, str)]
        if direct:
            out.append((label, direct))
        for child in children:
            if isinstance(child, ParameterGroup):
                walk(child.children, f"{label} - {child.label}")

    for group in groups:
        if isinstance(group, ParameterGroup):
            walk(group.children, group.label)
        else:
            out.append(("Parameters", [group]))
    return out


_LIST_ITEM = re.compile(r"\s*(?:[-*+]|\d+\.)\s")


def report_prose(markdown: str) -> str:
    """Adapt report prose, written for the app, to the site's Markdown renderer.

    Headings drop one level: the prose starts at `##`, and on its page it sits under a
    `##` section. A list directly under a paragraph line gets the blank line before it
    that Python-Markdown needs; the app's renderer does without it.
    """
    out: list[str] = []
    for line in markdown.splitlines():
        line = re.sub(r"^(#{1,5}) ", r"#\1 ", line)
        previous = out[-1] if out else ""
        if (
            _LIST_ITEM.match(line)
            and previous.strip()
            and not _LIST_ITEM.match(previous)
            and not previous.startswith((" ", "\t"))
        ):
            out.append("")
        out.append(line)
    return "\n".join(out)


def parameter_table(model: Model, ids: list[str]) -> list[str]:
    lines = [
        "| Parameter | Default | Unit | Range | Sources |",
        "| --- | --- | --- | --- | --- |",
    ]
    for pid in ids:
        param = model.parameters[pid]
        name = f"**{cell(param.label)}**<br>`{pid}`"
        if param.description:
            name += f"<br>{cell(param.description)}"
        sources = "<br><br>".join(cell(ref) for ref in param.references)
        lines.append(
            f"| {name} | {number(param.default)} | {cell(param.unit)} "
            f"| {value_range(param.min, param.max)} | {sources} |"
        )
    return lines


def render(stem: str, model: Model) -> str:
    lines = [f"# {model.title}", "", model.description.strip(), ""]
    if model.authors:
        lines += [f"**Authors:** {', '.join(a.name for a in model.authors)}", ""]
    lines += [
        f"Model id: `{stem}`. Open it in the app with `?model={stem}`; see "
        "[Sharing links](../sharing-links.md).",
        "",
    ]

    prose = [b.content for b in model.report if isinstance(b, MarkdownBlock)]
    if prose:
        lines += ["## About this model", ""]
        lines += [report_prose(text.strip()) + "\n" for text in prose]

    lines += ["## Parameters", ""]
    grouped = flatten_groups(model.groups)
    listed = {pid for _, ids in grouped for pid in ids}
    scenario_ids = [
        pid for pid, p in model.parameters.items() if p.context == "scenario"
    ]
    rest = [
        pid
        for pid, p in model.parameters.items()
        if pid not in listed and p.context != "scenario"
    ]
    if rest:
        grouped.append(("Other parameters", rest))
    for label, ids in grouped:
        lines += [f"### {label}", "", *parameter_table(model, ids), ""]
    if scenario_ids:
        lines += [
            "### Set per scenario",
            "",
            "Each scenario supplies its own value for these; the default applies to "
            "scenarios added in the app.",
            "",
            *parameter_table(model, scenario_ids),
            "",
        ]

    if model.scenarios:
        var_ids = list(
            dict.fromkeys(
                key for s in model.scenarios for key in s.vars.model_dump()
            )
        )
        header = ["Scenario"] + [
            cell(model.parameters[v].label) if v in model.parameters else v
            for v in var_ids
        ]
        lines += [
            "## Scenarios",
            "",
            "| " + " | ".join(header) + " |",
            "| " + " | ".join("---" for _ in header) + " |",
        ]
        for scenario in model.scenarios:
            values = scenario.vars.model_dump()
            row = [f"{cell(scenario.label)}<br>`{scenario.id}`"]
            row += [number(values.get(v, "")) for v in var_ids]
            lines.append("| " + " | ".join(row) + " |")
        lines.append("")

    if model.presets:
        lines += ["## Presets", "", "| Preset | Changes |", "| --- | --- |"]
        for preset in model.presets:
            changes = "<br>".join(
                f"`{k}` = {number(v)}" for k, v in preset.params.items()
            )
            lines.append(f"| {cell(preset.label)}<br>`{preset.id}` | {changes} |")
        lines.append("")

    lines += [
        "## Equations",
        "",
        "Evaluated in order; each can use the parameters and any equation above it.",
        "",
    ]
    for eid, eq in model.equations.items():
        unit = f" ({eq.unit})" if eq.unit else ""
        lines += [
            f"**{eq.label}**{unit} `{eid}`",
            "",
            "```python",
            eq.compute.strip(),
            "```",
            "",
        ]
    return "\n".join(lines)


def main() -> int:
    args = cli().parse_args()
    out: Path = args.out
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    index = [
        "# Models",
        "",
        "Every model bundled with EPICC. These pages are generated from the model "
        "files in `src/epicc/model/models/` each time the site is built.",
        "",
        "| Model | Description |",
        "| --- | --- |",
    ]
    for stem in MODEL_REGISTRY:
        model = load(stem)
        (out / f"{stem}.md").write_text(render(stem, model), encoding="utf-8")
        index.append(
            f"| [{cell(model.title)}]({stem}.md) | {cell(model.description)} |"
        )
        print(f"wrote {stem}.md", file=sys.stderr)
    (out / "index.md").write_text("\n".join(index) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
