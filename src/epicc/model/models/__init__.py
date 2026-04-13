"""
epicc.model.models - Model registry and loading.

This package contains YAML/XLSX model definition files and provides
the registry and loading functionality.
"""

import importlib.resources
import sys

from epicc.formats import get_format, opaque_to_typed
from epicc.model.base import BaseSimulationModel
from epicc.model.factory import create_model_instance
from epicc.model.schema import Model

# Static registry of model names (without .yaml extension)
# To add a new model, add a YAML file to this package and register it here
MODEL_REGISTRY = [
    "tb_isolation",
    "measles",
]


def get_all_models() -> list[BaseSimulationModel]:
    """
    Return all available models loaded from this package.

    Models are loaded from epicc.model.models/ using importlib.resources.
    If a model fails to load, an error message is printed to stderr.

    Returns:
        List of all available BaseSimulationModel instances
    """
    models = []

    for model_name in MODEL_REGISTRY:
        try:
            # Get the resource file from the package
            model_resource = importlib.resources.files("epicc.model.models").joinpath(
                f"{model_name}.yaml"
            )

            # Read the YAML file
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
            # Print error but continue loading other models
            print(
                f"warning: failed to load model '{model_name}': {e}",
                file=sys.stderr,
            )
            continue

    return models


__all__ = ["get_all_models", "MODEL_REGISTRY"]
