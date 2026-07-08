"""Forward Home Assistant room sensor temperatures to IDM GLT registers."""

from __future__ import annotations

import asyncio
import logging
import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_state_change_event

from idm_heatpump import RegisterDef

from .coordinator import IdmCoordinator

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


def _register_for_circuit(coordinator: IdmCoordinator, circuit: str) -> RegisterDef | None:
    register_name = f"hc_{circuit}_ext_room_temp"
    # O(1) lookup via the coordinator's cached name index instead of a linear
    # scan over all number descriptions on every forward write.
    return coordinator.get_register(register_name)


class RoomTempForwarder:
    """Copies selected HA room temperatures into heating-circuit GLT registers."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: IdmCoordinator,
        config: RoomTempForwardingConfig,
    ) -> None:
        self._hass = hass
        self._coordinator = coordinator
        self._config = config
        self._last_written: dict[str, float] = {}
        self._unsub_state: list[Callable[[], None]] = []

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
                    _LOGGER.exception("IDM room temperature forwarding cycle failed; retrying next interval")
        finally:
            for unsub in self._unsub_state:
                unsub()
            self._unsub_state.clear()

    def _handle_state_change(self, event: Any) -> None:
        entity_id = event.data.get("entity_id")
        if not isinstance(entity_id, str):
            return
        self._hass.async_create_task(self.async_forward_entity(entity_id))

    async def async_forward_all(self) -> None:
        for entity_id in self._config.entities.values():
            if entity_id:
                await self.async_forward_entity(entity_id)

    async def async_forward_entity(self, entity_id: str) -> None:
        circuits = [circuit for circuit, source in self._config.entities.items() if source == entity_id]
        state = self._hass.states.get(entity_id)
        temperature = _coerce_temperature(getattr(state, "state", None))
        if temperature is None:
            _LOGGER.debug("Skipping IDM room temperature forwarding from %s: invalid state", entity_id)
            return

        for circuit in circuits:
            await self._async_write_circuit(circuit, temperature, entity_id)

    async def _async_write_circuit(self, circuit: str, temperature: float, entity_id: str) -> None:
        reg = _register_for_circuit(self._coordinator, circuit)
        if reg is None:
            _LOGGER.warning("Skipping IDM room temperature forwarding for HK %s: register not available", circuit)
            return

        if reg.min_val is not None and temperature < float(reg.min_val):
            _LOGGER.warning(
                "Skipping IDM room temperature forwarding from %s to %s: %.2f is below %.2f",
                entity_id,
                reg.name,
                temperature,
                float(reg.min_val),
            )
            return
        if reg.max_val is not None and temperature > float(reg.max_val):
            _LOGGER.warning(
                "Skipping IDM room temperature forwarding from %s to %s: %.2f is above %.2f",
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
        except Exception:
            _LOGGER.warning(
                "Failed to forward room temperature %.2f from %s to %s",
                temperature,
                entity_id,
                reg.name,
                exc_info=True,
            )
            return

        self._last_written[circuit] = temperature
        _LOGGER.debug("Forwarded room temperature %.2f from %s to %s", temperature, entity_id, reg.name)
