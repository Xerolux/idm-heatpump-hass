"""Adapter layer between idm_heatpump library and the Home Assistant integration.

This file is the core of the migration (Option B). It allows the HA integration
to use the clean idm_heatpump library as the source of truth for:

- Modbus communication (IdmModbusClient)
- Register definitions (via build_register_map, get_*_registers, etc.)
- Model detection and capabilities

While still providing the rich HA-specific EntityDescriptions (German names,
icons, device classes, categories, etc.) that the current integration uses.

Goal: Over time, move as much logic as possible into the library and keep this
adapter relatively thin.
"""

from __future__ import annotations

import logging
import re
from dataclasses import replace
from typing import Any

from homeassistant.components.number import (
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.helpers.entity import EntityCategory  # type: ignore[attr-defined]

from idm_heatpump import (
    MODEL_NAVIGATOR_10,
    MODEL_NAVIGATOR_20,
    MODEL_NAVIGATOR_PRO,
    RegisterDef,
    get_heating_circuit_registers,
    get_zone_module_registers as _library_get_zone_module_registers,
)
from idm_heatpump import IdmModbusClient as LibIdmModbusClient

from .adapter_enums import get_bitflag_de_labels, get_slug_map_and_key
from .adapter_descriptions import (
    get_icon_for_register,
    infer_binary_device_class,
    infer_sensor_classes,
    infer_suggested_display_precision,
    make_sensor_description,
)
from .adapter_glt import is_glt_measurement, is_zone_room_measurement
from .adapter_metadata import (
    NUMBER_METADATA,
    SENSOR_METADATA,
    entity_enabled_by_default,
    native_step_for_register,
)
from .adapter_names import _get_german_name
from .adapter_registers import build_filtered_register_map

_LOGGER = logging.getLogger(__name__)

# Note: We import the HA helpers only inside functions to avoid circular imports during early migration.

_SENSOR_STATE_CLASS_MAP: dict[str, SensorStateClass] = {
    SensorStateClass.MEASUREMENT: SensorStateClass.MEASUREMENT,
    SensorStateClass.TOTAL: SensorStateClass.TOTAL,
    SensorStateClass.TOTAL_INCREASING: SensorStateClass.TOTAL_INCREASING,
}

_ZONE_ROOM_REGISTER = re.compile(r"^(?P<prefix>zm(?P<zone>\d+)_room)(?P<room>\d+)(?P<suffix>_.+)$")


def _coerce_sensor_state_class(value: str | SensorStateClass | None) -> SensorStateClass | None:
    """Map neutral library state class values to Home Assistant's enum."""
    if value is None:
        return None
    return _SENSOR_STATE_CLASS_MAP.get(str(value))


def _clone_register_for_room(reg: RegisterDef, room: int, address: int) -> RegisterDef:
    """Clone a library room register for older 8-room zone modules."""
    match = _ZONE_ROOM_REGISTER.fullmatch(reg.name)
    if match is None:
        msg = f"Register {reg.name!r} is not a zone room register"
        raise ValueError(msg)
    name = f"{match.group('prefix')}{room}{match.group('suffix')}"
    try:
        return replace(reg, address=address, name=name)
    except TypeError:
        return RegisterDef(
            address,
            reg.datatype,
            name,
            unit=reg.unit,
            multiplier=reg.multiplier,
            enum_options=reg.enum_options,
            writable=reg.writable,
            binary=reg.binary,
            write_only=reg.write_only,
            exclude_from_write=reg.exclude_from_write,
            icon=reg.icon,
            min_val=reg.min_val,
            max_val=reg.max_val,
            enabled_by_default=reg.enabled_by_default,
            state_class=reg.state_class,
        )


def _get_zone_module_registers(zone_idx: int, room_count: int = 6) -> dict[str, RegisterDef]:
    """Return zone module registers, extending 6-room library maps to 8 rooms."""
    try:
        return _library_get_zone_module_registers(zone_idx, room_count)
    except ValueError:
        if room_count <= 6:
            raise

    base_regs = _library_get_zone_module_registers(zone_idx, 6)
    extended = dict(base_regs)
    for room in range(7, room_count + 1):
        previous_room = room - 1
        template_room = previous_room - 1
        for reg in list(extended.values()):
            previous_match = _ZONE_ROOM_REGISTER.fullmatch(reg.name)
            if previous_match is None or int(previous_match.group("room")) != previous_room:
                continue
            template_name = f"{previous_match.group('prefix')}{template_room}{previous_match.group('suffix')}"
            template_reg = extended.get(template_name)
            stride = reg.address - template_reg.address if template_reg is not None else 10
            cloned = _clone_register_for_room(reg, room, reg.address + stride)
            extended[cloned.name] = cloned
    return extended


def _get_zone_module_registers_compat(zone_idx: int, room_count: int = 6) -> dict[str, RegisterDef]:
    """Return zone registers, including 8-room modules with older API releases."""
    return _get_zone_module_registers(zone_idx, room_count)


# ============================================================
# Enum slug maps — stable translation keys per register
# ============================================================


# ============================================================
# GLT-Messwert-Register: beschreibbare Register, die physikalische Messwerte
# abbilden (PV-Block, Zonenraum-Temperatur/-Feuchte). Seit Library 0.3.2 sind
# diese laut iDM-Doku per GLT beschreibbar. Sie werden doppelt exponiert:
# als Sensor (Anzeige/Historie) UND als Number (externe Vorgabe).
# ============================================================

# ============================================================
# Deutsche Namen für wichtige Register (wird sukzessive erweitert)
# ============================================================


def _build_sensor_description(reg: RegisterDef, *, include_enabled_default: bool = False) -> SensorEntityDescription:
    """Build a SensorEntityDescription from a register using shared icon/enum logic.

    Centralizes the ENUM-vs-default branching duplicated by the per-platform
    sensor generators. When *include_enabled_default* is set, the register's
    enabled_by_default flag is propagated (used by the library-wide sensor
    generator, not the circuit/zone generators).

    The expert-default profile (``entity_enabled_by_default``) is shared with
    ``make_sensor_description`` so both code paths agree on which generated
    technical registers stay disabled by default. The only difference is the
    source of the seed default: this path trusts the library's
    ``RegisterDef.enabled_by_default``, while ``make_sensor_description``
    trusts explicit ``SENSOR_METADATA`` overrides first.
    """
    name = reg.name
    icon = reg.icon or get_icon_for_register(name, reg.unit)
    slug_map, t_key = get_slug_map_and_key(name)
    extra: dict[str, Any] = {}
    if include_enabled_default:
        extra["entity_registry_enabled_default"] = entity_enabled_by_default(
            name,
            default=reg.enabled_by_default,
        )
    if reg.enum_options and reg.datatype.value != "BITFLAG" and slug_map is not None:
        return SensorEntityDescription(
            key=name,
            name=_get_german_name(name),
            device_class=SensorDeviceClass.ENUM,
            options=list(slug_map.values()),
            translation_key=t_key,
            icon=icon,
            entity_category=EntityCategory.DIAGNOSTIC,
            **extra,
        )
    dc, sc = infer_sensor_classes(name, reg.unit)
    if reg.state_class:
        sc = _coerce_sensor_state_class(reg.state_class)
    return SensorEntityDescription(
        key=name,
        name=_get_german_name(name),
        native_unit_of_measurement=reg.unit,
        device_class=dc,
        state_class=sc,
        suggested_display_precision=infer_suggested_display_precision(reg.unit),
        icon=icon,
        entity_category=EntityCategory.DIAGNOSTIC,
        **extra,
    )


def get_library_sensors(
    model_info: Any = None,
    circuits: list[str] | None = None,
    zone_modules: int = 0,
    enable_cascade: bool = True,
) -> list[dict[str, Any]]:
    """
    Returns sensor descriptions primarily sourced from the idm_heatpump library.
    This is intended to become the main source over time.
    """
    reg_map = build_filtered_register_map(model_info, circuits, zone_modules)
    sensors = []

    # Explicitly mapped sensors (best quality)
    for key, meta in SENSOR_METADATA.items():
        if key in reg_map:
            reg = reg_map[key]
            desc = make_sensor_description(reg, meta, _get_german_name(reg.name))
            sensors.append(
                {
                    "register": reg,
                    "description": desc,
                    "category": "system",
                }
            )

    # Fallback: Generate basic but usable descriptions for everything else from the library
    # This helps during the migration so we don't have to duplicate every register manually.
    known_keys = set(SENSOR_METADATA.keys())
    for name, reg in reg_map.items():
        if name in known_keys:
            continue  # already handled above

        if reg.writable and not is_glt_measurement(name):
            continue
        if reg.write_only:
            continue
        if reg.binary:
            continue

        desc = _build_sensor_description(reg, include_enabled_default=True)
        sensors.append(
            {
                "register": reg,
                "description": desc,
                "category": "library",
            }
        )

    return sensors


# ============================================================
# Spezialisierte Generatoren für Heizkreise und Zonen (stark verbessert)
# ============================================================


def get_library_heating_circuit_sensors(circuit: str) -> list[dict[str, Any]]:
    """Erzeugt Sensor-Beschreibungen für einen Heizkreis direkt aus der Library."""
    try:
        circuit_regs = get_heating_circuit_registers(circuit)
    except Exception:
        _LOGGER.debug("Failed to load heating circuit %s sensor registers", circuit, exc_info=True)
        return []

    sensors = []
    for name, reg in circuit_regs.items():
        if reg.writable:
            continue

        desc = _build_sensor_description(reg)
        sensors.append(
            {
                "register": reg,
                "description": desc,
                "category": f"heating_circuit_{circuit.lower()}",
            }
        )
    return sensors


def get_library_zone_sensors(zone_idx: int, room_count: int = 6) -> list[dict[str, Any]]:
    """Erzeugt Sensor-Beschreibungen für ein Zonenmodul direkt aus der Library."""
    try:
        zone_regs = _get_zone_module_registers_compat(zone_idx, room_count)
    except Exception:
        _LOGGER.debug("Failed to load zone %d sensor registers", zone_idx, exc_info=True)
        return []

    sensors = []
    for name, reg in zone_regs.items():
        if reg.writable and not is_glt_measurement(name):
            continue
        # Binary status registers (e.g. room relay) belong on binary_sensor,
        # not sensor. Filter them out here so they never produce a numeric
        # 0/1 sensor. The name-based fallback keeps older idm-heatpump-api
        # releases (where the relay has binary=False) working correctly.
        if reg.binary or name.endswith("_relay"):
            continue

        desc = _build_sensor_description(reg)
        sensors.append(
            {
                "register": reg,
                "description": desc,
                "category": f"zone_{zone_idx}",
            }
        )
    return sensors


def get_library_zone_binary_sensors(zone_idx: int, room_count: int = 6) -> list[dict[str, Any]]:
    """Binary sensor descriptions for a single zone module.

    Mirrors :func:`get_library_zone_sensors` for binary status registers
    (currently the per-room relay). Read-only registers that are either
    flagged ``binary=True`` by the library or follow the ``_relay`` naming
    convention are routed here so Home Assistant exposes them as
    ``binary_sensor`` entities with ``on``/``off`` instead of numeric 0/1.
    """
    from homeassistant.components.binary_sensor import BinarySensorEntityDescription

    try:
        zone_regs = _get_zone_module_registers_compat(zone_idx, room_count)
    except Exception:
        _LOGGER.debug("Failed to load zone %d binary registers", zone_idx, exc_info=True)
        return []

    sensors = []
    for name, reg in zone_regs.items():
        if reg.writable:
            continue
        if not (reg.binary or name.endswith("_relay")):
            continue
        desc = BinarySensorEntityDescription(
            key=name,
            name=_get_german_name(name),
            device_class=infer_binary_device_class(name),
            icon=get_icon_for_register(name, reg.unit),
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=entity_enabled_by_default(name),
        )
        sensors.append(
            {
                "register": reg,
                "description": desc,
                "category": f"zone_binary_{zone_idx}",
            }
        )
    return sensors


# ============================================================
# Weitere Generatoren für umfassende Abdeckung (System, Energy, Pumps, Solar, PV, Cascade, GLT)
# ============================================================


def get_library_binary_sensors(
    circuits: list[str] | None = None,
    zone_modules: int = 0,
    model_info: Any = None,
) -> list[dict[str, Any]]:
    """Binary sensors from library registers with binary=True flag."""
    from homeassistant.components.binary_sensor import BinarySensorEntityDescription

    reg_map = build_filtered_register_map(model_info, circuits, zone_modules)
    sensors = []
    for name, reg in reg_map.items():
        if not reg.binary or reg.writable:
            continue
        desc = BinarySensorEntityDescription(
            key=name,
            name=_get_german_name(name),
            device_class=infer_binary_device_class(name),
            icon=get_icon_for_register(name, reg.unit),
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=entity_enabled_by_default(name),
        )
        sensors.append(
            {
                "register": reg,
                "description": desc,
                "category": "binary",
            }
        )
    return sensors


def _selects_from_register_map(reg_map: dict[str, RegisterDef]) -> list[dict[str, Any]]:
    """Build select entity descriptions from a register map.

    Shared by get_library_selects and get_library_zone_selects so the
    writable/enum/write_only filter, slug-map option resolution and
    SelectEntityDescription construction stay in lockstep.
    """
    from homeassistant.components.select import SelectEntityDescription

    selects = []
    for name, reg in reg_map.items():
        if not reg.writable or not reg.enum_options:
            continue
        if reg.write_only:
            continue

        slug_map, t_key = get_slug_map_and_key(name)
        excluded: set[int] = set(reg.exclude_from_write or [])

        if slug_map is not None:
            options = [v for k, v in slug_map.items() if k not in excluded]
        else:
            options = (
                [v for k, v in reg.enum_options.items() if k not in excluded]
                if excluded
                else list(reg.enum_options.values())
            )

        desc = SelectEntityDescription(
            key=name,
            name=_get_german_name(name),
            options=options,
            icon=reg.icon or get_icon_for_register(name),
            entity_category=EntityCategory.CONFIG,
            translation_key=t_key,
        )
        selects.append({"register": reg, "description": desc})
    return selects


def get_library_selects(
    circuits: list[str] | None = None,
    zone_modules: int = 0,
    model_info: Any = None,
) -> list[dict[str, Any]]:
    """Select entities (modes) from the library."""
    reg_map = build_filtered_register_map(model_info, circuits, zone_modules)
    return _selects_from_register_map(reg_map)


def get_library_zone_selects(zone_idx: int, room_count: int = 6) -> list[dict[str, Any]]:
    """Returns select descriptions for one zone module with its configured room count."""
    try:
        zone_regs = _get_zone_module_registers_compat(zone_idx, room_count)
    except Exception:
        _LOGGER.debug("Failed to load zone %d select registers", zone_idx, exc_info=True)
        return []
    return _selects_from_register_map(zone_regs)


def get_library_switches(model_info: Any = None) -> list[dict[str, Any]]:
    """Switch entities (GLT demands etc.) from the library."""
    from homeassistant.components.switch import SwitchEntityDescription

    reg_map = build_filtered_register_map(model_info, [], 0)
    switches = []
    for name, reg in reg_map.items():
        if reg.datatype.value != "BOOL" or not reg.writable:
            continue
        desc = SwitchEntityDescription(
            key=name,
            name=_get_german_name(name),
            icon=get_icon_for_register(name),
            entity_category=EntityCategory.CONFIG,
        )
        switches.append(
            {
                "register": reg,
                "description": desc,
            }
        )
    return switches


def get_library_numbers(
    model_info: Any = None,
    circuits: list[str] | None = None,
    zone_modules: int = 0,
    enable_cascade: bool = True,
) -> list[dict[str, Any]]:
    """Returns number descriptions for writable library registers with HA metadata."""
    reg_map = build_filtered_register_map(model_info, circuits, zone_modules)
    return _numbers_from_register_map(reg_map)


def get_library_zone_numbers(zone_idx: int, room_count: int = 6) -> list[dict[str, Any]]:
    """Returns number descriptions for writable room registers in one zone module."""
    try:
        zone_regs = _get_zone_module_registers_compat(zone_idx, room_count)
    except Exception:
        _LOGGER.debug("Failed to load zone %d number registers", zone_idx, exc_info=True)
        return []
    return _numbers_from_register_map(zone_regs)


def _numbers_from_register_map(reg_map: dict[str, RegisterDef]) -> list[dict[str, Any]]:
    """Build HA number descriptions from writable non-enum library registers."""
    numbers = []

    for name, reg in reg_map.items():
        if not reg.writable or reg.enum_options:
            continue
        if reg.datatype.value == "BOOL":
            continue
        if reg.write_only:
            continue

        meta = NUMBER_METADATA.get(name, {})
        min_val = meta.get("min", reg.min_val if reg.min_val is not None else -999)
        max_val = meta.get("max", reg.max_val if reg.max_val is not None else 999)

        number_name = meta.get("name", _get_german_name(name))
        if is_glt_measurement(name):
            # Das Register existiert zusätzlich als Sensor — die Number ist die
            # externe GLT-Vorgabe und braucht einen unterscheidbaren Namen.
            number_name = f"{number_name} (Vorgabe)"

        # Raumtemperatur/-feuchte ist laut iDM-Doku (812170) nur beschreibbar,
        # wenn für den jeweiligen Raum ein externer/GLT-Raumsensor konfiguriert
        # ist; bei Verwendung der iDM-eigenen Raumsensoren ist das Register RO
        # und ein Schreibversuch wird vom Gerät ignoriert. Welcher Sensortyp je
        # Raum aktiv ist, lässt sich nicht über Modbus auslesen, daher wird die
        # Number standardmäßig deaktiviert statt sie unwirksam anzubieten.
        enabled_by_default = meta.get("enabled_by_default", not is_zone_room_measurement(name))

        desc = NumberEntityDescription(
            key=name,
            name=number_name,
            native_min_value=min_val,
            native_max_value=max_val,
            native_step=native_step_for_register(reg, meta),
            native_unit_of_measurement=meta.get("unit") or reg.unit,
            device_class=meta.get("device_class"),
            icon=meta.get("icon", get_icon_for_register(name, reg.unit)),
            mode=NumberMode.BOX,
            entity_category=meta.get("entity_category", EntityCategory.CONFIG),
            entity_registry_enabled_default=enabled_by_default,
        )
        numbers.append(
            {
                "register": reg,
                "description": desc,
            }
        )

    return numbers


def get_idm_client(
    host: str,
    port: int = 502,
    slave_id: int = 1,
    timeout: float | None = None,
    max_retries: int | None = None,
) -> LibIdmModbusClient:
    """Factory that returns a properly typed client from the library.

    ``timeout`` and ``max_retries`` are passed through when supplied so the
    HA integration can tune them per config entry. They default to the
    library's own defaults (10 s and 3 retries) when ``None``.
    """
    kwargs: dict[str, Any] = {}
    if timeout is not None:
        kwargs["timeout"] = float(timeout)
    if max_retries is not None:
        kwargs["max_retries"] = int(max_retries)
    return LibIdmModbusClient(host=host, port=port, slave_id=slave_id, **kwargs)


__all__ = [
    "LibIdmModbusClient",
    "MODEL_NAVIGATOR_10",
    "MODEL_NAVIGATOR_20",
    "MODEL_NAVIGATOR_PRO",
    "get_library_sensors",
    "get_library_numbers",
    "get_library_zone_numbers",
    "get_idm_client",
    "get_slug_map_and_key",
    "get_bitflag_de_labels",
    "is_glt_measurement",
]
