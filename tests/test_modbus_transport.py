"""Tests for the Modbus transport contract and tmodbus implementation."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import Any

import pytest
from idm_heatpump import IdmModbusError, IdmTransportError, IllegalAddressError
from idm_heatpump.transport import IdmModbusTransport
from modbus_connection import (
    AcknowledgeError,
    GatewayPathUnavailableError,
    GatewayTargetError,
    IllegalDataAddressError,
    IllegalDataValueError,
    ModbusExceptionError,
    ServerDeviceBusyError,
)

from custom_components.idm_heatpump import modbus_transport
from custom_components.idm_heatpump.modbus_transport import (
    ModbusConnectionTransport,
    ModbusTcpEndpoint,
    ModbusTransportCapabilities,
)


class FakeTransport:
    """Minimal transport double satisfying the API 1.0 protocol."""

    connected = True

    async def connect(self) -> None:
        return None

    async def close(self) -> None:
        self.connected = False

    async def read_holding_registers(self, *, address: int, count: int) -> list[int]:
        return [address + offset for offset in range(count)]

    async def read_input_registers(self, *, address: int, count: int) -> list[int]:
        return [0x1000 + address + offset for offset in range(count)]

    async def write_registers(self, *, address: int, values: list[int]) -> None:
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

    def __init__(self) -> None:
        self.endpoints: list[ModbusTcpEndpoint] = []
        self.connections: list[RecordingConnection] = []

    def __call__(self, endpoint: ModbusTcpEndpoint) -> RecordingConnection:
        connection = RecordingConnection()
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
        (
            {
                "host": "192.0.2.10",
                "port": 502,
                "slave_id": 1,
                "timeout": 10.0,
                "retries": 3,
                "message_spacing": -0.01,
            },
            "message_spacing",
        ),
        (
            {
                "host": "192.0.2.10",
                "port": 502,
                "slave_id": 1,
                "timeout": 10.0,
                "retries": 3,
                "connect_delay": -1.0,
            },
            "connect_delay",
        ),
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
        "message_spacing": 0.0,
        "connect_delay": 0.0,
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
    """The concrete transport must satisfy the API 1.0 IdmModbusTransport protocol."""
    assert isinstance(FakeTransport(), IdmModbusTransport)


@pytest.mark.asyncio
async def test_transport_keeps_input_and_holding_reads_distinct() -> None:
    transport = FakeTransport()

    assert await transport.read_holding_registers(address=100, count=2) == [100, 101]
    assert await transport.read_input_registers(address=100, count=2) == [4196, 4197]


@pytest.mark.asyncio
async def test_tmodbus_transport_owns_lifecycle_and_binds_configured_slave() -> None:
    endpoint = ModbusTcpEndpoint("192.0.2.10", 502, 37, 10.0, 3)
    factory = RecordingConnectionFactory()
    transport = ModbusConnectionTransport(endpoint, connection_factory=factory)

    assert factory.endpoints == [endpoint]
    connection = factory.connections[0]
    assert connection.bound_unit_ids == [37]
    assert transport.endpoint is endpoint
    assert transport.connected is False

    await transport.connect()

    assert connection.connect_calls == 1
    assert transport.connected is True

    await transport.close()
    await transport.close()

    assert connection.close_calls == 1
    assert transport.connected is False


@pytest.mark.asyncio
async def test_tmodbus_transport_can_open_a_new_generation_after_close() -> None:
    endpoint = ModbusTcpEndpoint("192.0.2.10", 502, 37, 10.0, 3)
    factory = RecordingConnectionFactory()
    transport = ModbusConnectionTransport(endpoint, connection_factory=factory)
    await transport.connect()
    await transport.close()

    await transport.connect()

    assert len(factory.connections) == 2
    assert factory.connections[1].bound_unit_ids == [37]
    assert factory.connections[1].connect_calls == 1
    assert transport.connected is True


@pytest.mark.asyncio
async def test_tmodbus_transport_routes_fc03_and_fc04_to_distinct_unit_methods() -> None:
    endpoint = ModbusTcpEndpoint("192.0.2.10", 502, 4, 10.0, 3)
    factory = RecordingConnectionFactory()
    transport = ModbusConnectionTransport(endpoint, connection_factory=factory)
    unit = factory.connections[0].unit
    assert unit is not None

    holding = await transport.read_holding_registers(address=100, count=3)
    input_words = await transport.read_input_registers(address=200, count=2)

    assert holding == [100, 101, 102]
    assert input_words == [4296, 4297]
    assert unit.holding_reads == [(100, 3)]
    assert unit.input_reads == [(200, 2)]


@pytest.mark.asyncio
async def test_tmodbus_transport_uses_fc16_for_multi_register_write() -> None:
    endpoint = ModbusTcpEndpoint("192.0.2.10", 502, 4, 10.0, 3)
    factory = RecordingConnectionFactory()
    transport = ModbusConnectionTransport(endpoint, connection_factory=factory)
    unit = factory.connections[0].unit
    assert unit is not None

    await transport.write_registers(address=1200, values=[0, 65535, 42])

    assert unit.writes == [(1200, [0, 65535, 42])]


@pytest.mark.asyncio
async def test_tmodbus_transport_close_then_connect_replaces_connection() -> None:
    """Reconnect is now close+connect; verify it builds a fresh generation."""
    endpoint = ModbusTcpEndpoint("192.0.2.10", 1502, 9, 4.5, 2)
    factory = RecordingConnectionFactory()
    transport = ModbusConnectionTransport(endpoint, connection_factory=factory)
    first_connection = factory.connections[0]
    await transport.connect()

    await transport.close()
    await transport.connect()

    assert len(factory.connections) == 2
    second_connection = factory.connections[1]
    assert first_connection.close_calls == 1
    assert first_connection.connected is False
    assert second_connection.bound_unit_ids == [9]
    assert second_connection.connect_calls == 1
    assert second_connection.connected is True
    assert factory.endpoints == [endpoint, endpoint]
    assert transport.connected is True


@pytest.mark.asyncio
async def test_tmodbus_transport_satisfies_api_protocol_after_lifecycle() -> None:
    """The concrete transport must satisfy the API protocol throughout its lifecycle."""
    endpoint = ModbusTcpEndpoint("192.0.2.10", 1502, 9, 4.5, 2)
    factory = RecordingConnectionFactory()
    transport = ModbusConnectionTransport(endpoint, connection_factory=factory)

    assert isinstance(transport, IdmModbusTransport)
    await transport.connect()
    assert isinstance(transport, IdmModbusTransport)


@pytest.mark.asyncio
async def test_transport_translates_exception_code_2_to_illegal_address() -> None:
    """Backend code 2 must surface as IllegalAddressError with the coordinator marker."""
    endpoint = ModbusTcpEndpoint("192.0.2.10", 502, 1, 1.0, 0)

    class FailingUnit:
        async def read_input_registers(self, address: int, count: int) -> list[int]:
            raise ModbusExceptionError(exception_code=2, message="illegal address")

        async def read_holding_registers(self, address: int, count: int) -> list[int]:
            raise ModbusExceptionError(exception_code=2, message="illegal address")

        async def write_registers(self, address: int, values: list[int]) -> None:
            raise ModbusExceptionError(exception_code=2, message="illegal address")

    class FailingConnection:
        connected = False

        def __init__(self, *_: Any) -> None: ...

        def for_unit(self, _unit_id: int) -> FailingUnit:
            return FailingUnit()

        async def connect(self) -> None:
            self.connected = True

        async def close(self) -> None:
            self.connected = False

    transport = ModbusConnectionTransport(endpoint, connection_factory=lambda _: FailingConnection())  # type: ignore[arg-type]

    with pytest.raises(IllegalAddressError, match="exception_code=2"):
        await transport.read_input_registers(address=1000, count=1)


def _make_failing_transport(exception_code: int) -> ModbusConnectionTransport:
    """Build a transport whose unit always raises a given backend exception code."""

    class FailingUnit:
        async def read_holding_registers(self, address: int, count: int) -> list[int]:
            raise ModbusExceptionError(exception_code=exception_code, message="busy")

        async def read_input_registers(self, address: int, count: int) -> list[int]:
            raise ModbusExceptionError(exception_code=exception_code, message="busy")

        async def write_registers(self, address: int, values: list[int]) -> None:
            raise ModbusExceptionError(exception_code=exception_code, message="busy")

    class FailingConnection:
        connected = False

        def __init__(self, *_: Any) -> None: ...

        def for_unit(self, _unit_id: int) -> FailingUnit:
            return FailingUnit()

        async def connect(self) -> None:
            self.connected = True

        async def close(self) -> None:
            self.connected = False

    endpoint = ModbusTcpEndpoint("192.0.2.10", 502, 1, 1.0, 0)
    return ModbusConnectionTransport(endpoint, connection_factory=lambda _: FailingConnection())  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_transport_translates_transient_codes_to_modbus_exception() -> None:
    """Codes 5/6/10/11 must surface as IdmModbusError (retry-in-place path).

    IdmTransportError derives from IdmModbusError but triggers the API's hard
    reconnect path; the API 1.0 contract assigns codes 5/6/10/11 to the
    retry-in-place path, so they must not surface as IdmTransportError.
    """
    for code in (5, 6, 10, 11):
        transport = _make_failing_transport(code)

        with pytest.raises(IdmModbusError, match=f"exception_code={code}") as exc_info:
            await transport.read_holding_registers(address=2000, count=1)

        assert not isinstance(exc_info.value, IdmTransportError)


@pytest.mark.asyncio
async def test_tmodbus_transport_diagnostics_are_redacted_and_backend_neutral() -> None:
    endpoint = ModbusTcpEndpoint("private-heatpump.example", 1502, 6, 7.5, 1)
    factory = RecordingConnectionFactory()
    transport = ModbusConnectionTransport(endpoint, connection_factory=factory)
    await transport.connect()

    diagnostics = transport.as_redacted_diagnostics()

    assert diagnostics == {
        "endpoint": {
            "host": "**REDACTED**",
            "port": 1502,
            "slave_id": 6,
            "timeout": 7.5,
            "retries": 1,
            "message_spacing": 0.0,
            "connect_delay": 0.0,
        },
        "capabilities": {
            "source": "modbus_connection.tmodbus",
            "owns_socket": True,
            "supports_shared_connection": False,
        },
        "connected": True,
    }
    assert endpoint.host not in repr(diagnostics)


@pytest.mark.parametrize(
    ("error", "expected_code"),
    [
        (IllegalDataValueError(message="rejected value"), 3),
        (AcknowledgeError(message="accepted, needs time"), 5),
        (ServerDeviceBusyError(message="busy"), 6),
        (GatewayPathUnavailableError(message="no path"), 10),
        (GatewayTargetError(message="target silent"), 11),
        (ModbusExceptionError(exception_code=99, message="vendor specific"), 99),
    ],
)
@pytest.mark.asyncio
async def test_typed_backend_errors_keep_the_numeric_marker(
    error: ModbusExceptionError,
    expected_code: int,
) -> None:
    """The typed subclasses of 4.x must still render ``exception_code=<N>``.

    The coordinator matches that marker, and ``exception_code`` is an ``IntEnum``
    member for standard codes, so the transport has to render the number.
    """
    endpoint = ModbusTcpEndpoint("192.0.2.10", 502, 1, 1.0, 0)

    class FailingUnit:
        async def read_holding_registers(self, address: int, count: int) -> list[int]:
            raise error

        async def read_input_registers(self, address: int, count: int) -> list[int]:
            raise error

        async def write_registers(self, address: int, values: list[int]) -> None:
            raise error

    class FailingConnection:
        connected = False

        def for_unit(self, _unit_id: int) -> FailingUnit:
            return FailingUnit()

        async def connect(self) -> None:
            self.connected = True

        async def close(self) -> None:
            self.connected = False

    transport = ModbusConnectionTransport(endpoint, connection_factory=lambda _: FailingConnection())  # type: ignore[arg-type]

    with pytest.raises(IdmModbusError, match=rf"exception_code={expected_code}\)$"):
        await transport.read_holding_registers(address=2000, count=1)


@pytest.mark.asyncio
async def test_typed_illegal_data_address_maps_to_illegal_address_error() -> None:
    """The 4.x subclass for code 2 keeps the API's permanent-failure contract."""
    endpoint = ModbusTcpEndpoint("192.0.2.10", 502, 1, 1.0, 0)

    class FailingUnit:
        async def read_input_registers(self, address: int, count: int) -> list[int]:
            raise IllegalDataAddressError(message="unsupported register")

        async def read_holding_registers(self, address: int, count: int) -> list[int]:
            raise IllegalDataAddressError(message="unsupported register")

        async def write_registers(self, address: int, values: list[int]) -> None:
            raise IllegalDataAddressError(message="unsupported register")

    class FailingConnection:
        connected = False

        def for_unit(self, _unit_id: int) -> FailingUnit:
            return FailingUnit()

        async def connect(self) -> None:
            self.connected = True

        async def close(self) -> None:
            self.connected = False

    transport = ModbusConnectionTransport(endpoint, connection_factory=lambda _: FailingConnection())  # type: ignore[arg-type]

    with pytest.raises(IllegalAddressError, match="exception_code=2"):
        await transport.read_input_registers(address=1000, count=1)


