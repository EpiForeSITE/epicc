"""
Generic reader for YAML parameter files. Expects a YAML file with a mapping at the top level, which
is parsed into a dictionary.
"""

from io import StringIO
from typing import IO, Any

from pydantic import BaseModel
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap

from epicc.formats.base import BaseFormat


class YAMLFormat(BaseFormat[CommentedMap]):
    """Reader for YAML parameter files."""

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
        self, data: dict[str, Any], template: CommentedMap | None = None
    ) -> bytes:
        """Write a dictionary to a YAML file.

        Args:
            data: Dictionary to write.
            template: Optional parsed YAML mapping to use as a write template. When provided,
                comments and formatting trivia from the template are preserved.

        Returns:
            Byte array containing the YAML data, UTF-8 encoded.
        """

        yaml = YAML(typ="rt")
        if template is not None:
            _merge_mapping(template, data)
            payload: dict[str, Any] | CommentedMap = template
        else:
            payload = data
        output = StringIO()
        yaml.dump(payload, output)
        return output.getvalue().encode("utf-8")

    def write_template(self, model: BaseModel) -> bytes:
        """Write a YAML template from a model instance.

        The model is dumped to a nested mapping; the natural YAML structure
        is preserved without flattening. Descriptions are not embedded as
        comments (YAML comment support is left to a future enhancement).
        """
        return self.write(model.model_dump())


def _merge_mapping(target: CommentedMap, updates: dict[str, Any]) -> None:
    """Recursively merge plain updates into a CommentedMap template."""
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(target.get(key), CommentedMap):
            _merge_mapping(target[key], value)
        else:
            target[key] = value


__all__ = ["YAMLFormat"]
