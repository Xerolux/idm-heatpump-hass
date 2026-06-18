"""Register definitions for IDM Navigator 2.0 heat pumps.

All Modbus register addresses, data types, units, and read/write capabilities
are defined here. Registers are organized by functional group and provide
entity descriptions for Home Assistant platforms.
"""

from __future__ import annotations

# IDM Heatpump for Home Assistant
# © 2026 Xerolux — Inoffizielle Community-Integration für IDM Navigator 2.0 Wärmepumpen
# Erstellt von Xerolux | https://github.com/Xerolux/idm-heatpump-hass
# Lizenz: MIT

from typing import Any

from idm_heatpump import RegisterDef

from .library_adapter import (
    get_library_binary_sensors,
    get_library_heating_circuit_sensors,
    get_library_numbers,
    get_library_selects,
    get_library_sensors,
    get_library_switches,
    get_library_zone_numbers,
    get_library_zone_sensors,
)

# ============================================================
# PUBLIC FUNCTIONS - Collect all register descriptions
# All registers are sourced from the idm_heatpump library via library_adapter.
# ============================================================


def get_all_sensor_descriptions(
    circuits: list[str],
    zone_count: int,
    zone_rooms: dict[int, int],
    enable_cascade: bool = False,
) -> list[dict[str, Any]]:
    """
    Assembles all sensor descriptions.

    The library + adapter is now the preferred source.
    Local definitions are kept for rich German names and specific icons.
    """
    descriptions = []

    # Library + Adapter is now the primary and preferred source.
    # zone_modules=0: zone registers are added below via the per-zone loop,
    # which respects each zone's configured room count (zone_rooms). The
    # library's bulk zone handling only supports one uniform room count for
    # all zones, so it must not also generate zone registers here.
    try:
        descriptions.extend(get_library_sensors(circuits=circuits, zone_modules=0))
    except Exception:
        pass

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

    return unique


def get_all_binary_sensor_descriptions(
    circuits: list[str],
    zone_count: int,
    zone_rooms: dict[int, int],
    enable_cascade: bool = False,
) -> list[dict[str, Any]]:
    descriptions = []
    try:
        descriptions.extend(get_library_binary_sensors(circuits=circuits, zone_modules=zone_count))
    except Exception:
        pass
    # Old local binary sensors disabled during migration
    return descriptions


def get_all_number_descriptions(
    circuits: list[str],
    zone_count: int,
    zone_rooms: dict[int, int],
    enable_cascade: bool = False,
) -> list[dict[str, Any]]:
    descriptions = []

    # Library numbers (preferred).
    # zone_modules=0: see comment in get_all_sensor_descriptions above.
    try:
        descriptions.extend(get_library_numbers(circuits=circuits, zone_modules=0))
    except Exception:
        pass
    for z in range(zone_count):
        rooms = zone_rooms.get(z, 6)
        descriptions.extend(get_library_zone_numbers(z + 1, rooms))

    # Legacy numbers deaktiviert
    return descriptions


def get_all_select_descriptions(
    circuits: list[str],
    zone_count: int,
    zone_rooms: dict[int, int],
    enable_cascade: bool = False,
) -> list[dict[str, Any]]:
    descriptions = []
    try:
        descriptions.extend(get_library_selects(circuits=circuits, zone_modules=zone_count))
    except Exception:
        pass
    # Old local selects disabled during migration
    return descriptions


def get_all_switch_descriptions(
    circuits: list[str],
    zone_count: int,
    zone_rooms: dict[int, int],
    enable_cascade: bool = False,
) -> list[dict[str, Any]]:
    descriptions = []
    try:
        descriptions.extend(get_library_switches())
    except Exception:
        pass
    # Old local switches disabled during migration
    return descriptions


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
) -> list[dict[str, Any]]:
    """Collect all entity descriptions across all platforms."""
    return (
        get_all_sensor_descriptions(circuits, zone_count, zone_rooms, enable_cascade)
        + get_all_binary_sensor_descriptions(circuits, zone_count, zone_rooms, enable_cascade)
        + get_all_number_descriptions(circuits, zone_count, zone_rooms, enable_cascade)
        + get_all_select_descriptions(circuits, zone_count, zone_rooms, enable_cascade)
        + get_all_switch_descriptions(circuits, zone_count, zone_rooms, enable_cascade)
    )


def collect_all_registers(
    circuits: list[str],
    zone_count: int,
    zone_rooms: dict[int, int],
    enable_cascade: bool = False,
) -> list[RegisterDef]:
    """Collect all unique registers for batch reading."""
    all_descriptions = _collect_all_descriptions(circuits, zone_count, zone_rooms, enable_cascade)

    seen: dict[int, RegisterDef] = {}
    for desc in all_descriptions:
        reg: RegisterDef = desc["register"]
        if reg.address not in seen:
            seen[reg.address] = reg

    return list(seen.values())


def collect_alias_map(
    circuits: list[str],
    zone_count: int,
    zone_rooms: dict[int, int],
    enable_cascade: bool = False,
) -> dict[int, list[str]]:
    """Collect address -> [register_names] alias mapping.

    Multiple entity types (sensor + number) can share the same Modbus address
    but use different register names. ``read_batch`` returns data keyed by one
    name per address.  This map lets the coordinator populate the other names.
    """
    all_descriptions = _collect_all_descriptions(circuits, zone_count, zone_rooms, enable_cascade)
    return _build_alias_map(all_descriptions)
