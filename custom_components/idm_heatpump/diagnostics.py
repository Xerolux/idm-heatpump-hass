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

from .const import CONF_HOST, CONF_PORT, CONF_SLAVE_ID, CONF_WEB_HOST, CONF_WEB_PIN, DOMAIN
from .versions import async_runtime_versions

TO_REDACT = {CONF_HOST, CONF_PORT, CONF_SLAVE_ID, CONF_WEB_HOST, CONF_WEB_PIN}
# Device identifiers must not leak into diagnostics either.
TO_REDACT.update({"myidm_id", "serial_number", "serial"})


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


def _sanitized_error_message(error: Any, *, fallback: str) -> str | None:
    """Return a useful error category without URLs, hosts, PINs or query data.

    Error strings from the underlying web or Modbus transport clients can
    embed host, IP, port or other connection details (e.g. "could not
    connect to 192.168.1.10:502"). Only a leading identifier-shaped
    ``SomeError: ...`` token is kept as a category label; anything else —
    which is exactly where private data would live — is replaced by
    ``fallback``.
    """
    if not isinstance(error, str) or not error.strip():
        return None
    clean_error = error.strip()
    if clean_error == "No web supplement data returned":
        return clean_error
    error_type, _, _details = clean_error.partition(":")
    clean_type = error_type.strip()
    if clean_type.isidentifier() and clean_type.endswith(("Error", "Exception", "Failed", "Failure")):
        return clean_type
    return fallback


def _client_diagnostics(coordinator: Any) -> dict[str, Any]:
    """Return the API client's diagnostics with free-text error content sanitized.

    ``async_redact_data`` (applied by the caller) only redacts by dict key, so
    it cannot catch a host/port embedded inside ``last_error``'s free-text
    message (e.g. "could not connect to 192.168.1.10:502"). That field is
    sanitized here to a safe category label before redaction ever runs.
    """
    getter = getattr(coordinator, "client_diagnostics", None)
    if not callable(getter):
        return {}
    diagnostics = getter()
    if not isinstance(diagnostics, dict):
        return {}
    diagnostics = dict(diagnostics)
    if "last_error" in diagnostics:
        diagnostics["last_error"] = _sanitized_error_message(diagnostics["last_error"], fallback="Connection error")
    return diagnostics


def _sanitized_web_error(error: Any) -> str | None:
    """Return a useful error category without URLs, hosts, PINs or query data."""
    return _sanitized_error_message(error, fallback="Web supplement error")


def _web_supplement_diagnostics(coordinator: Any) -> dict[str, Any]:
    return {
        "enabled": bool(getattr(coordinator, "web_enabled", False)),
        "available": getattr(coordinator, "web_supplement", None) is not None,
        "last_error": _sanitized_web_error(getattr(coordinator, "last_web_error", None)),
        "available_values": list(getattr(coordinator, "web_value_keys", ()) or ()),
        "missing_core_values": list(getattr(coordinator, "missing_web_core_values", ()) or ()),
    }


def _model_conflict_diagnostics(coordinator: Any) -> dict[str, Any]:
    """Structured, redacted model-conflict summary for #170 diagnostics.

    Only detection-source fields are emitted (selected/stored family, web variant,
    firmware evidence, manual override, conflict flag). No host, PIN, serial, or
    other private connection data is included.
    """
    summary = getattr(coordinator, "model_conflict_summary", None)
    if not isinstance(summary, dict):
        return {
            "selected_family": None,
            "stored_family": None,
            "web_variant": None,
            "software_version": None,
            "manual_override": None,
            "conflict": False,
        }
    return {
        "selected_family": summary.get("selected_family"),
        "stored_family": summary.get("stored_family"),
        "web_variant": summary.get("web_variant"),
        "software_version": summary.get("software_version"),
        "manual_override": summary.get("manual_override"),
        "conflict": bool(summary.get("conflict")),
    }


def _controller_stats_cross_reference(coordinator: Any) -> dict[str, Any]:
    """Emit the syscount cross-reference for every known register that is
    currently present in the coordinator's data.

    Lets users correlate their Home Assistant reading with the controller's
    on-device ``syscount.ini`` counter and the KNX example-project object
    number, without having to pull the SD card. Only registers that are
    actually in ``coordinator.data`` are listed; absent registers are
    omitted so the diagnostics stay focused on what the integration can
    really see on this plant.

    No values are emitted here - this is purely a label cross-reference.
    """
    from .controller_stats_reference import SYSCOUNT_REGISTER_REFERENCE

    data = getattr(coordinator, "data", None) or {}
    rows: dict[str, Any] = {}
    for register_name in sorted(SYSCOUNT_REGISTER_REFERENCE):
        if register_name not in data:
            continue
        ref = SYSCOUNT_REGISTER_REFERENCE[register_name]
        rows[register_name] = {
            "syscount_key": ref.syscount_key,
            "internal_stats_id": ref.internal_stats_id,
            "knx_object": ref.knx_object,
            "label": ref.semantic_label,
        }
    return rows


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    coordinator = entry.runtime_data.coordinator
    integration = await async_get_integration(hass, DOMAIN)
    versions = await async_runtime_versions(integration.manifest.get("version"))

    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "data": async_redact_data(
            {
                "scan_interval": (
                    coordinator.update_interval.total_seconds() if coordinator.update_interval is not None else None
                ),
                "registers_count": coordinator.registers_count,
                "last_update_success": coordinator.last_update_success,
                "communication": {
                    "last_poll_success": (
                        coordinator._last_poll_success.isoformat() if coordinator._last_poll_success else None
                    ),
                    "last_poll_duration_seconds": coordinator._last_poll_duration,
                    "consecutive_failures": coordinator._consecutive_poll_failures,
                    "total_polls": coordinator._total_poll_count,
                    "total_failures": coordinator._total_poll_failures,
                    "active_registers": coordinator._polling_plan_active_count,
                    "total_registers_in_plan": coordinator._polling_plan_total_count,
                    "polling_jitter_percent": coordinator._polling_jitter_percent,
                    "write_cooldown_seconds": coordinator._write_cooldown_seconds,
                },
                "model_name": coordinator.model_name,
                "firmware_version": coordinator.firmware_version,
                "versions": {
                    "integration": versions.integration,
                    "idm_heatpump_api": versions.api,
                    "modbus_connection": versions.modbus_connection,
                    "tmodbus": versions.tmodbus,
                    "pymodbus": versions.pymodbus,
                },
                "model_info": _model_info_diagnostics(coordinator.model_info),
                "model_conflict": _model_conflict_diagnostics(coordinator),
                "controller_stats_cross_reference": _controller_stats_cross_reference(coordinator),
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
