"""Tests for optional IDM local web supplement handling."""

from types import SimpleNamespace

import pytest

import idm_heatpump

from custom_components.idm_heatpump.const import MODEL
from custom_components.idm_heatpump.web_data import (
    IdmWebAuthenticationFailed,
    IdmWebClientPool,
    IdmWebSensorValue,
    IdmWebSupplement,
    _is_wrong_variant_error,
    _preferred_web_variant,
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


def test_wrong_variant_detection_handles_os_error_subclasses() -> None:
    """Transport subclasses should trigger fallback to the other web variant."""
    assert _is_wrong_variant_error(ConnectionRefusedError("connection refused"))
    assert _is_wrong_variant_error(ConnectionResetError("connection reset"))


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


async def test_async_read_web_supplement_extracts_myidm_id_local_part(monkeypatch: pytest.MonkeyPatch) -> None:
    web_data = SimpleNamespace(
        navigator_version="Navigator 10",
        software_version="NAV10_20.23-903.iup",
        heatpump_model="iPump",
        simple_values={"myidm_id": "m129236@example.invalid"},
    )
    nav10 = _FakeWebClient(web_data)

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
    assert result.myidm_id == "m129236"
    assert result.values["myidm_id"] == "m129236"
    assert result.sensor_values["myidm_id"].native_value == "m129236"


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


async def test_async_read_web_supplement_falls_back_to_navigator20_after_nav10_auth_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    nav10 = _FakeWebClient(error=IdmWebAuthenticationError("not navigator 10"))
    nav20 = _FakeWebClient(
        SimpleNamespace(
            navigator_version="Navigator 2.0",
            software_version="2.35",
            heatpump_model="TERRA SWM 6-17 HGL",
            simple_values={},
        )
    )

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
        lambda host, pin: nav20,
        raising=False,
    )

    result = await async_read_web_supplement("192.0.2.10", "1234")

    assert result is not None
    assert result.navigator_version == "Navigator 2.0"
    assert result.software_version == "2.35"
    assert result.heatpump_model == "TERRA SWM 6-17 HGL"
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


async def test_async_read_web_supplement_prefers_nav20_auth_error_over_nav10_connection_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    nav10 = _FakeWebClient(error=RuntimeError("Cannot connect to host 192.0.2.10:61220"))
    nav20 = _FakeWebClient(error=IdmWebAuthenticationError("bad pin"))

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
        lambda host, pin: nav20,
        raising=False,
    )

    with pytest.raises(IdmWebAuthenticationFailed):
        await async_read_web_supplement("192.0.2.10", "0000")

    assert nav10.closed
    assert nav20.closed


async def test_async_read_web_supplement_switches_on_wrong_variant_response_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A response-format error on the first variant must trigger the other variant."""

    class IdmWebResponseError(Exception):
        """Fake API response error (wrong variant signal)."""

    nav10 = _FakeWebClient(error=IdmWebResponseError("Navigator 10 authorization response was not recognized"))
    nav20 = _FakeWebClient(
        SimpleNamespace(
            navigator_version="Navigator 2.0",
            software_version="2.35",
            heatpump_model="TERRA SWM 6-17 HGL",
            simple_values={},
        )
    )

    monkeypatch.setattr(idm_heatpump, "IdmWebResponseError", IdmWebResponseError, raising=False)
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
    assert nav10.closed
    assert nav20.closed


async def test_async_read_web_supplement_tries_both_variants_before_invalid_pin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An auth error on the first variant does not stop us from trying the other one."""
    nav10 = _FakeWebClient(error=IdmWebAuthenticationError("not navigator 10"))
    nav20 = _FakeWebClient(error=IdmWebAuthenticationError("bad pin"))

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
        lambda host, pin: nav20,
        raising=False,
    )

    with pytest.raises(IdmWebAuthenticationFailed):
        await async_read_web_supplement("192.0.2.10", "0000")

    assert nav10.closed
    assert nav20.closed


def test_merge_model_info_prefers_web_supplement() -> None:
    model_name, firmware_version = merge_model_info(
        MODEL,
        None,
        IdmWebSupplement(navigator_version="Navigator 10", software_version="NAV10_20.23"),
    )

    assert model_name == "Navigator 10"
    assert firmware_version == "NAV10_20.23"


# ---------------------------------------------------------------------------
# Model-aware web client selection
# ---------------------------------------------------------------------------


def _patch_web_factories(monkeypatch: pytest.MonkeyPatch, nav10: _FakeWebClient, nav20: _FakeWebClient) -> None:
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


def test_preferred_web_variant_detects_navigator_20() -> None:
    assert _preferred_web_variant("Navigator 2.0") == "nav20"
    assert _preferred_web_variant("IDM Navigator 2.0") == "nav20"


def test_preferred_web_variant_detects_navigator_10() -> None:
    assert _preferred_web_variant("Navigator 10") == "nav10"
    assert _preferred_web_variant("IDM Navigator 10") == "nav10"


