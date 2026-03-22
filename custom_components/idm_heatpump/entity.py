from __future__ import annotations
"""Base entity for IDM Heatpump integration."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL, UNUSED_VALUE
from .coordinator import IdmCoordinator
from .modbus_client import RegisterDef


class IdmEntity(CoordinatorEntity[IdmCoordinator]):
    """Base class for all IDM Heatpump entities."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: IdmCoordinator, reg: RegisterDef, entity_desc
    ) -> None:
        super().__init__(coordinator)
        self._register = reg
        self.entity_description = entity_desc
        self._attr_unique_id = (
            f"{coordinator.client.host}:{coordinator.client.port}_{reg.name}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            name=coordinator.config_entry.title,
            manufacturer=MANUFACTURER,
            model=MODEL,
        )

    @property
    def available(self) -> bool:
        if not super().available:
            return False
        if not self.coordinator.data or self._register.name not in self.coordinator.data:
            return False
        if self.coordinator.hide_unused:
            value = self.coordinator.data.get(self._register.name)
            if isinstance(value, (int, float)) and abs(value - UNUSED_VALUE) < 0.01:
                return False
        return True
