"""Tests for the IDM API bridge backed by ``modbus-connection``."""

from __future__ import annotations

import asyncio
from importlib.metadata import PackageNotFoundError, version
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from idm_heatpump import DataType, IllegalAddressError, RegisterDef, RETRY_BACKOFF_BASE, RegisterType
from modbus_connection import (
    ModbusConnectionError,
    ModbusError,
    ModbusExceptionError,
    ModbusProtocolError,
    ModbusTimeoutError,
)
from pymodbus.exceptions import ConnectionException, ModbusException, ModbusIOException

from custom_components.idm_heatpump.error_messages import classify_write_error
from custom_components.idm_heatpump.modbus_client import IdmModbusConnectionClient


try:
    _IDM_API_VERSION = version("idm-heatpump-api")
except PackageNotFoundError:
    _IDM_API_VERSION = "unavailable"


def _make_transport() -> MagicMock:
    """Return a raw transport double with explicit async operations."""
    transport = MagicMock()
    transport.is_connected = False
    transport.async_connect = AsyncMock()
    transport.async_close = AsyncMock()
    transport.async_reconnect = AsyncMock()
    transport.async_read_holding_registers = AsyncMock()
    transport.async_read_input_registers = AsyncMock()
    transport.async_write_registers = AsyncMock()
    transport.as_redacted_diagnostics = MagicMock()
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


@pytest.mark.asyncio
async def test_client_lifecycle_delegates_to_owned_transport() -> None:
    transport = _make_transport()
    transport.is_connected = True
    client = _make_client(transport)

    assert client.is_connected is True

    await client.connect()
    await client.force_reconnect()
    await client.disconnect()

    transport.async_connect.assert_awaited_once_with()
    transport.async_reconnect.assert_awaited_once_with()
    transport.async_close.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_client_routes_holding_input_and_write_commands() -> None:
    transport = _make_transport()
    transport.async_read_holding_registers.return_value = (11, 12)
    transport.async_read_input_registers.return_value = (21, 22, 23)
    client = _make_client(transport)

    holding = await client._read_registers(100, 2, RegisterType.HOLDING)
    input_words = await client._read_registers(200, 3, RegisterType.INPUT)
    await client._write_registers(300, [0, 65535, 42])

    assert holding == [11, 12]
    assert input_words == [21, 22, 23]
    transport.async_read_holding_registers.assert_awaited_once_with(100, 2)
    transport.async_read_input_registers.assert_awaited_once_with(200, 3)
    transport.async_write_registers.assert_awaited_once_with(300, (0, 65535, 42))


@pytest.mark.asyncio
async def test_illegal_address_is_translated_without_retry() -> None:
    transport = _make_transport()
    backend_error = ModbusExceptionError(exception_code=2, message="device rejected request")
    transport.async_read_input_registers.side_effect = backend_error
    client = _make_client(transport, max_retries=4)

    with (
        patch(
            "custom_components.idm_heatpump.modbus_client.asyncio.sleep",
            new_callable=AsyncMock,
        ) as sleep,
        pytest.raises(IllegalAddressError, match="address 410") as exc_info,
    ):
        await client._read_registers(410, 1, RegisterType.INPUT)

    assert exc_info.value.__cause__ is backend_error
    assert "Illegal Data Address" in str(exc_info.value)
    assert "exception_code=2" in str(exc_info.value)
    assert classify_write_error(exc_info.value) == "write_not_supported"
    assert transport.async_read_input_registers.await_count == 1
    sleep.assert_not_awaited()


@pytest.mark.asyncio
async def test_server_busy_is_not_retried_above_the_backend() -> None:
    transport = _make_transport()
    backend_error = ModbusExceptionError(exception_code=6, message="server device busy")
    transport.async_read_input_registers.side_effect = backend_error
    client = _make_client(transport, max_retries=4)

    with (
        patch(
            "custom_components.idm_heatpump.modbus_client.asyncio.sleep",
            new_callable=AsyncMock,
        ) as sleep,
        pytest.raises(ModbusIOException, match="exception_code=6"),
    ):
        await client._read_registers(411, 1, RegisterType.INPUT)

    assert transport.async_read_input_registers.await_count == 1
    transport.async_reconnect.assert_not_awaited()
    sleep.assert_not_awaited()


@pytest.mark.parametrize("exception_code", [5, 10, 11])
@pytest.mark.asyncio
async def test_transient_device_exceptions_retry_without_reconnect(exception_code: int) -> None:
    transport = _make_transport()
    transport.async_read_input_registers.side_effect = ModbusExceptionError(
        exception_code=exception_code,
        message="transient device or gateway response",
    )
    client = _make_client(transport, max_retries=3)

    with (
        patch(
            "custom_components.idm_heatpump.modbus_client.asyncio.sleep",
            new_callable=AsyncMock,
        ) as sleep,
        pytest.raises(ModbusIOException, match=rf"exception_code={exception_code}"),
    ):
        await client._read_registers(412, 1, RegisterType.INPUT)

    assert transport.async_read_input_registers.await_count == 3
    transport.async_reconnect.assert_not_awaited()
    assert sleep.await_args_list == [
        call(RETRY_BACKOFF_BASE),
        call(RETRY_BACKOFF_BASE * 2),
    ]


