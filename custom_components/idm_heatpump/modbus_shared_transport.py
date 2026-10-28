"""Shared Modbus connection provider through Home Assistant's modbus component.

Home Assistant 2026.10 rebuilt its ``modbus`` integration on the same
``modbus-connection``/``tmodbus`` pair this integration already drives and
published the cross-integration sharing contract this module consumes:
``homeassistant.components.modbus.async_get_unit`` hands out a unit on a
connection keyed by the endpoint, shared and reference-counted between every
config entry and integration that asks for the same device.  Requests of all
consumers serialize behind the connection's lock, and the socket closes when
the last holder unloads — the private per-entry socket of
:class:`~.modbus_transport.ModbusConnectionTransport` remains the fallback for
Home Assistant releases without the contract (before 2026.10) and for the
short-lived config-flow probe.

The transport implements the API ``IdmModbusTransport`` protocol plus the
optional coil extension and declares ``connects_lazily`` (idm-heatpump-api
2.15.0): :meth:`SharedModbusUnitTransport.connect` acquires the shared claim
and negotiates this endpoint's timeout and pacing floors, while the wire
itself is opened by ``modbus-connection`` on the first request.  Closing is a
soft release of our claim by design — the link belongs to every holder, so it
must never be torn down for the others; the reference Home Assistant keeps on
our config entry ends with that entry's unload.
"""

from __future__ import annotations

import logging
import re
from importlib import import_module
from typing import TYPE_CHECKING, Any

from modbus_connection import ModbusTcpParams, ModbusUnit

from idm_heatpump import IdmConnectionError, IdmDeviceError

from .modbus_transport import (
    ModbusConnectionTransport,
    ModbusTcpEndpoint,
    ModbusTransportCapabilities,
    _invoke_backend,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

#: Domain of Home Assistant's built-in ``modbus`` integration.
SHARED_MODBUS_DOMAIN = "modbus"

#: First Home Assistant (major, minor) that publishes the sharing contract.
SHARED_MODBUS_MIN_HA_VERSION = (2026, 10)

_HA_VERSION_PATTERN = re.compile(r"(\d+)\.(\d+)\.(\d+)")

type HaModbusTransport = ModbusConnectionTransport | SharedModbusUnitTransport
"""Either production transport: the private per-entry socket or the shared claim."""


def _ha_version(hass: HomeAssistant) -> tuple[int, int, int] | None:
    """Return the running Home Assistant version, or ``None`` if unknowable.

    The stubbed unit suite provides no ``__version__``; an unparseable value
    is treated the same way so the caller stays on the private socket.
    """
    try:
        from homeassistant.const import __version__ as version
    except ImportError:
        return None
    match = _HA_VERSION_PATTERN.match(str(version))
    if match is None:
        return None
    major, minor, patch = (int(group) for group in match.groups())
    return (major, minor, patch)


def shared_modbus_supported(hass: HomeAssistant) -> bool:
    """Return whether this Home Assistant offers the shared Modbus contract.

    Feature detection is version-based on purpose: importing the component
    package must not happen on older releases because it would install the
    legacy pymodbus requirement this integration deliberately dropped.
    """
    version = _ha_version(hass)
    if version is None:
        return False
    return version[:2] >= SHARED_MODBUS_MIN_HA_VERSION


def _load_async_get_unit() -> Any | None:
    """Return ``modbus.async_get_unit``, or ``None`` when unavailable.

    Imported lazily so this module loads on every supported Home Assistant;
    ``import_module`` keeps strict mypy content on both the 2026.8 and the
    2026.10 trees, where the attribute exists on only one of them.
    """
    try:
        module = import_module("homeassistant.components.modbus")
    except Exception:  # noqa: BLE001 - pymodbus may be absent on partial installs
        return None
    getter = getattr(module, "async_get_unit", None)
    return getter if callable(getter) else None


class SharedModbusUnitTransport:
    """Raw IDM transport holding a claim on Home Assistant's shared connection.

    Implements the API ``IdmModbusTransport`` protocol (``connect``/``close``/
    ``connected`` plus keyword-only ``read_*``/``write_*`` returning
    ``list[int]``) and the optional ``IdmCoilTransportExtension``
    (``read_coils``/``write_coil``, FC01/FC05).  One instance serves one Home
    Assistant config entry on one shared connection that other entries and
    integrations may hold units on as well.

    ``connects_lazily`` is the idm-heatpump-api 2.15.0 declaration that the
    wire opens with the first request: the claim exists after
    :meth:`connect`, the socket state does not.  :meth:`close` releases only
    this transport's view of the claim — the shared link stays up for the
    other holders and our reference ends with the config entry's unload, per
    the Home Assistant contract.

    Backend-neutral ``ModbusError`` failures are translated to the API's
    exception contract by the same helpers the private transport uses, so the
    API retry loop classifies them identically.
    """

    connects_lazily = True

    capabilities = ModbusTransportCapabilities(
        source="homeassistant.modbus",
        owns_socket=False,
        supports_shared_connection=True,
    )

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        endpoint: ModbusTcpEndpoint,
    ) -> None:
        """Prepare the claim for ``endpoint`` without touching the network."""
        self._hass = hass
        self._entry = entry
        self._endpoint = endpoint
        self._unit: ModbusUnit | None = None

    @property
    def endpoint(self) -> ModbusTcpEndpoint:
        """Return the immutable endpoint definition."""
        return self._endpoint

    @property
    def connected(self) -> bool:
        """Return the live state of the shared link, claim or not."""
        return self._unit is not None and bool(self._unit.connected)

    async def connect(self) -> None:
        """Acquire (or keep) the shared claim and negotiate link floors.

        Re-acquires a claim after :meth:`close` so the transport stays
        reusable across the API client's reconnect cycles.  Home Assistant
        registers the hold's release on the config entry; calling this more
        than once per entry is safe because the underlying holder set is
        keyed by entry and unit id.
        """
        if self._unit is not None:
            return
        get_unit = _load_async_get_unit()
        if get_unit is None:
            raise IdmConnectionError("Home Assistant's shared Modbus connection API is unavailable")
        try:
            unit = get_unit(
                self._hass,
                self._entry,
                ModbusTcpParams(
                    host=self._endpoint.host.strip(),
                    port=self._endpoint.port,
                ),
                self._endpoint.slave_id,
            )
        except Exception as err:
            raise IdmConnectionError(f"Could not acquire the shared Modbus connection: {err}") from err
        self._unit = unit
        self._negotiate_link_options(unit)

    def _negotiate_link_options(self, unit: ModbusUnit) -> None:
        """Ask the shared link for this endpoint's timeout and pacing floors.

        The negotiation methods are part of the unit protocol on the pinned
        transport library; the ``getattr`` guard keeps older library floors
        working with their defaults instead of failing the claim.
        """
        requests: tuple[tuple[str, float], ...] = (
            ("require_timeout", self._endpoint.timeout),
            ("set_message_spacing", self._endpoint.message_spacing),
            ("require_connect_delay", self._endpoint.connect_delay),
        )
        for name, value in requests:
            method = getattr(unit, name, None)
            if callable(method):
                method(float(value))

    async def close(self) -> None:
        """Detach this transport from the shared claim (soft close).

        The shared connection itself stays open: other holders keep using it,
        and Home Assistant releases our reference when the config entry
        unloads.  A later :meth:`connect` re-acquires a claim.
        """
        self._unit = None

    def _require_unit(self) -> ModbusUnit:
        """Return the acquired unit or raise the API's connection error."""
        if self._unit is None:
            raise IdmConnectionError("The shared Modbus unit is not acquired; connect() first")
        return self._unit

    async def read_holding_registers(self, *, address: int, count: int) -> list[int]:
        """Read raw holding-register words (function code 03)."""
        words = await _invoke_backend(
            "read",
            address,
            self._require_unit().read_holding_registers(address, count),
        )
        return list(words)

    async def read_input_registers(self, *, address: int, count: int) -> list[int]:
        """Read raw input-register words (function code 04)."""
        words = await _invoke_backend(
            "read",
            address,
            self._require_unit().read_input_registers(address, count),
        )
        return list(words)

    async def write_registers(self, *, address: int, values: list[int]) -> None:
        """Write raw holding-register words with function code 16."""
        await _invoke_backend(
            "write",
            address,
            self._require_unit().write_registers(address, [int(value) for value in values]),
        )

    async def read_coils(self, *, address: int, count: int) -> list[bool]:
        """Read discrete coils with function code 01 (Navigator 1.x coil block)."""
        bits = await _invoke_backend(
            "read coils",
            address,
            self._require_unit().read_coils(address, count),
        )
        if len(bits) < count:
            # Same classification rule as the private transport: a device
            # answer with the wrong length is a device failure, so the API's
            # batch fallback can isolate the address instead of reconnecting.
            raise IdmDeviceError(
                f"Incomplete coil response at address {address}: got {len(bits)} coils, expected {count}"
            )
        return [bool(bit) for bit in bits[:count]]

    async def write_coil(self, *, address: int, value: bool) -> None:
        """Write a single coil with function code 05 (error acknowledge)."""
        await _invoke_backend(
            "write coil",
            address,
            self._require_unit().write_coil(address, bool(value)),
        )

    def as_redacted_diagnostics(self) -> dict[str, object]:
        """Return connection diagnostics without exposing the host."""
        return {
            "endpoint": self._endpoint.as_redacted_diagnostics(),
            "capabilities": self.capabilities.as_diagnostics(),
            "connected": self.connected,
        }


