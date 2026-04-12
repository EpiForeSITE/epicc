from typing import Any

import streamlit as st


def _render_block(block: Any) -> None:
    if hasattr(block, "columns"):
        st.table(block)
        return

    if isinstance(block, str):
        st.markdown(block, unsafe_allow_html=True)
        return

    st.write(block)


def render_sections(sections: list[dict[str, Any]]) -> None:
    for i, section in enumerate(sections):
        title = section.get("title", "")
        content = section.get("content", [])

        st.markdown(f"## {title}")
        for block in content:
            _render_block(block)

        if i < len(sections) - 1:
            st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
