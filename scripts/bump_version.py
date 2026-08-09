"""Bump the app version and print the steps that publish the release.

Usage:
    uv run scripts/bump_version.py patch      # 0.1.0 -> 0.1.1
    uv run scripts/bump_version.py minor      # 0.1.0 -> 0.2.0
    uv run scripts/bump_version.py major      # 0.1.0 -> 1.0.0
    uv run scripts/bump_version.py 1.4.2      # explicit version

Release notes are not kept in the repository: pushing the tag makes GitHub publish a
release with notes generated from the pull requests merged since the previous one.
This script only touches the two places the version is recorded, which
`tests/epicc/test_version.py` keeps in step.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INIT_PATH = PROJECT_ROOT / "src" / "epicc" / "__init__.py"
PYPROJECT_PATH = PROJECT_ROOT / "pyproject.toml"

SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
_INIT_VERSION = re.compile(r'^(__version__\s*=\s*)"[^"]*"', re.MULTILINE)
_PROJECT_VERSION = re.compile(r'^(version\s*=\s*)"[^"]*"', re.MULTILINE)


def cli() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "target",
        help="'major', 'minor', 'patch', or an explicit MAJOR.MINOR.PATCH version",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would change without writing anything",
    )
    return parser


def read_current_version() -> str:
    match = _INIT_VERSION.search(INIT_PATH.read_text(encoding="utf-8"))
    if match is None:
        raise SystemExit(f"Error: no __version__ found in {INIT_PATH}")

    return match.group(0).split('"')[1]


def resolve_target(current: str, target: str) -> str:
    if target in ("major", "minor", "patch"):
        major, minor, patch = (int(part) for part in current.split("."))
        if target == "major":
            return f"{major + 1}.0.0"
        if target == "minor":
            return f"{major}.{minor + 1}.0"
        return f"{major}.{minor}.{patch + 1}"

    if not SEMVER.match(target):
        raise SystemExit(f"Error: '{target}' is not a MAJOR.MINOR.PATCH version")

    return target


def main() -> int:
    args = cli().parse_args()

    current = read_current_version()
    version = resolve_target(current, args.target)
    if version == current:
        raise SystemExit(f"Error: already at version {current}")

    updates = {
        INIT_PATH: _INIT_VERSION.sub(
            rf'\g<1>"{version}"', INIT_PATH.read_text(encoding="utf-8"), count=1
        ),
        PYPROJECT_PATH: _PROJECT_VERSION.sub(
            rf'\g<1>"{version}"', PYPROJECT_PATH.read_text(encoding="utf-8"), count=1
        ),
    }

    print(f"{current} -> {version}")
    for path, content in updates.items():
        relative = path.relative_to(PROJECT_ROOT)
        if args.dry_run:
            print(f"  would update {relative}")
            continue

        path.write_text(content, encoding="utf-8")
        print(f"  updated {relative}")

    if args.dry_run:
        return 0

    print("\nNext steps:")
    print(f'  git commit -am "Release v{version}"')
    print(f'  git tag -a v{version} -m "v{version}"')
    print("  git push --follow-tags")
    print("\nPushing the tag publishes the release and its generated notes.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
