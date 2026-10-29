"""The app links to the documentation website from every page.

The link comes from `app.docs_url` and is not versioned, so every release of the app,
old or new, points at the current documentation.
"""

from __future__ import annotations

from streamlit.testing.v1 import AppTest

from epicc.config import CONFIG

DOCS_URL = "https://epiforesite.github.io/epicc/docs/"


def _markdown(app: AppTest) -> str:
    return "\n".join(block.value for block in app.markdown)


def test_the_configured_link_is_the_unversioned_site() -> None:
    assert CONFIG.app.docs_url == DOCS_URL


def test_the_header_and_welcome_page_link_to_the_documentation() -> None:
    app = AppTest.from_file("app.py")
    app.run(timeout=60)

    assert not app.exception
    page = _markdown(app)
    assert f'class="brand-header__docs" href="{DOCS_URL}"' in page, "no header link"
    assert f"[EPICC documentation]({DOCS_URL})" in page, "no welcome-page link"


def test_the_header_link_stays_once_a_model_is_open() -> None:
    app = AppTest.from_file("app.py")
    app.query_params["model"] = "measles"
    app.run(timeout=60)

    assert not app.exception
    assert f'class="brand-header__docs" href="{DOCS_URL}"' in _markdown(app)
