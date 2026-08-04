"""Backend-neutral Modbus transport contract and tmodbus implementation.

The IDM device model remains in ``idm-heatpump-api``.  This module owns only
the physical connection and exposes raw register words so the API continues to
handle batching, decoding, model detection and write safety.

The transport implements the API 1.0 ``IdmModbusTransport`` protocol
(``connect``/``close``/``connected`` plus keyword-only ``read_*``/``write_*``
methods returning ``list[int]``).  Backend-neutral ``ModbusError`` failures are
translated to the API's established exception contract
(:class:`~idm_heatpump.IllegalAddressError` for code 2,
:class:`~pymodbus.exceptions.ModbusIOException` for transient device codes 5/6/10/11,
:class:`~pymodbus.exceptions.ConnectionException`/``TimeoutError`` for transport
failures) before they leave the transport, so the API retry loop classifies
them correctly.  The string markers (``exception_code=2`` etc.) are preserved
verbatim because the Home Assistant coordinator relies on them for bisect logic.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeVar

from modbus_connection import (
    ModbusConnectionError,
    ModbusError,
    ModbusExceptionError,
    ModbusProtocolError,
    ModbusTcpParams,
    ModbusTimeoutError,
    ModbusUnit,
)
from modbus_connection.tmodbus import ModbusConnection
from pymodbus.exceptions import ConnectionException, ModbusException, ModbusIOException

from idm_heatpump import IllegalAddressError

type ModbusTransportDiagnosticValue = bool | float | int | str

_LOGGER = logging.getLogger(__name__)

# Exception codes that are permanent for a given address (code 2) or that the
# tmodbus backend already retries internally (code 6, Slave Device Busy).  Both
# must surface without a second API retry so retries are not stacked.
_NON_RETRYABLE_DEVICE_EXCEPTION_CODES = frozenset({2, 6})

# Exception codes that are transient for the endpoint, not evidence that any
# register in the requested batch is unsupported.  The transport maps these to
# ``ModbusIOException`` so the API retry loop treats them as transport-level
# failures (retry in place, no per-register fallback, no quarantine).
_TRANSIENT_DEVICE_EXCEPTION_CODES = frozenset({5, 6, 10, 11})

_T = TypeVar("_T")


def _translate_backend_error(error: ModbusError, operation: str, address: int) -> Exception:
    """Map a backend-neutral error to the API's established exception contract.

    The string markers (``exception_code=2``, ``exception_code=<N>``) are
    preserved verbatim because the Home Assistant coordinator matches on them
    to detect illegal-address responses and trigger batch bisect logic.
    """
    message = f"Modbus {operation} at address {address} failed: {error}"
    if isinstance(error, ModbusExceptionError):
        if error.exception_code == 2:
            return IllegalAddressError(f"Illegal Data Address (exception_code=2): {message}")
        if error.exception_code in _TRANSIENT_DEVICE_EXCEPTION_CODES:
            # Acknowledge, Server Device Busy, and gateway availability errors
            # are transient for the endpoint.  Map to ModbusIOException so the
            # API retry loop retries in place without reconnecting, without
            # fanning out into per-register reads, and without permanently
            # quarantining registers.  Code 6 remains non-retryable here because
            # the tmodbus backend owns its busy-response policy.
            return ModbusIOException(f"{message} (exception_code={error.exception_code})")
        return ModbusException(f"{message} (exception_code={error.exception_code})")
    if isinstance(error, ModbusTimeoutError):
        return TimeoutError(message)
    if isinstance(error, ModbusConnectionError):
        return ConnectionException(message)
    if isinstance(error, ModbusProtocolError):
        return ModbusIOException(message)
    return ModbusException(message)


async def _invoke_backend(
    operation: str,
    address: int,
    coroutine: Awaitable[_T],
) -> _T:
    """Await a backend coroutine, translating ``ModbusError`` to API exceptions."""
    try:
        return await coroutine
    except ModbusError as error:
        raise _translate_backend_error(error, operation, address) from error


@dataclass(frozen=True, slots=True)
class ModbusTcpEndpoint:
    """Connection identity for an IDM Modbus TCP endpoint."""

    host: str
    port: int
    slave_id: int
    timeout: float
    retries: int

    def __post_init__(self) -> None:
        """Validate the static endpoint definition before any transport uses it."""
        if not self.host.strip():
            raise ValueError("host must not be empty")
        if not 1 <= self.port <= 65535:
            raise ValueError("port must be between 1 and 65535")
        if not 1 <= self.slave_id <= 247:
            raise ValueError("slave_id must be between 1 and 247")
        if self.timeout <= 0:
            raise ValueError("timeout must be greater than 0")
        if self.retries < 0:
            raise ValueError("retries must not be negative")

    @property
    def connection_key(self) -> tuple[str, int, int]:
        """Return the stable key used to detect duplicate endpoint usage."""
        return (self.host.strip().lower(), self.port, self.slave_id)

    def as_redacted_diagnostics(self) -> dict[str, ModbusTransportDiagnosticValue]:
        """Return endpoint diagnostics without exposing the host name or IP address."""
        return {
            "host": "**REDACTED**",
            "port": self.port,
            "slave_id": self.slave_id,
            "timeout": self.timeout,
            "retries": self.retries,
        }


@dataclass(frozen=True, slots=True)
class ModbusTransportCapabilities:
    """Static capabilities of one concrete Modbus transport implementation."""

    source: str
    owns_socket: bool
    supports_shared_connection: bool = False

    def as_diagnostics(self) -> dict[str, ModbusTransportDiagnosticValue]:
        """Return diagnostics-safe static transport capabilities."""
        return {
            "source": self.source,
            "owns_socket": self.owns_socket,
            "supports_shared_connection": self.supports_shared_connection,
        }


type ModbusConnectionFactory = Callable[[ModbusTcpEndpoint], ModbusConnection]


def _create_tmodbus_connection(endpoint: ModbusTcpEndpoint) -> ModbusConnection:
    """Create the real backend connection without performing network I/O."""
    return ModbusConnection(
        ModbusTcpParams(host=endpoint.host.strip(), port=endpoint.port),
        timeout=endpoint.timeout,
    )


class ModbusConnectionTransport:
    """Raw IDM transport backed by ``modbus-connection`` and tmodbus.

    Implements the API 1.0 ``IdmModbusTransport`` protocol (``connect``/``close``/
    ``connected`` plus keyword-only ``read_*``/``write_*`` returning ``list[int]``).
    One instance owns one connection for one Home Assistant config entry.  The
    upstream connection serializes requests, connects on demand and reconnects
    on the next request after a dropped link.  Cross-entry sharing is not claimed
    here because Home Assistant's central sharing layer is not public.

    Backend-neutral ``ModbusError`` failures are translated to the API's exception
    contract (``IllegalAddressError``/``ModbusException``/``ConnectionException``/
    ``ModbusIOException``/``TimeoutError``) before they propagate, so the API
    retry loop classifies them correctly without any private-method overrides.
    """

    capabilities = ModbusTransportCapabilities(
        source="modbus_connection.tmodbus",
        owns_socket=True,
        supports_shared_connection=False,
    )

    def __init__(
        self,
        endpoint: ModbusTcpEndpoint,
        *,
        connection_factory: ModbusConnectionFactory | None = None,
    ) -> None:
        self._endpoint = endpoint
        self._connection_factory = connection_factory or _create_tmodbus_connection
        self._connection, self._unit = self._new_connection()
        self._closed = False

    def _new_connection(self) -> tuple[ModbusConnection, ModbusUnit]:
        """Create one connection generation and bind the configured unit."""
        connection = self._connection_factory(self._endpoint)
        return connection, connection.for_unit(self._endpoint.slave_id)

    @property
    def endpoint(self) -> ModbusTcpEndpoint:
        """Return the immutable endpoint definition."""
        return self._endpoint

    @property
    def connected(self) -> bool:
        """Return the current connection state without opening the socket."""
        return not self._closed and self._connection.connected

    async def connect(self) -> None:
        """Establish the connection for setup-time validation.

        Re-opens a fresh connection generation after :meth:`close` so the
        transport is reusable.  Translates backend errors to the API contract.
        """
        if self._closed:
            self._connection, self._unit = self._new_connection()
            self._closed = False
        try:
            await self._connection.connect()
        except ModbusError as error:
            raise _translate_backend_error(error, "connect", 0) from error

    async def close(self) -> None:
        """Close the owned connection exactly once (idempotent)."""
        if self._closed:
            return
        self._closed = True
        try:
            await self._connection.close()
        except ModbusError as error:
            raise _translate_backend_error(error, "disconnect", 0) from error

    async def read_holding_registers(self, *, address: int, count: int) -> list[int]:
        """Read raw holding-register words (function code 03)."""
        words = await _invoke_backend(
            "read",
            address,
            self._unit.read_holding_registers(address, count),
        )
        return list(words)

    async def read_input_registers(self, *, address: int, count: int) -> list[int]:
        """Read raw input-register words (function code 04)."""
        words = await _invoke_backend(
            "read",
            address,
            self._unit.read_input_registers(address, count),
        )
        return list(words)

    async def write_registers(self, *, address: int, values: list[int]) -> None:
        """Write raw holding-register words with function code 16."""
        await _invoke_backend(
            "write",
            address,
            self._unit.write_registers(address, [int(value) for value in values]),
        )

    def as_redacted_diagnostics(self) -> dict[str, object]:
        """Return connection diagnostics without exposing the host."""
        return {
            "endpoint": self._endpoint.as_redacted_diagnostics(),
            "capabilities": self.capabilities.as_diagnostics(),
            "connected": self.connected,
        }


__all__ = [
    "ModbusConnectionFactory",
    "ModbusConnectionTransport",
    "ModbusTcpEndpoint",
    "ModbusTransportCapabilities",
    "ModbusTransportDiagnosticValue",
]
