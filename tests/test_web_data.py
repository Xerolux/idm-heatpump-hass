"""Tests for optional IDM local web supplement handling."""

from types import SimpleNamespace

import pytest

import idm_heatpump

from custom_components.idm_heatpump.const import MODEL
from custom_components.idm_heatpump.web_data import (
    IdmWebAuthenticationFailed,
    IdmWebSensorValue,
    IdmWebSupplement,
    async_read_web_supplement,
    merge_model_info,
    web_pin_configured,
)


class _FakeWebClient:
    def __init__(
        self,
        data=None,
        error: Exception | None = None,
        notifications=None,
        notification_error: Exception | None = None,
    ) -> None:
        self.data = data
        self.error = error
        self.notifications = notifications
        self.notification_error = notification_error
        self.closed = False

    async def read_data(self):
        if self.error is not None:
            raise self.error
        return self.data

    async def read_notifications(self):
        if self.notification_error is not None:
            raise self.notification_error
        return self.notifications

    async def close(self) -> None:
        self.closed = True


class IdmWebAuthenticationError(Exception):
    """Fake API authentication error."""


def test_web_pin_configured_without_api_symbol() -> None:
    assert web_pin_configured(" 1234 ")
    assert not web_pin_configured("")
    assert not web_pin_configured(None)


async def test_async_read_web_supplement_returns_none_without_pin() -> None:
    assert await async_read_web_supplement("192.0.2.10", None) is None


async def test_async_read_web_supplement_reads_navigator10(monkeypatch: pytest.MonkeyPatch) -> None:
    web_data = SimpleNamespace(
        navigator_version="Navigator 10",
        software_version="NAV10_20.23-903.iup",
        heatpump_model="iPump",
        simple_values={"software_version": "NAV10_20.23-903.iup"},
    )
    nav10 = _FakeWebClient(web_data)
    nav20 = _FakeWebClient(web_data)

    monkeypatch.setattr(idm_heatpump, "web_pin_configured", lambda pin: bool(pin.strip()), raising=False)
    monkeypatch.setattr(
        idm_heatpump,
        "create_optional_navigator10_web_client",
        lambda host, pin: nav10,
        raising=False,
    )
    monkeypatch.setattr(
        idm_heatpump,
        "create_optional_navigator20_web_client",
        lambda host, pin: nav20,
        raising=False,
    )

    result = await async_read_web_supplement("192.0.2.10", "1234")

    assert result == IdmWebSupplement(
        navigator_version="Navigator 10",
        software_version="NAV10_20.23-903.iup",
        heatpump_model="iPump",
        values={
            "software_version": "NAV10_20.23-903.iup",
            "navigator_version": "Navigator 10",
            "heatpump_model": "iPump",
        },
        sensor_values={
            "software_version": IdmWebSensorValue("NAV10_20.23-903.iup", "NAV10_20.23-903.iup"),
            "navigator_version": IdmWebSensorValue("Navigator 10", "Navigator 10"),
            "heatpump_model": IdmWebSensorValue("iPump", "iPump"),
        },
    )
    assert nav10.closed
    assert not nav20.closed


