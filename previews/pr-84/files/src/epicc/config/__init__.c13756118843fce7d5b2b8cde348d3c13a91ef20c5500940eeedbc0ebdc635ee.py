"""
TODO: A lot of of this stuff is very restrictive, since the calculator was initially built to be
  deployed for handling one single model without being retargetable. In the future, we may want to
  make this more flexible, but for now, it's good enough.
"""

import importlib.resources
from typing import Any

from epicc.config.schema import Config
from epicc.formats import read_from_format


def load_config(name: str) -> tuple[Config, Any]:
    resource = importlib.resources.files("epicc").joinpath(f"config/{name}.yaml")
    filename = f"config/{name}.yaml"
    return read_from_format(filename, resource.open("rb"), Config)


CONFIG, _ = load_config("default")

__all__ = ["CONFIG"]
