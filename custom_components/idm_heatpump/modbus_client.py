"""Bridge ``idm-heatpump-api`` to the backend-neutral Modbus transport."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from modbus_connection import (
    ModbusConnectionError,
    ModbusError,
    ModbusExceptionError,
    ModbusProtocolError,
    ModbusTimeoutError,
)
from pymodbus.exceptions import ConnectionException, ModbusException, ModbusIOException

from idm_heatpump import (
    RETRY_BACKOFF_BASE,
    IdmModbusClient,
    IllegalAddressError,
    RegisterType,
)

from .modbus_transport import ModbusConnectionTransport, ModbusTcpEndpoint

_T = TypeVar("_T")
_NON_RETRYABLE_DEVICE_EXCEPTION_CODES = frozenset({2, 6})
_TRANSIENT_DEVICE_EXCEPTION_CODES = frozenset({5, 6, 10, 11})


def _translate_transport_error(error: ModbusError, operation: str, address: int) -> Exception:
    """Map backend-neutral errors to the API's established error contract."""
    message = f"Modbus {operation} at address {address} failed: {error}"
    if isinstance(error, ModbusExceptionError):
        if error.exception_code == 2:
            return IllegalAddressError(f"Illegal Data Address (exception_code=2): {message}")
        if error.exception_code in _TRANSIENT_DEVICE_EXCEPTION_CODES:
            # Acknowledge, Server Device Busy, and gateway availability errors
            # are transient for the endpoint, not evidence that any register
            # in the requested batch is unsupported.  The pinned API re-raises
            # transport errors but falls back to individual reads for a generic
            # ModbusException; use its transport-error contract here so these
            # responses cannot fan out into per-register reads and permanent
            # register quarantine.  Code 6 remains non-retryable in this
            # adapter because the tmodbus backend owns its busy-response policy.
            return ModbusIOException(f"{message} (exception_code={error.exception_code})")
        return ModbusException(f"{message} (exception_code={error.exception_code})")
    if isinstance(error, ModbusTimeoutError):
        return TimeoutError(message)
    if isinstance(error, ModbusConnectionError):
        return ConnectionException(message)
    if isinstance(error, ModbusProtocolError):
        return ModbusIOException(message)
    return ModbusException(message)


