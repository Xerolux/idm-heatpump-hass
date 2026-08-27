"""Publish IDM heat pump values on KNX and accept commands from the bus.

The bridge talks to Home Assistant's own ``knx`` integration rather than
to the bus directly, so it needs no gateway of its own: outgoing values go
through the ``knx.send`` service, incoming commands arrive as ``knx_event``
after registering the relevant group addresses with ``knx.event_register``.

Objects, datapoint types and directions come from :mod:`knx_catalog`,
which mirrors IDM's own ETS example project for the Weinzierl BAOS
gateway. That keeps a KNX installation that already speaks to an IDM
controller working the same way when the values are served from this
integration instead.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import math
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir

from idm_heatpump import DataType, RegisterDef

from .const import DOMAIN
from .coordinator import IdmCoordinator
from .error_messages import classify_write_error, friendly_write_error
from .knx_catalog import KNX_OBJECTS, KnxObject, object_for_register, resolve_group_addresses

_LOGGER = logging.getLogger(__name__)

KNX_DOMAIN = "knx"
SERVICE_SEND = "send"
SERVICE_EVENT_REGISTER = "event_register"
EVENT_KNX = "knx_event"

# KNX TP1 carries roughly 30-50 telegrams per second in theory and far
# fewer in practice. Pace outgoing telegrams so a first full export of
# several hundred objects does not saturate the line other devices share.
DEFAULT_SEND_GAP: float = 0.05

# A value we just published comes back from a mirroring device or a
# visualisation often enough that writing it straight back would loop.
# Ignore an inbound telegram that only repeats what we sent this recently.
ECHO_SUPPRESSION_SECONDS: float = 5.0

# Datapoint types whose payload is a float; everything else is sent as an
# integer. The catalogue only uses the main types listed here.
_FLOAT_DPT_PREFIXES: tuple[str, ...] = ("9.", "14.")


@dataclass(frozen=True, slots=True)
class KnxBridgeConfig:
    """Runtime configuration for the KNX bridge."""

    base_address: str
    send_enabled: bool = True
    receive_enabled: bool = True
    groups: tuple[str, ...] | None = None
    overrides: Mapping[str, str] = field(default_factory=dict)
    resend_interval: int = 0
    tolerance: float = 0.1
    send_gap: float = DEFAULT_SEND_GAP


def _is_float_dpt(dpt: str | None) -> bool:
    return dpt is not None and dpt.startswith(_FLOAT_DPT_PREFIXES)


def _coerce_outgoing(value: Any, dpt: str | None) -> float | int | None:
    """Convert a register value into a payload for ``knx.send``."""
    if value is None or isinstance(value, str):
        return None
    if isinstance(value, bool):
        number: float = float(value)
    else:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
    if math.isnan(number) or math.isinf(number):
        return None
    if dpt is None:
        return 1 if number else 0
    if _is_float_dpt(dpt):
        return number
    return int(round(number))


def _coerce_incoming(value: Any, register: RegisterDef) -> float | int | bool | None:
    """Convert a decoded KNX value into something writable to ``register``."""
    if isinstance(value, bool):
        number: float = float(value)
    elif isinstance(value, (int, float)):
        number = float(value)
    elif isinstance(value, (tuple, list)) and len(value) == 1:
        # Untyped 1-bit registration delivers the raw payload only.
        return _coerce_incoming(value[0], register)
    else:
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    if register.datatype is DataType.BOOL:
        return bool(number)
    if register.datatype is DataType.FLOAT:
        return number
    return int(round(number))


class KnxBridge:
    """Mirrors coordinator values onto KNX and applies commands from it."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: IdmCoordinator,
        config: KnxBridgeConfig,
        *,
        entry_id: str,
    ) -> None:
        self._hass = hass
        self._coordinator = coordinator
        self._config = config
        self._entry_id = entry_id
        self._objects: dict[str, KnxObject] = {}
        self._addresses: dict[str, str] = {}
        self._address_to_object: dict[str, KnxObject] = {}
        self._last_sent: dict[str, float] = {}
        self._last_sent_at: dict[str, float] = {}
        self._last_full_send: float = 0.0
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._unsubscribers: list[Callable[[], None]] = []
        self._worker: asyncio.Task[None] | None = None
        self._started = False

    @property
    def group_addresses(self) -> Mapping[str, str]:
        """Return the resolved register -> group address mapping."""
        return dict(self._addresses)

    def _knx_available(self) -> bool:
        return KNX_DOMAIN in self._hass.config.components and self._hass.services.has_service(KNX_DOMAIN, SERVICE_SEND)

    def _issue_id(self) -> str:
        return f"knx_unavailable_{self._entry_id}"

    def _resolve(self) -> None:
        """Work out which objects this controller can actually serve."""
        available = {
            register
            for register in (self._coordinator.data or {})
            if self._coordinator.get_register(register) is not None
        }
        # Write-only registers (error acknowledge) never carry a value, so
        # they are reachable from the bus but never published to it.
        for obj in _catalogue_objects(self._config.groups):
            register = self._coordinator.get_register(obj.register)
            if register is None:
                continue
            if obj.register not in available and not register.write_only:
                continue
            self._objects[obj.register] = obj

        self._addresses = resolve_group_addresses(
            self._config.base_address,
            overrides=self._config.overrides,
            registers=self._objects.keys(),
            groups=self._config.groups,
        )
        self._objects = {register: obj for register, obj in self._objects.items() if register in self._addresses}
        self._address_to_object = {self._addresses[register]: obj for register, obj in self._objects.items()}

    async def async_start(self) -> None:
        """Resolve addresses, subscribe to updates and start the sender."""
        if not self._knx_available():
            _LOGGER.warning(
                "KNX bridge for %s stays idle: the Home Assistant KNX integration is not set up",
                self._entry_id,
            )
            ir.async_create_issue(
                self._hass,
                DOMAIN,
                self._issue_id(),
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="knx_not_available",
            )
            return

        ir.async_delete_issue(self._hass, DOMAIN, self._issue_id())
        self._resolve()
        if not self._objects:
            _LOGGER.warning(
                "KNX bridge for %s has no objects to serve; check the selected object groups",
                self._entry_id,
            )
            return

        _LOGGER.info(
            "KNX bridge for %s serving %d objects from base address %s",
            self._entry_id,
            len(self._objects),
            self._config.base_address,
        )
        self._started = True

        if self._config.receive_enabled:
            await self._async_register_events()
            self._unsubscribers.append(self._hass.bus.async_listen(EVENT_KNX, self._handle_knx_event))

        if self._config.send_enabled:
            self._worker = asyncio.create_task(self._async_send_worker())
            self._unsubscribers.append(self._coordinator.async_add_listener(self._handle_coordinator_update))
            self._handle_coordinator_update()

    async def async_stop(self) -> None:
        """Unsubscribe, deregister group addresses and stop the sender."""
        for unsubscribe in self._unsubscribers:
            unsubscribe()
        self._unsubscribers.clear()
        worker = self._worker
        self._worker = None
        if worker is not None:
            worker.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await worker
        if self._started and self._config.receive_enabled:
            await self._async_register_events(remove=True)
        self._started = False

    async def _async_register_events(self, *, remove: bool = False) -> None:
        """Ask the KNX integration to raise ``knx_event`` for writable objects.

        Registering explicitly is what makes the commands work without the
        user having to widen the KNX integration's own event filter, and it
        gives us decoded values instead of raw payloads.
        """
        by_dpt: dict[str | None, list[str]] = {}
        for register, obj in self._objects.items():
            if not obj.writable:
                continue
            by_dpt.setdefault(obj.dpt, []).append(self._addresses[register])
        for dpt, addresses in by_dpt.items():
            data: dict[str, Any] = {"address": sorted(addresses)}
            if dpt is not None:
                data["type"] = dpt
            if remove:
                data["remove"] = True
            try:
                await self._hass.services.async_call(KNX_DOMAIN, SERVICE_EVENT_REGISTER, data, blocking=True)
            except Exception:
                _LOGGER.warning(
                    "Failed to %s %d KNX group addresses for events",
                    "deregister" if remove else "register",
                    len(addresses),
                    exc_info=True,
                )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Queue every object whose value moved since the last telegram."""
        data = self._coordinator.data or {}
        now = time.monotonic()
        resend_all = self._config.resend_interval > 0 and now - self._last_full_send >= self._config.resend_interval
        if resend_all:
            self._last_full_send = now

        for register, obj in self._objects.items():
            definition = self._coordinator.get_register(register)
            if definition is None or definition.write_only:
                continue
            value = data.get(register)
            if value is None or self._coordinator.is_register_unused(register, value):
                continue
            payload = _coerce_outgoing(value, obj.dpt)
            if payload is None:
                continue
            previous = self._last_sent.get(register)
            if not resend_all and previous is not None:
                threshold = self._config.tolerance if _is_float_dpt(obj.dpt) else 0.0
                if abs(float(payload) - previous) <= threshold:
                    continue
            self._last_sent[register] = float(payload)
            self._queue.put_nowait(register)

    async def _async_send_worker(self) -> None:
        """Drain the send queue, pacing telegrams so the bus stays usable."""
        while True:
            register = await self._queue.get()
            obj = self._objects.get(register)
            address = self._addresses.get(register)
            if obj is None or address is None:
                continue
            payload = self._last_sent.get(register)
            if payload is None:
                continue
            data: dict[str, Any] = {"address": address}
            if obj.dpt is None:
                data["payload"] = int(payload)
            else:
                data["type"] = obj.dpt
                data["payload"] = payload if _is_float_dpt(obj.dpt) else int(payload)
            try:
                await self._hass.services.async_call(KNX_DOMAIN, SERVICE_SEND, data, blocking=False)
            except Exception:
                _LOGGER.debug("Failed to send %s to KNX %s", register, address, exc_info=True)
            else:
                self._last_sent_at[register] = time.monotonic()
            if self._config.send_gap > 0:
                await asyncio.sleep(self._config.send_gap)

    @callback
    def _handle_knx_event(self, event: Event) -> None:
        """Turn an incoming group write into a heat pump register write."""
        data = event.data
        if data.get("direction") != "Incoming":
            return
        if data.get("telegramtype") not in (None, "GroupValueWrite"):
            return
        destination = str(data.get("destination", ""))
        obj = self._address_to_object.get(destination)
        if obj is None or not obj.writable:
            return
        definition = self._coordinator.get_register(obj.register)
        if definition is None or not definition.writable:
            return

        raw = data.get("value")
        if raw is None:
            raw = data.get("data")
        value = _coerce_incoming(raw, definition)
        if value is None:
            _LOGGER.debug("Ignoring KNX telegram for %s with payload %r", destination, raw)
            return

        sent_at = self._last_sent_at.get(obj.register)
        last = self._last_sent.get(obj.register)
        if (
            sent_at is not None
            and last is not None
            and time.monotonic() - sent_at < ECHO_SUPPRESSION_SECONDS
            and abs(float(value) - last) <= self._config.tolerance
        ):
            # Our own value coming back around; writing it again would
            # bounce between the bus and the controller.
            return

        self._hass.async_create_task(self._async_write(definition, value, destination))

    async def _async_write(self, register: RegisterDef, value: Any, destination: str) -> None:
        try:
            await self._coordinator.async_write_register(register, value)
        except Exception as err:
            _LOGGER.warning(
                "KNX command on %s could not be written to %s: %s",
                destination,
                register.name,
                friendly_write_error(classify_write_error(err), register.name),
            )
        else:
            _LOGGER.debug("KNX command on %s wrote %s = %s", destination, register.name, value)


def _catalogue_objects(groups: tuple[str, ...] | None) -> list[KnxObject]:
    if groups is None:
        return list(KNX_OBJECTS)
    allowed = set(groups)
    return [obj for obj in KNX_OBJECTS if obj.group in allowed]


__all__ = [
    "EVENT_KNX",
    "KNX_DOMAIN",
    "KnxBridge",
    "KnxBridgeConfig",
    "object_for_register",
]
