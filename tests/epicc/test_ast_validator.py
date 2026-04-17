import pytest

from epicc.model.ast_validator import (
    compile_equation,
    validate_equation_ast,
)


class TestSafeExpressions:
    """Test that safe expressions are accepted."""

    def test_arithmetic_and_variables(self):
        """Test basic arithmetic with variables."""
        validate_equation_ast("a + b * 2")
        validate_equation_ast("x / (y - 1)")
        validate_equation_ast("2 ** 8")

    def test_comparisons_and_conditionals(self):
        """Test comparisons and ternary expressions."""
        validate_equation_ast("x > 5 and y < 10")
        validate_equation_ast("result if condition else 0")

    def test_safe_functions(self):
        """Test safe built-in functions."""
        validate_equation_ast("sum([1, 2, 3])")
        validate_equation_ast("max(a, b)")
        validate_equation_ast("abs(-5)")

    def test_comprehensions(self):
        """Test list comprehensions and generators."""
        validate_equation_ast("[x * 2 for x in range(10)]")
        validate_equation_ast("sum(x for x in values if x > 0)")


class TestUnsafeExpressions:
    """Test that unsafe expressions are rejected."""

    def test_dangerous_functions_blocked(self):
        """Test that dangerous functions are blocked."""
        with pytest.raises(ValueError, match="not allowed"):
            validate_equation_ast("eval('1 + 1')")

        with pytest.raises(ValueError, match="not allowed"):
            validate_equation_ast("open('/etc/passwd')")

        with pytest.raises(ValueError, match="not allowed"):
            validate_equation_ast("__import__('os')")

    def test_statements_blocked(self):
        """Test that statements are blocked."""
        with pytest.raises(SyntaxError):
            validate_equation_ast("import os")

        with pytest.raises(SyntaxError):
            validate_equation_ast("x = 5")


class TestCompileEquation:
    """Test equation compilation."""

    def test_compile_and_extract_dependencies(self):
        """Test compiling equation and extracting dependencies."""
        code, deps = compile_equation("a + b * 2")
        assert isinstance(code, type(compile("1", "<string>", "eval")))
        assert deps == {"a", "b"}

    def test_function_names_in_dependencies(self):
        """Test that function names are included in dependencies."""
        code, deps = compile_equation("sum(range(limit))")
        # Function names are included, evaluator provides them in namespace
        assert "sum" in deps
        assert "range" in deps
        assert "limit" in deps

    def test_compiled_equation_executable(self):
        """Test that compiled equation can be executed."""
        code, deps = compile_equation("x * 2 + y")
        result = eval(code, {"__builtins__": {}}, {"x": 10, "y": 5})
        assert result == 25
