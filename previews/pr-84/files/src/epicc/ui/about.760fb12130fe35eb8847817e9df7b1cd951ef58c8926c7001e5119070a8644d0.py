"""Surface the app version and point users at the published release notes.

Release notes live in GitHub Releases rather than in the repository, so there is
nothing to keep in sync here: the button targets `/releases/latest`, which GitHub
always redirects to the newest published release.
"""

from __future__ import annotations

from typing import Any

import streamlit as st

from epicc import __version__


def render_whats_new_button(
    releases_url: str | None, *, container: Any = st
) -> None:
    """Render the header link to the latest published release, if one is configured."""
    if not releases_url:
        return

    container.link_button(
        "What's new",
        releases_url,
        type="tertiary",
        width="stretch",
        help=f"You are running EPICC v{__version__}. See the latest release notes.",
    )
