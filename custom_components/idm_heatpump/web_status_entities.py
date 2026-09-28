"""Home Assistant entities for the Navigator 10 status/overview frame."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory  # type: ignore[attr-defined]

from idm_heatpump import IdmWebStatus

from .coordinator import IdmCoordinator
from .device_hierarchy import build_subdevice_info
from .entity import IdmCoordinatorEntityBase, build_entity_unique_id


def _nav10_status(coordinator: IdmCoordinator) -> IdmWebStatus | None:
    """Return the status/overview state of a Navigator 10 web supplement."""
    supplement = coordinator.web_supplement
    if supplement is None or supplement.web_variant != "nav10":
        return None
    status = supplement.status
    return status if isinstance(status, IdmWebStatus) else None


def web_status_sensor_entities(coordinator: IdmCoordinator) -> list[IdmWebControllerClockSensor]:
    """Create the controller-clock sensor for a Navigator 10 web supplement.

    The variant is enough to create the entity: it reports unavailable until
    the first ``status/overview`` frame lands.
    """
    supplement = coordinator.web_supplement
    if supplement is None or supplement.web_variant != "nav10":
        return []
    return [IdmWebControllerClockSensor(coordinator)]


class IdmWebControllerClockSensor(IdmCoordinatorEntityBase, SensorEntity):
    """Controller clock with the connection-level status facts as attributes.

    The Navigator controller clock can drift, and the time-dependent L1/L2
    technician codes must be computed from the time shown on the display —
    exposing the clock as a sensor makes that drift visible. The attributes
    carry the facts that clarify support cases: jsonVersion, active user
    level, language, notification count and the frost-protection flag.
    """

    def __init__(self, coordinator: IdmCoordinator) -> None:
        super().__init__(coordinator)
        entry_id = coordinator.config_entry.entry_id  # type: ignore[union-attr]
        self._attr_unique_id = build_entity_unique_id(entry_id, "web_controller_clock")
        self.entity_description = SensorEntityDescription(
            key="web_controller_clock",
            translation_key="web_controller_clock",
            device_class=SensorDeviceClass.TIMESTAMP,
            entity_category=EntityCategory.DIAGNOSTIC,
            icon="mdi:clock-outline",
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Place the sensor on the controller subdevice when the hierarchy is enabled."""
        if subdevice := build_subdevice_info(self.coordinator, "web_controller_clock"):
            return subdevice
        return super().device_info

    def _state(self) -> IdmWebStatus | None:
        return _nav10_status(self.coordinator)

    @property
    def available(self) -> bool:
        # A pure web value: a Modbus outage must not hide the controller clock
        # (see IdmWebSensor.available).
        return self._state() is not None

    @property
    def native_value(self) -> datetime | None:
        status = self._state()
        if status is None or status.timestamp_ms is None:
            return None
        try:
            return datetime.fromtimestamp(status.timestamp_ms / 1000, tz=UTC)
        except (OverflowError, OSError, ValueError):
            return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        status = self._state()
        if status is None:
            return {}
        return {
            "json_version": status.json_version,
            "userlevel": status.userlevel,
            "language": status.language,
            "notification_count": status.notification_count,
            "frost_protection_active": status.frost_protection_active,
            "network": status.network,
            "authentication_enabled": status.authentication_enabled,
        }
