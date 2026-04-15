from __future__ import annotations

import ast
import sys
from types import CodeType

_BASE_SAFE_NODES: set[type] = {
    ast.Module,
    ast.Expression,
    ast.Expr,
    ast.Load,
    ast.Store,
    ast.Name,
    ast.Constant,
    # Unary operators
    ast.UnaryOp,
    ast.UAdd,
    ast.USub,
    ast.Not,
    # Binary operators
    ast.BinOp,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.FloorDiv,
    ast.Mod,
    ast.Pow,
    # Comparisons
    ast.Compare,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    ast.Is,
    ast.IsNot,
    ast.In,
    ast.NotIn,
    # Boolean operations
    ast.BoolOp,
    ast.And,
    ast.Or,
    # Collections
    ast.List,
    ast.Tuple,
    ast.Dict,
    ast.Set,
    # Comprehensions
    ast.ListComp,
    ast.SetComp,
    ast.DictComp,
    ast.GeneratorExp,
    ast.comprehension,
    # Control flow (limited)
    ast.IfExp,  # Ternary: a if b else c
    # Subscripting and slicing
    ast.Subscript,
    ast.Slice,
    # Attribute access (for methods)
    ast.Attribute,
    # Function calls (with whitelist)
    ast.Call,
    ast.keyword,
}

# Legacy node types for Python < 3.8
if sys.version_info < (3, 8):
    _BASE_SAFE_NODES.update(
        {
            ast.Num,
            ast.Str,
            ast.NameConstant,
            ast.Index,
        }
    )

SAFE_NODES: set[type] = _BASE_SAFE_NODES


# TODO: whitelist?
BLOCKED_FUNCTIONS: set[str] = {
    "eval",
    "exec",
    "compile",
    "open",
    "globals",
    "locals",
    "__import__",
    "delattr",
    "setattr",
    "getattr",
    "vars",
    "dir",
    "breakpoint",
}


# Allowed method names on objects
SAFE_METHODS: set[str] = {
    "count",
    "index",
    "get",
    "keys",
    "values",
    "items",
}


def validate_equation_ast(expr: str) -> ast.Expression:
    # Parse the expression
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        raise SyntaxError(f"Invalid Python expression: {e}") from e

    # Walk the AST and validate each node
    for node in ast.walk(tree):
        node_type = type(node)

        if node_type not in SAFE_NODES:
            raise ValueError(
                f"Unsafe operation in equation: {node_type.__name__} is not allowed. "
                f"Expression: {expr}"
            )

        if isinstance(node, ast.Call):
            _validate_call_node(node, expr)

        if isinstance(node, ast.Attribute):
            _validate_attribute_node(node, expr)

    return tree


def _validate_call_node(node: ast.Call, expr: str) -> None:
    # Direct function call (e.g., sum(...))
    if isinstance(node.func, ast.Name):
        func_name = node.func.id

        if func_name in BLOCKED_FUNCTIONS:
            raise ValueError(
                f"Function '{func_name}' is not allowed in equations. "
                f"Expression: {expr}"
            )

        # Block anything starting with underscore (dunder methods, private functions)
        if func_name.startswith("_"):
            raise ValueError(
                f"Function '{func_name}' is not allowed in equations. "
                f"Expression: {expr}"
            )

    # Method calls 
    elif isinstance(node.func, ast.Attribute):
        method_name = node.func.attr
        if method_name.startswith("_"):
            raise ValueError(
                f"Method '{method_name}' is not allowed in equations. "
                f"Expression: {expr}"
            )


def _validate_attribute_node(node: ast.Attribute, expr: str) -> None:
    # For now, we allow all attribute access for reading
    # Method calls are validated separately in _validate_call_node
    # This allows things like: my_dict.get('key', default)
    
    pass


def compile_equation(expr: str) -> tuple[CodeType, set[str]]:
    "Compile an equation expression to a code object and extract variable dependencies."
    tree = validate_equation_ast(expr)

    dependencies = {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
    }

    code_obj = compile(tree, "<equation>", "eval")
    return code_obj, dependencies


__all__ = [
    "SAFE_NODES",
    "BLOCKED_FUNCTIONS",
    "SAFE_METHODS",
    "validate_equation_ast",
    "compile_equation",
]
