"""Diagnostics support for IDM Heatpump integration."""

from __future__ import annotations

# IDM Heatpump for Home Assistant
# © 2026 Xerolux — Inoffizielle Community-Integration für IDM Navigator 2.0 / 10 Wärmepumpen
# Erstellt von Xerolux | https://github.com/Xerolux/idm-heatpump-hass
# Lizenz: MIT

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from .const import CONF_HOST, CONF_PORT, CONF_SLAVE_ID, DOMAIN
from .versions import async_runtime_versions

TO_REDACT = {CONF_HOST, CONF_PORT, CONF_SLAVE_ID}


def _model_info_diagnostics(model_info: Any) -> dict[str, Any]:
    if model_info is None:
        return {
            "detected": False,
            "active_heating_circuits": [],
            "zone_modules": 0,
            "features": [],
            "capabilities": {},
        }

    return {
        "detected": True,
        "active_heating_circuits": list(getattr(model_info, "active_heating_circuits", []) or []),
        "zone_modules": int(getattr(model_info, "zone_modules", 0) or 0),
        "features": sorted(getattr(model_info, "features", set()) or []),
        "capabilities": {
            "solar": bool(getattr(model_info, "has_solar", False)),
            "isc": bool(getattr(model_info, "has_isc", False)),
            "pv": bool(getattr(model_info, "has_pv", False)),
            "cascade": bool(getattr(model_info, "has_cascade", False)),
        },
    }


def _client_diagnostics(coordinator: Any) -> dict[str, Any]:
    getter = getattr(coordinator, "client_diagnostics", None)
    if not callable(getter):
        return {}
    diagnostics = getter()
    if isinstance(diagnostics, dict):
        return diagnostics
    return {}


def _web_supplement_diagnostics(coordinator: Any) -> dict[str, Any]:
    return {
        "enabled": bool(getattr(coordinator, "web_enabled", False)),
        "available": getattr(coordinator, "web_supplement", None) is not None,
        "last_error": getattr(coordinator, "last_web_error", None),
        "available_values": list(getattr(coordinator, "web_value_keys", ()) or ()),
        "missing_core_values": list(getattr(coordinator, "missing_web_core_values", ()) or ()),
    }


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    coordinator = entry.runtime_data.coordinator
    integration = await async_get_integration(hass, DOMAIN)
    versions = await async_runtime_versions(integration.manifest.get("version"))

    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "data": async_redact_data(
            {
                "scan_interval": coordinator.update_interval.total_seconds(),
                "registers_count": coordinator.registers_count,
                "last_update_success": coordinator.last_update_success,
                "model_name": coordinator.model_name,
                "firmware_version": coordinator.firmware_version,
                "versions": {
                    "integration": versions.integration,
                    "idm_heatpump_api": versions.api,
                    "pymodbus": versions.pymodbus,
                },
                "model_info": _model_info_diagnostics(coordinator.model_info),
                "client_diagnostics": async_redact_data(_client_diagnostics(coordinator), TO_REDACT),
                "web_supplement": _web_supplement_diagnostics(coordinator),
                "unused_registers": sorted(coordinator.unused_registers),
                "unsupported_registers": sorted(coordinator.unsupported_registers),
                "sensor_count": len(coordinator.sensor_descriptions),
                "binary_sensor_count": len(coordinator.binary_sensor_descriptions),
                "number_count": len(coordinator.number_descriptions),
                "select_count": len(coordinator.select_descriptions),
                "switch_count": len(coordinator.switch_descriptions),
            },
            TO_REDACT,
        ),
    }
