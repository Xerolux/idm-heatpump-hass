"""Bridge ``idm_heatpump-api`` to the backend-neutral Modbus transport.

With API 1.0 the IDM device library accepts an injectable transport via its
``transport=`` constructor parameter.  This thin wrapper builds a
:class:`ModbusConnectionTransport` (tmodbus-backed) and injects it, so the API
owns every public operation (connection lifecycle, retry loop, batching,
decoding, model detection, write safety) and this class no longer overrides
private API hooks or duplicates the retry loop.

Backend-neutral ``ModbusError`` failures are translated to the API's exception
contract inside the transport (see :mod:`.modbus_transport`), so the API retry
loop classifies them correctly without any private-method overrides here.
"""

from __future__ import annotations

from idm_heatpump import IdmModbusClient

from .modbus_shared_transport import HaModbusTransport, SharedModbusUnitTransport
from .modbus_transport import ModbusConnectionTransport, ModbusTcpEndpoint


class IdmModbusConnectionClient(IdmModbusClient):
    """Use the IDM API's device logic with a tmodbus-backed raw transport.

    The API 1.0 ``transport=`` constructor parameter receives either the
    owned :class:`ModbusConnectionTransport` (private per-entry socket) or a
    :class:`SharedModbusUnitTransport` claiming Home Assistant's shared
    Modbus connection (2026.10+).  All public operations (model detection,
    batch planning, decoding, write safety, retry, reconnect) are implemented
    by the API; this class only adds transport-aware diagnostics.

    ``message_spacing`` and ``connect_delay`` are connection-wide pacing.  On
    the owned transport they reach ``modbus-connection`` directly; on the
    shared transport they are negotiated per unit as floors, and a ready-made
    ``transport`` ignores them entirely.
    """

    def __init__(
        self,
        host: str,
        port: int = 502,
        slave_id: int = 1,
        timeout: float = 10.0,
        max_retries: int = 3,
        *,
        message_spacing: float = 0.0,
        connect_delay: float = 0.0,
        transport: HaModbusTransport | None = None,
    ) -> None:
        endpoint = ModbusTcpEndpoint(
            host=host,
            port=port,
            slave_id=slave_id,
            timeout=timeout,
            retries=max_retries,
            message_spacing=message_spacing,
            connect_delay=connect_delay,
        )
        owned_transport = transport or ModbusConnectionTransport(endpoint)
        super().__init__(
            host=host,
            port=port,
            slave_id=slave_id,
            timeout=timeout,
            max_retries=max_retries,
            transport=owned_transport,
        )
        # Keep a dedicated handle to the transport so diagnostics can reach the
        # backend-neutral details without relying on the API's private attribute.
        self._owned_transport: HaModbusTransport = owned_transport

    def __repr__(self) -> str:
        return f"IdmModbusConnectionClient(host={self.host!r}, port={self.port}, connected={self.is_connected})"

    def transport_diagnostics(self) -> dict[str, object]:
        """Return redaction-safe transport details for HA diagnostics."""
        return self._owned_transport.as_redacted_diagnostics()


__all__ = ["IdmModbusConnectionClient", "SharedModbusUnitTransport"]