class IdmModbusConnectionClient(IdmModbusClient):
    """Use the IDM API's device logic with a tmodbus-backed raw transport.

    ``idm-heatpump-api`` 0.9.1 still constructs Pymodbus internally.  This
    narrow adapter replaces only its protected raw-I/O hooks; every public
    operation (model detection, batch planning, decoding and write safety)
    remains implemented by the pinned API version.
    """

    def __init__(
        self,
        host: str,
        port: int = 502,
        slave_id: int = 1,
        timeout: float = 10.0,
        max_retries: int = 3,
        *,
        transport: ModbusConnectionTransport | None = None,
    ) -> None:
        super().__init__(
            host=host,
            port=port,
            slave_id=slave_id,
            timeout=timeout,
            max_retries=max_retries,
        )
        endpoint = ModbusTcpEndpoint(
            host=host,
            port=port,
            slave_id=slave_id,
            timeout=timeout,
            retries=max_retries,
        )
        self._transport = transport or ModbusConnectionTransport(endpoint)

    def __repr__(self) -> str:
        return f"IdmModbusConnectionClient(host={self.host!r}, port={self.port}, connected={self.is_connected})"

    @property
    def is_connected(self) -> bool:
        """Return the connection state reported by ``modbus-connection``."""
        return self._transport.is_connected

    async def connect(self) -> None:
        """Connect eagerly during config-entry validation and setup."""
        async with self._lock:
            await self._connect_transport()

    async def _connect_transport(self) -> None:
        """Connect while the caller owns the API lifecycle lock."""
        try:
            await self._transport.async_connect()
        except ModbusError as error:
            translated = _translate_transport_error(error, "connect", 0)
            raise translated from error

    async def disconnect(self) -> None:
        """Close the config entry's owned connection."""
        async with self._lock:
            try:
                await self._transport.async_close()
            except ModbusError as error:
                translated = _translate_transport_error(error, "disconnect", 0)
                raise translated from error
            finally:
                self._connection_suspect = False

    async def force_reconnect(self) -> None:
        """Replace the connection only when explicitly requested by a caller."""
        async with self._lock:
            await self._reconnect_transport()
            self._connection_suspect = False

    async def _reconnect_transport(self) -> None:
        """Replace the connection while the caller owns the API lifecycle lock."""
        try:
            await self._transport.async_reconnect()
        except ModbusError as error:
            translated = _translate_transport_error(error, "reconnect", 0)
            raise translated from error

    async def _ensure_connected(self) -> Any:
        """Preserve the API hook while delegating connection ownership."""
        async with self._lock:
            if self._connection_suspect:
                await self._reconnect_transport()
                self._connection_suspect = False
            elif not self._transport.is_connected:
                await self._connect_transport()
        return self._transport

    async def _try_reconnect(self) -> None:
        """Replace a suspect link while preserving the API retry contract."""
        try:
            await self._transport.async_reconnect()
        except ModbusError:
            # Keep the replacement connection usable after a failed handshake.
            # The next unit request will perform another connect-on-demand attempt.
            return

    def _record_transport_error(
        self,
        operation: str,
        address: int,
        count: int,
        register_type: RegisterType,
        error: Exception,
        attempt: int,
    ) -> None:
        """Feed failures into API diagnostics when the pinned API supports it."""
        recorder = getattr(self, "_record_error_context", None)
        if callable(recorder):
            recorder(
                operation,
                address,
                count,
                register_type,
                error,
                attempt,
            )

    async def _run_transport_command(
        self,
        operation: str,
        address: int,
        count: int,
        register_type: RegisterType,
        command: Callable[[], Awaitable[_T]],
        *,
        max_retries: int | None = None,
    ) -> _T:
        """Run raw I/O with the API's configured retry and backoff policy."""
        retries = self._max_retries if max_retries is None else max(1, int(max_retries))
        async with self._lock:
            for attempt in range(1, retries + 1):
                try:
                    result = await command()
                    self._connection_suspect = False
                    return result
                except ModbusExceptionError as error:
                    translated = _translate_transport_error(error, operation, address)
                    self._connection_suspect = False
                    self._record_transport_error(
                        operation,
                        address,
                        count,
                        register_type,
                        translated,
                        attempt,
                    )
                    if error.exception_code in _NON_RETRYABLE_DEVICE_EXCEPTION_CODES or attempt == retries:
                        raise translated from error
                except ModbusError as error:
                    translated = _translate_transport_error(error, operation, address)
                    transport_failed = isinstance(
                        error,
                        (ModbusConnectionError, ModbusProtocolError, ModbusTimeoutError),
                    )
                    self._connection_suspect = transport_failed
                    self._record_transport_error(
                        operation,
                        address,
                        count,
                        register_type,
                        translated,
                        attempt,
                    )
                    if attempt == retries:
                        raise translated from error
                    if transport_failed:
                        await self._try_reconnect()
                except TimeoutError as error:
                    self._connection_suspect = True
                    self._record_transport_error(
                        operation,
                        address,
                        count,
                        register_type,
                        error,
                        attempt,
                    )
                    if attempt == retries:
                        raise
                    await self._try_reconnect()

                await asyncio.sleep(RETRY_BACKOFF_BASE * (2 ** (attempt - 1)))

        raise RuntimeError("Unreachable: retry count is always positive")

    async def _read_registers(
        self,
        address: int,
        count: int,
        reg_type: RegisterType = RegisterType.INPUT,
        *,
        max_retries: int | None = None,
        request_timeout: float | None = None,
    ) -> list[int]:
        """Read raw words through FC03 or FC04 without a Pymodbus client."""

        async def _read() -> list[int]:
            if reg_type == RegisterType.HOLDING:
                request = self._transport.async_read_holding_registers(address, count)
            else:
                request = self._transport.async_read_input_registers(address, count)
            words = (
                await asyncio.wait_for(request, timeout=request_timeout)
                if request_timeout is not None
                else await request
            )
            if len(words) != count:
                raise ModbusProtocolError(
                    f"Incomplete Modbus response at address {address}: got {len(words)} registers, expected {count}"
                )
            return [int(word) for word in words]

        return await self._run_transport_command(
            "read",
            address,
            count,
            reg_type,
            _read,
            max_retries=max_retries,
        )

    async def _write_registers(self, address: int, values: list[int]) -> None:
        """Write raw words through FC16 without a Pymodbus client."""

        async def _write() -> None:
            await self._transport.async_write_registers(
                address,
                tuple(int(value) for value in values),
            )

        await self._run_transport_command(
            "write",
            address,
            len(values),
            RegisterType.HOLDING,
            _write,
        )

    def transport_diagnostics(self) -> dict[str, object]:
        """Return redaction-safe transport details for HA diagnostics."""
        return self._transport.as_redacted_diagnostics()


__all__ = ["IdmModbusConnectionClient"]
