from __future__ import annotations

from pathlib import Path
from typing import IO, Any

from pydantic import BaseModel

from epicc.formats import get_format
from epicc.model.base import BaseSimulationModel


def flatten_dict(data: dict[str, Any], level: int = 0) -> dict[str, Any]:
    """Flatten nested dictionaries for the sidebar renderer using tab-indented labels."""

    flat: dict[str, Any] = {}
    for key, value in data.items():
        indented_key = ("\t" * level) + str(key)
        if isinstance(value, dict):
            flat[indented_key] = None
            flat.update(flatten_dict(value, level + 1))
            continue

        flat[indented_key] = value

    return flat


def _load_typed_params(
    path: Path, data: IO[bytes], model: type[BaseModel]
) -> dict[str, Any]:
    reader = get_format(path)
    opaque, _ = reader.read(data)
    typed = model.model_validate(opaque)
    return typed.model_dump(by_alias=True)


def load_model_params(
    model: BaseSimulationModel,
    uploaded_params: IO[bytes] | None = None,
    uploaded_name: str | None = None,
) -> dict[str, Any]:
    """Load model parameters from upload or model defaults."""

    if uploaded_params is not None:
        if not uploaded_name:
            raise ValueError("Uploaded parameter files must include a filename.")
        uploaded_params.seek(0)
        return flatten_dict(
            _load_typed_params(
                Path(uploaded_name),
                uploaded_params,
                model.parameter_model(),
            )
        )

    return flatten_dict(model.default_params())
