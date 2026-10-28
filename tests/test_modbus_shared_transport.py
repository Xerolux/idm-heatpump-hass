"""Tests for the shared Home Assistant Modbus connection provider."""

from __future__ import annotations

import logging
import sys
import types
from typing import Any

import pytest
from idm_heatpump import IdmConnectionError, IdmDeviceError, IllegalAddressError

from custom_components.idm_heatpump.library_adapter import get_idm_client
from custom_components.idm_heatpump.modbus_shared_transport import (
    SHARED_MODBUS_DOMAIN,
    SharedModbusUnitTransport,
    create_shared_modbus_transport,
    shared_modbus_supported,
)
from custom_components.idm_heatpump.modbus_transport import ModbusTcpEndpoint


class _FakeSharedUnit:
    """Doubles the unit handed out by ``modbus.async_get_unit``."""

    def __init__(
        self,
        *,
        connected: bool = True,
        holding: dict[int, list[int]] | None = None,
        coils: list[bool] | None = None,
    ) -> None:
        self.connected = connected
        self.negotiated: dict[str, float] = {}
        self.holding_calls: list[tuple[int, int]] = []
        self.input_calls: list[tuple[int, int]] = []
        self.write_calls: list[tuple[int, list[int]]] = []
        self.coil_read_calls: list[tuple[int, int]] = []
        self.coil_write_calls: list[tuple[int, bool]] = []
        self._holding = holding or {}
        self._coils = coils

    def require_timeout(self, seconds: float) -> None:
        self.negotiated["require_timeout"] = seconds

    def set_message_spacing(self, seconds: float) -> None:
        self.negotiated["set_message_spacing"] = seconds

    def require_connect_delay(self, seconds: float) -> None:
        self.negotiated["require_connect_delay"] = seconds

    async def read_holding_registers(self, address: int, count: int) -> list[int]:
        self.holding_calls.append((address, count))
        if address in self._holding:
            return self._holding[address][:count]
        from modbus_connection import ModbusConnectionError

        raise ModbusConnectionError("no holding data")

    async def read_input_registers(self, address: int, count: int) -> list[int]:
        self.input_calls.append((address, count))
        return [0] * count

    async def write_registers(self, address: int, values: list[int]) -> None:
        self.write_calls.append((address, list(values)))

    async def read_coils(self, address: int, count: int) -> list[bool]:
        self.coil_read_calls.append((address, count))
        if self._coils is None:
            from modbus_connection import ModbusConnectionError

            raise ModbusConnectionError("no coil data")
        return self._coils[:count]

    async def write_coil(self, address: int, value: bool) -> None:
        self.coil_write_calls.append((address, value))


class _SharedModbusHarness:
    """Installs fake ``modbus`` and ``setup`` modules for one test."""

    def __init__(self, unit: _FakeSharedUnit, setup_result: bool = True) -> None:
        self.unit = unit
        self.get_unit_calls: list[dict[str, Any]] = []
        self.setup_calls: list[str] = []
        self.release_calls = 0
        self._before: dict[str, Any] = {}

        harness = self

        def async_get_unit(hass: Any, entry: Any, params: Any, unit_id: int) -> _FakeSharedUnit:
            # Home Assistant's contract is a synchronous @callback; only the
            # setup call above is async.
            harness.get_unit_calls.append(
                {
                    "entry_id": entry.entry_id,
                    "params": params,
                    "unit_id": unit_id,
                }
            )
            entry.async_on_unload(harness._release)
            return harness.unit

        modbus_module = types.ModuleType("homeassistant.components.modbus")
        modbus_module.async_get_unit = async_get_unit  # type: ignore[attr-defined]
        self.modbus_module = modbus_module

        setup_module = types.ModuleType("homeassistant.setup")

        async def async_setup_component(hass: Any, domain: str, config: Any) -> bool:
            harness.setup_calls.append(domain)
            return setup_result

        setup_module.async_setup_component = async_setup_component  # type: ignore[attr-defined]
        self.setup_module = setup_module

    def _release(self) -> None:
        self.release_calls += 1

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        components = sys.modules["homeassistant.components"]
        monkeypatch.setitem(sys.modules, "homeassistant.components.modbus", self.modbus_module)
        monkeypatch.setitem(sys.modules, "homeassistant.setup", self.setup_module)
        monkeypatch.setattr(components, "modbus", self.modbus_module, raising=False)
        monkeypatch.setattr(sys.modules["homeassistant"], "setup", self.setup_module, raising=False)

    def with_ha_version(self, monkeypatch: pytest.MonkeyPatch, version: str) -> None:
        monkeypatch.setattr(sys.modules["homeassistant.const"], "__version__", version, raising=False)


