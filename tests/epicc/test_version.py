import re
import tomllib
from pathlib import Path

import pytest

import epicc
from bump_version import resolve_target
from epicc.config import CONFIG

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


@pytest.fixture
def pyproject() -> dict:
    with open(PROJECT_ROOT / "pyproject.toml", "rb") as f:
        return tomllib.load(f)


def test_version_is_semver() -> None:
    assert SEMVER.match(epicc.__version__)


def test_pyproject_version_matches_the_package(pyproject: dict) -> None:
    """`scripts/bump_version.py` keeps these two in step; catch manual edits."""
    assert pyproject["project"]["version"] == epicc.__version__


def test_releases_url_is_configured() -> None:
    """Without it the header hides 'What's new' and users lose the release notes."""
    assert CONFIG.app.releases_url
    assert CONFIG.app.releases_url.startswith("https://")


@pytest.mark.parametrize(
    ("target", "expected"),
    [("patch", "1.2.4"), ("minor", "1.3.0"), ("major", "2.0.0"), ("3.0.1", "3.0.1")],
)
def test_resolve_target(target: str, expected: str) -> None:
    assert resolve_target("1.2.3", target) == expected


def test_resolve_target_rejects_non_semver() -> None:
    with pytest.raises(SystemExit):
        resolve_target("1.2.3", "1.2")
