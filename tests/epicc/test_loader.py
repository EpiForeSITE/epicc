"""Tests for epicc.model.loader (importlib.resources-based loading)."""

import pytest

from epicc.model.base import BaseSimulationModel
from epicc.model.models import MODEL_REGISTRY, get_all_models


class TestGetAllModels:
    """Test model loading from package resources."""

    def test_returns_list(self):
        """Test that get_all_models returns a list."""
        models = get_all_models()
        assert isinstance(models, list)

    def test_returns_base_simulation_models(self):
        """Test that all returned models are BaseSimulationModel instances."""
        models = get_all_models()
        for model in models:
            assert isinstance(model, BaseSimulationModel)

    def test_models_have_human_name(self):
        """Test that models have human_name method."""
        models = get_all_models()
        assert len(models) > 0, "Should load at least one model"

        for model in models:
            name = model.human_name()
            assert isinstance(name, str)
            assert len(name) > 0

    def test_models_have_title_and_description(self):
        """Test that models have title and description properties."""
        models = get_all_models()
        assert len(models) > 0

        for model in models:
            assert isinstance(model.model_title, str)
            assert isinstance(model.model_description, str)

    def test_models_have_scenario_labels(self):
        """Test that models have scenario_labels property."""
        models = get_all_models()
        assert len(models) > 0

        for model in models:
            labels = model.scenario_labels
            assert isinstance(labels, dict)

    def test_models_have_default_params(self):
        """Test that models provide default parameters."""
        models = get_all_models()
        assert len(models) > 0

        for model in models:
            defaults = model.default_params()
            assert isinstance(defaults, dict)

    def test_loads_registered_models(self):
        """Test that models from registry are loaded."""
        models = get_all_models()
        model_names = [m.human_name() for m in models]

        # Should load models from the registry
        assert len(models) == len(MODEL_REGISTRY)

        # Models should have distinct names
        assert len(set(model_names)) == len(model_names)


class TestModelRegistry:
    """Test the MODEL_REGISTRY configuration."""

    def test_registry_is_list(self):
        """Test that MODEL_REGISTRY is a list."""
        assert isinstance(MODEL_REGISTRY, list)

    def test_registry_has_entries(self):
        """Test that MODEL_REGISTRY has at least one entry."""
        assert len(MODEL_REGISTRY) > 0

    def test_registry_entries_are_strings(self):
        """Test that all registry entries are strings."""
        for entry in MODEL_REGISTRY:
            assert isinstance(entry, str)
            assert len(entry) > 0
