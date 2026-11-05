"""Firmware observations, present only while the owner consents to telemetry."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .const import CONF_TELEMETRY, CONF_TELEMETRY_POLICY, DOMAIN
from .coordinator import IdmCoordinator
from .entity import IdmCoordinatorEntityBase, build_entity_unique_id
from .telemetry import TELEMETRY_POLICY, Telemetry

KEY = "telemetry_latest_firmware"


def firmware_sensor_entities(
    hass: HomeAssistant, entry: Any, coordinator: IdmCoordinator
) -> list[IdmTelemetryFirmwareSensor]:
    """Remove registry remnants when consent is absent, including after restarts."""
    enabled = entry.options.get(CONF_TELEMETRY) is True and entry.options.get(CONF_TELEMETRY_POLICY) == TELEMETRY_POLICY
    if enabled:
        return [IdmTelemetryFirmwareSensor(coordinator)]
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id("sensor", DOMAIN, build_entity_unique_id(entry.entry_id, KEY))
    if isinstance(entity_id, str):
        registry.async_remove(entity_id)
    return []


class IdmTelemetryFirmwareSensor(IdmCoordinatorEntityBase, SensorEntity):
    """Latest matching community observation; it never installs firmware."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:chip"

    def __init__(self, coordinator: IdmCoordinator) -> None:
        super().__init__(coordinator)
        assert coordinator.config_entry is not None
        self._entry = coordinator.config_entry
        self._attr_unique_id = build_entity_unique_id(self._entry.entry_id, KEY)
        self.entity_description = SensorEntityDescription(key=KEY, translation_key=KEY)

    @property
    def _telemetry(self) -> Telemetry | None:
        telemetry = getattr(self._entry.runtime_data, "telemetry", None)
        return telemetry if isinstance(telemetry, Telemetry) else None

    @property
    def available(self) -> bool:
        telemetry = self._telemetry
        return (
            self._entry.options.get(CONF_TELEMETRY) is True
            and telemetry is not None
            and bool(telemetry.firmware_result)
        )

    @property
    def native_value(self) -> str | None:
        telemetry = self._telemetry
        value = telemetry.firmware_result.get("latest_firmware") if telemetry is not None else None
        return value if isinstance(value, str) else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        telemetry = self._telemetry
        return dict(telemetry.firmware_result) if telemetry is not None else {"status": "not_ready"}

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (telemetry := self._telemetry) is not None:
            self.async_on_remove(telemetry.async_add_firmware_listener(self._async_firmware_updated))
        self.async_on_remove(self._entry.add_update_listener(self._async_options_updated))

    @callback
    def _async_firmware_updated(self) -> None:
        self.async_write_ha_state()

    async def _async_options_updated(self, hass: HomeAssistant, entry: Any) -> None:
        if (
            entry.options.get(CONF_TELEMETRY) is not True
            or entry.options.get(CONF_TELEMETRY_POLICY) != TELEMETRY_POLICY
        ):
            registry = er.async_get(hass)
            if self.entity_id in registry.entities:
                registry.async_remove(self.entity_id)
            else:
                await self.async_remove()
