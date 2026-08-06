"""Tests for epicc.ui.url_params encode/decode logic."""

from epicc.ui.url_params import decode_params, encode_params


def test_roundtrip_simple() -> None:
    model = "Test Model"
    values = {"rate": 0.5, "count": 100, "label": "hello"}
    encoded = encode_params(model, values)
    result = decode_params(encoded)
    assert result is not None
    assert result[0] == model
    assert result[1] == values


def test_roundtrip_empty_params() -> None:
    encoded = encode_params("M", {})
    result = decode_params(encoded)
    assert result == ("M", {})


def test_decode_invalid_returns_none() -> None:
    assert decode_params("not-valid-base64!!!") is None
    assert decode_params("") is None


def test_decode_wrong_shape_returns_none() -> None:
    import base64
    import json

    # Missing 'model' key
    raw = json.dumps({"values": {}})
    encoded = base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")
    assert decode_params(encoded) is None
