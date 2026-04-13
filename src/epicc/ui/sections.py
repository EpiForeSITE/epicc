"""Legacy section renderer.

New code should use epicc.ui.report.get_report_renderer() instead.
render_sections() is retained for backward compatibility with hand-written
models that still implement build_sections() returning the old dict format.
"""

from typing import Any

import streamlit as st


def render_sections(sections: list[dict[str, Any]]) -> None:
    for i, section in enumerate(sections):
        block_type = section.get("type")

        if block_type == "markdown":
            st.markdown(section["content"], unsafe_allow_html=True)

        elif block_type == "table":
            caption = section.get("caption")
            if caption:
                st.caption(caption)
            st.dataframe(section["content"], width='stretch')

        elif block_type == "figure":
            st.subheader(section.get("title", "Figure"))
            st.write(section.get("content", ""))

        else:
            st.warning(f"Unknown section block type: {block_type!r}", icon="⚠️")

        if i < len(sections) - 1:
            st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
