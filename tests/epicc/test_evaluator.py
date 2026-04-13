"""Tests for equation evaluator with dependency resolution."""

import pytest

from epicc.model.evaluator import EquationEvaluator


class TestBasicEvaluation:
    """Test basic equation evaluation."""

    def test_simple_equation(self):
        """Test evaluating a single equation."""
        equations = {"result": "2 + 3"}
        evaluator = EquationEvaluator(equations)
        results = evaluator.evaluate_all({})
        assert results["result"] == 5

    def test_equation_with_parameters(self):
        """Test equation using parameters from context."""
        equations = {"total": "price * quantity"}
        evaluator = EquationEvaluator(equations)
        results = evaluator.evaluate_all({"price": 10.5, "quantity": 3})
        assert results["total"] == 31.5


class TestDependencyResolution:
    """Test dependency resolution between equations."""

    def test_simple_dependency(self):
        """Test equation depending on another equation."""
        equations = {
            "base": "10",
            "derived": "base * 2",
        }
        evaluator = EquationEvaluator(equations)
        results = evaluator.evaluate_all({})
        assert results["base"] == 10
        assert results["derived"] == 20

    def test_chain_dependencies(self):
        """Test chain of dependencies: A -> B -> C."""
        equations = {
            "a": "5",
            "b": "a * 2",
            "c": "b + 10",
        }
        evaluator = EquationEvaluator(equations)
        results = evaluator.evaluate_all({})
        assert results["a"] == 5
        assert results["b"] == 10
        assert results["c"] == 20

    def test_complex_dependency_graph(self):
        """Test complex dependency graph."""
        equations = {
            "a": "5",
            "b": "10",
            "c": "a + b",
            "d": "c * 2",
            "e": "a + d",
        }
        evaluator = EquationEvaluator(equations)
        results = evaluator.evaluate_all({})
        assert results["c"] == 15
        assert results["d"] == 30
        assert results["e"] == 35


class TestCircularDependencies:
    """Test detection of circular dependencies."""

    def test_self_reference(self):
        """Test equation referencing itself."""
        equations = {"a": "a + 1"}
        with pytest.raises(ValueError, match="Circular dependency"):
            EquationEvaluator(equations)

    def test_simple_cycle(self):
        """Test simple two-equation cycle."""
        equations = {
            "a": "b + 1",
            "b": "a + 1",
        }
        with pytest.raises(ValueError, match="Circular dependency"):
            EquationEvaluator(equations)

    def test_longer_cycle(self):
        """Test cycle involving multiple equations."""
        equations = {
            "a": "c + 1",
            "b": "a + 1",
            "c": "b + 1",
        }
        with pytest.raises(ValueError, match="Circular dependency"):
            EquationEvaluator(equations)


class TestMathFunctions:
    """Test evaluation with math functions."""

    def test_basic_math_functions(self):
        """Test basic math functions."""
        equations = {
            "sqrt_result": "sqrt(16)",
            "abs_result": "abs(-5)",
            "max_result": "max(10, 20, 5)",
        }
        evaluator = EquationEvaluator(equations)
        results = evaluator.evaluate_all({})
        assert results["sqrt_result"] == 4.0
        assert results["abs_result"] == 5
        assert results["max_result"] == 20


class TestComprehensions:
    """Test equations with comprehensions."""

    def test_list_comprehension(self):
        """Test list comprehensions."""
        equations = {
            "squares": "sum([x**2 for x in range(5)])",
        }
        evaluator = EquationEvaluator(equations)
        results = evaluator.evaluate_all({})
        assert results["squares"] == 30  # 0 + 1 + 4 + 9 + 16

    def test_generator_expression(self):
        """Test generator expressions."""
        equations = {
            "gen_sum": "sum(x * 2 for x in range(5))",
        }
        evaluator = EquationEvaluator(equations)
        results = evaluator.evaluate_all({})
        assert results["gen_sum"] == 20


class TestConditionalExpressions:
    """Test conditional (ternary) expressions."""

    def test_simple_ternary(self):
        """Test ternary expression."""
        equations = {"result": "100 if x > 0 else 0"}
        evaluator = EquationEvaluator(equations)

        results_positive = evaluator.evaluate_all({"x": 5})
        assert results_positive["result"] == 100

        results_negative = evaluator.evaluate_all({"x": -5})
        assert results_negative["result"] == 0


class TestErrorHandling:
    """Test error handling during evaluation."""

    def test_missing_parameter(self):
        """Test error when parameter is missing."""
        equations = {"result": "a + b"}
        evaluator = EquationEvaluator(equations)
        with pytest.raises(RuntimeError, match="undefined variable"):
            evaluator.evaluate_all({"a": 10})

    def test_division_by_zero(self):
        """Test runtime error for division by zero."""
        equations = {"result": "10 / x"}
        evaluator = EquationEvaluator(equations)
        with pytest.raises(RuntimeError, match="Error evaluating equation"):
            evaluator.evaluate_all({"x": 0})

    def test_invalid_syntax(self):
        """Test that syntax errors are caught during initialization."""
        equations = {"bad": "1 + (2"}
        with pytest.raises(SyntaxError):
            EquationEvaluator(equations)

    def test_unsafe_operation(self):
        """Test that unsafe operations are caught."""
        equations = {"bad": "eval('x')"}
        with pytest.raises(ValueError):
            EquationEvaluator(equations)
