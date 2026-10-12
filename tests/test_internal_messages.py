"""Tests for internal message labels and vendor error-code lookups."""

from __future__ import annotations

from types import SimpleNamespace

from custom_components.idm_heatpump import internal_messages as module


def test_message_code_rejects_unusable_values() -> None:
    assert module._message_code(None) is None
    assert module._message_code("not-a-number") is None
    assert module._message_code(42.0) == 42


def test_internal_message_text_paths() -> None:
    assert module.internal_message_text(None) is None
    assert module.internal_message_text("bad") is None
    # Exact-table entries resolve; unknown codes fall through to None or ranges.
    assert module.internal_message_text(20) is not None
    assert isinstance(module.internal_message_text(310), str)


def test_error_number_text_requires_vendor_display_text(monkeypatch) -> None:
    assert module.error_number_text(None) is None
    monkeypatch.setattr(module, "get_error_code_info", lambda code: None)
    assert module.error_number_text(530) is None
    info = SimpleNamespace(display_text="", is_warning=False, user_description=None, service_description=None)
    monkeypatch.setattr(module, "get_error_code_info", lambda code: info)
    assert module.error_number_text(530) is None
    info.display_text = "Inverter Verriegelung"
    assert module.error_number_text(530) == "Inverter Verriegelung"


def test_error_code_attributes_paths(monkeypatch) -> None:
    assert module.error_code_attributes(None) is None
    monkeypatch.setattr(module, "get_error_code_info", lambda code: None)
    assert module.error_code_attributes(20) is None
    info = SimpleNamespace(display_text="x", is_warning=True, user_description="user text", service_description=None)
    monkeypatch.setattr(module, "get_error_code_info", lambda code: info)
    assert module.error_code_attributes(20) == {"warning": True, "user_description": "user text"}


def test_format_internal_message_paths() -> None:
    assert module.format_internal_message(None) is None
    assert module.format_internal_message("bad") is None
    assert module.format_internal_message(20) == "020 - " + module.internal_message_text(20)


def test_warm_error_code_database_completes_the_first_lookup() -> None:
    module.warm_error_code_database()
