import importlib.resources
import sys
from typing import IO

from epicc.formats import read_from_format
from epicc.model.base import BaseSimulationModel
from epicc.model.factory import create_model_instance
from epicc.model.schema import Model

MODEL_REGISTRY = [
    "tb_isolation",
    "measles",
    "measles_oregon",
]


def load_model_from_stream(filename: str, stream: IO[bytes]) -> BaseSimulationModel:
    model_def, _ = read_from_format(filename, stream, Model)
    return create_model_instance(model_def, source_path=filename)


def get_all_models() -> list[BaseSimulationModel]:
    models = []

    for model_name in MODEL_REGISTRY:
        filename = f"epicc.model.models/{model_name}.yaml"
        try:
            resource = importlib.resources.files("epicc.model.models").joinpath(
                f"{model_name}.yaml"
            )
            with resource.open("rb") as f:
                models.append(load_model_from_stream(filename, f))
        except Exception as e:
            print(f"warning: failed to load model '{model_name}': {e}", file=sys.stderr)

    return models


__all__ = ["get_all_models", "load_model_from_stream", "MODEL_REGISTRY"]
