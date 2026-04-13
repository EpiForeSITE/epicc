"""Session-state accessors for the epicc Streamlit app.

All session-state keys and read/write helpers live here so that the rest of
the UI code never hard-codes key strings.
"""

from __future__ import annotations

from typing import Any

import streamlit as st

# ---------------------------------------------------------------------------
# Key constants
# ---------------------------------------------------------------------------

_RESULTS_KEY = "results_payload"
_PRINT_REQUESTED_KEY = "print_requested"
_PRINT_TOKEN_KEY = "print_trigger_token"
_ACTIVE_MODEL_KEY = "active_model_key"
_ACTIVE_PARAM_IDENTITY_KEY = "active_param_identity"
_PARAMS_KEY = "params"
_UPLOAD_HASH_CACHE_KEY = "_upload_hash_cache"


# ---------------------------------------------------------------------------
# Initialisation / reset
# ---------------------------------------------------------------------------

def initialize_state() -> None:
    """Ensure all session-state keys are present.  Safe to call on every run."""
    st.session_state.setdefault(_RESULTS_KEY, None)
    st.session_state.setdefault(_PRINT_REQUESTED_KEY, False)
    st.session_state.setdefault(_PRINT_TOKEN_KEY, 0)


def clear_results() -> None:
    """Wipe run results and reset export flags."""
    st.session_state[_RESULTS_KEY] = None
    st.session_state[_PRINT_REQUESTED_KEY] = False
    st.session_state[_PRINT_TOKEN_KEY] = 0


def sync_active_model(model_key: str) -> dict[str, Any]:
    """Switch active model if needed, resetting params and results.

    Returns the current params dict (may be empty after a reset).
    """
    if st.session_state.get(_ACTIVE_MODEL_KEY) != model_key:
        st.session_state[_ACTIVE_MODEL_KEY] = model_key
        st.session_state[_PARAMS_KEY] = {}
        clear_results()

    st.session_state.setdefault(_PARAMS_KEY, {})
    return st.session_state[_PARAMS_KEY]


# ---------------------------------------------------------------------------
# Results accessors
# ---------------------------------------------------------------------------

def has_results() -> bool:
    return st.session_state.get(_RESULTS_KEY) is not None


def get_run_output() -> dict[str, Any]:
    """Return the raw run-output dict.  Caller must check has_results() first."""
    return st.session_state[_RESULTS_KEY]["run_output"]


def set_run_output(run_output: dict[str, Any]) -> None:
    st.session_state[_RESULTS_KEY] = {"run_output": run_output}


# ---------------------------------------------------------------------------
# Upload-identity helpers (used by parameter sidebar)
# ---------------------------------------------------------------------------

def get_upload_hash_cache() -> tuple | None:
    return st.session_state.get(_UPLOAD_HASH_CACHE_KEY)


def set_upload_hash_cache(cache: tuple) -> None:
    st.session_state[_UPLOAD_HASH_CACHE_KEY] = cache


def get_active_param_identity() -> tuple | None:
    return st.session_state.get(_ACTIVE_PARAM_IDENTITY_KEY)


def set_active_param_identity(identity: tuple) -> None:
    st.session_state[_ACTIVE_PARAM_IDENTITY_KEY] = identity


def reset_params() -> dict[str, Any]:
    """Clear the params dict and return the new empty one."""
    st.session_state[_PARAMS_KEY] = {}
    return st.session_state[_PARAMS_KEY]
