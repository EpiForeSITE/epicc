UV ?= uv

STLITE_VER ?= 0.86.0
PORT ?= 8000
BUMP ?= patch

APP_PY := app.py
SOURCE := src/epicc
DIST_DIR := dist
DOCS_OUT ?= site

.DEFAULT_GOAL := help

.PHONY: help
help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

.PHONY: setup
setup: install build ## Install dependencies and build the stlite app

.PHONY: install
install: ## Install Python dependencies with uv
	$(UV) sync

.PHONY: build
build: ## Generate the bundle.
	mkdir -p $(DIST_DIR)
	$(UV) run scripts/build.py --app $(APP_PY) --out $(DIST_DIR)

.PHONY: serve
serve: build ## Serve the stlite static build
	$(UV) run python -m http.server $(PORT) --directory $(DIST_DIR)

.PHONY: dev
dev: ## Run normal Streamlit locally
	$(UV) run streamlit run $(APP_PY)

.PHONY: stlite
stlite: setup serve ## Install, build, and serve the stlite app

.PHONY: lint
lint: ## Run ruff linter
	$(UV) run -m ruff check $(SOURCE)

.PHONY: typecheck
typecheck: ## Run mypy type checker
	$(UV) run -m mypy --check-untyped-defs $(SOURCE)

.PHONY: test
test: ## Run pytest
	$(UV) run -m pytest 

.PHONY: check
check: lint typecheck test ## Run all quality checks

.PHONY: docs
docs: docs-generate ## Build the documentation website into site/ (strict: broken links fail)
	$(UV) run --group docs -m mkdocs build --strict --site-dir $(DOCS_OUT)

.PHONY: docs-serve
docs-serve: docs-generate ## Serve the documentation website with live reload
	$(UV) run --group docs -m mkdocs serve

.PHONY: docs-generate
docs-generate: ## Generate the documentation pages built from code (the model pages)
	$(UV) run --group docs scripts/build_model_docs.py

.PHONY: bump
bump: ## Cut a release (make bump BUMP=minor, or make bump VERSION=1.2.3)
	$(UV) run scripts/bump_version.py $(if $(VERSION),$(VERSION),$(BUMP))

.PHONY: clean
clean: ## Remove build artifacts
	rm -rf $(DIST_DIR) .mypy_cache .ruff_cache .pytest_cache __pycache__
