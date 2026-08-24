from typing import Any

from epicc.ui import export
from epicc.ui.state import _PRINT_REQUESTED_KEY, _PRINT_TOKEN_KEY


def _fake_button(monkeypatch) -> dict[str, Any]:
    captured: dict[str, Any] = {}

    def button(label: str, **kwargs: Any) -> bool:
        captured["label"] = label
        captured.update(kwargs)
        # The click is delivered through the callback, never the return value.
        return False

    monkeypatch.setattr(export.st, "button", button)
    return captured


def test_pdf_button_requests_print_from_a_callback(monkeypatch) -> None:
    # A request read from the button's return value only reaches the page on the
    # rerun *after* the click, which made the button need two clicks.
    monkeypatch.setattr(export, "has_results", lambda: True)
    captured = _fake_button(monkeypatch)

    export.render_pdf_export_button()

    assert captured["on_click"] is export._request_print
    assert captured["disabled"] is False


def test_request_print_marks_a_fresh_request(monkeypatch) -> None:
    state: dict[str, Any] = {_PRINT_REQUESTED_KEY: False, _PRINT_TOKEN_KEY: 3}
    monkeypatch.setattr(export.st, "session_state", state)
    monkeypatch.setattr(export, "has_results", lambda: True)

    export._request_print()

    assert state[_PRINT_REQUESTED_KEY] is True
    # A new token so repeat clicks are not mistaken for the previous request.
    assert state[_PRINT_TOKEN_KEY] == 4


def test_request_print_ignored_without_results(monkeypatch) -> None:
    state: dict[str, Any] = {_PRINT_REQUESTED_KEY: False, _PRINT_TOKEN_KEY: 0}
    monkeypatch.setattr(export.st, "session_state", state)
    monkeypatch.setattr(export, "has_results", lambda: False)

    export._request_print()

    assert state[_PRINT_REQUESTED_KEY] is False
    assert state[_PRINT_TOKEN_KEY] == 0


def test_cancel_print_request_clears_a_pending_request(monkeypatch) -> None:
    state: dict[str, Any] = {_PRINT_REQUESTED_KEY: True, _PRINT_TOKEN_KEY: 1}
    monkeypatch.setattr(export.st, "session_state", state)

    export.cancel_print_request()

    assert state[_PRINT_REQUESTED_KEY] is False