def test_preferred_web_variant_detects_navigator_pro() -> None:
    assert _preferred_web_variant("Navigator Pro") == "nav10"


def test_preferred_web_variant_returns_none_for_generic_or_unknown() -> None:
    assert _preferred_web_variant(MODEL) is None
    assert _preferred_web_variant("Navigator 2.0 / 10") is None
    assert _preferred_web_variant(None) is None
    assert _preferred_web_variant("") is None
    assert _preferred_web_variant("Terra SWM") is None


async def test_model_hint_navigator20_tries_nav20_first(monkeypatch: pytest.MonkeyPatch) -> None:
    """With a Nav 2.0 model hint, the HTTP client must be tried first."""
    nav10 = _FakeWebClient(
        SimpleNamespace(navigator_version="Navigator 10", software_version=None, heatpump_model=None, simple_values={})
    )
    nav20 = _FakeWebClient(
        SimpleNamespace(
            navigator_version="Navigator 2.0", software_version="2.35", heatpump_model=None, simple_values={}
        )
    )
    _patch_web_factories(monkeypatch, nav10, nav20)

    result = await async_read_web_supplement("192.0.2.10", "1234", model_hint="Navigator 2.0")

    assert result is not None
    assert result.navigator_version == "Navigator 2.0"
    assert nav20.closed  # Nav 20 was tried (and succeeded)
    assert not nav10.closed  # Nav 10 WebSocket was never attempted


async def test_model_hint_navigator10_tries_nav10_first(monkeypatch: pytest.MonkeyPatch) -> None:
    """With a Nav 10 model hint, the WebSocket client must be tried first."""
    nav10 = _FakeWebClient(
        SimpleNamespace(
            navigator_version="Navigator 10", software_version="NAV10_1.0", heatpump_model=None, simple_values={}
        )
    )
    nav20 = _FakeWebClient(
        SimpleNamespace(
            navigator_version="Navigator 2.0", software_version="2.35", heatpump_model=None, simple_values={}
        )
    )
    _patch_web_factories(monkeypatch, nav10, nav20)

    result = await async_read_web_supplement("192.0.2.10", "1234", model_hint="Navigator 10")

    assert result is not None
    assert result.navigator_version == "Navigator 10"
    assert nav10.closed  # Nav 10 was tried (and succeeded)
    assert not nav20.closed  # Nav 20 HTTP was never attempted


