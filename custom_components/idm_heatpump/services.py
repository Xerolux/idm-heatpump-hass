"""Service handlers for IDM Heatpump integration."""

from __future__ import annotations

# IDM Heatpump for Home Assistant
# © 2026 Xerolux — Inoffizielle Community-Integration für IDM Navigator 2.0 / 10 Wärmepumpen
# Erstellt von Xerolux | https://github.com/Xerolux/idm-heatpump-hass
# Lizenz: MIT

import logging
import math
from collections.abc import Mapping, Sequence
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
from homeassistant.util.json import JsonValueType

from idm_heatpump import DataType, RegisterDef

from .const import DOMAIN, HEATING_CIRCUITS, REGISTER_ADDRESS_ERROR_ACKNOWLEDGE, REGISTER_ADDRESS_SYSTEM_MODE
from .coordinator import IdmCoordinator
from .error_messages import classify_write_error, write_error_placeholders

_LOGGER = logging.getLogger(__name__)

_SERVICES = ["set_system_mode", "acknowledge_errors", "write_register", "set_external_climate"]


def _encoded_registers_from_safety_result(safety_result: object) -> list[JsonValueType] | None:
    """Extract dry-run encoded registers from idm-heatpump-api write-safety results."""
    if safety_result is None:
        return None
    if isinstance(safety_result, Mapping):
        encoded = safety_result.get("encoded_registers")
    else:
        encoded = getattr(safety_result, "encoded_registers", None)
    if not isinstance(encoded, Sequence) or isinstance(encoded, (str, bytes, bytearray)):
        return None
    return [int(value) for value in encoded]


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
    hass.services.async_register(
        DOMAIN,
        "set_external_climate",
        partial(_handle_set_external_climate, hass),  # type: ignore[arg-type]
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
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="multiple_entries_select_entry",
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


async def _async_write_register(
    coordinator: IdmCoordinator,
    reg: RegisterDef,
    value: object,
    *,
    allow_custom_register: bool = False,
) -> None:
    """Write a known register and expose communication failures consistently."""
    try:
        await coordinator.async_write_register(
            reg,
            value,
            allow_custom_register=allow_custom_register,
        )
    except Exception as err:
        translation_key = classify_write_error(err)
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key=translation_key,
            translation_placeholders=write_error_placeholders(reg.name),
        ) from err


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

    reg = coordinator.get_register("system_mode")
    allow_custom = False
    if not isinstance(reg, RegisterDef) or not getattr(reg, "writable", False):
        reg = RegisterDef(
            address=REGISTER_ADDRESS_SYSTEM_MODE,
            datatype=DataType.UCHAR,
            name="system_mode",
            writable=True,
        )
        allow_custom = True
    await _async_write_register(coordinator, reg, mode_val, allow_custom_register=allow_custom)


async def _handle_acknowledge_errors(hass: HomeAssistant, call: ServiceCall) -> None:
    coordinator = await _get_coordinator(hass, call)
    reg = coordinator.get_register("error_acknowledge")
    allow_custom = False
    if not isinstance(reg, RegisterDef) or not getattr(reg, "writable", False):
        reg = RegisterDef(
            address=REGISTER_ADDRESS_ERROR_ACKNOWLEDGE,
            datatype=DataType.UCHAR,
            name="error_acknowledge",
            writable=True,
        )
        allow_custom = True
    await _async_write_register(coordinator, reg, 1, allow_custom_register=allow_custom)


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
    except (ValueError, TypeError, OverflowError) as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_value",
            translation_placeholders={"value": str(value), "datatype": datatype_str},
        ) from err

    reg = RegisterDef(
        address=address,
        datatype=datatype,
        name=f"manual_{address}",
        writable=True,
    )

    try:
        safety_result = coordinator.simulate_write(
            reg,
            value,
            dry_run=True,
            allow_custom_register=True,
        )
        await coordinator.client.write_register(
            reg,
            value,
            allow_custom_register=True,
        )
        _LOGGER.warning("Manual register write: address=%d value=%s", address, value)
        response: dict[str, JsonValueType] = {"success": True, "address": address, "value": str(value)}
        encoded_registers = _encoded_registers_from_safety_result(safety_result)
        if encoded_registers is not None:
            response["encoded_registers"] = encoded_registers
        return response
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
        translation_key = classify_write_error(err)
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key=translation_key,
            translation_placeholders=write_error_placeholders(reg.name),
        ) from err


def _coerce_float_field(call: ServiceCall, field: str) -> float:
    """Return a finite float from service data or raise a translated validation error."""
    raw_value = call.data.get(field)
    if raw_value is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_value",
            translation_placeholders={"value": str(raw_value), "datatype": "float"},
        )
    try:
        value = float(raw_value)
    except (TypeError, ValueError, OverflowError) as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_value",
            translation_placeholders={"value": str(raw_value), "datatype": "float"},
        ) from err
    if math.isnan(value) or math.isinf(value):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_value",
            translation_placeholders={"value": str(raw_value), "datatype": "float"},
        )
    return value


def _external_climate_register(coordinator: IdmCoordinator, register_name: str) -> RegisterDef:
    """Return a writable external climate register exposed by the library map."""
    reg = coordinator.get_register(register_name)
    if reg is None or not reg.writable:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="write_not_supported",
            translation_placeholders=write_error_placeholders(register_name),
        )
    return reg


async def _handle_set_external_climate(hass: HomeAssistant, call: ServiceCall) -> None:
    """Write external room temperature and optional humidity via known GLT registers."""
    coordinator = await _get_coordinator(hass, call)

    circuit = str(call.data.get("heating_circuit", "")).strip().lower()
    if circuit not in HEATING_CIRCUITS:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_heating_circuit",
            translation_placeholders={"heating_circuit": str(call.data.get("heating_circuit", ""))},
        )

    room_temperature = _coerce_float_field(call, "room_temperature")
    if not -20.0 <= room_temperature <= 60.0:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="external_climate_temperature_out_of_range",
            translation_placeholders={"value": str(room_temperature)},
        )

    writes: list[tuple[RegisterDef, float]] = [
        (_external_climate_register(coordinator, f"hc_{circuit}_ext_room_temp"), room_temperature)
    ]

    if "humidity" in call.data and call.data.get("humidity") is not None:
        humidity = _coerce_float_field(call, "humidity")
        if not 0.0 <= humidity <= 100.0:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="external_climate_humidity_out_of_range",
                translation_placeholders={"value": str(humidity)},
            )
        writes.append((_external_climate_register(coordinator, "ext_humidity"), humidity))

    for reg, value in writes:
        await _async_write_register(coordinator, reg, value)
