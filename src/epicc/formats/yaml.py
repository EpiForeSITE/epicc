"""
Generic reader for YAML parameter files. Expects a YAML file with a mapping at the top level, which
is parsed into a dictionary.
"""

from io import StringIO
from typing import IO, Any

from pydantic import BaseModel
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap
from ruamel.yaml.error import CommentMark
from ruamel.yaml.tokens import CommentToken

from epicc.formats.base import BaseFormat
from epicc.formats.xlsx import _extract_nested_model as extract_nested_model


class YAMLFormat(BaseFormat[CommentedMap]):
    """Reader for YAML parameter files."""

    mime_type = "text/yaml"
    label = "YAML"

    def read(self, data: IO) -> tuple[dict[str, Any], CommentedMap]:
        """Read a YAML file and return its contents as a dictionary.

        Args:
            data: Input stream containing the YAML data.

        Returns:
            A tuple containing:
              - Dictionary representation of the YAML contents.
              - Parsed YAML mapping (CommentedMap), which can be used as a template for writing.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the file cannot be parsed as valid YAML,
                or if the top-level structure is not a mapping.
        """

        yaml = YAML(typ="rt")

        try:
            data = yaml.load(data)
        except Exception as e:
            raise ValueError(f"Failed to parse YAML data at {self.path}") from e

        if not isinstance(data, CommentedMap):
            raise ValueError(
                f"Expected a YAML mapping at the top level in {self.path}, got {type(data).__name__}"
            )

        return data, data

    def write(
        self,
        data: dict[str, Any],
        template: CommentedMap | None = None,
        *,
        pydantic_model: type[BaseModel] | None = None,
    ) -> bytes:
        """Write a dictionary to a YAML file.

        Args:
            data: Dictionary to write.
            template: Optional parsed YAML mapping to use as a write template. When provided,
                comments and formatting trivia from the template are preserved.
            pydantic_model: Optional Pydantic model whose field descriptions are emitted
                as inline ``#`` YAML comments.

        Returns:
            Byte array containing the YAML data, UTF-8 encoded.
        """

        yaml = YAML(typ="rt")
        if template is not None:
            _merge_mapping(template, data)
            payload: dict[str, Any] | CommentedMap = template
        else:
            payload = _dict_to_commented_map(data)

        if pydantic_model is not None:
            descriptions = _field_descriptions_nested(pydantic_model)
            if isinstance(payload, CommentedMap):
                _apply_comments(payload, descriptions)

        output = StringIO()
        yaml.dump(payload, output)
        return output.getvalue().encode("utf-8").strip()

    def write_template(self, model: BaseModel) -> bytes:
        """Write a YAML template from a model instance.

        The model is dumped to a nested mapping; the natural YAML structure
        is preserved without flattening. Comments with field descriptions
        are included when possible.
        """
        return self.write(model.model_dump(), pydantic_model=type(model))


def _merge_mapping(target: CommentedMap, updates: dict[str, Any]) -> None:
    """Recursively merge plain updates into a CommentedMap template."""
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(target.get(key), CommentedMap):
            _merge_mapping(target[key], value)
        else:
            target[key] = value


def _dict_to_commented_map(data: dict[str, Any]) -> CommentedMap:
    """Recursively convert a plain dict to a CommentedMap."""
    cm = CommentedMap()
    for key, value in data.items():
        cm[key] = _dict_to_commented_map(value) if isinstance(value, dict) else value
    return cm


def _field_descriptions_nested(model: type[BaseModel], prefix: str = "") -> dict[str, str]:
    """Return ``{dot_key: description}`` for all fields in *model*, recursing into sub-models."""
    result: dict[str, str] = {}
    for name, field_info in model.model_fields.items():
        key = f"{prefix}.{name}" if prefix else name
        
        # Use field_info.annotation for better type resolution
        annotation = field_info.annotation
        nested_model = extract_nested_model(annotation)
        
        if nested_model:
            result.update(_field_descriptions_nested(nested_model, prefix=key))
        else:
            result[key] = field_info.description or ""
    return result


def _apply_comments(
    mapping: CommentedMap,
    descriptions: dict[str, str],
    prefix: str = "",
) -> None:
    """Attach above-key YAML comments from *descriptions* to *mapping* (mutates in place)."""
    for key in mapping:
        dot_key = f"{prefix}.{key}" if prefix else key
        value = mapping[key]
        if isinstance(value, CommentedMap):
            _apply_comments(value, descriptions, prefix=dot_key)
        else:
            desc = descriptions.get(dot_key, "")
            if desc:
                raw = _format_comment_block(desc)
                token = CommentToken(raw, CommentMark(0), None)
                if key not in mapping.ca.items:
                    mapping.ca.items[key] = [None, None, None, None]
                mapping.ca.items[key][1] = [token]


def _format_comment_block(desc: str) -> str:
    """Format a description string into a raw YAML comment block.

    Each non-empty line gets ``# `` and blank separator lines get bare ``#``,
    producing e.g.::

        \\n# First sentence.\\n#\\n# Options: A, B\\n
    """
    lines = [f"# {line}" if line.strip() else "#" for line in desc.split("\n")]
    return "\n" + "\n".join(lines) + "\n"


__all__ = ["YAMLFormat"]
