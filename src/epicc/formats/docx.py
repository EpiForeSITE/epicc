"""Legacy DOCX compatibility shim.

This module remains only for backwards compatibility. New report exports live
in ``epicc.ui.report_exports`` and are intentionally decoupled from the
structured parameter format system.
"""

from __future__ import annotations

from typing import Any

from epicc.formats.base import BaseFormat
from epicc.ui.report_exports import build_report_docx_bytes
from pydantic import BaseModel


class DOCXFormat(BaseFormat):
    """Deprecated wrapper around report export functionality."""

    label = "Word (DOCX)"
    mime_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    def read(self, data) -> tuple[dict[str, Any], Any]:
        raise NotImplementedError("DOCX parameter import is not supported.")

    def write(self, data: dict[str, Any], template: Any | None = None) -> bytes:
        if "__report__" not in data:
            raise ValueError("DOCX export only supports report payloads.")
        return build_report_docx_bytes(data)

    def write_template(self, model: BaseModel) -> bytes:
        raise NotImplementedError("DOCX parameter templates are not supported.")