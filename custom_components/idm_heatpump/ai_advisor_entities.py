"""Experimental report display and explicit, read-only report request buttons."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo

from .ai_advisor import AdvisorError, AiAdvisor, capture_sample
from .ai_learning import BASELINE_MIN_DAYS, BASELINE_MIN_HOURS
from .const import DOMAIN
from .coordinator import IdmCoordinator
from .device_hierarchy import build_subdevice_info
from .entity import IdmCoordinatorEntityBase, build_entity_unique_id


class IdmAiReportSensor(IdmCoordinatorEntityBase, SensorEntity):
    """Keep generated prose in attributes, never in the 255-character state."""

    _unrecorded_attributes = frozenset({"report", "facts", "reports"})

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
        next_run = self.manager.next_run
        return {
            "experimental": True,
            "read_only": True,
            "report": self.manager.report,
            "generated_at": self.manager.generated_at,
            "report_type": self.manager.report_type,
            "facts": self.manager.facts,
            "error": self.manager.error,
            "history_samples": len(self.manager.records),
            "reports": self.manager.reports,
            "next_run": next_run,
            "next_run_utc": datetime.fromtimestamp(next_run, UTC).isoformat() if next_run is not None else None,
            "storage_limit_mib": self.manager.storage_limit // (1024 * 1024),
            "model_text_verified": False,
            "cloud_budget_day_utc": self.manager.cloud_day,
            "cloud_requests_reserved": self.manager.cloud_requests,
            "cloud_budget_available_today": self.manager.cloud_budget_available_today,
        }

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.manager.on_update = self._write_state_if_added

    @callback
    def _write_state_if_added(self) -> None:
        # The adviser outlives this entity: it keeps observing while the user
        # has the report sensor disabled or removes it from HA.
        if self.hass is not None:
            self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        # Bound methods compare equal by instance and function, not identity.
        if self.manager.on_update == self._write_state_if_added:
            self.manager.on_update = lambda: None
        await super().async_will_remove_from_hass()


class IdmAiReportButton(IdmCoordinatorEntityBase, ButtonEntity):
    """Request a report; never control the heat pump."""

    _attr_icon = "mdi:robot-outline"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: IdmCoordinator, report_type: str) -> None:
        super().__init__(coordinator)
        assert coordinator.config_entry is not None
        self.report_type = report_type
        self._attr_translation_key = f"ai_report_{report_type}"
        self._attr_unique_id = build_entity_unique_id(coordinator.config_entry.entry_id, self._attr_translation_key)

    @property
    def device_info(self) -> DeviceInfo:
        return build_subdevice_info(self.coordinator, "ai_report") or super().device_info

    async def async_press(self) -> None:
        assert self.coordinator.config_entry is not None
        manager = getattr(self.coordinator.config_entry.runtime_data, "ai_advisor", None)
        if not isinstance(manager, AiAdvisor):
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="ai_disabled")
        try:
            await manager.async_generate(self.report_type)
        except AdvisorError as err:
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key=str(err)) from err


AI_METRICS = ("ai_learning_status", "ai_storage_used", "ai_coverage", "ai_observed_cop")


class IdmAiMetricSensor(IdmCoordinatorEntityBase, SensorEntity):
    """Compact recordable metrics for dashboard history graphs."""

    def __init__(self, coordinator: IdmCoordinator, manager: AiAdvisor, key: str) -> None:
        super().__init__(coordinator)
        assert coordinator.config_entry is not None
        self.manager = manager
        self.entity_description = SensorEntityDescription(
            key=key,
            translation_key=key,
            icon="mdi:chart-line",
            native_unit_of_measurement={"ai_storage_used": "MiB", "ai_coverage": "%"}.get(key),
            entity_category=EntityCategory.DIAGNOSTIC,
        )
        self._attr_unique_id = build_entity_unique_id(coordinator.config_entry.entry_id, key)

    @property
    def available(self) -> bool:
        return True

    @property
    def native_value(self) -> str | float | None:
        key = self.entity_description.key
        if key == "ai_storage_used":
            return round(self.manager.storage_bytes / (1024 * 1024), 3)
        if key == "ai_learning_status":
            if not self.manager.learning_enabled:
                return "disabled"
            return str(self.manager.learning.comparison(capture_sample(self.coordinator, time.time()))["status"])
        period = self.manager.observed_period
        value = period.get("energy_counter_coverage_percent" if key == "ai_coverage" else "cop_observed")
        return float(value) if value is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if self.entity_description.key != "ai_learning_status":
            return {}
        if not self.manager.learning_enabled:
            return {"enabled": False}
        comparison = self.manager.learning.comparison(capture_sample(self.coordinator, time.time()))
        totals = self.manager.learning.summary(time.time())
        return {
            "enabled": True,
            "status": comparison.get("status"),
            "days": comparison.get("days"),
            "hours": comparison.get("hours"),
            "required_days": BASELINE_MIN_DAYS,
            "required_hours": BASELINE_MIN_HOURS,
            "mode": comparison.get("mode"),
            "outdoor_bin_c": comparison.get("outdoor_bin_c"),
            "baseline_cop": comparison.get("baseline_cop"),
            "current_cop": comparison.get("current_cop"),
            "deviation_percent": comparison.get("deviation_percent"),
            "total_days": totals.get("total_days"),
            "total_hours": totals.get("total_hours"),
            "total_buckets": totals.get("buckets"),
            "modes": totals.get("modes"),
            "oldest_learning_day_utc": totals.get("oldest_learning_day_utc"),
        }
