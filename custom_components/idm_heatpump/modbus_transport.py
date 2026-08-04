"""Backend-neutral Modbus transport contract and tmodbus implementation.

The IDM device model remains in ``idm-heatpump-api``.  This module owns only
the physical connection and exposes raw register words so the API continues to
handle batching, decoding, model detection and write safety.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from modbus_connection import ModbusTcpParams, ModbusUnit
from modbus_connection.tmodbus import ModbusConnection

type ModbusTransportDiagnosticValue = bool | float | int | str

_LOGGER = logging.getLogger(__name__)


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


@runtime_checkable
class IdmModbusTransport(Protocol):
    """Minimal async Modbus transport contract for device-library adapters.

    The contract deliberately uses raw register addresses and register-word
    payloads. Register metadata, batching, decoding, encoding and write-safety
    rules remain responsibilities of ``idm-heatpump-api``.
    """

    @property
    def endpoint(self) -> ModbusTcpEndpoint:
        """Return the endpoint identity used for conflict and diagnostics logic."""

    @property
    def capabilities(self) -> ModbusTransportCapabilities:
        """Return static information about socket ownership and sharing support."""

    async def async_connect(self) -> None:
        """Open or reserve the transport."""

    async def async_close(self) -> None:
        """Release the transport."""

    async def async_read_holding_registers(self, address: int, count: int) -> tuple[int, ...]:
        """Read raw holding-register words from the device."""

    async def async_read_input_registers(self, address: int, count: int) -> tuple[int, ...]:
        """Read raw input-register words from the device."""

    async def async_write_registers(self, address: int, values: tuple[int, ...]) -> None:
        """Write raw holding-register words to the device."""


class _ModbusConnection(Protocol):
    """Narrow connection surface used by the concrete transport and its tests."""

    @property
    def connected(self) -> bool:
        """Return whether the physical connection is currently established."""

    def for_unit(self, unit_id: int) -> ModbusUnit:
        """Return a handle bound to one Modbus unit ID."""

    async def connect(self) -> None:
        """Establish the connection eagerly."""

    async def close(self) -> None:
        """Permanently close the connection."""


type ModbusConnectionFactory = Callable[[ModbusTcpEndpoint], _ModbusConnection]


def _create_tmodbus_connection(endpoint: ModbusTcpEndpoint) -> _ModbusConnection:
    """Create the real backend connection without performing network I/O."""
    return ModbusConnection(
        ModbusTcpParams(host=endpoint.host.strip(), port=endpoint.port),
        timeout=endpoint.timeout,
    )


class ModbusConnectionTransport:
    """Raw IDM transport backed by ``modbus-connection`` and tmodbus.

    One instance owns one connection for one Home Assistant config entry.  The
    upstream connection serializes requests, connects on demand and reconnects
    on the next request after a dropped link.  Cross-entry sharing is not
    claimed here because Home Assistant's central sharing layer is not public.
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

    def _new_connection(self) -> tuple[_ModbusConnection, ModbusUnit]:
        """Create one connection generation and bind the configured unit."""
        connection = self._connection_factory(self._endpoint)
        return connection, connection.for_unit(self._endpoint.slave_id)

    @property
    def endpoint(self) -> ModbusTcpEndpoint:
        """Return the immutable endpoint definition."""
        return self._endpoint

    @property
    def is_connected(self) -> bool:
        """Return the current connection state without opening the socket."""
        return not self._closed and self._connection.connected

    async def async_connect(self) -> None:
        """Establish the connection for setup-time validation."""
        if self._closed:
            self._connection, self._unit = self._new_connection()
            self._closed = False
        await self._connection.connect()

    async def async_close(self) -> None:
        """Close the owned connection exactly once."""
        if self._closed:
            return
        self._closed = True
        await self._connection.close()

    async def async_reconnect(self) -> None:
        """Replace the connection when a caller explicitly requests a reset.

        Normal link loss does not use this method: ``modbus-connection`` marks
        the link down and the next unit operation reconnects automatically.
        """
        if not self._closed:
            try:
                await self._connection.close()
            except Exception:
                _LOGGER.debug(
                    "Error closing suspect Modbus connection before replacement",
                    exc_info=True,
                )
        self._connection, self._unit = self._new_connection()
        self._closed = False
        await self._connection.connect()

    async def async_read_holding_registers(self, address: int, count: int) -> tuple[int, ...]:
        """Read raw holding-register words (function code 03)."""
        return tuple(await self._unit.read_holding_registers(address, count))

    async def async_read_input_registers(self, address: int, count: int) -> tuple[int, ...]:
        """Read raw input-register words (function code 04)."""
        return tuple(await self._unit.read_input_registers(address, count))

    async def async_write_registers(self, address: int, values: tuple[int, ...]) -> None:
        """Write raw holding-register words with function code 16."""
        await self._unit.write_registers(address, [int(value) for value in values])

    def as_redacted_diagnostics(self) -> dict[str, object]:
        """Return connection diagnostics without exposing the host."""
        return {
            "endpoint": self._endpoint.as_redacted_diagnostics(),
            "capabilities": self.capabilities.as_diagnostics(),
            "connected": self.is_connected,
        }


__all__ = [
    "IdmModbusTransport",
    "ModbusConnectionFactory",
    "ModbusConnectionTransport",
    "ModbusTcpEndpoint",
    "ModbusTransportCapabilities",
    "ModbusTransportDiagnosticValue",
]