def test_backend_connection_receives_configured_pacing(monkeypatch: pytest.MonkeyPatch) -> None:
    """``message_spacing``/``connect_delay`` must reach the backend connection.

    The pacing is implemented by ``modbus-connection`` itself, so the only thing
    this integration owns is handing the configured values to the constructor.
    """
    recorded: dict[str, Any] = {}

    def _record(params: Any, **kwargs: Any) -> Any:
        recorded["params"] = params
        recorded.update(kwargs)
        return RecordingConnection()

    monkeypatch.setattr(modbus_transport, "ModbusConnection", _record)

    endpoint = ModbusTcpEndpoint("192.0.2.10", 502, 1, 7.5, 3, message_spacing=0.1, connect_delay=1.5)
    modbus_transport._create_tmodbus_connection(endpoint)

    assert recorded["timeout"] == 7.5
    assert recorded["message_spacing"] == 0.1
    assert recorded["connect_delay"] == 1.5


def test_backend_connection_stays_unpaced_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """An endpoint without pacing options must not slow the link down."""
    recorded: dict[str, Any] = {}

    def _record(params: Any, **kwargs: Any) -> Any:
        recorded.update(kwargs)
        return RecordingConnection()

    monkeypatch.setattr(modbus_transport, "ModbusConnection", _record)

    modbus_transport._create_tmodbus_connection(ModbusTcpEndpoint("192.0.2.10", 502, 1, 10.0, 3))

    assert recorded["message_spacing"] == 0.0
    assert recorded["connect_delay"] == 0.0
