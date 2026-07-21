"""Future Modbus transport contract for IDM device-library adapters.

This module is intentionally not wired into the running integration yet. It
captures the narrow contract the external ``idm-heatpump-api`` can target when
Home Assistant finalizes its shared Modbus connection API, while the current
runtime continues to use the tested library ``IdmModbusClient`` path.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


type ModbusTransportDiagnosticValue = bool | float | int | str


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
        if not 0 <= self.slave_id <= 247:
            raise ValueError("slave_id must be between 0 and 247")
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
    """Minimal async Modbus transport contract for future adapters.

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

    async def async_write_registers(self, address: int, values: tuple[int, ...]) -> None:
        """Write raw holding-register words to the device."""


__all__ = [
    "IdmModbusTransport",
    "ModbusTcpEndpoint",
    "ModbusTransportDiagnosticValue",
    "ModbusTransportCapabilities",
]
