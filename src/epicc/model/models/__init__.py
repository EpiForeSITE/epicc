import importlib.resources
import sys

from epicc.formats import get_format, opaque_to_typed
from epicc.model.base import BaseSimulationModel
from epicc.model.factory import create_model_instance
from epicc.model.schema import Model

MODEL_REGISTRY = [
    "tb_isolation",
    "measles",
]


def get_all_models() -> list[BaseSimulationModel]:
    models = []

    for model_name in MODEL_REGISTRY:
        try:
            # Get the resource file from the package
            model_resource = importlib.resources.files("epicc.model.models").joinpath(
                f"{model_name}.yaml"
            )

            with model_resource.open("rb") as f:
                yaml_format = get_format(f"{model_name}.yaml")
                data, _ = yaml_format.read(f)

            # Validate against Model schema
            model_def = opaque_to_typed(data, Model)

            # Create model instance from definition
            model = create_model_instance(
                model_def, source_path=f"epicc.model.models/{model_name}.yaml"
            )
            models.append(model)

        except Exception as e:
            print(
                f"warning: failed to load model '{model_name}': {e}",
                file=sys.stderr,
            )

            continue

    return models


__all__ = ["get_all_models", "MODEL_REGISTRY"]
