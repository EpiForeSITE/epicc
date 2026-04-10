# AGENTS.md — epicc Cost Calculator

This file describes the conventions, roles, and constraints for contributors working in this
repository. All agents — whether running in GitHub Actions or invoked interactively — should
read and follow this document before making changes.

---

## Project overview

**epicc** is a browser-based epidemiological cost calculator built with **Streamlit** and
distributed as a static **stlite** build for browser execution.

The current app supports two model flows:

1. **Python + YAML models**
   - A Python module in `models/` implements model logic.
   - A paired YAML file provides default parameters.
   - `app.py` loads the Python module, loads YAML defaults, renders parameter inputs,
     runs the model, and renders sections.

2. **Excel-driven models**
   - An uploaded `.xlsx` file is parsed by `utils/excel_model_runner.py`.
   - Parameters and computed outputs are rendered from workbook contents.

Current high-level flow:

`discover_models() → load_model_from_file() / load_model_params() → render_parameters_with_indent() → run_model() → build_sections() → render_sections()`

Persistence helpers:
- `store_model_state()`
- `save_current_model()`

---

## Architecture notes

Use this section to reason about where changes belong and what contracts must remain stable.

### Runtime layers

1. **UI composition layer** (`src/epicc/__main__.py`)
    - Owns Streamlit controls, session-state synchronization, run triggers, and wiring for model selection.
    - Delegates rendering and IO behavior to helpers in `src/epicc/utils/`.
2. **Model execution layer** (`src/epicc/model/`, `src/epicc/models/`, `models/`)
    - `BaseSimulationModel` defines the contract for Python-coded models.
    - Built-in model classes in `src/epicc/models/` implement `run()`, defaults, scenario labels, and section construction.
3. **Format/validation layer** (`src/epicc/formats/`, `src/epicc/model/schema.py`)
    - Parses YAML/XLSX input into a shared dictionary shape.
    - Applies typed validation via Pydantic where a strict schema is required.

### Pydantic model system

- `src/epicc/model/schema.py` defines the canonical typed schema for structured model documents:
   - `Model` (root object),
   - `Metadata`, `Parameter`, `Equation`, `Table`, `Scenario`, and `Figure` submodels.
- This schema is the primary contract for validating model-like YAML payloads and should be updated in lockstep with any document-structure changes.
- `src/epicc/formats/__init__.py` exposes `opaque_to_typed()` and `read_from_format()` to bridge:
   - untyped dictionaries from parsers, and
   - typed Pydantic objects used by callers.
- `src/epicc/utils/parameter_loader.py` uses a lightweight `RootModel[dict[str, Any]]` envelope (`OpaqueParameters`) when only shape-preserving parse/validation is needed, without imposing the full simulation-document schema.

### `epicc.formats` package design

- `src/epicc/formats/base.py` defines `BaseFormat[T]` with three responsibilities:
   - `read()` for parse to opaque dict + template,
   - `write()` for serialize from opaque dict (optionally preserving template trivia),
   - `write_template()` for schema-driven starter files.
- `src/epicc/formats/__init__.py` performs suffix-based dispatch (`.yaml`, `.yml`, `.xlsx`) through `get_format()`.
- `src/epicc/formats/yaml.py` uses ruamel round-trip nodes (`CommentedMap`) so edits can preserve comments/formatting when writing back.
- `src/epicc/formats/xlsx.py` maps worksheet rows to dot-notation keys for nested dictionaries and reuses workbook templates when possible.
- `src/epicc/formats/template.py` builds model templates from Pydantic defaults/placeholders and delegates rendering to the target format backend.

### Architectural guardrails for contributors

- Prefer adding format support through a new `BaseFormat` implementation and `_FORMATS` registration, rather than branching logic in UI code.
- Keep Streamlit concerns in `__main__.py`/`utils` and keep schema/serialization concerns in `model` + `formats`.
- If a change affects model document structure, update all of:
   - Pydantic schema (`src/epicc/model/schema.py`),
   - relevant format reader/writer behavior,
   - tests under `tests/epicc/`.
- Preserve backward compatibility for existing model YAML and Excel templates unless breaking changes are explicitly approved.

---

## Repository layout

Top-level files and directories you will use most often:

- `app.py`:
   - Root Streamlit shim that adds `src/` to `PYTHONPATH` and imports `epicc.__main__`.
- `src/epicc/__main__.py`:
   - Main app composition and UI flow (model selector, parameter widgets, run triggers).