async def create_shared_modbus_transport(
    hass: HomeAssistant,
    entry: ConfigEntry,
    endpoint: ModbusTcpEndpoint,
) -> SharedModbusUnitTransport | None:
    """Return a transport on Home Assistant's shared connection, or ``None``.

    ``None`` means "not available here, use the private per-entry socket":
    releases without the contract, an unloadable ``modbus`` component (its
    requirements include pymodbus for the legacy YAML-hub path) and a failed
    claim are all logged once and degrade gracefully.  The caller never has
    to distinguish the causes.
    """
    if not shared_modbus_supported(hass):
        return None
    try:
        from homeassistant.setup import async_setup_component

        if not await async_setup_component(hass, SHARED_MODBUS_DOMAIN, {}):
            _LOGGER.warning(
                "Home Assistant's modbus component could not be set up; the entry keeps its own Modbus socket"
            )
            return None
        transport = SharedModbusUnitTransport(hass, entry, endpoint)
        await transport.connect()
    except Exception as err:  # noqa: BLE001 - any setup/claim failure falls back
        _LOGGER.warning(
            "The shared Modbus connection is unavailable (%s: %s); the entry keeps its own Modbus socket",
            type(err).__name__,
            err,
        )
        return None
    _LOGGER.debug(
        "Using Home Assistant's shared Modbus connection for slave %d on port %d",
        endpoint.slave_id,
        endpoint.port,
    )
    return transport


__all__ = [
    "SHARED_MODBUS_DOMAIN",
    "SHARED_MODBUS_MIN_HA_VERSION",
    "HaModbusTransport",
    "SharedModbusUnitTransport",
    "create_shared_modbus_transport",
    "shared_modbus_supported",
]
