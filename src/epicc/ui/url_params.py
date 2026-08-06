"""Encode and decode model parameters to/from URL query parameters.

The parameters are stored as a base64url-encoded JSON payload in a single
``params`` query parameter.  The payload contains two keys:

- ``model``: the human-readable model label
- ``values``: the flat parameter dictionary

This keeps the URL compact and avoids key collisions with Streamlit internals.
"""

from __future__ import annotations

import base64
import json
from typing import Any

import streamlit as st

_QUERY_KEY = "params"


def encode_params(model_label: str, params: dict[str, Any]) -> str:
    """Return a base64url-encoded JSON string for embedding in the URL."""
    payload = {"model": model_label, "values": params}
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def decode_params(encoded: str) -> tuple[str, dict[str, Any]] | None:
    """Decode a URL param string back into (model_label, params).

    Returns ``None`` if decoding fails.
    """
    try:
        # Re-pad base64
        padded = encoded + "=" * (-len(encoded) % 4)
        raw = base64.urlsafe_b64decode(padded).decode()
        payload = json.loads(raw)
        model = payload["model"]
        values = payload["values"]
        if not isinstance(model, str) or not isinstance(values, dict):
            return None
        return model, values
    except Exception:  # noqa: BLE001
        return None


def read_url_params() -> tuple[str, dict[str, Any]] | None:
    """Read and decode parameters from the current URL query string.

    Returns ``(model_label, param_dict)`` or ``None`` if no valid payload found.
    """
    qp = st.query_params
    encoded = qp.get(_QUERY_KEY)
    if not encoded:
        return None
    return decode_params(encoded)


def write_url_params(model_label: str, params: dict[str, Any]) -> None:
    """Update the browser URL with the current parameter state."""
    encoded = encode_params(model_label, params)
    st.query_params[_QUERY_KEY] = encoded


def clear_url_params() -> None:
    """Remove parameter payload from the URL."""
    if _QUERY_KEY in st.query_params:
        del st.query_params[_QUERY_KEY]