- `src/epicc/model/`:
   - Core model abstractions and schema definitions (`base.py`, `schema.py`).
- `src/epicc/formats/`:
   - Parameter format readers/writers (`yaml.py`, `xlsx.py`, templates).
- `src/epicc/utils/`:
   - App support modules (`model_loader.py`, `parameter_loader.py`, `parameter_ui.py`, `section_renderer.py`, `excel_model_runner.py`).
- `models/`:
   - Built-in model implementations and matching parameter defaults.
- `config/`:
   - App configuration (`app.yaml`, `global_defaults.yaml`, `paths.yaml`).
- `styles/` and `src/epicc/web/`:
   - UI styling resources.
- `tests/epicc/`:
   - Unit tests for formats and model loading.
- `.devcontainer/`:
   - Development container setup. `post-create.sh` is the source of truth for extra setup steps.
- `.github/workflows/`:
   - CI and agent workflow definitions.

---

## Local development commands

Use `uv` for dependency and command execution.

- Install dependencies:
   - `uv sync`
- Run Streamlit app:
   - `uv run -m streamlit run app.py`
- Run complete quality gate (recommended before PR):
   - `make check`
- Individual checks:
   - `make lint`
   - `make typecheck`
   - `make test`
- Build static stlite bundle:
   - `make build`
- Serve static bundle locally:
   - `make serve`

If you are in a devcontainer or CI environment intended to mirror local contributor setup,
ensure development dependencies are present:

- `uv sync --frozen --group dev --no-install-project`

---

## Coding conventions

- Keep changes minimal and targeted to the requested behavior.
- Preserve existing module boundaries under `src/epicc/`:
   - model logic in model modules,
   - format parsing/serialization in `formats`,
   - Streamlit rendering concerns in `utils`/`__main__.py`.
- Prefer explicit typing for new public functions and non-trivial internal helpers.
- Follow current style used in the repository:
   - straightforward function names,
   - small helpers for Streamlit state/UI behavior,
   - concise docstrings where useful.
- Do not introduce broad refactors unless explicitly requested.

---

## Model and parameter rules

When adding or editing Python+YAML models:

- Keep model pairs aligned:
   - `models/<name>.py` with `models/<name>.yaml`.
- Ensure YAML default keys map to parameters expected by model code.
- Preserve scenario label behavior:
   - Python models can provide scenario labels,
   - Excel flow supports header overrides from uploaded workbook columns.
- If changing parameter structures, validate both:
   - default-loading behavior,
   - reset-to-default behavior in sidebar controls.

When editing Excel-driven behavior:

- Maintain support for uploaded `.xlsx` files in the sidebar.
- Keep computed outputs and editable defaults behavior intact.
- Avoid breaking scenario-header override support.

---

## Testing expectations

- Add or update tests when behavior changes.
- Run `make check` locally before finalizing changes.
- At minimum for focused fixes, run the most relevant subset:
   - `uv run -m pytest tests/epicc/<target_test>.py`
- Keep tests deterministic and file-system safe (use temp files/fixtures).

---

## CI and workflow guidance

- Workflows that pull container images from GHCR must declare explicit permissions:
   - `contents: read`
   - `packages: read`
- Keep GitHub Actions environment setup aligned with `.devcontainer/post-create.sh`
   when the workflow's intent is to mirror local contributor/agent environments.
- Use frozen dependency sync in CI where practical for reproducibility.

---

## Agent operating checklist

Before editing:

1. Read the relevant modules and tests for the target behavior.
2. Identify whether the change affects Python-model flow, Excel flow, or both.
3. Confirm config and schema assumptions.

During editing:

1. Keep patches narrowly scoped.
2. Preserve user-visible text and layout unless change requires otherwise.
3. Avoid introducing new dependencies without justification.

Before handoff:

1. Run targeted tests (or `make check` for broader changes).
2. Summarize exactly what changed and why.
3. Call out anything not validated.

---

## Common pitfalls

- Breaking session-state reset behavior when switching model/input files.
- Updating parameter loaders without updating UI/reset paths.
- Changing schema/format behavior without corresponding tests.
- Introducing workflow changes that work in permissive repos but fail in restricted
   `GITHUB_TOKEN` permission settings.

---

## Definition of done

A change is complete when:

1. Requested behavior is implemented.
2. Existing model flows still run (Python+YAML and Excel-driven, if affected).
3. Relevant tests pass locally.
4. Documentation/config/workflow updates needed for the change are included.

