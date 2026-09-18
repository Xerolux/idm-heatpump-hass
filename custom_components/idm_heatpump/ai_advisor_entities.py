"""Experimental report display and explicit, read-only report request buttons."""

from __future__ import annotations

from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError

from .ai_advisor import AdvisorError, AiAdvisor
from .const import DOMAIN
from .coordinator import IdmCoordinator
from .entity import IdmCoordinatorEntityBase, build_entity_unique_id


class IdmAiReportSensor(IdmCoordinatorEntityBase, SensorEntity):
    """Keep generated prose in attributes, never in the 255-character state."""

    _unrecorded_attributes = frozenset({"report", "facts"})

    def __init__(self, coordinator: IdmCoordinator, manager: AiAdvisor) -> None:
        super().__init__(coordinator)
        assert coordinator.config_entry is not None
        self.manager = manager
        self._attr_unique_id = build_entity_unique_id(coordinator.config_entry.entry_id, "ai_report")
        self.entity_description = SensorEntityDescription(
            key="ai_report",
            translation_key="ai_report",
            icon="mdi:robot-outline",
            entity_category=EntityCategory.DIAGNOSTIC,
        )

    @property
    def available(self) -> bool:
        return True

    @property
    def native_value(self) -> str:
        return self.manager.status

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "experimental": True,
            "read_only": True,
            "report": self.manager.report,
            "generated_at": self.manager.generated_at,
            "report_type": self.manager.report_type,
            "facts": self.manager.facts,
            "error": self.manager.error,
            "history_samples": len(self.manager.records),
        }

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.manager.on_update = self.async_write_ha_state
        self.manager.observe()

    @callback
    def _handle_coordinator_update(self) -> None:
        self.manager.observe()
        super()._handle_coordinator_update()

    async def async_will_remove_from_hass(self) -> None:
        await self.manager.async_stop()
        await super().async_will_remove_from_hass()


class IdmAiReportButton(IdmCoordinatorEntityBase, ButtonEntity):
    """Ask the local model for a report; never control the heat pump."""

    _attr_icon = "mdi:robot-outline"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: IdmCoordinator, report_type: str) -> None:
        super().__init__(coordinator)
        assert coordinator.config_entry is not None
        self.report_type = report_type
        self._attr_translation_key = f"ai_report_{report_type}"
        self._attr_unique_id = build_entity_unique_id(coordinator.config_entry.entry_id, self._attr_translation_key)

    async def async_press(self) -> None:
        assert self.coordinator.config_entry is not None
        manager = getattr(self.coordinator.config_entry.runtime_data, "ai_advisor", None)
        if not isinstance(manager, AiAdvisor):
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="ai_disabled")
        try:
            await manager.async_generate(self.report_type)
        except AdvisorError as err:
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key=str(err)) from err
