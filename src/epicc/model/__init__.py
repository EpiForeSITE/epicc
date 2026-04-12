import importlib.resources
from pathlib import Path
from typing import Any

from epicc.formats import read_from_format
from epicc.model.loader import get_built_in_models
from epicc.model.parameters import flatten_dict, load_model_params
from epicc.model.schema import Model


def load_model(name: str) -> tuple[Model, Any]:
    # Use a Traversable for opening the resource, and a real Path/str for suffix detection.
    config_resource = importlib.resources.files("epicc.model.models").joinpath(
        f"{name}.yaml"
    )
    config_name = Path(f"{name}.yaml")

    return read_from_format(config_name, config_resource.open("rb"), Model)


__all__ = [
    "flatten_dict",
    "get_built_in_models",
    "load_model",
    "load_model_params",
]
