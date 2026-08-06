from contextlib import nullcontext

from epicc.model.schema import GraphBlock
from epicc.ui import report


def test_callout_escapes_dynamic_text(monkeypatch) -> None:
    rendered: list[str] = []
    monkeypatch.setattr(
        report.st,
        "markdown",
        lambda content, **_kwargs: rendered.append(content),
    )

    report._callout("<script>alert('summary')</script>", "<img src=x>")

    assert "<script>" not in rendered[0]
    assert "&lt;script&gt;alert(&#x27;summary&#x27;)&lt;/script&gt;" in rendered[0]
    assert "&lt;img src=x&gt;" in rendered[0]


def test_graph_metadata_escapes_dynamic_text(monkeypatch) -> None:
    rendered: list[str] = []
    renderer = report.GraphBlockRenderer(
        GraphBlock(
            type="graph",
            title="<strong>Title</strong>",
            caption="<img src=x>",
        ),
        equations={},
        scenarios=[],
    )
    monkeypatch.setattr(renderer, "_build_figure", lambda _results: object())
    monkeypatch.setattr(report.st, "container", lambda **_kwargs: nullcontext())
    monkeypatch.setattr(
        report.st,
        "markdown",
        lambda content, **_kwargs: rendered.append(content),
    )
    monkeypatch.setattr(report.st, "plotly_chart", lambda *_args, **_kwargs: None)

    renderer.render({})

    assert "&lt;strong&gt;Title&lt;/strong&gt;" in rendered[0]
    assert "&lt;img src=x&gt;" in rendered[1]