async def test_preferred_variant_overrides_model_hint(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cached preferred_variant takes priority over model_hint."""
    nav10 = _FakeWebClient(
        SimpleNamespace(navigator_version="Navigator 10", software_version=None, heatpump_model=None, simple_values={})
    )
    nav20 = _FakeWebClient(
        SimpleNamespace(
            navigator_version="Navigator 2.0", software_version="2.35", heatpump_model=None, simple_values={}
        )
    )
    _patch_web_factories(monkeypatch, nav10, nav20)

    # model_hint says Nav 10 but cached variant says Nav 20
    result = await async_read_web_supplement("192.0.2.10", "1234", model_hint="Navigator 10", preferred_variant="nav20")

    assert result is not None
    assert result.navigator_version == "Navigator 2.0"
    assert nav20.closed
    assert not nav10.closed


async def test_preferred_variant_accepts_family_name(monkeypatch: pytest.MonkeyPatch) -> None:
    """Preferred variant also accepts the internal navigator family name."""
    nav10 = _FakeWebClient(
        SimpleNamespace(navigator_version="Navigator 10", software_version=None, heatpump_model=None, simple_values={})
    )
    nav20 = _FakeWebClient(
        SimpleNamespace(
            navigator_version="Navigator 2.0", software_version="2.35", heatpump_model=None, simple_values={}
        )
    )
    _patch_web_factories(monkeypatch, nav10, nav20)

    result = await async_read_web_supplement(
        "192.0.2.10", "1234", model_hint="Navigator 10", preferred_variant="navigator_20"
    )

    assert result is not None
    assert result.navigator_version == "Navigator 2.0"
    assert nav20.closed
    assert not nav10.closed


async def test_no_hint_keeps_default_nav10_first(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without any hint, Nav 10 WebSocket is tried first (current generation)."""
    nav10 = _FakeWebClient(
        SimpleNamespace(navigator_version="Navigator 10", software_version=None, heatpump_model=None, simple_values={})
    )
    nav20 = _FakeWebClient(
        SimpleNamespace(
            navigator_version="Navigator 2.0", software_version="2.35", heatpump_model=None, simple_values={}
        )
    )
    _patch_web_factories(monkeypatch, nav10, nav20)

    result = await async_read_web_supplement("192.0.2.10", "1234")

    assert result is not None
    assert result.navigator_version == "Navigator 10"
    assert nav10.closed
    assert not nav20.closed


async def test_nav20_hint_falls_back_to_nav10_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """If the preferred Nav 20 client fails, we still fall back to Nav 10."""
    nav10 = _FakeWebClient(
        SimpleNamespace(
            navigator_version="Navigator 10", software_version="NAV10_1.0", heatpump_model=None, simple_values={}
        )
    )
    nav20 = _FakeWebClient(error=RuntimeError("HTTP 500"))
    _patch_web_factories(monkeypatch, nav10, nav20)

    result = await async_read_web_supplement("192.0.2.10", "1234", model_hint="Navigator 2.0")

    assert result is not None
    assert result.navigator_version == "Navigator 10"
    assert nav20.closed  # Nav 20 was tried first (and failed)
    assert nav10.closed  # Nav 10 was tried as fallback (and succeeded)


def _web_data_snapshot(navigator_version="Navigator 10", software_version="NAV10_1.0"):
    return SimpleNamespace(
        navigator_version=navigator_version,
        software_version=software_version,
        heatpump_model="iPump",
        simple_values={"software_version": software_version},
    )


class TestWebClientPool:
    """Cover persistent web client reuse (P1)."""

    async def test_reuses_cached_client_across_polls_without_closing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A successful client is cached and reused on the next poll (no reconnect)."""
        creation_count = {"nav10": 0, "nav20": 0}

        def make_nav10(host, pin):
            creation_count["nav10"] += 1
            return _FakeWebClient(_web_data_snapshot())

        def make_nav20(host, pin):
            creation_count["nav20"] += 1
            return _FakeWebClient(_web_data_snapshot())

        monkeypatch.setattr(idm_heatpump, "web_pin_configured", lambda pin: bool(pin.strip()), raising=False)
        monkeypatch.setattr(idm_heatpump, "create_optional_navigator10_web_client", make_nav10, raising=False)
        monkeypatch.setattr(idm_heatpump, "create_optional_navigator20_web_client", make_nav20, raising=False)
        pool = IdmWebClientPool()

        first = await async_read_web_supplement("192.0.2.10", "1234", client_pool=pool)
        second = await async_read_web_supplement("192.0.2.10", "1234", client_pool=pool)

        assert first is not None and second is not None
        # The nav10 client was created exactly once (first poll) and reused on
        # the second poll instead of reconnecting. nav20 was never created.
        assert creation_count["nav10"] == 1
        assert creation_count["nav20"] == 0
        assert pool.get() is not None

    async def test_invalidates_cached_client_on_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """On a read failure the cached client is dropped and the next poll rebuilds."""
        nav10_first = _FakeWebClient(_web_data_snapshot())
        nav10_second = _FakeWebClient(_web_data_snapshot())
        # The factory returns the first client on the first call, the second on
        # the next call (simulating a reconnect after the cached client failed).
        clients = [nav10_first, nav10_second]

        def factory(host, pin):
            return clients.pop(0) if clients else _FakeWebClient(_web_data_snapshot())

        monkeypatch.setattr(idm_heatpump, "web_pin_configured", lambda pin: bool(pin.strip()), raising=False)
        monkeypatch.setattr(
            idm_heatpump, "create_optional_navigator10_web_client", factory, raising=False
        )
        monkeypatch.setattr(
            idm_heatpump, "create_optional_navigator20_web_client", lambda host, pin: None, raising=False
        )
        pool = IdmWebClientPool()

        first = await async_read_web_supplement("192.0.2.10", "1234", client_pool=pool)
        assert first is not None
        assert not nav10_first.closed  # cached after success

        # Force a failure on the cached client by making read_data raise.
        nav10_first.error = RuntimeError("connection reset")
        # Retry: cached client fails → invalidated → fresh client built.
        second = await async_read_web_supplement("192.0.2.10", "1234", client_pool=pool)
        assert second is not None
        assert nav10_first.closed  # failed cached client was closed on invalidation
        assert not nav10_second.closed  # new client cached

    async def test_close_releases_held_client(self, monkeypatch: pytest.MonkeyPatch) -> None:
        nav10 = _FakeWebClient(_web_data_snapshot())
        nav20 = _FakeWebClient(_web_data_snapshot())
        _patch_web_factories(monkeypatch, nav10, nav20)
        pool = IdmWebClientPool()

        await async_read_web_supplement("192.0.2.10", "1234", client_pool=pool)
        assert pool.get() is not None

        await pool.close()
        assert pool.get() is None
        assert nav10.closed

    async def test_without_pool_keeps_legacy_close_after_read(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Without a pool, a successful read still closes the client (backward compat)."""
        nav10 = _FakeWebClient(_web_data_snapshot())
        nav20 = _FakeWebClient(_web_data_snapshot())
        _patch_web_factories(monkeypatch, nav10, nav20)

        result = await async_read_web_supplement("192.0.2.10", "1234")
        assert result is not None
        assert nav10.closed  # legacy behaviour preserved