def _endpoint(**overrides: Any) -> ModbusTcpEndpoint:
    values: dict[str, Any] = {
        "host": "192.0.2.10",
        "port": 502,
        "slave_id": 17,
        "timeout": 12.5,
        "retries": 4,
        "message_spacing": 0.2,
        "connect_delay": 0.5,
    }
    values.update(overrides)
    return ModbusTcpEndpoint(**values)


def _entry() -> Any:
    entry = types.SimpleNamespace(entry_id="test_entry", async_on_unload=lambda cb: None)
    return entry


def _hass() -> Any:
    return types.SimpleNamespace(data={})


# --- version gate ------------------------------------------------------------


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        ("2026.10.0", True),
        ("2026.10.2", True),
        ("2026.11.0", True),
        ("2026.8.1", False),
        ("2026.9.9", False),
        ("2027.1.0b1", True),
    ],
)
def test_shared_modbus_supported_by_ha_version(monkeypatch: pytest.MonkeyPatch, version: str, expected: bool) -> None:
    hass = _hass()
    monkeypatch.setattr(sys.modules["homeassistant.const"], "__version__", version, raising=False)
    assert shared_modbus_supported(hass) is expected


def test_shared_modbus_supported_without_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A Home Assistant without a parsable version keeps the private socket."""
    const = sys.modules["homeassistant.const"]
    monkeypatch.delattr(const, "__version__", raising=False)
    assert shared_modbus_supported(_hass()) is False


# --- factory -----------------------------------------------------------------


async def test_create_shared_transport_acquires_and_negotiates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The factory sets up the modbus component, claims a unit and negotiates floors."""
    unit = _FakeSharedUnit(connected=False)
    harness = _SharedModbusHarness(unit)
    harness.install(monkeypatch)
    harness.with_ha_version(monkeypatch, "2026.10.2")

    entry = _entry()
    transport = await create_shared_modbus_transport(_hass(), entry, _endpoint())

    assert transport is not None
    assert harness.setup_calls == [SHARED_MODBUS_DOMAIN]
    assert len(harness.get_unit_calls) == 1
    call = harness.get_unit_calls[0]
    assert call["entry_id"] == "test_entry"
    assert call["unit_id"] == 17
    assert call["params"].host == "192.0.2.10"
    assert call["params"].port == 502
    # The endpoint's timeout and pacing floors reach the shared link.
    assert unit.negotiated == {
        "require_timeout": 12.5,
        "set_message_spacing": 0.2,
        "require_connect_delay": 0.5,
    }
    diagnostics = transport.as_redacted_diagnostics()
    assert diagnostics["capabilities"] == {
        "source": "homeassistant.modbus",
        "owns_socket": False,
        "supports_shared_connection": True,
    }
    assert diagnostics["connected"] is False  # lazily connecting, claim acquired
    assert transport.connects_lazily is True


