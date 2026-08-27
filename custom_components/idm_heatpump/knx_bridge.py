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
import re
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir

from idm_heatpump import DataType, RegisterDef

from .const import DOMAIN
from .coordinator import IdmCoordinator
from .error_messages import classify_write_error, friendly_write_error, write_error_detail
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

# KNX controls often emit several intermediate setpoints while the user turns
# a dial or taps an arrow. Keep the newest command for a short quiet period so
# only the final value consumes a write cycle on the controller.
DEFAULT_WRITE_DEBOUNCE: float = 1.0

# Home Assistant can mark the KNX component and its services as available
# before the KNX module itself has finished loading. Retry event registration
# after that startup race instead of leaving incoming group addresses inactive
# until the IDM integration is reloaded manually.
KNX_EVENT_REGISTRATION_RETRY_SECONDS: float = 5.0

# Leave a small margin after a locally reported cooldown. The displayed
# remaining time is rounded, so retrying at the exact value can still arrive a
# fraction too early and need another avoidable attempt.
WRITE_RETRY_MARGIN: float = 0.1
MAX_WRITE_RETRY_DELAY: float = 3600.0
_EEPROM_RETRY_PATTERN = re.compile(r"try again in\s*([0-9]+(?:\.[0-9]+)?)s", re.IGNORECASE)

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
    respond_to_read: bool = True
    groups: tuple[str, ...] | None = None
    overrides: Mapping[str, str] = field(default_factory=dict)
    resend_interval: int = 0
    tolerance: float = 0.1
    send_gap: float = DEFAULT_SEND_GAP
    write_debounce: float = DEFAULT_WRITE_DEBOUNCE
    write_cooldown: float = 5.0
    eeprom_write_interval: float = 60.0


