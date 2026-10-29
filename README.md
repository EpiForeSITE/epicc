# epicc

[![Documentation](https://img.shields.io/badge/docs-epiforesite.github.io%2Fepicc%2Fdocs-A60F2D)](https://epiforesite.github.io/epicc/docs/)

Streamlit webapp for epiworld.

Please install dependencies with a dependency manager capable of reading `pyproject.toml` files
(most modern solutions will work). For example, with [`uv`](https://docs.astral.sh/uv/):

```
uv sync
```

Please note that this step is not required if working in a containerized context.

You may then run with:

```
uv run -m streamlit run app.py
```

## Launch the App online

Click below to open the live Streamlit application, as currently deployed:

https://epiworldpythonapp.streamlit.app/

*(If the app is still deploying, it may take a few seconds to load.)*

Please follow instructions in your console for loading development versions.

## Documentation

The documentation website is at <https://epiforesite.github.io/epicc/docs/>, built from
the Markdown in [`docs/`](docs/) with MkDocs. It covers:

- [the bundled models](https://epiforesite.github.io/epicc/docs/models/), with their
  parameters and sources, generated from the model files;
- [sharing a calculation by URL](https://epiforesite.github.io/epicc/docs/sharing-links/);
- [branding and themes](https://epiforesite.github.io/epicc/docs/branding/);
- [development](https://epiforesite.github.io/epicc/docs/development/) and
  [versioning and releases](https://epiforesite.github.io/epicc/docs/versioning/).

Build it locally with `make docs` (or `make docs-serve` for live reload).
