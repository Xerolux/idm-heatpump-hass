# IDM Heatpump for Home Assistant
# © 2026 Xerolux — Inoffizielle Community-Integration für IDM Navigator 2.0 Wärmepumpen
# Erstellt von Xerolux | https://github.com/Xerolux/idm-heatpump-hass
# Lizenz: MIT
from __future__ import annotations
"""Diagnostics support for IDM Heatpump integration."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_HOST, CONF_PORT

TO_REDACT = {CONF_HOST, CONF_PORT}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    coordinator = entry.runtime_data.coordinator

    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "data": async_redact_data(
            {
                "scan_interval": coordinator.update_interval.total_seconds(),
                "registers_count": coordinator.registers_count,
                "last_update_success": coordinator.last_update_success,
                "sensor_count": len(coordinator.sensor_descriptions),
                "binary_sensor_count": len(coordinator.binary_sensor_descriptions),
                "number_count": len(coordinator.number_descriptions),
                "select_count": len(coordinator.select_descriptions),
                "switch_count": len(coordinator.switch_descriptions),
            },
            TO_REDACT,
        ),
    }
