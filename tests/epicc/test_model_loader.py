import base64
import builtins
import lzma

import pytest

from epicc.ui.model_loader import _decode_model_code


def test_decode_model_code_decodes_lzma_payload():
    model = b"name: Test model\n"
    code = base64.b64encode(lzma.compress(model)).decode()

    assert _decode_model_code(code) == model


def test_decode_model_code_reports_missing_lzma(monkeypatch):
    original_import = builtins.__import__

    def import_without_lzma(name, *args, **kwargs):
        if name == "lzma":
            raise ModuleNotFoundError("No module named 'lzma'")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_without_lzma)

    with pytest.raises(ValueError, match="lacks LZMA support"):
        _decode_model_code("YW55IGNvZGU=")
