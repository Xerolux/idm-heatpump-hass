"""Tests for the Modbus transport contract and tmodbus implementation."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from custom_components.idm_heatpump.modbus_transport import (
    IdmModbusTransport,
    ModbusConnectionTransport,
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


class RecordingUnit:
    """Small unit double that records which Modbus function was requested."""

    def __init__(self, unit_id: int) -> None:
        self.unit_id = unit_id
        self.holding_reads: list[tuple[int, int]] = []
        self.input_reads: list[tuple[int, int]] = []
        self.writes: list[tuple[int, list[int]]] = []

    async def read_holding_registers(self, address: int, count: int) -> list[int]:
        self.holding_reads.append((address, count))
        return [address + offset for offset in range(count)]

    async def read_input_registers(self, address: int, count: int) -> list[int]:
        self.input_reads.append((address, count))
        return [0x1000 + address + offset for offset in range(count)]

    async def write_registers(self, address: int, values: list[int]) -> None:
        self.writes.append((address, values))


class RecordingConnection:
    """Connection double with observable lifecycle and unit binding."""

    def __init__(self, *, fail_on_close: bool = False) -> None:
        self.connected = False
        self.connect_calls = 0
        self.close_calls = 0
        self.bound_unit_ids: list[int] = []
        self.unit: RecordingUnit | None = None
        self.fail_on_close = fail_on_close

    def for_unit(self, unit_id: int) -> RecordingUnit:
        self.bound_unit_ids.append(unit_id)
        self.unit = RecordingUnit(unit_id)
        return self.unit

    async def connect(self) -> None:
        self.connect_calls += 1
        self.connected = True

    async def close(self) -> None:
        self.close_calls += 1
        self.connected = False
        if self.fail_on_close:
            raise RuntimeError("simulated close failure")


class RecordingConnectionFactory:
    """Create a fresh recording connection for each transport generation."""

    def __init__(self, *, fail_first_close: bool = False) -> None:
        self.endpoints: list[ModbusTcpEndpoint] = []
        self.connections: list[RecordingConnection] = []
        self.fail_first_close = fail_first_close

    def __call__(self, endpoint: ModbusTcpEndpoint) -> RecordingConnection:
        connection = RecordingConnection(
            fail_on_close=self.fail_first_close and not self.connections,
        )
        self.endpoints.append(endpoint)
        self.connections.append(connection)
        return connection


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


@pytest.mark.asyncio
async def test_tmodbus_transport_owns_lifecycle_and_binds_configured_slave() -> None:
    endpoint = ModbusTcpEndpoint("192.0.2.10", 502, 37, 10.0, 3)
    factory = RecordingConnectionFactory()
    transport = ModbusConnectionTransport(endpoint, connection_factory=factory)

    assert factory.endpoints == [endpoint]
    connection = factory.connections[0]
    assert connection.bound_unit_ids == [37]
    assert transport.endpoint is endpoint
    assert transport.is_connected is False

    await transport.async_connect()

    assert connection.connect_calls == 1
    assert transport.is_connected is True

    await transport.async_close()
    await transport.async_close()

    assert connection.close_calls == 1
    assert transport.is_connected is False


@pytest.mark.asyncio
async def test_tmodbus_transport_can_open_a_new_generation_after_close() -> None:
    endpoint = ModbusTcpEndpoint("192.0.2.10", 502, 37, 10.0, 3)
    factory = RecordingConnectionFactory()
    transport = ModbusConnectionTransport(endpoint, connection_factory=factory)
    await transport.async_connect()
    await transport.async_close()

    await transport.async_connect()

    assert len(factory.connections) == 2
    assert factory.connections[1].bound_unit_ids == [37]
    assert factory.connections[1].connect_calls == 1
    assert transport.is_connected is True


@pytest.mark.asyncio
async def test_tmodbus_transport_routes_fc03_and_fc04_to_distinct_unit_methods() -> None:
    endpoint = ModbusTcpEndpoint("192.0.2.10", 502, 4, 10.0, 3)
    factory = RecordingConnectionFactory()
    transport = ModbusConnectionTransport(endpoint, connection_factory=factory)
    unit = factory.connections[0].unit
    assert unit is not None

    holding = await transport.async_read_holding_registers(100, 3)
    input_words = await transport.async_read_input_registers(200, 2)

    assert holding == (100, 101, 102)
    assert input_words == (4296, 4297)
    assert unit.holding_reads == [(100, 3)]
    assert unit.input_reads == [(200, 2)]


@pytest.mark.asyncio
async def test_tmodbus_transport_uses_fc16_for_multi_register_write() -> None:
    endpoint = ModbusTcpEndpoint("192.0.2.10", 502, 4, 10.0, 3)
    factory = RecordingConnectionFactory()
    transport = ModbusConnectionTransport(endpoint, connection_factory=factory)
    unit = factory.connections[0].unit
    assert unit is not None

    await transport.async_write_registers(1200, (0, 65535, 42))

    assert unit.writes == [(1200, [0, 65535, 42])]


@pytest.mark.asyncio
async def test_tmodbus_transport_reconnects_with_fresh_connection_and_same_slave() -> None:
    endpoint = ModbusTcpEndpoint("192.0.2.10", 1502, 9, 4.5, 2)
    factory = RecordingConnectionFactory()
    transport = ModbusConnectionTransport(endpoint, connection_factory=factory)
    first_connection = factory.connections[0]
    await transport.async_connect()

    await transport.async_reconnect()

    assert len(factory.connections) == 2
    second_connection = factory.connections[1]
    assert first_connection.close_calls == 1
    assert first_connection.connected is False
    assert second_connection.bound_unit_ids == [9]
    assert second_connection.connect_calls == 1
    assert second_connection.connected is True
    assert factory.endpoints == [endpoint, endpoint]
    assert transport.is_connected is True


@pytest.mark.asyncio
async def test_tmodbus_transport_reconnects_even_when_old_close_fails() -> None:
    endpoint = ModbusTcpEndpoint("192.0.2.10", 1502, 9, 4.5, 2)
    factory = RecordingConnectionFactory(fail_first_close=True)
    transport = ModbusConnectionTransport(endpoint, connection_factory=factory)
    await transport.async_connect()

    await transport.async_reconnect()

    assert len(factory.connections) == 2
    assert factory.connections[0].close_calls == 1
    assert factory.connections[1].connect_calls == 1
    assert transport.is_connected is True


@pytest.mark.asyncio
async def test_tmodbus_transport_diagnostics_are_redacted_and_backend_neutral() -> None:
    endpoint = ModbusTcpEndpoint("private-heatpump.example", 1502, 6, 7.5, 1)
    factory = RecordingConnectionFactory()
    transport = ModbusConnectionTransport(endpoint, connection_factory=factory)
    await transport.async_connect()

    diagnostics = transport.as_redacted_diagnostics()

    assert diagnostics == {
        "endpoint": {
            "host": "**REDACTED**",
            "port": 1502,
            "slave_id": 6,
            "timeout": 7.5,
            "retries": 1,
        },
        "capabilities": {
            "source": "modbus_connection.tmodbus",
            "owns_socket": True,
            "supports_shared_connection": False,
        },
        "connected": True,
    }
    assert endpoint.host not in repr(diagnostics)
