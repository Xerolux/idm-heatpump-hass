# IDM Heatpump for Home Assistant
# © 2026 Xerolux — Inoffizielle Community-Integration für IDM Navigator 2.0 Wärmepumpen
# Erstellt von Xerolux | https://github.com/Xerolux/idm-heatpump-hass
# Lizenz: MIT
from __future__ import annotations
"""Service handlers for IDM Heatpump integration."""

import logging

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .const import DOMAIN
from .modbus_client import DataType, RegisterDef

_LOGGER = logging.getLogger(__name__)

_SERVICES = ["set_system_mode", "acknowledge_errors", "write_register"]


async def async_setup_services(hass: HomeAssistant) -> None:
    """Register services. Called from async_setup (once per domain load)."""
    if hass.services.has_service(DOMAIN, "set_system_mode"):
        return

    hass.services.async_register(
        DOMAIN,
        "set_system_mode",
        _handle_set_system_mode,
    )
    hass.services.async_register(
        DOMAIN,
        "acknowledge_errors",
        _handle_acknowledge_errors,
    )
    hass.services.async_register(
        DOMAIN,
        "write_register",
        _handle_write_register,
        supports_response=SupportsResponse.OPTIONAL,
    )


async def async_unload_services(hass: HomeAssistant) -> None:
    """Remove services when no more IDM entries are loaded."""
    loaded = [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state == ConfigEntryState.LOADED
    ]
    if len(loaded) > 1:
        return
    for service in _SERVICES:
        hass.services.async_remove(DOMAIN, service)


async def _get_coordinator(hass: HomeAssistant, call: ServiceCall):
    """Return the first loaded IDM coordinator."""
    from .coordinator import IdmCoordinator

    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.state == ConfigEntryState.LOADED:
            try:
                coordinator = entry.runtime_data.coordinator
                if isinstance(coordinator, IdmCoordinator):
                    return coordinator
            except AttributeError:
                continue
    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="no_device_configured",
    )


async def _handle_set_system_mode(hass: HomeAssistant, call: ServiceCall) -> None:
    coordinator = await _get_coordinator(hass, call)

    mode_map = {
        # German
        "standby": 0,
        "automatik": 1,
        "abwesend": 2,
        "urlaub": 3,
        "nur warmwasser": 4,
        "nur heizung/kuehlung": 5,
        # English aliases
        "automatic": 1,
        "away": 2,
        "holiday": 3,
        "hot water only": 4,
        "heating/cooling only": 5,
    }

    mode_str = call.data.get("mode", "").lower()
    mode_val = mode_map.get(mode_str)

    if mode_val is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_mode",
            translation_placeholders={"mode": mode_str},
        )

    reg = RegisterDef(
        address=1005,
        datatype=DataType.UCHAR,
        name="system_mode",
        writable=True,
    )
    await coordinator.async_write_register(reg, mode_val)


async def _handle_acknowledge_errors(hass: HomeAssistant, call: ServiceCall) -> None:
    coordinator = await _get_coordinator(hass, call)
    reg = RegisterDef(
        address=1999,
        datatype=DataType.UCHAR,
        name="error_acknowledge",
        writable=True,
    )
    await coordinator.async_write_register(reg, 1)


async def _handle_write_register(
    hass: HomeAssistant, call: ServiceCall
) -> ServiceResponse:
    coordinator = await _get_coordinator(hass, call)

    if call.data.get("acknowledge_risk") is not True:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="acknowledge_risk_required",
        )

    address = int(call.data["address"])
    value = call.data["value"]

    _DATATYPE_MAP = {
        "uint16": DataType.UINT16,
        "int16": DataType.INT16,
        "float": DataType.FLOAT,
        "uchar": DataType.UCHAR,
        "bool": DataType.BOOL,
    }
    datatype_str = str(call.data.get("datatype", "uint16")).lower()
    datatype = _DATATYPE_MAP.get(datatype_str)
    if datatype is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_datatype",
            translation_placeholders={"datatype": datatype_str},
        )

    try:
        value = int(value) if datatype != DataType.FLOAT else float(value)
    except (ValueError, TypeError):
        _LOGGER.debug("Value %r is not numeric, passing as-is", value)

    reg = RegisterDef(
        address=address,
        datatype=datatype,
        name=f"manual_{address}",
        writable=True,
    )

    try:
        await coordinator.client.write_register(reg, value)
        _LOGGER.warning("Manual register write: address=%d value=%s", address, value)
        return {"success": True, "address": address, "value": str(value)}
    except Exception as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="write_failed",
            translation_placeholders={"error": str(err)},
        ) from err
