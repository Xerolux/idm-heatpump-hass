"""Service handlers for IDM Heatpump integration."""

from __future__ import annotations

# IDM Heatpump for Home Assistant
# © 2026 Xerolux — Inoffizielle Community-Integration für IDM Navigator 2.0 / 10 Wärmepumpen
# Erstellt von Xerolux | https://github.com/Xerolux/idm-heatpump-hass
# Lizenz: MIT

import logging
from collections.abc import Mapping
from functools import partial

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import issue_registry as ir

from idm_heatpump import RegisterDef
from idm_heatpump.client import DataType

from .const import DOMAIN
from .coordinator import IdmCoordinator

_LOGGER = logging.getLogger(__name__)

_SERVICES = ["set_system_mode", "acknowledge_errors", "write_register"]


async def async_setup_services(hass: HomeAssistant) -> None:
    """Register services. Called from async_setup (once per domain load)."""
    if hass.services.has_service(DOMAIN, "set_system_mode"):
        return

    hass.services.async_register(
        DOMAIN,
        "set_system_mode",
        partial(_handle_set_system_mode, hass),  # type: ignore[arg-type]
    )
    hass.services.async_register(
        DOMAIN,
        "acknowledge_errors",
        partial(_handle_acknowledge_errors, hass),  # type: ignore[arg-type]
    )
    hass.services.async_register(
        DOMAIN,
        "write_register",
        partial(_handle_write_register, hass),  # type: ignore[arg-type]
        supports_response=SupportsResponse.OPTIONAL,
    )


async def async_unload_services(hass: HomeAssistant) -> None:
    """Remove services when no more IDM entries are loaded."""
    loaded = [entry for entry in hass.config_entries.async_entries(DOMAIN) if entry.state == ConfigEntryState.LOADED]
    if len(loaded) > 1:
        return
    for service in _SERVICES:
        hass.services.async_remove(DOMAIN, service)


async def _get_coordinator(hass: HomeAssistant, call: ServiceCall) -> IdmCoordinator:
    """Return the first loaded IDM coordinator."""
    from homeassistant.helpers import entity_registry as er

    call_data = call.data if isinstance(call.data, Mapping) else {}

    requested_entry_id = None
    entity_ids = call_data.get("entity_id")
    if isinstance(entity_ids, list) and len(entity_ids) > 0:
        registry = er.async_get(hass)
        for entity_id in entity_ids:
            entity_entry = registry.async_get(entity_id)
            if entity_entry and entity_entry.config_entry_id:
                requested_entry_id = entity_entry.config_entry_id
                break
    elif isinstance(entity_ids, str):
        registry = er.async_get(hass)
        entity_entry = registry.async_get(entity_ids)
        if entity_entry and entity_entry.config_entry_id:
            requested_entry_id = entity_entry.config_entry_id

    if requested_entry_id is None:
        requested_entry_id = call_data.get("entry_id")
        if requested_entry_id is not None:
            requested_entry_id = str(requested_entry_id).strip()
            if not requested_entry_id:
                requested_entry_id = None

    loaded_entries = [
        entry for entry in hass.config_entries.async_entries(DOMAIN) if entry.state == ConfigEntryState.LOADED
    ]

    if requested_entry_id is not None:
        for entry in loaded_entries:
            if str(entry.entry_id) != requested_entry_id:
                continue
            try:
                coordinator = entry.runtime_data.coordinator
                if isinstance(coordinator, IdmCoordinator):
                    return coordinator
            except AttributeError:
                break
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="entry_not_loaded",
            translation_placeholders={"entry_id": requested_entry_id},
        )

    if len(loaded_entries) > 1:
        _LOGGER.debug(
            "Multiple loaded IDM entries found, using first loaded entry. "
            "Provide entry_id in service data for explicit selection."
        )

    for entry in loaded_entries:
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


async def _handle_write_register(hass: HomeAssistant, call: ServiceCall) -> ServiceResponse:
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
        ir.async_create_issue(
            hass,
            DOMAIN,
            "write_rejected",
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="write_rejected",
            translation_placeholders={"register": reg.name, "address": str(reg.address)},
        )
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="write_failed",
            translation_placeholders={"error": str(err)},
        ) from err
