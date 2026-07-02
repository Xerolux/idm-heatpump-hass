"""Base entity for IDM Heatpump integration."""

from __future__ import annotations

# IDM Heatpump for Home Assistant
# © 2026 Xerolux — Inoffizielle Community-Integration für IDM Navigator 2.0 / 10 Wärmepumpen
# Erstellt von Xerolux | https://github.com/Xerolux/idm-heatpump-hass
# Lizenz: MIT

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from idm_heatpump import RegisterDef

from .const import DOMAIN, MANUFACTURER
from .coordinator import IdmCoordinator


def build_entity_unique_id(entry_id: str, entity_key: str) -> str:
    """Build a stable entity unique ID independent of connection settings."""
    return f"{entry_id}_{entity_key}"


class IdmEntity(CoordinatorEntity[IdmCoordinator]):
    """Base class for all IDM Heatpump entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: IdmCoordinator,
        reg: RegisterDef,
        entity_desc: EntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self._register = reg
        self.entity_description = entity_desc
        entry_id = coordinator.config_entry.entry_id  # type: ignore[union-attr]
        self._attr_unique_id = build_entity_unique_id(entry_id, reg.name)
        device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},  # type: ignore[union-attr]
            name=coordinator.config_entry.title,  # type: ignore[union-attr]
            manufacturer=MANUFACTURER,
            model=coordinator.model_name,
        )
        if coordinator.firmware_version:
            device_info["sw_version"] = coordinator.firmware_version
        self._attr_device_info = device_info

    @property
    def available(self) -> bool:
        if not super().available:
            return False
        if not self.coordinator.data or self._register.name not in self.coordinator.data:
            return False
        value = self.coordinator.data.get(self._register.name)
        if self.coordinator.is_register_unused(self._register.name, value):
            return False
        return True
