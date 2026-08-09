"""Encode and decode model parameters to/from URL query parameters.

The simulator state is stored as a base64url-encoded JSON payload in a single
``params`` query parameter. The payload contains these keys:

- ``model``: the human-readable model label
- ``values``: the flat parameter dictionary
- ``scenarios``: the optional scenario definitions, labels, and values

This keeps the URL compact and avoids key collisions with Streamlit internals.
"""

from __future__ import annotations

import base64
import json
from typing import Any

import streamlit as st

from epicc.model.schema import Scenario

_QUERY_KEY = "params"


def encode_params(
    model_label: str,
    params: dict[str, Any],
    scenarios: list[Scenario] | None = None,
) -> str:
    """Return a base64url-encoded JSON string for embedding in the URL."""
    payload: dict[str, Any] = {"model": model_label, "values": params}
    if scenarios is not None:
        payload["scenarios"] = [
            scenario.model_dump(mode="json") for scenario in scenarios
        ]
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def decode_params(
    encoded: str,
) -> tuple[str, dict[str, Any], list[Scenario] | None] | None:
    """Decode a URL param string back into model, parameters, and scenarios.

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
        scenario_data = payload.get("scenarios")
        if scenario_data is None:
            scenarios = None
        elif isinstance(scenario_data, list):
            scenarios = [Scenario.model_validate(item) for item in scenario_data]
        else:
            return None
        return model, values, scenarios
    except Exception:  # noqa: BLE001
        return None


def read_url_params() -> tuple[str, dict[str, Any], list[Scenario] | None] | None:
    """Read and decode parameters from the current URL query string.

    Returns ``(model_label, param_dict, scenarios)`` or ``None`` if no valid
    payload is found. Parameter-only links created by older versions return
    ``None`` for scenarios.
    """
    qp = st.query_params
    encoded = qp.get(_QUERY_KEY)
    if not encoded:
        return None
    return decode_params(encoded)


def write_url_params(
    model_label: str,
    params: dict[str, Any],
    scenarios: list[Scenario] | None = None,
) -> None:
    """Update the browser URL with the current parameter state."""
    encoded = encode_params(model_label, params, scenarios)
    st.query_params[_QUERY_KEY] = encoded


def clear_url_params() -> None:
    """Remove parameter payload from the URL."""
    if _QUERY_KEY in st.query_params:
        del st.query_params[_QUERY_KEY]
