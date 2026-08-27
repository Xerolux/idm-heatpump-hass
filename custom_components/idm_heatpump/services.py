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

from .adapter_glt import EXTERNAL_POWER_MEASUREMENT_NAMES
from .const import (
    CONF_KNX_BASE_ADDRESS,
    CONF_KNX_GROUPS,
    CONF_KNX_OVERRIDES,
    DEFAULT_KNX_BASE_ADDRESS,
    DOMAIN,
    HEATING_CIRCUITS,
    REGISTER_ADDRESS_ERROR_ACKNOWLEDGE,
    REGISTER_ADDRESS_SYSTEM_MODE,
)
from .coordinator import IdmCoordinator
from .error_messages import (
    classify_write_error,
    scoped_issue_id,
    write_error_detail,
    write_error_placeholders,
)
from .knx_catalog import (
    KNX_OBJECTS,
    OBJECT_GROUPS,
    InvalidGroupAddressError,
    resolve_group_addresses,
)

_LOGGER = logging.getLogger(__name__)


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
        partial(_handle_set_system_mode, hass),
    )
    hass.services.async_register(
        DOMAIN,
        "acknowledge_errors",
        partial(_handle_acknowledge_errors, hass),
    )
    hass.services.async_register(
        DOMAIN,
        "write_register",
        partial(_handle_write_register, hass),
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        "set_external_climate",
        partial(_handle_set_external_climate, hass),
    )
    hass.services.async_register(
        DOMAIN,
        "set_external_power",
        partial(_handle_set_external_power, hass),
    )
    hass.services.async_register(
        DOMAIN,
        "export_knx_group_addresses",
        partial(_handle_export_knx_group_addresses, hass),
        supports_response=SupportsResponse.ONLY,
    )


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
    except HomeAssistantError:
        raise
    except Exception as err:
        translation_key = classify_write_error(err)
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key=translation_key,
            translation_placeholders=write_error_placeholders(reg.name, err),
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

    _MISSING = object()
    address_raw = call.data.get("address", _MISSING)
    value = call.data.get("value", _MISSING)
    if address_raw is _MISSING or value is _MISSING:
        # services.yaml marks both required, but hass.services.async_register
        # is called below without a schema=, so that is UI-only guidance, not
        # a server-side guarantee (e.g. a script/automation calling the
        # service directly can omit either field).
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="write_register_missing_fields",
        )

    try:
        address = int(address_raw)
    except (ValueError, TypeError) as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_address",
            translation_placeholders={"value": str(address_raw)},
        ) from err

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
        safety_result = await coordinator.async_write_register(
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
    except HomeAssistantError:
        raise
    except Exception as err:
        entry_id = coordinator.config_entry.entry_id if coordinator.config_entry is not None else None
        ir.async_create_issue(
            hass,
            DOMAIN,
            scoped_issue_id(entry_id, "write_rejected"),
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="write_rejected",
            translation_placeholders={
                "register": reg.name,
                "address": str(reg.address),
                "detail": write_error_detail(err),
            },
        )
        translation_key = classify_write_error(err)
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key=translation_key,
            translation_placeholders=write_error_placeholders(reg.name, err),
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


def _writable_library_register(coordinator: IdmCoordinator, register_name: str) -> RegisterDef:
    """Return a writable register exposed by the library map."""
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
        (_writable_library_register(coordinator, f"hc_{circuit}_ext_room_temp"), room_temperature)
    ]

    if "humidity" in call.data and call.data.get("humidity") is not None:
        humidity = _coerce_float_field(call, "humidity")
        if not 0.0 <= humidity <= 100.0:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="external_climate_humidity_out_of_range",
                translation_placeholders={"value": str(humidity)},
            )
        writes.append((_writable_library_register(coordinator, "ext_humidity"), humidity))

    for reg, value in writes:
        await _async_write_register(coordinator, reg, value)


async def _handle_set_external_power(hass: HomeAssistant, call: ServiceCall) -> None:
    """Write the supplied external energy measurements via known GLT registers."""
    coordinator = await _get_coordinator(hass, call)
    supplied_fields = [
        field for field in EXTERNAL_POWER_MEASUREMENT_NAMES if field in call.data and call.data.get(field) is not None
    ]
    if not supplied_fields:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="external_power_no_values",
        )

    writes: list[tuple[RegisterDef, float]] = []
    for field in supplied_fields:
        value = _coerce_float_field(call, field)
        if field == "battery_soc" and (not value.is_integer() or not 0.0 <= value <= 100.0):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="external_power_battery_soc_out_of_range",
                translation_placeholders={"value": str(value)},
            )

        reg = _writable_library_register(coordinator, field)
        if (reg.min_val is not None and value < reg.min_val) or (reg.max_val is not None and value > reg.max_val):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="write_out_of_range",
                translation_placeholders=write_error_placeholders(field),
            )
        writes.append((reg, value))

    for reg, value in writes:
        await _async_write_register(coordinator, reg, value)


async def _handle_export_knx_group_addresses(hass: HomeAssistant, call: ServiceCall) -> ServiceResponse:
    """Return the KNX object table so it can be imported into ETS.

    Answers for the objects this controller actually exposes, which is the
    list a fresh ETS project needs: object number, IDM label, datapoint
    type, direction and the group address the bridge uses.
    """
    coordinator = await _get_coordinator(hass, call)
    call_data = call.data if isinstance(call.data, Mapping) else {}

    # The coordinator already holds its entry; going back through
    # hass.config_entries would only re-find the same object. It is typed
    # optional, so fall back to the defaults when it is not there.
    config_entry = coordinator.config_entry
    options: Mapping[str, object] = config_entry.options if config_entry is not None else {}

    base_address = str(call_data.get(CONF_KNX_BASE_ADDRESS) or options.get(CONF_KNX_BASE_ADDRESS) or "").strip()
    if not base_address:
        base_address = DEFAULT_KNX_BASE_ADDRESS
    requested_groups = call_data.get(CONF_KNX_GROUPS) or options.get(CONF_KNX_GROUPS) or list(OBJECT_GROUPS)
    # A single group may arrive as a bare string from a YAML call. str is a
    # Sequence, so iterating it would silently ask for the groups "s", "o",
    # "l", "a", "r" and answer with nothing.
    if isinstance(requested_groups, str):
        groups = [requested_groups]
    elif isinstance(requested_groups, Sequence):
        groups = [str(group) for group in requested_groups]
    else:
        groups = list(OBJECT_GROUPS)
    overrides = options.get(CONF_KNX_OVERRIDES) or {}

    available = {register for register in (coordinator.data or {}) if coordinator.get_register(register) is not None}
    for obj in KNX_OBJECTS:
        definition = coordinator.get_register(obj.register)
        if definition is not None and definition.write_only:
            available.add(obj.register)

    try:
        addresses = resolve_group_addresses(
            base_address,
            overrides=overrides if isinstance(overrides, Mapping) else {},
            registers=available,
            groups=groups,
        )
    except InvalidGroupAddressError as err:
        raise ServiceValidationError(str(err)) from err

    rows: list[JsonValueType] = []
    for obj in KNX_OBJECTS:
        address = addresses.get(obj.register)
        if address is None:
            continue
        definition = coordinator.get_register(obj.register)
        rows.append(
            {
                "object": obj.number,
                "group_address": address,
                "register": obj.register,
                "dpt": obj.dpt or "1.001",
                "group": obj.group,
                "writable": bool(obj.writable and definition is not None and definition.writable),
                "unit": (definition.unit or "") if definition is not None else "",
            }
        )

    return {
        "base_address": base_address,
        "count": len(rows),
        "objects": rows,
    }
