"""EPICC -- the Epidemiological Cost Calculator.

`__version__` is the single source of truth for the application version at runtime.
It is deliberately not read from package metadata: in the stlite build the app runs
from mounted source files and is never installed, so `importlib.metadata` is
unavailable there. `pyproject.toml` is kept in step with this value by
`scripts/bump_version.py` and checked by `tests/epicc/test_version.py`.
"""

__version__ = "1.0.0"

__all__ = ["__version__"]
