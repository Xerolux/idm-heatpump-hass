"""Forward Home Assistant sensor values to IDM GLT registers.

Two independent forwarder shapes live here:

- ``RoomTempForwarder`` — N keyed HA entities into N fixed target registers,
  looked up via an injectable ``register_for_key`` resolver. Used for
  per-heating-circuit room temperatures (``hc_{circuit}_ext_room_temp``, the
  default resolver) and for external storage temperatures
  (``glt_heat_storage_temp`` etc., via ``register_for_storage_temp_key``) — both
  are the same "N keys -> N registers, periodic + debounced" shape, so they
  share this implementation instead of duplicating it.
- ``HumidityForwarder`` — a single HA entity into the one global
  ``ext_humidity`` register. Kept as its own small class rather than folded
  into the keyed shape above: humidity has no per-key loop or per-key
  tolerance keying, so unifying it would add indirection without a second
  concrete single-entity use case to justify it.
"""

from __future__ import annotations

import asyncio
import logging
import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event

from idm_heatpump import RegisterDef

from .coordinator import IdmCoordinator
from .error_messages import classify_write_error, friendly_write_error, write_error_detail

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class RoomTempForwardingConfig:
    """Runtime configuration for room temperature forwarding."""

    entities: dict[str, str]
    interval: int
    tolerance: float


def _coerce_temperature(value: Any) -> float | None:
    try:
        temperature = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(temperature) or abs(temperature) == float("inf"):
        return None
    return temperature


def _coerce_humidity(value: Any) -> float | None:
    humidity = _coerce_temperature(value)  # same float-parse/NaN/inf guard
    if humidity is None:
        return None
    if not 0.0 <= humidity <= 100.0:
        return None
    return humidity


def _register_for_circuit(coordinator: IdmCoordinator, circuit: str) -> RegisterDef | None:
    register_name = f"hc_{circuit}_ext_room_temp"
    # O(1) lookup via the coordinator's cached name index instead of a linear
    # scan over all number descriptions on every forward write.
    return coordinator.get_register(register_name)


# Fixed GLT storage-temperature registers, keyed the same way heating
# circuits are keyed for room temperature forwarding above.
STORAGE_TEMP_REGISTER_NAMES: dict[str, str] = {
    "heat_storage": "glt_heat_storage_temp",
    "cold_storage": "glt_cold_storage_temp",
    "dhw_bottom": "glt_dhw_temp_bottom",
    "dhw_top": "glt_dhw_temp_top",
}


def register_for_storage_temp_key(coordinator: IdmCoordinator, key: str) -> RegisterDef | None:
    register_name = STORAGE_TEMP_REGISTER_NAMES.get(key)
    if register_name is None:
        return None
    return coordinator.get_register(register_name)


