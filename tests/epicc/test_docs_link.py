"""The app links to the documentation website from every page.

The link comes from `app.docs_url`, with `{version}` filled in, so each release links
to the documentation of its own version (`docs/<version>/`), which
`scripts/deploy_docs.sh` publishes.
"""

from __future__ import annotations

from streamlit.testing.v1 import AppTest

from epicc import __version__
from epicc.config import CONFIG

DOCS_URL = f"https://epiforesite.github.io/epicc/docs/{__version__}/"


def _markdown(app: AppTest) -> str:
    return "\n".join(block.value for block in app.markdown)


def test_the_configured_link_is_versioned() -> None:
    assert CONFIG.app.docs_url == "https://epiforesite.github.io/epicc/docs/{version}/"


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
