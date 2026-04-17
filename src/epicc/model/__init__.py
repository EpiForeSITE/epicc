"""
epicc.model - Model loading and execution.

This package provides infrastructure for loading and executing epidemiological
cost models from YAML/XLSX files with interpreted Python equations.
"""

from epicc.model.ast_validator import (
    BLOCKED_FUNCTIONS,
    SAFE_METHODS,
    SAFE_NODES,
    compile_equation,
    validate_equation_ast,
)
from epicc.model.evaluator import EquationEvaluator
from epicc.model.factory import (
    create_model_class,
    create_model_instance,
)
from epicc.model.models import get_all_models
from epicc.model.parameters import flatten_dict, load_model_params
from epicc.model.schema import Model

__all__ = [
    # Model loading
    "get_all_models",
    # Model creation
    "create_model_class",
    "create_model_instance",
    # Schema
    "Model",
    # Parameters
    "load_model_params",
    "flatten_dict",
    # Evaluation (advanced use)
    "EquationEvaluator",
    # Validation (for testing/debugging)
    "validate_equation_ast",
    "compile_equation",
    "SAFE_NODES",
    "BLOCKED_FUNCTIONS",
    "SAFE_METHODS",
]