async def test_create_shared_transport_skips_unsupported_ha(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Before 2026.10 nothing is imported, set up or claimed."""
    unit = _FakeSharedUnit()
    harness = _SharedModbusHarness(unit)
    harness.install(monkeypatch)
    harness.with_ha_version(monkeypatch, "2026.8.1")

    transport = await create_shared_modbus_transport(_hass(), _entry(), _endpoint())

    assert transport is None
    assert harness.setup_calls == []
    assert harness.get_unit_calls == []


async def test_create_shared_transport_falls_back_when_component_fails(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A modbus component that will not set up degrades to the private socket."""
    unit = _FakeSharedUnit()
    harness = _SharedModbusHarness(unit, setup_result=False)
    harness.install(monkeypatch)
    harness.with_ha_version(monkeypatch, "2026.10.2")
    caplog.set_level(logging.WARNING)

    transport = await create_shared_modbus_transport(_hass(), _entry(), _endpoint())

    assert transport is None
    assert harness.get_unit_calls == []
    assert any("modbus component could not be set up" in rec.message for rec in caplog.records)


async def test_create_shared_transport_falls_back_without_api(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A modbus component without async_get_unit degrades with one warning."""
    harness = _SharedModbusHarness(_FakeSharedUnit())
    harness.install(monkeypatch)
    harness.with_ha_version(monkeypatch, "2026.10.2")
    # Remove the sharing API from the fake component.
    monkeypatch.delattr(harness.modbus_module, "async_get_unit", raising=False)
    caplog.set_level(logging.WARNING)

    transport = await create_shared_modbus_transport(_hass(), _entry(), _endpoint())

    assert transport is None
    assert any("shared Modbus connection is unavailable" in rec.message for rec in caplog.records)


async def test_create_shared_transport_falls_back_on_conflict(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A rejected claim (conflicting link settings) degrades instead of failing setup."""

    class _ConflictingHarness(_SharedModbusHarness):
        def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
            super().install(monkeypatch)

            def conflicting_get_unit(hass: Any, entry: Any, params: Any, unit_id: int) -> _FakeSharedUnit:
                raise RuntimeError("already in use with different link settings")

            monkeypatch.setattr(self.modbus_module, "async_get_unit", conflicting_get_unit)

    harness = _ConflictingHarness(_FakeSharedUnit())
    harness.install(monkeypatch)
    harness.with_ha_version(monkeypatch, "2026.10.2")
    caplog.set_level(logging.WARNING)

    transport = await create_shared_modbus_transport(_hass(), _entry(), _endpoint())

    assert transport is None
    assert any("shared Modbus connection is unavailable" in rec.message for rec in caplog.records)


# --- transport behaviour -------------------------------------------------------


async def test_shared_transport_routes_reads_and_writes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    unit = _FakeSharedUnit(holding={100: [1, 2, 3]}, coils=[True, False])
    harness = _SharedModbusHarness(unit)
    harness.install(monkeypatch)
    harness.with_ha_version(monkeypatch, "2026.10.2")

    transport = await create_shared_modbus_transport(_hass(), _entry(), _endpoint())
    assert transport is not None

    words = await transport.read_holding_registers(address=100, count=3)
    assert words == [1, 2, 3]
    input_words = await transport.read_input_registers(address=200, count=2)
    assert input_words == [0, 0]
    await transport.write_registers(address=300, values=[5, 6])
    bits = await transport.read_coils(address=3000, count=2)
    assert bits == [True, False]
    await transport.write_coil(address=3003, value=True)

    assert unit.holding_calls == [(100, 3)]
    assert unit.input_calls == [(200, 2)]
    assert unit.write_calls == [(300, [5, 6])]
    assert unit.coil_read_calls == [(3000, 2)]
    assert unit.coil_write_calls == [(3003, True)]


async def test_shared_transport_translates_illegal_address(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from modbus_connection import IllegalDataAddressError

    class _IllegalUnit(_FakeSharedUnit):
        async def read_holding_registers(self, address: int, count: int) -> list[int]:
            raise IllegalDataAddressError(message="unsupported block")

    harness = _SharedModbusHarness(_IllegalUnit())
    harness.install(monkeypatch)
    harness.with_ha_version(monkeypatch, "2026.10.2")

    transport = await create_shared_modbus_transport(_hass(), _entry(), _endpoint())
    assert transport is not None

    with pytest.raises(IllegalAddressError, match="exception_code=2"):
        await transport.read_holding_registers(address=100, count=1)


async def test_shared_transport_rejects_short_coil_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _SharedModbusHarness(_FakeSharedUnit(coils=[True]))
    harness.install(monkeypatch)
    harness.with_ha_version(monkeypatch, "2026.10.2")

    transport = await create_shared_modbus_transport(_hass(), _entry(), _endpoint())
    assert transport is not None

    with pytest.raises(IdmDeviceError, match="Incomplete coil response"):
        await transport.read_coils(address=3000, count=3)


async def test_shared_transport_close_is_soft_and_reacquires(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """close() detaches the claim; connect() re-acquires without disturbing others."""
    unit = _FakeSharedUnit(connected=True)
    harness = _SharedModbusHarness(unit)
    harness.install(monkeypatch)
    harness.with_ha_version(monkeypatch, "2026.10.2")

    entry = _entry()
    transport = await create_shared_modbus_transport(_hass(), entry, _endpoint())
    assert transport is not None
    assert transport.connected is True

    await transport.close()
    assert transport.connected is False  # our view; the shared link stays up
    assert unit.connected is True

    await transport.connect()
    assert transport.connected is True
    assert len(harness.get_unit_calls) == 2  # claim re-acquired


async def test_shared_transport_requires_unit_before_io() -> None:
    """A transport that never connected refuses I/O with the API's error."""
    transport = SharedModbusUnitTransport(_hass(), _entry(), _endpoint())
    with pytest.raises(IdmConnectionError, match="not acquired"):
        await transport.read_holding_registers(address=1, count=1)


# --- client factory ------------------------------------------------------------


async def test_get_idm_client_accepts_injected_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The sync factory wires a ready-made transport through unchanged."""
    unit = _FakeSharedUnit()
    harness = _SharedModbusHarness(unit)
    harness.install(monkeypatch)
    harness.with_ha_version(monkeypatch, "2026.10.2")

    transport = await create_shared_modbus_transport(_hass(), _entry(), _endpoint())
    assert transport is not None
    client = get_idm_client(host="192.0.2.10", port=502, slave_id=17, transport=transport)
    assert client.transport_diagnostics()["capabilities"]["source"] == "homeassistant.modbus"
