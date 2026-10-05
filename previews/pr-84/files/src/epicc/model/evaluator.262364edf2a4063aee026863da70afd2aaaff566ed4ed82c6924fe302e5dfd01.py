from __future__ import annotations

import math
from collections import deque
from difflib import get_close_matches
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
        # Only include references to other equations (no params).
        equation_deps = {
            eq_id: deps & self.equations.keys()
            for eq_id, deps in self.dependencies.items()
        }

        # According to Wikipedia, this is Kahn's algorithm for topological sorting. See:
        # https://en.wikipedia.org/wiki/Topological_sorting#Kahn's_algorithm

        in_degree = {eq_id: len(deps) for eq_id, deps in equation_deps.items()}
        queue = deque([eq_id for eq_id, degree in in_degree.items() if degree == 0])
        result = []

        while queue:
            eq_id = queue.popleft()
            result.append(eq_id)

            for other_eq_id, deps in equation_deps.items():
                if eq_id in deps:
                    in_degree[other_eq_id] -= 1
                    if in_degree[other_eq_id] == 0:
                        queue.append(other_eq_id)

        # Cycle?
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
        namespace = {**self._build_safe_namespace(), **context}
        results = {}

        # Evaluate equations in dependency order
        for eq_id in self.evaluation_order:
            code_obj = self.compiled[eq_id]

            # Evaluate with namespace as globals so generator expressions /
            # comprehensions can access model variables in their inner scope.
            try:
                value = eval(code_obj, {**namespace, "__builtins__": {}})
                results[eq_id] = value

                # Make result available for dependent equations
                namespace[eq_id] = value

            except NameError as e:
                missing_var = str(e).split("'")[1] if "'" in str(e) else "unknown"
                available = sorted(set(context.keys()) | set(results.keys()))
                suggestions = get_close_matches(missing_var, available, n=3, cutoff=0.6)
                suggestion_hint = (
                    f" Did you mean: {', '.join(repr(s) for s in suggestions)}?"
                    if suggestions
                    else ""
                )

                raise RuntimeError(
                    f"Error evaluating equation '{eq_id}': "
                    f"undefined variable '{missing_var}'.{suggestion_hint}"
                ) from e

            except Exception as e:
                raise RuntimeError(f"Error evaluating equation '{eq_id}': {e}") from e

        return results


__all__ = ["EquationEvaluator"]
