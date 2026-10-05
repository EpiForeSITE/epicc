"""Utilities for generating fill-in templates from Pydantic models."""

from __future__ import annotations

import types
import typing
from typing import Any, Literal, get_args, get_origin

from pydantic import BaseModel
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined

from epicc.formats.base import BaseFormat


def generate_template(model_cls: type[BaseModel], fmt: BaseFormat) -> bytes:
    """Generate a fill-in template for the given Pydantic model.

    Instantiates ``model_cls`` with defaults and type-appropriate placeholders
    for any required fields, then delegates serialisation to ``fmt``.

    Args:
        model_cls: The Pydantic ``BaseModel`` subclass to template.
        fmt: Any ``BaseFormat`` instance; determines the output format and
             how field metadata (descriptions, etc.) is rendered.

    Returns:
        Serialised bytes ready to write to a file.
    """
    return fmt.write_template(_instantiate(model_cls))


def _instantiate(model_cls: type[BaseModel]) -> BaseModel:
    """Recursively build a model instance using defaults and placeholders."""
    kwargs: dict[str, Any] = {}
    for name, field_info in model_cls.model_fields.items():
        kwargs[name] = _resolve(field_info)

    return model_cls.model_construct(**kwargs)


def _resolve(field_info: FieldInfo) -> Any:
    if field_info.default is not PydanticUndefined:
        return field_info.default

    if field_info.default_factory is not None:
        # `default_factory` may be called without arguments, but mypy doesn't know that.
        return field_info.default_factory()  # type: ignore

    return _placeholder(field_info.annotation)


def _placeholder(annotation: Any) -> Any:
    inner = _unwrap_optional(annotation)

    if _is_model(inner):
        return _instantiate(inner)

    origin = get_origin(inner)
    if origin is Literal:
        args = get_args(inner)
        return args[0] if args else None
    if origin is list:
        return []
    if origin is dict:
        return {}
    if inner is str:
        return ""
    if inner is int:
        return 0
    if inner is float:
        return 0.0
    if inner is bool:
        return False
    return None


def _unwrap_optional(annotation: Any) -> Any:
    origin = get_origin(annotation)
    if origin is types.UnionType or origin is typing.Union:
        non_none = [a for a in get_args(annotation) if a is not type(None)]
        if len(non_none) == 1:
            return non_none[0]
    return annotation


def _is_model(annotation: Any) -> bool:
    try:
        return isinstance(annotation, type) and issubclass(annotation, BaseModel)
    except TypeError:
        return False


__all__ = ["generate_template"]