class RoomTempForwarder:
    """Copies selected HA temperature sensors into N fixed GLT registers.

    ``register_for_key`` resolves each configured key (a heating circuit
    letter by default) to its target register; pass
    ``register_for_storage_temp_key`` to reuse this same class for the fixed
    storage-temperature registers instead.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: IdmCoordinator,
        config: RoomTempForwardingConfig,
        *,
        register_for_key: Callable[[IdmCoordinator, str], RegisterDef | None] = _register_for_circuit,
        key_label: str = "HK",
        value_label: str = "room temperature",
    ) -> None:
        self._hass = hass
        self._coordinator = coordinator
        self._config = config
        self._register_for_key = register_for_key
        self._key_label = key_label
        self._value_label = value_label
        self._last_written: dict[str, float] = {}
        self._unsub_state: list[Callable[[], None]] = []
        self._pending_forward_tasks: dict[str, asyncio.Task[None]] = {}
        self._debounce_seconds = 1.0

    async def async_run(self) -> None:
        """Run forwarding until cancelled."""
        entity_ids = [entity_id for entity_id in self._config.entities.values() if entity_id]
        if entity_ids:
            self._unsub_state.append(async_track_state_change_event(self._hass, entity_ids, self._handle_state_change))
        try:
            await self.async_forward_all()
            while True:
                await asyncio.sleep(self._config.interval)
                try:
                    await self.async_forward_all()
                except Exception:
                    _LOGGER.exception("IDM %s forwarding cycle failed; retrying next interval", self._value_label)
        finally:
            for task in self._pending_forward_tasks.values():
                if not task.done():
                    task.cancel()
            self._pending_forward_tasks.clear()
            for unsub in self._unsub_state:
                unsub()
            self._unsub_state.clear()

    @callback
    def _handle_state_change(self, event: Any) -> None:
        """Schedule a debounced forward for the entity that changed.

        ``@callback`` is required, not decorative: Home Assistant builds a
        ``HassJob`` from this listener, and a plain function without the marker
        is classified as an executor job and run in a worker thread. From there
        ``hass.async_create_task`` is a thread-safety violation that Home
        Assistant reports and that can corrupt loop state (#237).
        """
        entity_id = event.data.get("entity_id")
        if not isinstance(entity_id, str):
            return
        # Debounce noisy sensors: replace any pending forward for this entity
        # so rapid updates collapse into one Modbus write.
        existing = self._pending_forward_tasks.get(entity_id)
        if existing is not None and not existing.done():
            existing.cancel()

        async def _debounced() -> None:
            try:
                await asyncio.sleep(self._debounce_seconds)
                await self.async_forward_entity(entity_id)
            finally:
                current = self._pending_forward_tasks.get(entity_id)
                if current is not None and current.done():
                    self._pending_forward_tasks.pop(entity_id, None)

        self._pending_forward_tasks[entity_id] = self._hass.async_create_task(_debounced())

    async def async_forward_all(self) -> None:
        for entity_id in self._config.entities.values():
            if entity_id:
                await self.async_forward_entity(entity_id)

    async def async_forward_entity(self, entity_id: str) -> None:
        circuits = [circuit for circuit, source in self._config.entities.items() if source == entity_id]
        state = self._hass.states.get(entity_id)
        temperature = _coerce_temperature(getattr(state, "state", None))
        if temperature is None:
            _LOGGER.debug("Skipping IDM %s forwarding from %s: invalid state", self._value_label, entity_id)
            return

        for circuit in circuits:
            await self._async_write_circuit(circuit, temperature, entity_id)

    async def _async_write_circuit(self, circuit: str, temperature: float, entity_id: str) -> None:
        reg = self._register_for_key(self._coordinator, circuit)
        if reg is None:
            _LOGGER.warning(
                "Skipping IDM %s forwarding for %s %s: register not available",
                self._value_label,
                self._key_label,
                circuit,
            )
            return

        if reg.min_val is not None and temperature < float(reg.min_val):
            _LOGGER.warning(
                "Skipping IDM %s forwarding from %s to %s: %.2f is below %.2f",
                self._value_label,
                entity_id,
                reg.name,
                temperature,
                float(reg.min_val),
            )
            return
        if reg.max_val is not None and temperature > float(reg.max_val):
            _LOGGER.warning(
                "Skipping IDM %s forwarding from %s to %s: %.2f is above %.2f",
                self._value_label,
                entity_id,
                reg.name,
                temperature,
                float(reg.max_val),
            )
            return

        last = self._last_written.get(circuit)
        if last is not None and abs(last - temperature) < self._config.tolerance:
            return

        try:
            await self._coordinator.async_write_register(reg, temperature)
        except Exception as err:
            error_kind = classify_write_error(err)
            _LOGGER.warning(
                "Could not forward %s %.2f from %s to %s because %s. "
                "Check the source sensor and integration configuration",
                self._value_label,
                temperature,
                entity_id,
                reg.name,
                friendly_write_error(error_kind, reg.name),
            )
            _LOGGER.warning("Technical IDM write error for %s: %s", reg.name, write_error_detail(err))
            _LOGGER.debug("Technical %s forwarding error", self._value_label, exc_info=True)
            return

        self._last_written[circuit] = temperature
        _LOGGER.debug("Forwarded %s %.2f from %s to %s", self._value_label, temperature, entity_id, reg.name)


@dataclass(frozen=True)
class HumidityForwardingConfig:
    """Runtime configuration for external humidity forwarding."""

    entity_id: str
    interval: int
    tolerance: float


class HumidityForwarder:
    """Copies one HA humidity sensor into the global IDM ext_humidity GLT register."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: IdmCoordinator,
        config: HumidityForwardingConfig,
    ) -> None:
        self._hass = hass
        self._coordinator = coordinator
        self._config = config
        self._last_written: float | None = None
        self._unsub_state: Callable[[], None] | None = None
        self._pending_forward_task: asyncio.Task[None] | None = None
        self._debounce_seconds = 1.0

    async def async_run(self) -> None:
        """Run forwarding until cancelled."""
        if self._config.entity_id:
            self._unsub_state = async_track_state_change_event(
                self._hass, [self._config.entity_id], self._handle_state_change
            )
        try:
            await self.async_forward()
            while True:
                await asyncio.sleep(self._config.interval)
                try:
                    await self.async_forward()
                except Exception:
                    _LOGGER.exception("IDM humidity forwarding cycle failed; retrying next interval")
        finally:
            if self._pending_forward_task is not None and not self._pending_forward_task.done():
                self._pending_forward_task.cancel()
            self._pending_forward_task = None
            if self._unsub_state is not None:
                self._unsub_state()
                self._unsub_state = None

    @callback
    def _handle_state_change(self, event: Any) -> None:
        """Schedule a debounced humidity forward.

        ``@callback`` is required, not decorative: Home Assistant builds a
        ``HassJob`` from this listener, and a plain function without the marker
        is classified as an executor job and run in a worker thread. From there
        ``hass.async_create_task`` is a thread-safety violation that Home
        Assistant reports and that can corrupt loop state (#237).
        """
        entity_id = event.data.get("entity_id")
        if not isinstance(entity_id, str):
            return
        if self._pending_forward_task is not None and not self._pending_forward_task.done():
            self._pending_forward_task.cancel()

        async def _debounced() -> None:
            try:
                await asyncio.sleep(self._debounce_seconds)
                await self.async_forward()
            finally:
                if self._pending_forward_task is not None and self._pending_forward_task.done():
                    self._pending_forward_task = None

        self._pending_forward_task = self._hass.async_create_task(_debounced())

    async def async_forward(self) -> None:
        entity_id = self._config.entity_id
        if not entity_id:
            return
        state = self._hass.states.get(entity_id)
        humidity = _coerce_humidity(getattr(state, "state", None))
        if humidity is None:
            _LOGGER.debug("Skipping IDM humidity forwarding from %s: invalid state", entity_id)
            return

        reg = self._coordinator.get_register("ext_humidity")
        if reg is None:
            _LOGGER.warning("Skipping IDM humidity forwarding: ext_humidity register not available")
            return

        if reg.min_val is not None and humidity < float(reg.min_val):
            _LOGGER.warning(
                "Skipping IDM humidity forwarding from %s to %s: %.2f is below %.2f",
                entity_id,
                reg.name,
                humidity,
                float(reg.min_val),
            )
            return
        if reg.max_val is not None and humidity > float(reg.max_val):
            _LOGGER.warning(
                "Skipping IDM humidity forwarding from %s to %s: %.2f is above %.2f",
                entity_id,
                reg.name,
                humidity,
                float(reg.max_val),
            )
            return

        if self._last_written is not None and abs(self._last_written - humidity) < self._config.tolerance:
            return

        try:
            await self._coordinator.async_write_register(reg, humidity)
        except Exception as err:
            error_kind = classify_write_error(err)
            _LOGGER.warning(
                "Could not forward humidity %.2f from %s to %s because %s. "
                "Check the source sensor and integration configuration",
                humidity,
                entity_id,
                reg.name,
                friendly_write_error(error_kind, reg.name),
            )
            _LOGGER.warning("Technical IDM write error for %s: %s", reg.name, write_error_detail(err))
            _LOGGER.debug("Technical humidity forwarding error", exc_info=True)
            return

        self._last_written = humidity
        _LOGGER.debug("Forwarded humidity %.2f from %s to %s", humidity, entity_id, reg.name)
