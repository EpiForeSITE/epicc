import base64
import gzip

import pytest

from epicc.ui.model_loader import _MAX_MODEL_BYTES, _decode_model_code


def test_decode_model_code_decodes_gzip_payload():
    model = b"name: Test model\n"
    code = base64.b64encode(gzip.compress(model)).decode()

    assert _decode_model_code(code) == model


def test_decode_model_code_rejects_oversized_gzip_payload():
    model = b"x" * (_MAX_MODEL_BYTES + 1)
    code = base64.b64encode(gzip.compress(model)).decode()

    with pytest.raises(ValueError, match="expands beyond 2 MiB"):
        _decode_model_code(code)
