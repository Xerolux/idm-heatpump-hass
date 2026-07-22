"""Tests for the future Modbus transport contract."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from custom_components.idm_heatpump.modbus_transport import (
    IdmModbusTransport,
    ModbusTcpEndpoint,
    ModbusTransportCapabilities,
)


class FakeTransport:
    endpoint = ModbusTcpEndpoint("192.0.2.10", 502, 1, 10.0, 3)
    capabilities = ModbusTransportCapabilities(
        source="test",
        owns_socket=True,
        supports_shared_connection=False,
    )

    async def async_connect(self) -> None:
        return None

    async def async_close(self) -> None:
        return None

    async def async_read_holding_registers(self, address: int, count: int) -> tuple[int, ...]:
        return tuple(address + offset for offset in range(count))

    async def async_read_input_registers(self, address: int, count: int) -> tuple[int, ...]:
        return tuple(0x1000 + address + offset for offset in range(count))

    async def async_write_registers(self, address: int, values: tuple[int, ...]) -> None:
        return None


def test_endpoint_is_immutable() -> None:
    endpoint = ModbusTcpEndpoint("192.0.2.10", 502, 1, 10.0, 3)

    with pytest.raises(FrozenInstanceError):
        endpoint.port = 1502  # type: ignore[misc]


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"host": " ", "port": 502, "slave_id": 1, "timeout": 10.0, "retries": 3}, "host"),
        ({"host": "192.0.2.10", "port": 0, "slave_id": 1, "timeout": 10.0, "retries": 3}, "port"),
        ({"host": "192.0.2.10", "port": 502, "slave_id": 0, "timeout": 10.0, "retries": 3}, "slave_id"),
        ({"host": "192.0.2.10", "port": 502, "slave_id": 248, "timeout": 10.0, "retries": 3}, "slave_id"),
        ({"host": "192.0.2.10", "port": 502, "slave_id": 1, "timeout": 0.0, "retries": 3}, "timeout"),
        ({"host": "192.0.2.10", "port": 502, "slave_id": 1, "timeout": 10.0, "retries": -1}, "retries"),
    ],
)
def test_endpoint_rejects_invalid_values(kwargs: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        ModbusTcpEndpoint(**kwargs)  # type: ignore[arg-type]


def test_endpoint_connection_key_normalizes_host() -> None:
    endpoint = ModbusTcpEndpoint(" HeatPump.LOCAL ", 502, 1, 10.0, 3)

    assert endpoint.connection_key == ("heatpump.local", 502, 1)


def test_endpoint_diagnostics_redact_host() -> None:
    endpoint = ModbusTcpEndpoint("192.0.2.10", 1502, 2, 5.5, 1)

    assert endpoint.as_redacted_diagnostics() == {
        "host": "**REDACTED**",
        "port": 1502,
        "slave_id": 2,
        "timeout": 5.5,
        "retries": 1,
    }


def test_capabilities_default_to_private_socket() -> None:
    capabilities = ModbusTransportCapabilities(source="pymodbus", owns_socket=True)

    assert capabilities.source == "pymodbus"
    assert capabilities.owns_socket is True
    assert capabilities.supports_shared_connection is False


def test_capabilities_diagnostics_are_plain_values() -> None:
    capabilities = ModbusTransportCapabilities(
        source="homeassistant_modbus_connection",
        owns_socket=False,
        supports_shared_connection=True,
    )

    assert capabilities.as_diagnostics() == {
        "source": "homeassistant_modbus_connection",
        "owns_socket": False,
        "supports_shared_connection": True,
    }


def test_protocol_accepts_matching_transport() -> None:
    assert isinstance(FakeTransport(), IdmModbusTransport)


@pytest.mark.asyncio
async def test_transport_keeps_input_and_holding_reads_distinct() -> None:
    transport = FakeTransport()

    assert await transport.async_read_holding_registers(100, 2) == (100, 101)
    assert await transport.async_read_input_registers(100, 2) == (4196, 4197)
