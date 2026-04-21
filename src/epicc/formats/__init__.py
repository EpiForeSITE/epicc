"""
Tools for working with parameter files in heterogeneous formats. This module provides a common
interface for reading parameter files into a standardized dictionary format that can be used
by the rest of the application, as well as writing.

Supported formats are denoted in _LOADERS.

The rationale behind this abstraction is that, in order to support both effective serialization,
non-technical epidemiologists, and more technical users, we want to allow for multiple file
formats. For example, YAML files are more human-friendly and support nested structures, while
XLSX files are more familiar to epis who already work in spreadsheets and may find it easier to
organize parameters in that format.
"""

from pathlib import Path
from typing import IO, Any, Iterator, TypeVar

from pydantic import BaseModel

from epicc.formats.base import BaseFormat
from epicc.formats.template import generate_template
from epicc.formats.xlsx import XLSXFormat
from epicc.formats.yaml import YAMLFormat

M = TypeVar("M", bound=BaseModel)
"""Type variable for Pydantic models used in validation."""

_FORMATS: dict[str, type[BaseFormat]] = {
    ".yaml": YAMLFormat,
    ".yml": YAMLFormat,
    ".xlsx": XLSXFormat,
}


def iter_formats() -> Iterator[tuple[str, type[BaseFormat]]]:
    """Yield ``(suffix, format_class)`` for every entry in the format registry.

    Suffixes are returned with their leading dot (e.g. ``".yaml"``, ``".xlsx"``).
    Aliases such as ".yml" are included - callers that need unique classes
    can deduplicate using a ``seen`` set.

    Use this function everywhere format-registry iteration is needed instead of
    accessing ``_FORMATS`` directly.
    """
    yield from _FORMATS.items()


VALID_PARAMETER_SUFFIXES = {s.lstrip(".") for s, _ in iter_formats()}
"""Set of valid file suffixes for parameter files. These do not begin with a dot."""


def get_format(path: Path | str) -> BaseFormat:
    """Return the appropriate reader for the given file path.

    Args:
        path: Path to the file to read. If a string, it will be converted to a Path object.

    Returns:
        A reader instance appropriate for the file format.

    Raises:
        ValueError: If the file format is not supported.
    """

    suffix = Path(path).suffix.lower()  # calling constructor to handle `str` case.
    reader_class = _FORMATS.get(suffix)
    if reader_class is None:
        supported = ", ".join(s for s, _ in iter_formats())
        raise ValueError(
            f"Unsupported file format '{suffix}'. Supported formats: {supported}"
        )

    return reader_class(path)


def opaque_to_typed(data: dict, model: type[M]) -> M:
    """
    Validate the given data against a given Pydantic model.

    Raises:
        pydantic.ValidationError: if *data* does not conform to *model*'s schema.
    """
    return model.model_validate(data)


def read_from_format(path: Path | str, data: IO, model: type[M]) -> tuple[M, Any]:
    """
    Read parameters from the given file path, and validate. See get_format() and
    opaque_to_typed() for details.

    The reason for needing both a path and a data stream is that, in some cases, we
    may want to read from a file-like object (e.g. an uploaded file in Streamlit) that
    doesn't have a path, but we still need to determine the file format based on the
    original file name (which is what the path argument is for).
    """

    reader = get_format(path)
    opaque, template = reader.read(data)

    return opaque_to_typed(opaque, model), template


__all__ = [
    "VALID_PARAMETER_SUFFIXES",
    "BaseFormat",
    "YAMLFormat",
    "XLSXFormat",
    "generate_template",
    "get_format",
    "iter_formats",
    "opaque_to_typed",
    "read_from_format",
]
