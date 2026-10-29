# Development

## Running EPICC locally

Install dependencies with a manager that reads `pyproject.toml`; the project uses
[`uv`](https://docs.astral.sh/uv/):

```
uv sync
uv run -m streamlit run app.py
```

This step is not needed in the development container (`.devcontainer/`), which has
everything installed.

## Checks

| Command | What it runs |
| --- | --- |
| `make check` | lint, type check and tests; run it before opening a pull request |
| `make lint` | `ruff` |
| `make typecheck` | `mypy` |
| `make test` | `pytest` |

## The static app

The public app is a static [stlite](https://github.com/whitphx/stlite) build: Python
runs in the visitor's browser, so there is no server.

```
make build    # -> dist/
make serve    # serve dist/ locally
```

## This website

The site is built with [MkDocs](https://www.mkdocs.org/) and the
[Material](https://squidfunk.github.io/mkdocs-material/) theme from the Markdown in
`docs/`. The model pages under [Models](models/index.md) are generated from the model
files by `scripts/build_model_docs.py` and are not committed.

```
make docs          # generate the model pages and build the site -> site/
make docs-serve    # the same, served with live reload
```

On every push to `main`, the Pages workflow publishes the app at the site root and this
documentation under `/docs/`. Pull requests build the site in strict mode, so a broken
link or a missing page fails the check.

To document something, edit or add a Markdown page in `docs/` and list it under `nav`
in `mkdocs.yml`.
