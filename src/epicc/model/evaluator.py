"""
Equation evaluation engine with dependency resolution.

This module provides the EquationEvaluator class that safely evaluates mathematical
expressions with proper dependency ordering.
"""

from __future__ import annotations

import math
from typing import Any

from epicc.model.ast_validator import compile_equation


class EquationEvaluator:
    """
    Evaluates a collection of equations with automatic dependency resolution.

    Equations can reference parameters and other equations. The evaluator determines
    the correct evaluation order and executes equations in that order, making each
    result available to dependent equations.
    """

    def __init__(self, equations: dict[str, str]):
        """
        Initialize the evaluator with a set of equations.

        Args:
            equations: Dictionary mapping equation ID to compute expression string

        Raises:
            SyntaxError: If any equation has invalid syntax
            ValueError: If any equation contains unsafe operations or circular dependencies
        """
        self.equations = equations
        self.compiled: dict[str, Any] = {}
        self.dependencies: dict[str, set[str]] = {}

        # Compile and validate all equations upfront
        for eq_id, expr in equations.items():
            code_obj, deps = compile_equation(expr)
            self.compiled[eq_id] = code_obj
            self.dependencies[eq_id] = deps

        # Determine evaluation order
        self.evaluation_order = self._topological_sort()

    def _topological_sort(self) -> list[str]:
        """
        Compute the evaluation order using topological sort.

        Equations that don't depend on other equations are evaluated first,
        followed by equations that depend on them, and so on.

        Returns:
            List of equation IDs in evaluation order

        Raises:
            ValueError: If circular dependencies are detected
        """
        # Filter dependencies to only include references to other equations
        # (not parameters, which are provided in context)
        equation_deps = {
            eq_id: deps & self.equations.keys()
            for eq_id, deps in self.dependencies.items()
        }

        # Kahn's algorithm for topological sort
        # Count dependencies for each equation (in-degree)
        in_degree = {eq_id: len(deps) for eq_id, deps in equation_deps.items()}

        # Start with nodes that have no dependencies
        queue = [eq_id for eq_id, degree in in_degree.items() if degree == 0]
        result = []

        while queue:
            # Process equation with no remaining dependencies
            eq_id = queue.pop(0)
            result.append(eq_id)

            # For each equation that depends on this one, reduce its in-degree
            for other_eq_id, deps in equation_deps.items():
                if eq_id in deps:
                    in_degree[other_eq_id] -= 1
                    if in_degree[other_eq_id] == 0:
                        queue.append(other_eq_id)

        # If we didn't process all equations, there's a cycle
        if len(result) != len(self.equations):
            # Find the cycle for a better error message
            unprocessed = set(self.equations.keys()) - set(result)
            cycle_info = ", ".join(
                f"{eq_id} -> {list(equation_deps[eq_id] & unprocessed)}"
                for eq_id in unprocessed
            )
            raise ValueError(
                f"Circular dependency detected in equations. "
                f"Cycle involves: {cycle_info}"
            )

        return result

    def _build_safe_namespace(self) -> dict[str, Any]:
        """
        Build the namespace of safe functions available to equations.

        Returns:
            Dictionary of function names to function objects
        """
        return {
            # Basic built-ins
            "abs": abs,
            "all": all,
            "any": any,
            "bool": bool,
            "dict": dict,
            "enumerate": enumerate,
            "float": float,
            "int": int,
            "len": len,
            "list": list,
            "max": max,
            "min": min,
            "range": range,
            "round": round,
            "set": set,
            "sorted": sorted,
            "str": str,
            "sum": sum,
            "tuple": tuple,
            "zip": zip,
            # Math functions
            "sqrt": math.sqrt,
            "exp": math.exp,
            "log": math.log,
            "log10": math.log10,
            "log2": math.log2,
            "ceil": math.ceil,
            "floor": math.floor,
            "pow": pow,
            "sin": math.sin,
            "cos": math.cos,
            "tan": math.tan,
            "asin": math.asin,
            "acos": math.acos,
            "atan": math.atan,
            "atan2": math.atan2,
            "pi": math.pi,
            "e": math.e,
        }

    def evaluate_all(self, context: dict[str, Any]) -> dict[str, Any]:
        """
        Evaluate all equations with the given context.

        Args:
            context: Dictionary of parameter values and scenario variables.
                     Equation results are added to this namespace as they are computed.

        Returns:
            Dictionary mapping equation ID to computed value

        Raises:
            RuntimeError: If any equation fails to evaluate
        """
        # Build namespace with safe functions and context
        namespace = {**self._build_safe_namespace(), **context}

        # Store results
        results = {}

        # Evaluate equations in dependency order
        for eq_id in self.evaluation_order:
            code_obj = self.compiled[eq_id]

            try:
                # Evaluate with empty __builtins__ for safety
                value = eval(code_obj, {"__builtins__": {}}, namespace)
                results[eq_id] = value

                # Make result available for dependent equations
                namespace[eq_id] = value

            except NameError as e:
                # More helpful error for missing parameters/equations
                missing_var = str(e).split("'")[1] if "'" in str(e) else "unknown"
                available = set(context.keys()) | set(results.keys())
                raise RuntimeError(
                    f"Error evaluating equation '{eq_id}': "
                    f"undefined variable '{missing_var}'. "
                    f"Available variables: {sorted(available)}"
                ) from e

            except Exception as e:
                # Generic error handling
                raise RuntimeError(f"Error evaluating equation '{eq_id}': {e}") from e

        return results


__all__ = ["EquationEvaluator"]
