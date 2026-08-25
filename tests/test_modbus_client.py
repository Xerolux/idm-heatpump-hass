"""Tests for the IDM API bridge backed by ``modbus-connection``.

With API 1.0 the wrapper injects a :class:`ModbusConnectionTransport` via the
``transport=`` constructor parameter and no longer overrides any private API
hooks.  These tests therefore focus on the integration seam: that public API
operations route through the owned transport, that backend errors are translated
by the transport before the API retry loop sees them, and that transport-aware
diagnostics are exposed for Home Assistant.

The transport's own exception-mapping and the API's retry/backoff/quarantine
behaviour are covered separately in ``test_modbus_transport.py`` and in the API
contract tests (``test_library_client.py``).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from idm_heatpump import (
    DataType,
    IdmDeviceError,
    IdmModbusError,
    IdmTransportError,
    IllegalAddressError,
    RegisterDef,
    RegisterType,
)
from idm_heatpump.transport import IdmModbusTransport

from custom_components.idm_heatpump.error_messages import classify_write_error
from custom_components.idm_heatpump.modbus_client import IdmModbusConnectionClient


def _make_transport() -> MagicMock:
    """Return a transport double implementing the API 1.0 protocol.

    Uses ``spec=IdmModbusTransport`` so ``isinstance`` runtime checks and the
    API constructor validation accept it.  Read methods return raw ``list[int]``;
    callers override ``return_value``/``side_effect`` per test.
    """
    transport = MagicMock(spec=IdmModbusTransport)
    transport.connected = True
    transport.connect = AsyncMock()
    transport.close = AsyncMock()
    transport.read_holding_registers = AsyncMock(return_value=[])
    transport.read_input_registers = AsyncMock(return_value=[])
    transport.write_registers = AsyncMock(return_value=None)
    return transport


def _make_client(transport: MagicMock, *, max_retries: int = 3) -> IdmModbusConnectionClient:
    return IdmModbusConnectionClient(
        host="private-heatpump.example",
        port=1502,
        slave_id=7,
        timeout=4.0,
        max_retries=max_retries,
        transport=transport,
    )


def test_default_client_builds_a_protocol_satisfying_transport() -> None:
    """Without an explicit transport the wrapper constructs a real tmodbus one
    that satisfies the API 1.0 protocol."""
    client = IdmModbusConnectionClient(host="192.0.2.1")
    assert isinstance(client._owned_transport, IdmModbusTransport)


def test_injected_transport_is_owned_by_the_client() -> None:
    transport = _make_transport()
    client = _make_client(transport)

    assert client._owned_transport is transport
    # The API stores the same transport instance for its own routing.
    assert client._transport is transport


@pytest.mark.asyncio
async def test_connect_delegates_to_owned_transport() -> None:
    transport = _make_transport()
    transport.connected = False
    client = _make_client(transport)

    await client.connect()

    transport.connect.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_disconnect_delegates_to_owned_transport() -> None:
    transport = _make_transport()
    client = _make_client(transport)

    await client.disconnect()

    transport.close.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_force_reconnect_closes_then_connects() -> None:
    """API 1.0 force_reconnect is close+connect on the transport."""
    transport = _make_transport()

    async def close_then_mark_disconnected() -> None:
        transport.connected = False

    transport.close.side_effect = close_then_mark_disconnected
    client = _make_client(transport)

    await client.force_reconnect()

    transport.close.assert_awaited_once_with()
    transport.connect.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_read_register_routes_through_transport_input_read() -> None:
    transport = _make_transport()
    transport.read_input_registers.return_value = [7]
    client = _make_client(transport)

    reg = RegisterDef(1000, DataType.UCHAR, "uc")
    value = await client.read_register(reg)

    assert value == 7
    transport.read_input_registers.assert_awaited_once_with(address=1000, count=1)


@pytest.mark.asyncio
async def test_read_register_routes_holding_registers_correctly() -> None:
    transport = _make_transport()
    transport.read_holding_registers.return_value = [11, 12]
    client = _make_client(transport)

    reg = RegisterDef(1200, DataType.FLOAT, "f", register_type=RegisterType.HOLDING)
    value = await client.read_register(reg)

    assert value is not None
    transport.read_holding_registers.assert_awaited_once_with(address=1200, count=2)


@pytest.mark.asyncio
async def test_write_register_routes_through_transport_write() -> None:
    transport = _make_transport()
    client = _make_client(transport)

    reg = RegisterDef(1200, DataType.UCHAR, "uc", writable=True)
    await client.write_register(reg, 5)

    transport.write_registers.assert_awaited_once_with(address=1200, values=[5])


@pytest.mark.asyncio
async def test_exception_code_2_surfaces_as_illegal_address_error() -> None:
    """Backend code 2 must reach callers as IllegalAddressError (transport maps it)."""
    transport = _make_transport()
    transport.read_input_registers.side_effect = IllegalAddressError(
        "Illegal Data Address (exception_code=2): ...address 410..."
    )
    client = _make_client(transport, max_retries=1)

    reg = RegisterDef(410, DataType.UCHAR, "uc")
    with pytest.raises(IllegalAddressError) as exc_info:
        await client.read_register(reg)

    assert "exception_code=2" in str(exc_info.value)
    assert classify_write_error(exc_info.value) == "write_not_supported"
    # No retry on permanent errors.
    assert transport.read_input_registers.await_count == 1


@pytest.mark.asyncio
async def test_transient_code_6_surfaces_as_modbus_exception_after_in_place_retries() -> None:
    """Code 6 (translated by the transport to IdmModbusError) must reach
    callers as IdmModbusError with the marker string and be retried in place
    by the API retry loop (no reconnect, no quarantine)."""
    transport = _make_transport()
    transport.read_input_registers.side_effect = IdmDeviceError("...address 411... (exception_code=6)")
    client = _make_client(transport, max_retries=3)

    reg = RegisterDef(411, DataType.UCHAR, "uc")
    with pytest.raises(IdmModbusError, match="exception_code=6") as exc_info:
        await client.read_register(reg)

    assert not isinstance(exc_info.value, IdmTransportError)
    assert transport.read_input_registers.await_count == 3
    assert transport.close.await_count == 0


@pytest.mark.asyncio
async def test_read_batch_uses_transport_and_returns_decoded_values() -> None:
    transport = _make_transport()
    transport.read_input_registers.return_value = [0, 16800]
    client = _make_client(transport)

    registers = [
        RegisterDef(1000, DataType.FLOAT, "temp"),
    ]
    result = await client.read_batch(registers)

    assert "temp" in result
    transport.read_input_registers.assert_awaited_once_with(address=1000, count=2)


def test_transport_diagnostics_pass_through_redacted_payload() -> None:
    transport = _make_transport()
    safe_diagnostics = {
        "endpoint": {"host": "**REDACTED**", "port": 1502, "slave_id": 7},
        "capabilities": {"source": "modbus_connection.tmodbus"},
        "connected": True,
    }
    transport.as_redacted_diagnostics = MagicMock(return_value=safe_diagnostics)
    client = _make_client(transport)

    diagnostics = client.transport_diagnostics()

    assert diagnostics == safe_diagnostics
    assert "private-heatpump.example" not in repr(diagnostics)
    transport.as_redacted_diagnostics.assert_called_once_with()


def test_repr_identifies_wrapper_class() -> None:
    transport = _make_transport()
    client = _make_client(transport)

    # repr is a developer-facing identifier, not a diagnostics export; it should
    # name the wrapper class so logs distinguish it from the plain API client.
    assert "IdmModbusConnectionClient" in repr(client)
    assert "connected=" in repr(client)


def test_backend_exception_constants_are_not_duplicated_in_client() -> None:
    """The wrapper must not re-declare the exception-code taxonomy; the
    transport owns it now.  This guards against accidental re-introduction of
    the old private retry loop constants."""
    from custom_components.idm_heatpump import modbus_client as client_module

    assert not hasattr(client_module, "_NON_RETRYABLE_DEVICE_EXCEPTION_CODES")
    assert not hasattr(client_module, "_TRANSIENT_DEVICE_EXCEPTION_CODES")
    assert not hasattr(client_module, "_translate_transport_error")
    assert not hasattr(client_module, "_run_transport_command")


def test_client_hands_pacing_to_its_own_transport() -> None:
    """Per-entry pacing must reach the owned transport's endpoint."""
    client = IdmModbusConnectionClient(
        host="192.0.2.1",
        message_spacing=0.05,
        connect_delay=1.0,
    )

    endpoint = client._owned_transport.endpoint
    assert endpoint.message_spacing == 0.05
    assert endpoint.connect_delay == 1.0
    diagnostics = client.transport_diagnostics()
    assert diagnostics["endpoint"]["message_spacing"] == 0.05  # type: ignore[index]
    assert diagnostics["endpoint"]["connect_delay"] == 1.0  # type: ignore[index]


def test_client_defaults_to_an_unpaced_link() -> None:
    """Without explicit pacing the link keeps its current back-to-back behaviour."""
    endpoint = IdmModbusConnectionClient(host="192.0.2.1")._owned_transport.endpoint

    assert endpoint.message_spacing == 0.0
    assert endpoint.connect_delay == 0.0
