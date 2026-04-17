from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

ParamsT = TypeVar("ParamsT", bound=BaseModel)


class BaseSimulationModel(ABC, Generic[ParamsT]):
    """Abstract contract for Python-defined simulation models."""

    @abstractmethod
    def human_name(self) -> str:
        """Human-readable name shown in model selection UI."""

    @property
    @abstractmethod
    def model_title(self) -> str:
        """Page title displayed above simulation output."""

    @property
    @abstractmethod
    def model_description(self) -> str:
        """Short text describing the simulation."""

    @property
    @abstractmethod
    def scenario_labels(self) -> dict[str, str]:
        """Default scenario labels exposed for sidebar overrides."""

    @abstractmethod
    def run(
        self,
        params: ParamsT,
        label_overrides: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Run the model and return result payload for rendering."""

    @abstractmethod
    def default_params(self) -> dict[str, Any]:
        """Return the model's default parameters as a raw (unflattened) dict."""

    @abstractmethod
    def parameter_model(self) -> type[ParamsT]:
        """Return a Pydantic model used to validate uploaded parameter files."""

    @property
    def parameter_specs(self) -> dict[str, Any] | None:
        """Optional mapping of param_id to Parameter schema objects for rich UI rendering."""
        return None

    @property
    def parameter_groups(self) -> list | None:
        """Optional parameter group tree for visual organization in the UI."""
        return None

    def get_model_definition(self) -> Any:
        """Return model definition for report generation (optional, for YAML-compiled models)."""
        raise NotImplementedError(
            "get_model_definition() is only available for YAML-compiled models"
        )

    def get_source_path(self) -> str | None:
        """Return source file path for debugging/introspection (optional)."""
        return None
