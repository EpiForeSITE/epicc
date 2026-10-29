#!/usr/bin/env bash
# Publish this checkout's documentation as a version, with mike.
#
# Every version lives in its own folder on the docs branch (default `docs-versions`),
# which the Pages workflow serves under /docs/. The branch is the history: nothing is
# rebuilt for old versions.
#
# Usage:
#   scripts/deploy_docs.sh release   # a v* tag: publish __version__, point `latest` at it
#   scripts/deploy_docs.sh main      # a push to main: publish `dev`
#
# On main, __version__ is also published as "<version> (unreleased)" when no
# v<version> tag exists yet. The app links to docs/<its version>/, and the app on the
# site is built from main, so that page has to exist before the release does; the
# release then replaces it.
#
# Environment:
#   DOCS_BRANCH   branch holding the published versions (default: docs-versions)
#   PUSH          "true" to push the branch (CI); otherwise it is only committed locally
set -euo pipefail

mode="${1:?usage: scripts/deploy_docs.sh release|main}"
branch="${DOCS_BRANCH:-docs-versions}"
push=()
if [ "${PUSH:-false}" = "true" ]; then
  push=(--push)
  # Start from what is published, so the push is a fast-forward.
  git fetch origin "$branch:$branch" 2>/dev/null || true
fi

version="$(sed -n 's/^__version__ = "\(.*\)"/\1/p' src/epicc/__init__.py)"
if [ -z "$version" ]; then
  echo "could not read __version__ from src/epicc/__init__.py" >&2
  exit 1
fi

make docs-generate

mike() {
  uv run --frozen --group docs mike "$@" --branch "$branch" ${push[@]+"${push[@]}"}
}

case "$mode" in
  release)
    mike deploy --update-aliases --title "$version" "$version" latest
    mike set-default latest
    ;;
  main)
    mike deploy --title "dev (main)" dev
    if ! git rev-parse -q --verify "refs/tags/v$version" >/dev/null; then
      mike deploy --title "$version (unreleased)" "$version"
    fi
    # Until the first versioned release, /docs/ lands on dev.
    if ! uv run --frozen --group docs mike list --branch "$branch" | grep -q '\[latest\]'; then
      mike set-default dev
    fi
    ;;
  *)
    echo "unknown mode: $mode (expected release or main)" >&2
    exit 2
    ;;
esac
