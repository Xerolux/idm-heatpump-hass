"""Firmware observations gated solely by independent firmware consent."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorEntityDescription
from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .const import CONF_FIRMWARE_CHECK, CONF_FIRMWARE_CONSENT_AT, CONF_FIRMWARE_POLICY, DOMAIN
from .coordinator import IdmCoordinator
from .entity import IdmCoordinatorEntityBase, build_entity_unique_id
from .firmware_observations import FIRMWARE_POLICY, FirmwareObservations

KEY = "telemetry_latest_firmware"


def firmware_sensor_entities(
    hass: HomeAssistant, entry: Any, coordinator: IdmCoordinator
) -> list[IdmTelemetryFirmwareSensor]:
    """Remove registry remnants when consent is absent, including after restarts."""
    enabled = (
        entry.options.get(CONF_FIRMWARE_CHECK) is True
        and entry.options.get(CONF_FIRMWARE_POLICY) == FIRMWARE_POLICY
        and bool(entry.options.get(CONF_FIRMWARE_CONSENT_AT))
    )
    if enabled:
        return [IdmTelemetryFirmwareSensor(coordinator)]
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id("sensor", DOMAIN, build_entity_unique_id(entry.entry_id, KEY))
    if isinstance(entity_id, str):
        registry.async_remove(entity_id)
    return []


class _IdmFirmwareEntityBase(IdmCoordinatorEntityBase):
    """Latest matching community observation; it never installs firmware."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:chip"

    def __init__(self, coordinator: IdmCoordinator, key: str) -> None:
        super().__init__(coordinator)
        assert coordinator.config_entry is not None
        self._entry = coordinator.config_entry
        self._attr_unique_id = build_entity_unique_id(self._entry.entry_id, key)

    @property
    def _telemetry(self) -> FirmwareObservations | None:
        telemetry = getattr(self._entry.runtime_data, "firmware", None)
        return telemetry if isinstance(telemetry, FirmwareObservations) else None

    @property
    def available(self) -> bool:
        telemetry = self._telemetry
        return telemetry is not None and telemetry.enabled and bool(telemetry.firmware_result)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        telemetry = self._telemetry
        if telemetry is None:
            return {"status": "not_ready"}
        return dict(telemetry.firmware_result) | {
            "availability_note": "Community observation only; iDM or the installer must confirm availability and compatibility for this plant."
        }

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
            entry.options.get(CONF_FIRMWARE_CHECK) is not True
            or entry.options.get(CONF_FIRMWARE_POLICY) != FIRMWARE_POLICY
        ):
            registry = er.async_get(hass)
            if self.entity_id in registry.entities:
                registry.async_remove(self.entity_id)
            else:
                await self.async_remove()


class IdmTelemetryFirmwareSensor(_IdmFirmwareEntityBase, SensorEntity):
    """Latest matching community version; not a manufacturer availability claim."""

    def __init__(self, coordinator: IdmCoordinator) -> None:
        super().__init__(coordinator, KEY)
        self.entity_description = SensorEntityDescription(key=KEY, translation_key=KEY)

    @property
    def native_value(self) -> str | None:
        telemetry = self._telemetry
        value = telemetry.firmware_result.get("latest_firmware") if telemetry is not None else None
        return value if isinstance(value, str) else None


BINARY_KEY = "firmware_update_observed"


def firmware_binary_sensor_entities(
    hass: HomeAssistant, entry: Any, coordinator: IdmCoordinator
) -> list[IdmFirmwareObservedBinarySensor]:
    """Expose the orientation entity only with independent firmware consent."""
    if (
        entry.options.get(CONF_FIRMWARE_CHECK) is True
        and entry.options.get(CONF_FIRMWARE_POLICY) == FIRMWARE_POLICY
        and bool(entry.options.get(CONF_FIRMWARE_CONSENT_AT))
    ):
        return [IdmFirmwareObservedBinarySensor(coordinator)]
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(
        "binary_sensor", DOMAIN, build_entity_unique_id(entry.entry_id, BINARY_KEY)
    )
    if isinstance(entity_id, str):
        registry.async_remove(entity_id)
    return []


class IdmFirmwareObservedBinarySensor(_IdmFirmwareEntityBase, BinarySensorEntity):
    """A newer comparable community observation, explicitly unconfirmed."""

    _attr_icon = "mdi:binoculars"
    _attr_translation_key = BINARY_KEY

    def __init__(self, coordinator: IdmCoordinator) -> None:
        super().__init__(coordinator, BINARY_KEY)
        self.entity_description = BinarySensorEntityDescription(key=BINARY_KEY, translation_key=BINARY_KEY)

    @property
    def available(self) -> bool:
        telemetry = self._telemetry
        return bool(
            telemetry is not None
            and telemetry.enabled
            and isinstance(telemetry.firmware_result.get("newer_observed"), bool)
        )

    @property
    def is_on(self) -> bool | None:
        telemetry = self._telemetry
        value = telemetry.firmware_result.get("newer_observed") if telemetry is not None else None
        return value if isinstance(value, bool) else None
