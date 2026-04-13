from typing import Any

import streamlit as st


def render_sections(sections: list[dict[str, Any]]) -> None:
    for i, section in enumerate(sections):
        block_type = section.get("type", "legacy")

        if block_type == "markdown":
            st.markdown(section["content"], unsafe_allow_html=True)

        elif block_type == "table":
            caption = section.get("caption")
            if caption:
                st.caption(caption)
            st.table(section["content"])

        elif block_type == "figure":
            st.subheader(section.get("title", "Figure"))
            st.write(section.get("content", ""))

        else:
            # Legacy section format: {title, content: [...]}
            title = section.get("title", "")
            content = section.get("content", [])
            if title:
                st.markdown(f"## {title}")
            for block in content:
                if hasattr(block, "columns"):
                    st.table(block)
                elif isinstance(block, str):
                    st.markdown(block, unsafe_allow_html=True)
                else:
                    st.write(block)

        if i < len(sections) - 1:
            st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