@pytest.mark.skipif(
    _IDM_API_VERSION != "0.9.1",
    reason="requires the exact pinned idm-heatpump-api 0.9.1 read_batch implementation",
)
@pytest.mark.parametrize(
    ("exception_code", "expected_attempts"),
    [(5, 4), (6, 1), (10, 4), (11, 4)],
)
@pytest.mark.asyncio
async def test_transient_device_exception_read_batch_does_not_fallback_or_quarantine_registers(
    exception_code: int,
    expected_attempts: int,
) -> None:
    """Keep transient device responses out of API per-register failure tracking."""
    transport = _make_transport()
    transport.is_connected = True
    transport.async_read_input_registers.side_effect = ModbusExceptionError(
        exception_code=exception_code,
        message="transient device or gateway response",
    )
    client = _make_client(transport, max_retries=4)
    registers = [
        RegisterDef(1000, DataType.FLOAT, "busy_batch_first"),
        RegisterDef(1002, DataType.FLOAT, "busy_batch_second"),
    ]

    with (
        patch(
            "custom_components.idm_heatpump.modbus_client.asyncio.sleep",
            new_callable=AsyncMock,
        ) as sleep,
        pytest.raises(ModbusIOException, match=rf"exception_code={exception_code}"),
    ):
        await client.read_batch(registers)

    assert transport.async_read_input_registers.await_args_list == [call(1000, 4)] * expected_attempts
    assert sleep.await_args_list == [
        call(RETRY_BACKOFF_BASE * (2**attempt)) for attempt in range(expected_attempts - 1)
    ]
    transport.async_reconnect.assert_not_awaited()
    assert client.get_unsupported_registers() == ()
    assert client.get_diagnostics().permanently_failed_registers == ()


@pytest.mark.parametrize(
    ("backend_error", "expected_type"),
    [
        pytest.param(ModbusTimeoutError("timed out"), TimeoutError, id="timeout"),
        pytest.param(ModbusConnectionError("link down"), ConnectionException, id="connection"),
        pytest.param(ModbusProtocolError("bad frame"), ModbusIOException, id="protocol"),
        pytest.param(
            ModbusExceptionError(exception_code=3, message="illegal value"),
            ModbusException,
            id="device-exception",
        ),
        pytest.param(
            ModbusExceptionError(exception_code=4, message="server device failure"),
            ModbusException,
            id="server-device-failure-remains-generic",
        ),
        pytest.param(ModbusError("backend failure"), ModbusException, id="generic"),
    ],
)
@pytest.mark.asyncio
async def test_neutral_transport_errors_are_translated_to_library_contract(
    backend_error: ModbusError,
    expected_type: type[Exception],
) -> None:
    transport = _make_transport()
    transport.async_read_input_registers.side_effect = backend_error
    client = _make_client(transport, max_retries=1)

    with pytest.raises(expected_type, match="Modbus read at address 420") as exc_info:
        await client._read_registers(420, 1, RegisterType.INPUT)

    assert type(exc_info.value) is expected_type
    assert exc_info.value.__cause__ is backend_error


@pytest.mark.asyncio
async def test_transient_errors_retry_with_exponential_backoff() -> None:
    transport = _make_transport()
    transport.async_read_input_registers.side_effect = [
        ModbusConnectionError("first drop"),
        ModbusTimeoutError("second drop"),
        (101, 102),
    ]
    client = _make_client(transport, max_retries=3)

    with patch(
        "custom_components.idm_heatpump.modbus_client.asyncio.sleep",
        new_callable=AsyncMock,
    ) as sleep:
        result = await client._read_registers(500, 2, RegisterType.INPUT)

    assert result == [101, 102]
    assert transport.async_read_input_registers.await_count == 3
    assert sleep.await_args_list == [
        call(RETRY_BACKOFF_BASE),
        call(RETRY_BACKOFF_BASE * 2),
    ]
    assert transport.async_reconnect.await_count == 2
    assert client._connection_suspect is False


@pytest.mark.asyncio
async def test_concurrent_suspect_checks_share_one_reconnect() -> None:
    transport = _make_transport()
    transport.is_connected = True
    client = _make_client(transport)
    client._connection_suspect = True

    await asyncio.gather(client._ensure_connected(), client._ensure_connected())

    transport.async_reconnect.assert_awaited_once_with()
    assert client._connection_suspect is False


@pytest.mark.asyncio
async def test_incomplete_response_is_retried_then_raised_as_protocol_error() -> None:
    transport = _make_transport()
    transport.async_read_holding_registers.return_value = (10,)
    client = _make_client(transport, max_retries=2)

    with (
        patch(
            "custom_components.idm_heatpump.modbus_client.asyncio.sleep",
            new_callable=AsyncMock,
        ) as sleep,
        pytest.raises(ModbusIOException, match=r"got 1 registers, expected 2") as exc_info,
    ):
        await client._read_registers(600, 2, RegisterType.HOLDING)

    assert isinstance(exc_info.value.__cause__, ModbusProtocolError)
    assert transport.async_read_holding_registers.await_count == 2
    sleep.assert_awaited_once_with(RETRY_BACKOFF_BASE)


def test_client_transport_diagnostics_remain_redacted() -> None:
    transport = _make_transport()
    safe_diagnostics = {
        "endpoint": {"host": "**REDACTED**", "port": 1502, "slave_id": 7},
        "capabilities": {"source": "modbus_connection.tmodbus"},
        "connected": True,
    }
    transport.as_redacted_diagnostics.return_value = safe_diagnostics
    client = _make_client(transport)

    diagnostics = client.transport_diagnostics()

    assert diagnostics == safe_diagnostics
    assert "private-heatpump.example" not in repr(diagnostics)
    transport.as_redacted_diagnostics.assert_called_once_with()
