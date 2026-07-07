"""Register definitions for IDM Navigator 2.0 / 10 heat pumps.

All Modbus register addresses, data types, units, and read/write capabilities
are defined here. Registers are organized by functional group and provide
entity descriptions for Home Assistant platforms.
"""

from __future__ import annotations

# IDM Heatpump for Home Assistant
# © 2026 Xerolux — Inoffizielle Community-Integration für IDM Navigator 2.0 / 10 Wärmepumpen
# Erstellt von Xerolux | https://github.com/Xerolux/idm-heatpump-hass
# Lizenz: MIT

import logging
from typing import Any

from idm_heatpump import IdmModelInfo, RegisterDef

from .library_adapter import (
    get_library_binary_sensors,
    get_library_heating_circuit_sensors,
    get_library_numbers,
    get_library_selects,
    get_library_sensors,
    get_library_switches,
    get_library_zone_numbers,
    get_library_zone_selects,
    get_library_zone_sensors,
)

_LOGGER = logging.getLogger(__name__)


def normalize_zone_rooms(zone_rooms: dict[Any, Any] | None) -> dict[int, int]:
    """Return zone room counts with integer keys from HA JSON options."""
    if not isinstance(zone_rooms, dict):
        return {}

    normalized: dict[int, int] = {}
    for key, value in zone_rooms.items():
        try:
            normalized[int(key)] = int(value)
        except (TypeError, ValueError):
            _LOGGER.debug("Ignoring invalid zone room option %r=%r", key, value)
    return normalized


ENTITY_ORDER_BLOCKS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "system_status",
        (
            "system_",
            "operating_mode",
            "failure",
            "error",
            "infosystem",
            "software",
            "firmware",
            "navigator",
            "heatpump_model",
        ),
    ),
    (
        "configuration_controls",
        (
            "enable_",
            "switch_",
            "system_mode",
            "demand_onetime",
            "external_request",
            "ext_switch",
            "evu",
        ),
    ),
    (
        "heating_circuits",
        (
            "hc_",
            "flow_temp_hk",
            "flow_temp_HK",
            "mixer_heating_circuit",
            "pump_heating_circuit",
            "room_temperature_HK",
        ),
    ),
    (
        "domestic_hot_water",
        (
            "dhw",
            "hotwater",
            "water_temp",
            "loading_temperature",
            "valve_heating_hotwater",
        ),
    ),
    (
        "heat_pump_core",
        (
            "outside_air",
            "airsource",
            "flow_",
            "return_",
            "heat_sink",
            "heat_source",
            "heatstore",
            "compressor",
            "condenser",
            "evapor",
            "hotgas",
            "liquid_line",
            "brine",
            "ventilator",
        ),
    ),
    (
        "zones",
        (
            "zm",
            "zone_",
        ),
    ),
    (
        "energy_pv_glt",
        (
            "pv_",
            "glt_",
            "current_electrical_power",
            "current_expected_power",
            "heating_demand",
            "cooling_demand",
            "ext_demand",
            "electric_",
            "battery_",
            "house_",
        ),
    ),
    (
        "runtime_energy",
        (
            "runtime_",
            "switch_cycles",
            "heat_quantity",
        ),
    ),
    (
        "cascade",
        ("cascade",),
    ),
)

_ENTITY_ORDER_INDEX = {group: index for index, (group, _patterns) in enumerate(ENTITY_ORDER_BLOCKS)}


def entity_order_group(register_name: str) -> int:
    """Return a stable functional ordering group for an entity register."""
    lowered = register_name.casefold()
    for group, patterns in ENTITY_ORDER_BLOCKS:
        if any(lowered.startswith(pattern.casefold()) or pattern.casefold() in lowered for pattern in patterns):
            return _ENTITY_ORDER_INDEX[group]
    return len(ENTITY_ORDER_BLOCKS)


def description_sort_key(desc: dict[str, Any]) -> tuple[int, int, str, int]:
    """Sort entity descriptions into stable, user-facing functional blocks."""
    reg: RegisterDef = desc["register"]
    name = str(getattr(desc["description"], "name", "") or reg.name)
    entity_category = getattr(desc["description"], "entity_category", None)
    category_value = getattr(entity_category, "value", entity_category)
    category_rank = {"config": 0, None: 1, "diagnostic": 2}.get(category_value, 1)
    return (entity_order_group(reg.name), category_rank, name.casefold(), reg.address)


