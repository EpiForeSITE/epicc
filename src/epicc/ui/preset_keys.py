from __future__ import annotations

import streamlit as st

_PRESET_STACK_KEY_PREFIX = "_preset_stack_"
_FILE_PRESET_KEY_PREFIX = "_file_preset_"
_PRESET_INLINE_ADD_CTR_KEY_PREFIX = "_padd_inline_ctr_"
_PRESET_INLINE_ADD_SEL_KEY_PREFIX = "_padd_inline_"


def clear_preset_state(model_key: str) -> None:
    st.session_state.pop(_PRESET_STACK_KEY_PREFIX + model_key, None)
    st.session_state.pop(_FILE_PRESET_KEY_PREFIX + model_key, None)
    add_ctr: int = st.session_state.pop(
        _PRESET_INLINE_ADD_CTR_KEY_PREFIX + model_key, 0
    )
    for i in range(add_ctr + 1):
        st.session_state.pop(
            f"{_PRESET_INLINE_ADD_SEL_KEY_PREFIX}{model_key}_{i}", None
        )
