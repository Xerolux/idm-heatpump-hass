"""Diagnostics support for IDM Navigator Heatpump integration."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_HOST, CONF_PORT, CONF_SLAVE_ID, DOMAIN

TO_REDACT = {CONF_HOST, CONF_PORT}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    coordinator_data = hass.data[DOMAIN][entry.entry_id]
    coordinator = coordinator_data["coordinator"]

    diagnostics = {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "data": async_redact_data(
            {
                "scan_interval": coordinator.update_interval.total_seconds(),
                "registers_count": len(coordinator._registers),
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

    return diagnostics