async def test_async_read_web_supplement_adds_navigator10_notifications(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    web_data = SimpleNamespace(
        navigator_version="Navigator 10",
        software_version="NAV10_20.23-903.iup",
        heatpump_model="iPump",
        simple_values={},
    )
    notifications = SimpleNamespace(count=2, summary="E123: Fehler | W456: Filter pruefen")
    nav10 = _FakeWebClient(web_data, notifications=notifications)

    monkeypatch.setattr(idm_heatpump, "web_pin_configured", lambda pin: bool(pin.strip()), raising=False)
    monkeypatch.setattr(
        idm_heatpump,
        "create_optional_navigator10_web_client",
        lambda host, pin: nav10,
        raising=False,
    )
    monkeypatch.setattr(
        idm_heatpump,
        "create_optional_navigator20_web_client",
        lambda host, pin: None,
        raising=False,
    )

    result = await async_read_web_supplement("192.0.2.10", "1234")

    assert result is not None
    assert result.values["infosystem_notification_count"] == "2"
    assert result.values["infosystem_notifications"] == "E123: Fehler | W456: Filter pruefen"
    assert result.sensor_values["infosystem_notification_count"].native_value == 2.0
    assert result.sensor_values["infosystem_notifications"].native_value == "E123: Fehler | W456: Filter pruefen"


async def test_async_read_web_supplement_ignores_notification_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    web_data = SimpleNamespace(
        navigator_version="Navigator 10",
        software_version="NAV10_20.23-903.iup",
        heatpump_model="iPump",
        simple_values={},
    )
    nav10 = _FakeWebClient(web_data, notification_error=RuntimeError("notifications unavailable"))

    monkeypatch.setattr(idm_heatpump, "web_pin_configured", lambda pin: bool(pin.strip()), raising=False)
    monkeypatch.setattr(
        idm_heatpump,
        "create_optional_navigator10_web_client",
        lambda host, pin: nav10,
        raising=False,
    )
    monkeypatch.setattr(
        idm_heatpump,
        "create_optional_navigator20_web_client",
        lambda host, pin: None,
        raising=False,
    )

    result = await async_read_web_supplement("192.0.2.10", "1234")

    assert result is not None
    assert result.navigator_version == "Navigator 10"
    assert "infosystem_notification_count" not in result.sensor_values


async def test_async_read_web_supplement_falls_back_to_navigator20(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    nav10 = _FakeWebClient(error=RuntimeError("websocket refused"))
    nav20 = _FakeWebClient(
        SimpleNamespace(
            navigator_version="Navigator 2.0",
            software_version="2.35",
            heatpump_model=None,
            simple_values={},
        )
    )

    monkeypatch.setattr(idm_heatpump, "web_pin_configured", lambda pin: bool(pin.strip()), raising=False)
    monkeypatch.setattr(
        idm_heatpump,
        "create_optional_navigator10_web_client",
        lambda host, pin: nav10,
        raising=False,
    )
    monkeypatch.setattr(
        idm_heatpump,
        "create_optional_navigator20_web_client",
        lambda host, pin: nav20,
        raising=False,
    )

    result = await async_read_web_supplement("192.0.2.10", "1234")

    assert result is not None
    assert result.navigator_version == "Navigator 2.0"
    assert result.software_version == "2.35"
    assert result.sensor_values["navigator_version"].native_value == "Navigator 2.0"
    assert result.sensor_values["software_version"].native_value == "2.35"
    assert nav10.closed
    assert nav20.closed


async def test_async_read_web_supplement_raises_authentication_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    nav10 = _FakeWebClient(error=IdmWebAuthenticationError("bad pin"))

    monkeypatch.setattr(idm_heatpump, "IdmWebAuthenticationError", IdmWebAuthenticationError, raising=False)
    monkeypatch.setattr(idm_heatpump, "web_pin_configured", lambda pin: bool(pin.strip()), raising=False)
    monkeypatch.setattr(
        idm_heatpump,
        "create_optional_navigator10_web_client",
        lambda host, pin: nav10,
        raising=False,
    )
    monkeypatch.setattr(
        idm_heatpump,
        "create_optional_navigator20_web_client",
        lambda host, pin: None,
        raising=False,
    )

    with pytest.raises(IdmWebAuthenticationFailed):
        await async_read_web_supplement("192.0.2.10", "0000")

    assert nav10.closed


def test_merge_model_info_prefers_web_supplement() -> None:
    model_name, firmware_version = merge_model_info(
        MODEL,
        None,
        IdmWebSupplement(navigator_version="Navigator 10", software_version="NAV10_20.23"),
    )

    assert model_name == "Navigator 10"
    assert firmware_version == "NAV10_20.23"