def sort_entity_descriptions(descriptions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return descriptions grouped consistently for Home Assistant entity lists."""
    return sorted(descriptions, key=description_sort_key)


_ENTITY_ORDER_GROUPS = ENTITY_ORDER_BLOCKS
_entity_order_group = entity_order_group
_description_sort_key = description_sort_key
_sort_descriptions = sort_entity_descriptions


# ============================================================
# PUBLIC FUNCTIONS - Collect all register descriptions
# All registers are sourced from the idm_heatpump library via library_adapter.
# ============================================================


def get_all_sensor_descriptions(
    circuits: list[str],
    zone_count: int,
    zone_rooms: dict[int, int],
    enable_cascade: bool = False,
    model_info: IdmModelInfo | None = None,
) -> list[dict[str, Any]]:
    """
    Assembles all sensor descriptions.

    The library + adapter is now the preferred source.
    Local definitions are kept for rich German names and specific icons.
    """
    descriptions = []
    zone_rooms = normalize_zone_rooms(zone_rooms)

    # Library + Adapter is now the primary and preferred source.
    # zone_modules=0: zone registers are added below via the per-zone loop,
    # which respects each zone's configured room count (zone_rooms). The
    # library's bulk zone handling only supports one uniform room count for
    # all zones, so it must not also generate zone registers here.
    try:
        descriptions.extend(
            get_library_sensors(
                model_info=model_info,
                circuits=circuits,
                zone_modules=0,
                enable_cascade=enable_cascade,
            )
        )
    except Exception:
        _LOGGER.warning("Failed to load library sensor descriptions", exc_info=True)

    # Spezialisierte Generatoren für Heizkreise und Zonen aus dem Adapter
    for circuit in circuits:
        descriptions.extend(get_library_heating_circuit_sensors(circuit))
    for z in range(zone_count):
        rooms = zone_rooms.get(z, 6)
        descriptions.extend(get_library_zone_sensors(z + 1, rooms))

    # Legacy old generators are fully disabled for sensors.
    # The migration to library + adapter is the goal.

    # Deduplicate
    seen_keys: set[str] = set()
    unique: list[dict[str, Any]] = []
    for desc in descriptions:
        key = desc["description"].key
        if key not in seen_keys:
            seen_keys.add(key)
            unique.append(desc)

    return sort_entity_descriptions(unique)


def get_all_binary_sensor_descriptions(
    circuits: list[str],
    zone_count: int,
    zone_rooms: dict[int, int],
    enable_cascade: bool = False,
    model_info: IdmModelInfo | None = None,
) -> list[dict[str, Any]]:
    descriptions = []
    zone_rooms = normalize_zone_rooms(zone_rooms)
    try:
        descriptions.extend(
            get_library_binary_sensors(
                circuits=circuits,
                zone_modules=zone_count,
                model_info=model_info,
            )
        )
    except Exception:
        _LOGGER.warning("Failed to load library binary sensor descriptions", exc_info=True)
    # Old local binary sensors disabled during migration
    return sort_entity_descriptions(descriptions)


def get_all_number_descriptions(
    circuits: list[str],
    zone_count: int,
    zone_rooms: dict[int, int],
    enable_cascade: bool = False,
    model_info: IdmModelInfo | None = None,
) -> list[dict[str, Any]]:
    descriptions: list[dict[str, Any]] = []
    zone_rooms = normalize_zone_rooms(zone_rooms)

    # Library numbers (preferred).
    # zone_modules=0: see comment in get_all_sensor_descriptions above.
    try:
        descriptions.extend(
            get_library_numbers(
                model_info=model_info,
                circuits=circuits,
                zone_modules=0,
                enable_cascade=enable_cascade,
            )
        )
    except Exception:
        _LOGGER.warning("Failed to load library number descriptions", exc_info=True)
    for z in range(zone_count):
        rooms = zone_rooms.get(z, 6)
        descriptions.extend(get_library_zone_numbers(z + 1, rooms))

    # Deduplicate: zone registers may appear from both get_library_numbers
    # (when zone_modules > 0) and get_library_zone_numbers.
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for d in descriptions:
        key = d["description"].key
        if key not in seen:
            seen.add(key)
            deduped.append(d)
    return sort_entity_descriptions(deduped)


def get_all_select_descriptions(
    circuits: list[str],
    zone_count: int,
    zone_rooms: dict[int, int],
    enable_cascade: bool = False,
    model_info: IdmModelInfo | None = None,
) -> list[dict[str, Any]]:
    descriptions = []
    zone_rooms = normalize_zone_rooms(zone_rooms)
    try:
        descriptions.extend(
            get_library_selects(
                circuits=circuits,
                zone_modules=0,
                model_info=model_info,
            )
        )
    except Exception:
        _LOGGER.warning("Failed to load library select descriptions", exc_info=True)
    for z in range(zone_count):
        rooms = zone_rooms.get(z, 6)
        descriptions.extend(get_library_zone_selects(z + 1, rooms))

    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for d in descriptions:
        key = d["description"].key
        if key not in seen:
            seen.add(key)
            deduped.append(d)
    return sort_entity_descriptions(deduped)


def get_all_switch_descriptions(
    circuits: list[str],
    zone_count: int,
    zone_rooms: dict[int, int],
    enable_cascade: bool = False,
    model_info: IdmModelInfo | None = None,
) -> list[dict[str, Any]]:
    descriptions = []
    zone_rooms = normalize_zone_rooms(zone_rooms)
    try:
        descriptions.extend(get_library_switches(model_info=model_info))
    except Exception:
        _LOGGER.warning("Failed to load library switch descriptions", exc_info=True)
    # Old local switches disabled during migration
    return sort_entity_descriptions(descriptions)


def _build_alias_map(
    all_descriptions: list[dict[str, Any]],
) -> dict[int, list[str]]:
    """Build a mapping from register address to all register names sharing that address.

    Sensors and numbers often share the same Modbus address (e.g. a temperature
    sensor shows the current value, while a number entity allows setting it).
    Since ``read_batch`` returns data keyed by *register name*, we need to
    ensure that every entity can find its value under the name it expects.
    """
    addr_to_names: dict[int, list[str]] = {}
    for desc in all_descriptions:
        reg: RegisterDef = desc["register"]
        addr_to_names.setdefault(reg.address, []).append(reg.name)
    return addr_to_names


def _collect_all_descriptions(
    circuits: list[str],
    zone_count: int,
    zone_rooms: dict[int, int],
    enable_cascade: bool = False,
    model_info: IdmModelInfo | None = None,
) -> list[dict[str, Any]]:
    """Collect all entity descriptions across all platforms."""
    return (
        get_all_sensor_descriptions(circuits, zone_count, zone_rooms, enable_cascade, model_info)
        + get_all_binary_sensor_descriptions(circuits, zone_count, zone_rooms, enable_cascade, model_info)
        + get_all_number_descriptions(circuits, zone_count, zone_rooms, enable_cascade, model_info)
        + get_all_select_descriptions(circuits, zone_count, zone_rooms, enable_cascade, model_info)
        + get_all_switch_descriptions(circuits, zone_count, zone_rooms, enable_cascade, model_info)
    )


def collect_all_registers(
    circuits: list[str],
    zone_count: int,
    zone_rooms: dict[int, int],
    enable_cascade: bool = False,
    model_info: IdmModelInfo | None = None,
) -> list[RegisterDef]:
    """Collect all unique registers for batch reading."""
    all_descriptions = _collect_all_descriptions(circuits, zone_count, zone_rooms, enable_cascade, model_info)

    seen: dict[int, RegisterDef] = {}
    for desc in all_descriptions:
        reg: RegisterDef = desc["register"]
        if reg.address not in seen:
            seen[reg.address] = reg

    return list(seen.values())


def collect_registers_from_descriptions(
    descriptions: list[dict[str, Any]],
) -> list[RegisterDef]:
    """Extract unique registers from pre-built entity descriptions."""
    seen: dict[int, RegisterDef] = {}
    for desc in descriptions:
        reg: RegisterDef = desc["register"]
        if reg.address not in seen:
            seen[reg.address] = reg
    return list(seen.values())


def collect_aliases_from_descriptions(
    descriptions: list[dict[str, Any]],
) -> dict[int, list[str]]:
    """Extract alias map from pre-built entity descriptions."""
    addr_to_names: dict[int, list[str]] = {}
    for desc in descriptions:
        reg: RegisterDef = desc["register"]
        addr_to_names.setdefault(reg.address, []).append(reg.name)
    return addr_to_names


def collect_alias_map(
    circuits: list[str],
    zone_count: int,
    zone_rooms: dict[int, int],
    enable_cascade: bool = False,
    model_info: IdmModelInfo | None = None,
) -> dict[int, list[str]]:
    """Collect address -> [register_names] alias mapping.

    Multiple entity types (sensor + number) can share the same Modbus address
    but use different register names. ``read_batch`` returns data keyed by one
    name per address.  This map lets the coordinator populate the other names.
    """
    all_descriptions = _collect_all_descriptions(circuits, zone_count, zone_rooms, enable_cascade, model_info)
    return _build_alias_map(all_descriptions)
