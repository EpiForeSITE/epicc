"""The website's model pages, generated from the bundled model files.

Runs `scripts/build_model_docs.py` the way `make docs` does and reads what it wrote.
The full site build (MkDocs, strict mode) runs in CI's `docs` job.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from epicc.model.models import MODEL_REGISTRY

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = PROJECT_ROOT / "scripts" / "build_model_docs.py"


@pytest.fixture(scope="module")
def pages(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("models")
    subprocess.run(
        [sys.executable, str(SCRIPT), "--out", str(out)],
        check=True,
        capture_output=True,
        text=True,
    )
    return out


def test_every_bundled_model_gets_a_page_and_an_index_entry(pages: Path) -> None:
    index = (pages / "index.md").read_text(encoding="utf-8")
    for stem in MODEL_REGISTRY:
        assert (pages / f"{stem}.md").is_file(), f"no page for {stem}"
        assert f"]({stem}.md)" in index, f"{stem} missing from the models index"


def test_a_page_carries_the_model_s_parameters_and_their_sources(pages: Path) -> None:
    page = (pages / "measles.md").read_text(encoding="utf-8")
    assert page.startswith("# Measles Outbreak Cost Estimation")
    for section in ("## Parameters", "## Scenarios", "## Equations"):
        assert section in page
    assert "`cost_measles_hospitalization`" in page
    assert "CDC Measles surveillance data" in page


def test_report_lists_get_the_blank_line_python_markdown_needs(pages: Path) -> None:
    page = (pages / "measles.md").read_text(encoding="utf-8")
    assert "outbreaks:\n\n- **22 Cases**" in page


def test_enum_parameters_list_every_choice_with_its_label(pages: Path) -> None:
    """A sharing link takes the choice's value, so the page has to name them all."""
    page = (pages / "tb_isolation.md").read_text(encoding="utf-8")
    row = next(line for line in page.splitlines() if "`isolation_type`" in line)
    assert "`HOME_ISO`" in row, "the default is not shown as a value"
    for choice in (
        "`HOSP_ISO` = Hospital",
        "`MOTEL_ISO` = Motel, with nurse",
        "`HOME_ISO` = Home, with nurse",
    ):
        assert choice in row, f"missing {choice}"