@dataclass(frozen=True, slots=True)
class _PendingKnxWrite:
    """Newest KNX command waiting to be applied to one register."""

    register: RegisterDef
    value: Any
    destination: str
    updated_at: float


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
    return round(number)


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
    return round(number)


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
        self._registration_worker: asyncio.Task[None] | None = None
        self._registered_event_groups: set[tuple[str | None, tuple[str, ...]]] = set()
        self._pending_writes: dict[str, _PendingKnxWrite] = {}
        self._write_tasks: dict[str, asyncio.Task[None]] = {}
        self._last_write_completed_at: dict[str, float] = {}
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
            "KNX bridge (experimental) for %s serving %d objects from base address %s. "
            "Configuration and reload have been exercised with a live Home Assistant KNX "
            "interface; physical group-address telegram interoperability remains unverified",
            self._entry_id,
            len(self._objects),
            self._config.base_address,
        )
        self._started = True

        if self._config.receive_enabled:
            self._unsubscribers.append(self._hass.bus.async_listen(EVENT_KNX, self._handle_knx_event))
            if not await self._async_register_events():
                self._registration_worker = self._hass.async_create_task(self._async_registration_worker())

        if self._config.send_enabled:
            self._worker = asyncio.create_task(self._async_send_worker())
            self._unsubscribers.append(self._coordinator.async_add_listener(self._handle_coordinator_update))
            self._handle_coordinator_update()

    async def async_stop(self) -> None:
        """Unsubscribe, deregister group addresses and stop the sender."""
        for unsubscribe in self._unsubscribers:
            unsubscribe()
        self._unsubscribers.clear()
        registration_worker = self._registration_worker
        self._registration_worker = None
        if registration_worker is not None:
            registration_worker.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await registration_worker
        worker = self._worker
        self._worker = None
        if worker is not None:
            worker.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await worker
        write_tasks = list(self._write_tasks.values())
        self._write_tasks.clear()
        self._pending_writes.clear()
        for task in write_tasks:
            task.cancel()
        if write_tasks:
            await asyncio.gather(*write_tasks, return_exceptions=True)
        if self._started and self._config.receive_enabled and self._registered_event_groups:
            await self._async_register_events(remove=True)
        self._started = False

    async def _async_registration_worker(self) -> None:
        """Retry event registration until the KNX runtime is fully ready."""
        while True:
            await asyncio.sleep(KNX_EVENT_REGISTRATION_RETRY_SECONDS)
            if await self._async_register_events(log_failure=False):
                _LOGGER.info(
                    "Registered KNX group addresses for %s after the KNX integration became ready",
                    self._entry_id,
                )
                return

    def _event_registration_groups(self) -> list[tuple[str | None, tuple[str, ...]]]:
        """Return stable DPT/address batches required by ``knx.event_register``."""
        by_dpt: dict[str | None, list[str]] = {}
        for register, obj in self._objects.items():
            # Writable objects are registered so commands arrive. Read-only
            # ones are registered too when the bridge answers read requests,
            # because a GroupValueRead on them has to reach us as well.
            if not obj.writable and not self._answers_reads():
                continue
            by_dpt.setdefault(obj.dpt, []).append(self._addresses[register])
        return [(dpt, tuple(sorted(addresses))) for dpt, addresses in by_dpt.items()]

    async def _async_register_events(
        self,
        *,
        remove: bool = False,
        log_failure: bool = True,
    ) -> bool:
        """Ask the KNX integration to raise ``knx_event`` for writable objects.

        Registering explicitly is what makes the commands work without the
        user having to widen the KNX integration's own event filter, and it
        gives us decoded values instead of raw payloads.
        """
        groups = list(self._registered_event_groups) if remove else self._event_registration_groups()
        all_succeeded = True
        for group in groups:
            if not remove and group in self._registered_event_groups:
                continue
            dpt, addresses = group
            data: dict[str, Any] = {"address": list(addresses)}
            if dpt is not None:
                data["type"] = dpt
            if remove:
                data["remove"] = True
            try:
                await self._hass.services.async_call(KNX_DOMAIN, SERVICE_EVENT_REGISTER, data, blocking=True)
            except Exception:  # noqa: BLE001 - HA service failures share no stable public base
                all_succeeded = False
                log = _LOGGER.warning if log_failure else _LOGGER.debug
                log(
                    "Failed to %s %d KNX group addresses for events",
                    "deregister" if remove else "register",
                    len(addresses),
                    exc_info=True,
                )
            else:
                if remove:
                    self._registered_event_groups.discard(group)
                else:
                    self._registered_event_groups.add(group)
        return all_succeeded

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

    def _answers_reads(self) -> bool:
        """Whether the bridge should reply to GroupValueRead telegrams."""
        return self._config.send_enabled and self._config.respond_to_read

    @callback
    def _handle_knx_event(self, event: Event) -> None:
        """Act on a telegram for one of our group addresses.

        A group write on a writable object becomes a register write; a read
        request on any object we publish is answered with the current value.
        """
        data = event.data
        if data.get("direction") != "Incoming":
            return
        telegram_type = data.get("telegramtype")
        destination = str(data.get("destination", ""))

        if telegram_type == "GroupValueRead":
            if self._answers_reads():
                self._handle_read_request(destination)
            return
        if telegram_type not in (None, "GroupValueWrite"):
            # A GroupValueResponse carries a valid value too, but it is an
            # answer to somebody else's question rather than an instruction
            # to us. Only an explicit write reaches the controller.
            return
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

        task = self._write_tasks.get(definition.name)
        if self._matches_current_value(definition, value) and definition.name not in self._pending_writes:
            return

        pending = _PendingKnxWrite(definition, value, destination, time.monotonic())
        self._pending_writes[definition.name] = pending
        if task is None or task.done():
            self._write_tasks[definition.name] = self._hass.async_create_task(self._async_write_worker(definition.name))

    @callback
    def _handle_read_request(self, destination: str) -> None:
        """Answer a GroupValueRead with the value we currently hold.

        Without this a device that asks for the value after a restart --
        a push-button refreshing its display, a visualisation coming back
        up -- would stay blank until the next change happened to be sent.
        The reply goes out directly rather than through the paced send
        queue: a read request is answered now or not usefully at all, and
        the number of them is bounded by the devices asking.
        """
        obj = self._address_to_object.get(destination)
        if obj is None:
            return
        definition = self._coordinator.get_register(obj.register)
        if definition is None or definition.write_only:
            return
        value = (self._coordinator.data or {}).get(obj.register)
        if value is None or self._coordinator.is_register_unused(obj.register, value):
            return
        payload = _coerce_outgoing(value, obj.dpt)
        if payload is None:
            return
        self._hass.async_create_task(self._async_send_response(destination, obj, payload))

    async def _async_send_response(self, destination: str, obj: KnxObject, payload: float) -> None:
        data: dict[str, Any] = {"address": destination, "response": True}
        if obj.dpt is None:
            data["payload"] = int(payload)
        else:
            data["type"] = obj.dpt
            data["payload"] = payload if _is_float_dpt(obj.dpt) else int(payload)
        try:
            await self._hass.services.async_call(KNX_DOMAIN, SERVICE_SEND, data, blocking=False)
        except Exception:
            _LOGGER.debug("Failed to answer a KNX read request on %s", destination, exc_info=True)
        else:
            _LOGGER.debug("Answered KNX read request on %s with %s", destination, payload)

    def _matches_current_value(self, register: RegisterDef, value: Any) -> bool:
        """Return whether the coordinator already holds the commanded value."""
        if register.write_only:
            return False
        current = (self._coordinator.data or {}).get(register.name)
        if current is None:
            return False
        try:
            difference = abs(float(current) - float(value))
        except (TypeError, ValueError):
            return bool(current == value)
        tolerance = self._config.tolerance if register.datatype is DataType.FLOAT else 0.0
        return difference <= tolerance

    def _known_write_delay(self, pending: _PendingKnxWrite) -> float:
        """Return the remaining configured guard time after our last write."""
        last = self._last_write_completed_at.get(pending.register.name)
        if last is None:
            return 0.0
        interval = max(0.0, self._config.write_cooldown)
        if pending.register.eeprom_sensitive:
            interval = max(interval, self._config.eeprom_write_interval)
        return max(0.0, interval - (time.monotonic() - last))

    async def _async_write_worker(self, register_name: str) -> None:
        """Write the newest KNX value after quiet and safety intervals."""
        current_task = asyncio.current_task()
        try:
            while pending := self._pending_writes.get(register_name):
                quiet_remaining = self._config.write_debounce - (time.monotonic() - pending.updated_at)
                if quiet_remaining > 0:
                    await asyncio.sleep(quiet_remaining)
                    continue
                if self._matches_current_value(pending.register, pending.value):
                    if self._pending_writes.get(register_name) is pending:
                        self._pending_writes.pop(register_name, None)
                    continue

                known_delay = self._known_write_delay(pending)
                if known_delay > 0:
                    await asyncio.sleep(known_delay + WRITE_RETRY_MARGIN)
                    continue

                try:
                    await self._coordinator.async_write_register(pending.register, pending.value)
                except Exception as err:
                    retry_delay = _retry_delay_from_write_error(
                        err,
                        eeprom_fallback=(
                            self._config.eeprom_write_interval if pending.register.eeprom_sensitive else None
                        ),
                    )
                    if retry_delay is not None:
                        _LOGGER.info(
                            "KNX command on %s for %s remains queued; retrying the newest value in %.1fs",
                            pending.destination,
                            pending.register.name,
                            retry_delay,
                        )
                        await asyncio.sleep(retry_delay + WRITE_RETRY_MARGIN)
                        continue
                    _LOGGER.warning(
                        "KNX command on %s could not be written to %s because %s",
                        pending.destination,
                        pending.register.name,
                        friendly_write_error(classify_write_error(err), pending.register.name),
                    )
                    _LOGGER.warning(
                        "Technical IDM write error for %s: %s",
                        pending.register.name,
                        write_error_detail(err),
                    )
                    _LOGGER.debug("Technical KNX command error for %s", pending.destination, exc_info=True)
                    if self._pending_writes.get(register_name) is pending:
                        self._pending_writes.pop(register_name, None)
                else:
                    self._last_write_completed_at[register_name] = time.monotonic()
                    _LOGGER.debug(
                        "KNX command on %s wrote %s = %s",
                        pending.destination,
                        pending.register.name,
                        pending.value,
                    )
                    if self._pending_writes.get(register_name) is pending:
                        self._pending_writes.pop(register_name, None)
        finally:
            if self._write_tasks.get(register_name) is current_task:
                self._write_tasks.pop(register_name, None)


def _retry_delay_from_write_error(err: Exception, *, eeprom_fallback: float | None = None) -> float | None:
    """Return a safe retry delay for local write guards, never device errors."""
    if getattr(err, "translation_key", None) == "write_cooldown_active":
        placeholders = getattr(err, "translation_placeholders", {})
        try:
            return min(MAX_WRITE_RETRY_DELAY, max(0.0, float(placeholders["remaining"])))
        except (KeyError, TypeError, ValueError):
            return None
    if classify_write_error(err) != "write_eeprom_blocked":
        return None
    match = _EEPROM_RETRY_PATTERN.search(str(err))
    if match is not None:
        return min(MAX_WRITE_RETRY_DELAY, max(0.0, float(match.group(1))))
    if eeprom_fallback is None or eeprom_fallback <= 0:
        return None
    return min(MAX_WRITE_RETRY_DELAY, eeprom_fallback)


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
