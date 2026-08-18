"""Device hierarchy helpers for IDM Heatpump entities."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo

from .const import CONF_HEATING_CIRCUITS, CONF_TECHNICIAN_CODES, DOMAIN, MANUFACTURER

if TYPE_CHECKING:
    from .coordinator import IdmCoordinator

_LOGGER = logging.getLogger(__name__)

DeviceScopeKind = Literal[
    "heating_circuit",
    "zone_module",
    "zone_room",
    "solar",
    "isc",
    "cascade",
    "auxiliary_heat",
    "domestic_hot_water",
    "diagnostics",
]


@dataclass(frozen=True)
class DeviceScope:
    """Resolved subdevice scope for one IDM entity key."""

    kind: DeviceScopeKind
    primary: str
    secondary: int | None = None


_HEATING_CIRCUIT_REGISTER = re.compile(r"^hc_([a-g])_")
_ZONE_ROOM_REGISTER = re.compile(r"^zm(\d+)_room(\d+)_")
_ZONE_MODULE_REGISTER = re.compile(r"^zm(\d+)_")
_WEB_HEATING_CIRCUIT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^(?:flow_temp_HK_|room_temperature_HK_)([A-G])$"),
    re.compile(r"^(?:pump_heating_circuit|mixer_heating_circuit)([A-G])$"),
)
_OPTIONAL_MODULE_PREFIXES: tuple[tuple[str, DeviceScopeKind], ...] = (
    ("solar_", "solar"),
    ("isc_", "isc"),
    ("cascade_", "cascade"),
)
_AUXILIARY_HEAT_PREFIXES = (
    "bivalence_",
    "booster_",
    "second_heat_generator_",
    "eheating_",
    "electric_heater_",
)
_DHW_PREFIXES = ("dhw_", "hotwater_", "water_temp_")
_DHW_KEYS = frozenset(
    {
        "current_expected_power_hotwater",
        "energy_dhw",
        "glt_request_dhw",
        "glt_single_dhw",
        "request_dhw",
        "runtime_hotwater_hours",
        "valve_heating_hotwater",
        "ext_hotwater_signal",
    }
)
_DIAGNOSTIC_KEYS = frozenset(
    {
        "controller_online_hours",
        "error_acknowledge",
        "heatpump_model",
        "infosystem_notification_count",
        "infosystem_notifications",
        "internal_message",
        "myidm_id",
        "navigator_version",
        "software_version",
        "technician_codes",
        "technician_level_1",
        "technician_level_2",
    }
)

_AUXILIARY_HEAT_KEYS = frozenset(
    {
        "failure_eheating",
        "heat_generator_2nd",
        "heat_generator_2nd_3rd",
        "runtime_second_heat_generator_hours",
        "switch_cycles_second_heat_generator",
    }
)
_MODULE_DEVICE_METADATA: dict[DeviceScopeKind, tuple[str, str, str]] = {
    "solar": ("solar", "Solaranlage", "Solar"),
    "isc": ("isc", "IDM ISC", "ISC"),
    "cascade": ("cascade", "IDM Kaskade", "Kaskade"),
    "auxiliary_heat": (
        "auxiliary_heat",
        "Zusatzwärmeerzeuger",
        "Zusatzwärmeerzeuger",
    ),
    "domestic_hot_water": ("domestic_hot_water", "Warmwasser", "Warmwasserbereitung"),
    "diagnostics": ("diagnostics", "Diagnose", "Diagnose"),
}


def resolve_device_scope(entity_key: str) -> DeviceScope | None:
    """Return the subdevice scope for a register or web-value key."""
    key = entity_key.removeprefix("web_")

    if match := _ZONE_ROOM_REGISTER.match(key):
        return DeviceScope("zone_room", match.group(1), int(match.group(2)))
    if match := _ZONE_MODULE_REGISTER.match(key):
        return DeviceScope("zone_module", match.group(1))
    if match := _HEATING_CIRCUIT_REGISTER.match(key):
        return DeviceScope("heating_circuit", match.group(1).upper())
    for pattern in _WEB_HEATING_CIRCUIT_PATTERNS:
        if match := pattern.match(key):
            return DeviceScope("heating_circuit", match.group(1).upper())
    for prefix, kind in _OPTIONAL_MODULE_PREFIXES:
        if key.startswith(prefix):
            return DeviceScope(kind, prefix.removesuffix("_"))
    if key in _DHW_KEYS or key.startswith(_DHW_PREFIXES):
        return DeviceScope("domestic_hot_water", "domestic_hot_water")
    if key in _DIAGNOSTIC_KEYS:
        return DeviceScope("diagnostics", "diagnostics")
    if key in _AUXILIARY_HEAT_KEYS or key.startswith(_AUXILIARY_HEAT_PREFIXES):
        return DeviceScope("auxiliary_heat", "auxiliary_heat")
    return None


def main_device_identifier(coordinator: IdmCoordinator) -> tuple[str, str]:
    """Return the stable main-device identifier."""
    return DOMAIN, coordinator.config_entry.entry_id  # type: ignore[union-attr]


def precreate_main_device(hass: HomeAssistant, coordinator: IdmCoordinator) -> None:
    """Ensure the main device and every expected sub-device exist up front.

    Sub-device ``DeviceInfo`` links to its parent via ``via_device_id``, which
    needs the parent's actual registry-assigned device ID (a plain identifier
    tuple is no longer enough since Home Assistant 2026.8, where identifiers
    are only unique per config entry). Platforms are forwarded in an
    unspecified order, so the first entity added may be a sub-device (e.g. a
    binary_sensor) whose parent has not been created yet. Pre-creating the
    main device and every expected sub-device here — keyed by the same stable
    identifiers ``build_subdevice_info`` uses — guarantees every parent lookup
    resolves and caches the IDs on the coordinator so ``build_subdevice_info``
    stays a cheap, registry-free lookup. Name/model/manufacturer are enriched
    later when each device's first entity is added.
    """
    entry = coordinator.config_entry
    if entry is None:
        return
    registry = dr.async_get(hass)
    device_ids: dict[tuple[str, str], str] = {}

    for identifier in {main_device_identifier(coordinator), *expected_subdevice_identifiers(coordinator)}:
        device = registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={identifier},
        )
        device_ids[identifier] = device.id

    coordinator._hierarchy_device_ids = device_ids


HEATING_CIRCUIT_LETTERS: tuple[str, ...] = ("A", "B", "C", "D", "E", "F", "G")


def is_configured_heating_circuit_register(coordinator: IdmCoordinator, register_name: str) -> bool:
    """Return whether a register belongs to a heating circuit the user configured.

    Enabling a circuit is an explicit statement that it exists, so its registers
    must not disappear because a single poll happened to read an unused
    sentinel — see ``should_add_entity``.
    """
    match = _HEATING_CIRCUIT_REGISTER.match(register_name)
    if match is None:
        return False
    return match.group(1).upper() in active_heating_circuits(coordinator)


def active_heating_circuits(coordinator: IdmCoordinator) -> tuple[str, ...]:
    """Return the configured heating circuits as uppercase letters.

    Circuits can be enabled at any time through the options flow, so this
    reads the current config entry options and falls back to the Modbus
    register names when options are unavailable. Circuit A is always assumed
    because every IDM controller has it.
    """
    letters: set[str] = set()

    entry = getattr(coordinator, "config_entry", None)
    options: Any = getattr(entry, "options", None) or {}
    raw_circuits: Any = options.get(CONF_HEATING_CIRCUITS, ()) if hasattr(options, "get") else ()
    try:
        candidates = list(raw_circuits)
    except TypeError:
        candidates = []
    for candidate in candidates:
        if not isinstance(candidate, str):
            continue
        letter = candidate.strip().upper()
        if letter in HEATING_CIRCUIT_LETTERS:
            letters.add(letter)

    for register in getattr(coordinator, "_registers", ()) or ():
        match = _HEATING_CIRCUIT_REGISTER.match(str(getattr(register, "name", "")))
        if match is not None:
            letters.add(match.group(1).upper())

    letters.add("A")
    return tuple(sorted(letters))


def heating_circuit_identifier(coordinator: IdmCoordinator, circuit: str) -> tuple[str, str]:
    """Return the stable identifier for one heating circuit."""
    entry_id = coordinator.config_entry.entry_id  # type: ignore[union-attr]
    return DOMAIN, f"{entry_id}_heating_circuit_{circuit.casefold()}"


def zone_module_identifier(coordinator: IdmCoordinator, zone: str | int) -> tuple[str, str]:
    """Return the stable identifier for one zone module."""
    entry_id = coordinator.config_entry.entry_id  # type: ignore[union-attr]
    return DOMAIN, f"{entry_id}_zone_module_{int(zone)}"


def zone_room_identifier(coordinator: IdmCoordinator, zone: str | int, room: int) -> tuple[str, str]:
    """Return the stable identifier for one room below a zone module."""
    entry_id = coordinator.config_entry.entry_id  # type: ignore[union-attr]
    return DOMAIN, f"{entry_id}_zone_module_{int(zone)}_room_{room}"


def optional_module_identifier(coordinator: IdmCoordinator, module: str) -> tuple[str, str]:
    """Return the stable identifier for one detected optional module."""
    entry_id = coordinator.config_entry.entry_id  # type: ignore[union-attr]
    return DOMAIN, f"{entry_id}_module_{module}"


def _scope_identifiers(coordinator: IdmCoordinator, scope: DeviceScope) -> set[tuple[str, str]]:
    """Return all device identifiers required by one entity scope."""
    if scope.kind == "heating_circuit":
        return {heating_circuit_identifier(coordinator, scope.primary)}
    if scope.kind in _MODULE_DEVICE_METADATA:
        return {optional_module_identifier(coordinator, scope.primary)}

    zone = int(scope.primary)
    identifiers = {zone_module_identifier(coordinator, zone)}
    if scope.kind == "zone_room" and scope.secondary is not None:
        identifiers.add(zone_room_identifier(coordinator, zone, scope.secondary))
    return identifiers


def expected_subdevice_identifiers(coordinator: IdmCoordinator) -> set[tuple[str, str]]:
    """Return subdevices justified by the current register and web-value set."""
    if coordinator.device_hierarchy_enabled is not True:
        return set()

    entity_keys = {register.name for register in coordinator._registers}
    supplement = coordinator.web_supplement
    sensor_values = getattr(supplement, "sensor_values", None)
    if isinstance(sensor_values, dict):
        entity_keys.update(str(key) for key in sensor_values)
    options = getattr(coordinator.config_entry, "options", {}) if coordinator.config_entry is not None else {}
    if isinstance(options, dict) and options.get(CONF_TECHNICIAN_CODES, False):
        entity_keys.add("technician_codes")
    entity_keys.add("error_acknowledge")

    identifiers: set[tuple[str, str]] = set()
    for entity_key in entity_keys:
        if scope := resolve_device_scope(entity_key):
            identifiers.update(_scope_identifiers(coordinator, scope))
    return identifiers


def _is_hierarchy_identifier(entry_id: str, identifier: tuple[str, str]) -> bool:
    """Return whether an identifier belongs to an IDM hierarchy subdevice."""
    domain, value = identifier
    return domain == DOMAIN and value.startswith(
        (
            f"{entry_id}_heating_circuit_",
            f"{entry_id}_zone_module_",
            f"{entry_id}_module_",
        )
    )


def cleanup_stale_hierarchy_devices(hass: HomeAssistant, coordinator: IdmCoordinator) -> None:
    """Detach stale hierarchy devices without touching entities or the main device."""
    config_entry = coordinator.config_entry
    if config_entry is None:
        return

    entry_id = config_entry.entry_id
    expected = expected_subdevice_identifiers(coordinator)
    registry = dr.async_get(hass)

    entity_registry = er.async_get(hass)

    for device in dr.async_entries_for_config_entry(registry, entry_id):
        hierarchy_identifiers = {
            identifier for identifier in device.identifiers if _is_hierarchy_identifier(entry_id, identifier)
        }
        if not hierarchy_identifiers:
            continue
        if hierarchy_identifiers.isdisjoint(expected):
            registry.async_update_device(
                device.id,
                remove_config_entry_id=entry_id,
            )
            continue
        # Sub-devices are pre-created without a name so ``via_device`` links
        # resolve regardless of platform order; the name arrives with the first
        # entity. One that never receives an entity — because its registers are
        # filtered out or its feature was turned off — would otherwise sit in
        # the device list forever as an unnamed, empty entry.
        if not er.async_entries_for_device(entity_registry, device.id, include_disabled_entities=True):
            registry.async_update_device(
                device.id,
                remove_config_entry_id=entry_id,
            )


def cleanup_deconfigured_heating_circuit_entities(hass: HomeAssistant, coordinator: IdmCoordinator) -> None:
    """Remove registry entries of heating circuits the user turned off.

    Unchecking a circuit in the options flow is an explicit statement that it
    does not exist on this installation. Its entities are no longer created, so
    without this they linger in the registry forever, permanently unavailable —
    exactly what happened to installations that were once configured with more
    circuits than they have.

    This is deliberately narrow. Only register-backed entities of *this* config
    entry whose register belongs to a heating circuit that is currently not
    configured are removed. Nothing keyed on a default, a profile or an entity
    category is touched, and re-enabling the circuit recreates the entities
    under their unchanged unique IDs.
    """
    config_entry = coordinator.config_entry
    if config_entry is None:
        return

    entry_id = config_entry.entry_id
    configured = set(active_heating_circuits(coordinator))
    registry = er.async_get(hass)
    prefix = f"{entry_id}_"

    for entity in list(er.async_entries_for_config_entry(registry, entry_id)):
        unique_id = entity.unique_id
        if not unique_id.startswith(prefix):
            continue
        entity_key = unique_id[len(prefix) :]
        # Calculated sensors carry their circuit in the same shape behind a
        # prefix (``calculated_hc_b_flow_deviation``) and are just as absent
        # once the circuit is gone.
        register_name = entity_key.removeprefix("calculated_")
        match = _HEATING_CIRCUIT_REGISTER.match(register_name)
        if match is None:
            continue
        if match.group(1).upper() in configured:
            continue
        _LOGGER.debug(
            "Removing entity %s of deconfigured heating circuit %s",
            entity.entity_id,
            match.group(1).upper(),
        )
        registry.async_remove(entity.entity_id)


def _via_device_id(coordinator: IdmCoordinator, parent_identifier: tuple[str, str]) -> str | None:
    """Return the cached registry device ID for a hierarchy parent, if known.

    Populated by :func:`precreate_main_device` before entities are added. A
    missing entry (e.g. hierarchy mode toggled on without a reload) simply
    means the sub-device is created without a ``via_device_id`` link this
    round; the next reload/precreate pass fills it in.
    """
    return coordinator._hierarchy_device_ids.get(parent_identifier)


def build_subdevice_info(coordinator: IdmCoordinator, entity_key: str) -> DeviceInfo | None:
    """Build subdevice information when hierarchy mode is enabled."""
    if coordinator.device_hierarchy_enabled is not True:
        return None

    scope = resolve_device_scope(entity_key)
    if scope is None:
        return None

    main_identifier = main_device_identifier(coordinator)
    if scope.kind == "heating_circuit":
        circuit = scope.primary.upper()
        info = DeviceInfo(
            identifiers={heating_circuit_identifier(coordinator, circuit)},
            name=f"Heizkreis {circuit}",
            manufacturer=MANUFACTURER,
            model="Heizkreis",
        )
        if (via_device_id := _via_device_id(coordinator, main_identifier)) is not None:
            info["via_device_id"] = via_device_id
        return info

    if scope.kind in _MODULE_DEVICE_METADATA:
        module, name, model = _MODULE_DEVICE_METADATA[scope.kind]
        info = DeviceInfo(
            identifiers={optional_module_identifier(coordinator, module)},
            name=name,
            manufacturer=MANUFACTURER,
            model=model,
        )
        if (via_device_id := _via_device_id(coordinator, main_identifier)) is not None:
            info["via_device_id"] = via_device_id
        return info

    zone = int(scope.primary)
    if scope.kind == "zone_module":
        info = DeviceInfo(
            identifiers={zone_module_identifier(coordinator, zone)},
            name=f"Zonenmodul {zone}",
            manufacturer=MANUFACTURER,
            model="Zonenmodul",
        )
        if (via_device_id := _via_device_id(coordinator, main_identifier)) is not None:
            info["via_device_id"] = via_device_id
        return info

    room = scope.secondary
    if room is None:
        return None
    info = DeviceInfo(
        identifiers={zone_room_identifier(coordinator, zone, room)},
        name=f"Zonenmodul {zone} Raum {room}",
        manufacturer=MANUFACTURER,
        model="Raumregelung",
    )
    if (via_device_id := _via_device_id(coordinator, zone_module_identifier(coordinator, zone))) is not None:
        info["via_device_id"] = via_device_id
    return info
