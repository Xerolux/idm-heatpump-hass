"""Home Assistant entities for the effective connection state.

The integration supports four connection modes (auto, Modbus + web,
web-only, Modbus-only) that resolve automatically by default. These
diagnostic entities make the resulting reality visible on the dashboard:
which transports are actually live right now, which mode is configured,
and when the web path last answered.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.helpers.entity import EntityCategory  # type: ignore[attr-defined]

from .const import (
    connection_state_label,
    resolve_connection_mode,
)
from .coordinator import IdmCoordinator
from .entity import IdmCoordinatorEntityBase, build_entity_unique_id


def connection_sensor_entities(coordinator: IdmCoordinator) -> list[ConnectionSensorEntity]:
    """Create the connection-state sensors; they exist in every connection mode."""
    entities: list[ConnectionSensorEntity] = [IdmConnectionModeSensor(coordinator)]
    if coordinator.web_enabled:
        entities.append(IdmWebLastSuccessSensor(coordinator))
    return entities


def _modbus_transport_active(coordinator: IdmCoordinator) -> bool:
    """Modbus polling is active unless the entry runs in web-only mode."""
    return coordinator.update_interval is not None


def _web_transport_active(coordinator: IdmCoordinator) -> bool:
    """The web path is live when the last web refresh answered."""
    return coordinator.web_enabled and coordinator.web_alive is True


class IdmConnectionModeSensor(IdmCoordinatorEntityBase, SensorEntity):
    """Which transports the entry is actually using right now.

    The state is the live combination (``Modbus + Web``, ``Modbus only`` or
    ``Web only``); the attributes carry the configured mode and the detected
    web variant, so a fallback (for example Modbus down, web still serving)
    is visible at a glance.
    """

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:connection"

    def __init__(self, coordinator: IdmCoordinator) -> None:
        super().__init__(coordinator)
        entry_id = coordinator.config_entry.entry_id  # type: ignore[union-attr]
        self._attr_unique_id = build_entity_unique_id(entry_id, "connection_mode")
        self.entity_description = SensorEntityDescription(
            key="connection_mode",
            translation_key="connection_mode",
        )

    @property
    def native_value(self) -> str:
        coordinator = self.coordinator
        return connection_state_label(_modbus_transport_active(coordinator), _web_transport_active(coordinator))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        entry = self.coordinator.config_entry
        if entry is None:
            return {"configured_mode": "auto", "web_variant": self.coordinator.web_variant}
        return {
            "configured_mode": resolve_connection_mode(entry.options, entry.data),
            "web_variant": self.coordinator.web_variant,
        }


class IdmWebLastSuccessSensor(IdmCoordinatorEntityBase, SensorEntity):
    """When the local web interface last answered successfully."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:web-check"

    def __init__(self, coordinator: IdmCoordinator) -> None:
        super().__init__(coordinator)
        entry_id = coordinator.config_entry.entry_id  # type: ignore[union-attr]
        self._attr_unique_id = build_entity_unique_id(entry_id, "web_last_success")
        self.entity_description = SensorEntityDescription(
            key="web_last_success",
            translation_key="web_last_success",
        )

    @property
    def native_value(self) -> Any:
        return self.coordinator.web_last_success

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.web_last_success is not None


ConnectionSensorEntity = IdmConnectionModeSensor | IdmWebLastSuccessSensor
"""Union of the concrete connection-state sensor classes (for platform lists)."""
