"""Entity-aware Modbus polling plan for IDM Heatpump."""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Callable, Iterable
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .coordinator import IdmCoordinator

_LOGGER = logging.getLogger(__name__)

# These registers provide the communication heartbeat, faults, the restart-safe
# operating analysis and the safe DHW restore path. They are intentionally kept
# even when all related UI entities are disabled.
_ALWAYS_REQUIRED = frozenset(
    {
        "outdoor_temp",
        "internal_message",
        "system_mode",
        "dhw_temp_top",
        "dhw_setpoint",
        "hp_operating_mode",
        "hp_sum_alarm",
        "compressor_status_1",
        "compressor_status_2",
        "compressor_status_3",
        "compressor_status_4",
    }
)

_CALCULATED_DEPENDENCIES: dict[str, frozenset[str]] = {
    "calculated_hp_temperature_delta": frozenset({"hp_flow_temp", "hp_return_temp"}),
    "calculated_heat_source_temperature_delta": frozenset(
        {"heat_source_inlet_temp", "heat_source_outlet_temp"}
    ),
    "calculated_dhw_setpoint_deviation": frozenset({"dhw_temp_top", "dhw_setpoint"}),
}

_HEATING_CLIMATE = re.compile(r"^climate_hc_([a-g])$")
_ZONE_CLIMATE = re.compile(r"^climate_zm(\d+)_room(\d+)$")


def _entity_dependencies(unique_suffix: str) -> set[str]:
    """Return register dependencies for non-register entity unique IDs."""
    if unique_suffix in _CALCULATED_DEPENDENCIES:
        return set(_CALCULATED_DEPENDENCIES[unique_suffix])
    if unique_suffix == "water_heater":
        return {"dhw_temp_top", "dhw_setpoint"}
    if match := _HEATING_CLIMATE.fullmatch(unique_suffix):
        circuit = match.group(1)
        return {
            f"hc_{circuit}_mode",
            f"hc_{circuit}_room_setpoint_heat_normal",
            f"hc_{circuit}_room_temp",
            "hp_operating_mode",
        }
    if match := _ZONE_CLIMATE.fullmatch(unique_suffix):
        zone, room = match.groups()
        prefix = f"zm{zone}_room{room}"
        return {
            f"{prefix}_mode",
            f"{prefix}_setpoint",
            f"{prefix}_temp",
            "hp_operating_mode",
        }
    return set()


def build_required_register_names(
    registry: Any,
    entry_id: str,
    known_register_names: Iterable[str],
) -> set[str] | None:
    """Build the required register set or return None until registry data exists."""
    known = set(known_register_names)
    entries = list(er.async_entries_for_config_entry(registry, entry_id))
    if not entries:
        # First refresh intentionally remains complete. The optimized plan is
        # applied only after Home Assistant created the entity registry entries.
        return None

    required = set(_ALWAYS_REQUIRED) & known
    prefix = f"{entry_id}_"
    for registry_entry in entries:
        if getattr(registry_entry, "disabled_by", None) is not None:
            continue
        unique_id = getattr(registry_entry, "unique_id", None)
        if not isinstance(unique_id, str) or not unique_id.startswith(prefix):
            continue
        unique_suffix = unique_id.removeprefix(prefix)
        if unique_suffix in known:
            required.add(unique_suffix)
        required.update(_entity_dependencies(unique_suffix) & known)

    return required


class EntityAwarePollingManager:
    """Keep coordinator polling aligned with enabled entity registry entries."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        coordinator: IdmCoordinator,
        *,
        debounce_seconds: float = 1.0,
    ) -> None:
        self._hass = hass
        self._entry = entry
        self._coordinator = coordinator
        self._debounce_seconds = debounce_seconds
        self._refresh_task: asyncio.Task[None] | None = None
        self._unsub_registry: Callable[[], None] | None = None

    async def async_setup(self) -> None:
        """Apply the initial post-platform plan and subscribe to registry changes."""
        await self._async_apply_plan(request_refresh=False)
        event_name = getattr(er, "EVENT_ENTITY_REGISTRY_UPDATED", "entity_registry_updated")
        self._unsub_registry = self._hass.bus.async_listen(event_name, self._handle_registry_event)

    async def async_shutdown(self) -> None:
        """Cancel pending work and remove the entity registry listener."""
        if self._unsub_registry is not None:
            self._unsub_registry()
            self._unsub_registry = None
        if self._refresh_task is not None:
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass
            self._refresh_task = None

    @callback
    def _handle_registry_event(self, event: Event) -> None:
        """Debounce registry changes affecting this config entry."""
        entity_id = event.data.get("entity_id")
        if isinstance(entity_id, str):
            registry = er.async_get(self._hass)
            registry_entry = registry.async_get(entity_id)
            if registry_entry is not None and getattr(registry_entry, "config_entry_id", None) not in (
                None,
                self._entry.entry_id,
            ):
                return
        if self._refresh_task is not None:
            self._refresh_task.cancel()
        self._refresh_task = self._hass.async_create_task(self._async_debounced_apply())

    async def _async_debounced_apply(self) -> None:
        try:
            await asyncio.sleep(self._debounce_seconds)
            await self._async_apply_plan(request_refresh=True)
        except asyncio.CancelledError:
            raise
        finally:
            self._refresh_task = None

    async def _async_apply_plan(self, *, request_refresh: bool) -> None:
        registry = er.async_get(self._hass)
        required = build_required_register_names(
            registry,
            self._entry.entry_id,
            self._coordinator.register_names,
        )
        if required is None:
            return
        changed = self._coordinator.set_polling_register_names(required)
        if not changed:
            return
        _LOGGER.info(
            "IDM entity-aware polling uses %d of %d registers",
            self._coordinator.polling_register_count,
            self._coordinator.total_register_count,
        )
        if request_refresh:
            await self._coordinator.async_request_refresh()
