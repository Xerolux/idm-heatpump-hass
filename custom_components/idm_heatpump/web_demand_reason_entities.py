"""Home Assistant entities for the Navigator 10 web demand reason."""

from __future__ import annotations

from typing import Any, Final

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.helpers.device_registry import DeviceInfo

from .coordinator import IdmCoordinator
from .device_hierarchy import build_subdevice_info
from .entity import IdmCoordinatorEntityBase, build_entity_unique_id
from .web_demand_reason import WebDemandReasonState

_PV_BIT: Final = 32


def _nav10_demand_reason(coordinator: IdmCoordinator) -> WebDemandReasonState | None:
    """Return the demand reason state of a Navigator 10 web supplement."""
    supplement = coordinator.web_supplement
    if supplement is None or supplement.web_variant != "nav10":
        return None
    return supplement.demand_reason


def web_demand_reason_sensor_entities(coordinator: IdmCoordinator) -> list[IdmWebDemandReasonSensor]:
    """Create the demand reason sensor for a Navigator 10 web supplement."""
    if _nav10_demand_reason(coordinator) is None:
        return []
    return [IdmWebDemandReasonSensor(coordinator)]


def web_demand_reason_binary_entities(coordinator: IdmCoordinator) -> list[IdmWebDemandReasonPvBinarySensor]:
    """Create the PV demand reason binary sensor for a Navigator 10 web supplement."""
    if _nav10_demand_reason(coordinator) is None:
        return []
    return [IdmWebDemandReasonPvBinarySensor(coordinator)]


class IdmWebDemandReasonSensor(IdmCoordinatorEntityBase, SensorEntity):
    """Human-readable demand reason from the Navigator 10 web interface."""

    def __init__(self, coordinator: IdmCoordinator) -> None:
        super().__init__(coordinator)
        entry_id = coordinator.config_entry.entry_id  # type: ignore[union-attr]
        self._attr_unique_id = build_entity_unique_id(entry_id, "web_demand_reason")
        self.entity_description = SensorEntityDescription(
            key="web_demand_reason",
            translation_key="web_demand_reason",
            icon="mdi:format-list-checks",
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Place the sensor on the PV subdevice when the hierarchy is enabled."""
        if subdevice := build_subdevice_info(self.coordinator, "web_demand_reason"):
            return subdevice
        return super().device_info

    def _state(self) -> WebDemandReasonState | None:
        return _nav10_demand_reason(self.coordinator)

    @property
    def native_value(self) -> str | None:
        state = self._state()
        return state.label if state else None

    @property
    def available(self) -> bool:
        return super().available and self._state() is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        state = self._state()
        if state is None:
            return {}
        return {
            "nodes": [
                {
                    "path": node.path,
                    "operation_mode": node.operation_mode,
                    "info": node.info,
                    "reason": node.reason,
                }
                for node in state.nodes
            ],
            "pv_bit": _PV_BIT,
        }


class IdmWebDemandReasonPvBinarySensor(IdmCoordinatorEntityBase, BinarySensorEntity):
    """Binary sensor: the controller itself reports PV as demand reason."""

    def __init__(self, coordinator: IdmCoordinator) -> None:
        super().__init__(coordinator)
        entry_id = coordinator.config_entry.entry_id  # type: ignore[union-attr]
        self._attr_unique_id = build_entity_unique_id(entry_id, "web_demand_reason_pv")
        self.entity_description = BinarySensorEntityDescription(
            key="web_demand_reason_pv",
            translation_key="web_demand_reason_pv",
            icon="mdi:solar-power",
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Place the sensor on the PV subdevice when the hierarchy is enabled."""
        if subdevice := build_subdevice_info(self.coordinator, "web_demand_reason_pv"):
            return subdevice
        return super().device_info

    def _state(self) -> WebDemandReasonState | None:
        return _nav10_demand_reason(self.coordinator)

    @property
    def is_on(self) -> bool | None:
        state = self._state()
        return state.pv_active if state else None

    @property
    def available(self) -> bool:
        return super().available and self._state() is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        state = self._state()
        if state is None:
            return {}
        return {
            "reason": state.label,
            "pv_bit": _PV_BIT,
        }
