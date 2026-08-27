"""Device hierarchy helpers for IDM Heatpump entities."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, cast

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

# Every sub-device except the zone module is a *logical part* of the controller
# it hangs under, not a device reached through it. Home Assistant 2026.9 draws
# exactly that line: ``via_device_id`` describes connectivity, a child device
# describes composition. A zone module is separate hardware wired to the
# controller, so it stays an ordinary device linked by ``via_device_id``; the
# rooms below it are logical parts of that module and become its children.
_CHILD_DEVICE_KINDS: frozenset[DeviceScopeKind] = frozenset(
    {
        "heating_circuit",
        "zone_room",
        "solar",
        "isc",
        "cascade",
        "auxiliary_heat",
        "domestic_hot_water",
        "diagnostics",
    }
)


def child_devices_supported() -> bool:
    """Return whether this Home Assistant provides the child-device API.

    Child devices arrived in Home Assistant 2026.9. The integration still
    supports 2026.8, so the hierarchy falls back to ``via_device_id`` links
    there. The fallback is not a dead end: when the same installation later
    runs 2026.9, ``async_get_or_create_child`` converts a device whose
    identifiers already exist into a child device and keeps its device ID, so
    entities, areas and automations survive the switch untouched.
    """
    return hasattr(dr, "ChildDeviceInfo")


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

    Both link kinds need the parent's actual registry-assigned device ID rather
    than an identifier tuple: ``via_device_id`` since Home Assistant 2026.8,
    where identifiers are only unique per config entry, and ``parent_device_id``
    always. Platforms are forwarded in an unspecified order, so the first entity
    added may be a sub-device (e.g. a binary_sensor) whose parent has not been
    created yet. Pre-creating the main device and every expected sub-device
    here — keyed by the same stable identifiers ``build_subdevice_info`` uses —
    guarantees every parent lookup resolves and caches the IDs on the
    coordinator so ``build_subdevice_info`` stays a cheap, registry-free lookup.
    Names are enriched later when each device's first entity is added.

    Creation order is not cosmetic. A child device can only be created once its
    parent is registered, so the main device comes first, then the zone modules,
    then everything that hangs below one of them.
    """
    entry = coordinator.config_entry
    if entry is None:
        return
    registry = dr.async_get(hass)
    device_ids: dict[tuple[str, str], str] = {}

    main_identifier = main_device_identifier(coordinator)
    device_ids[main_identifier] = registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={main_identifier},
    ).id

    subdevices = expected_subdevices(coordinator)
    # Resolved dynamically because Home Assistant 2026.8 has no such method and
    # the integration still supports it; ``child_devices_supported`` gates the
    # same capability for the entity-facing device info.
    get_or_create_child = getattr(registry, "async_get_or_create_child", None)
    use_child_devices = child_devices_supported() and get_or_create_child is not None

    # Ordinary devices first — a zone module is the parent of its rooms.
    for identifier, placement in sorted(subdevices.items()):
        if use_child_devices and placement.is_child_device:
            continue
        device_ids[identifier] = registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={identifier},
        ).id

    if not use_child_devices:
        coordinator._hierarchy_device_ids = device_ids
        return

    for identifier, placement in sorted(subdevices.items()):
        if not placement.is_child_device:
            continue
        parent_identifier = placement.parent
        parent_device_id = device_ids.get(parent_identifier)
        if parent_device_id is None:
            # The parent is missing from this round (a room whose zone module no
            # longer has any register of its own, say). Skip rather than raise:
            # ``build_subdevice_info`` then falls back to an unlinked ordinary
            # device, and the next reload creates the child once the parent is
            # back.
            _LOGGER.debug(
                "Skipping child device %s: parent %s was not created",
                identifier,
                parent_identifier,
            )
            continue
        device_ids[identifier] = get_or_create_child(
            config_entry_id=entry.entry_id,
            identifiers={identifier},
            parent_device_id=parent_device_id,
        ).id

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


@dataclass(frozen=True)
class SubdevicePlacement:
    """Where one subdevice belongs in the hierarchy."""

    kind: DeviceScopeKind
    parent: tuple[str, str]

    @property
    def is_child_device(self) -> bool:
        """Return whether this subdevice is a logical part of its parent."""
        return self.kind in _CHILD_DEVICE_KINDS


def _scope_subdevices(
    coordinator: IdmCoordinator, scope: DeviceScope
) -> tuple[tuple[tuple[str, str], SubdevicePlacement], ...]:
    """Return every device one entity scope requires, with its placement.

    A room yields two entries, because the room cannot exist without its zone
    module: the module first, then the room. Callers that create devices rely on
    that order — a child device can only be created once its parent exists. The
    scope's own device is always the last entry.
    """
    main = main_device_identifier(coordinator)
    if scope.kind == "heating_circuit":
        placement = SubdevicePlacement(scope.kind, main)
        return ((heating_circuit_identifier(coordinator, scope.primary), placement),)
    if scope.kind in _MODULE_DEVICE_METADATA:
        placement = SubdevicePlacement(scope.kind, main)
        return ((optional_module_identifier(coordinator, scope.primary), placement),)

    zone = int(scope.primary)
    module_identifier = zone_module_identifier(coordinator, zone)
    module = (module_identifier, SubdevicePlacement("zone_module", main))
    if scope.kind == "zone_room" and scope.secondary is not None:
        room_identifier = zone_room_identifier(coordinator, zone, scope.secondary)
        return (module, (room_identifier, SubdevicePlacement(scope.kind, module_identifier)))
    return (module,)


def _scope_identifiers(coordinator: IdmCoordinator, scope: DeviceScope) -> set[tuple[str, str]]:
    """Return all device identifiers required by one entity scope."""
    return {identifier for identifier, _placement in _scope_subdevices(coordinator, scope)}


def expected_subdevices(coordinator: IdmCoordinator) -> dict[tuple[str, str], SubdevicePlacement]:
    """Map every justified subdevice identifier to its placement.

    The placement decides how the device is registered: a child device for the
    logical parts of a controller, an ordinary ``via_device_id``-linked device
    for the zone modules.
    """
    if coordinator.device_hierarchy_enabled is not True:
        return {}

    entity_keys = {register.name for register in coordinator._registers}
    supplement = coordinator.web_supplement
    sensor_values = getattr(supplement, "sensor_values", None)
    if isinstance(sensor_values, dict):
        entity_keys.update(str(key) for key in sensor_values)
    options = getattr(coordinator.config_entry, "options", {}) if coordinator.config_entry is not None else {}
    if isinstance(options, dict) and options.get(CONF_TECHNICIAN_CODES, False):
        entity_keys.add("technician_codes")
    entity_keys.add("error_acknowledge")

    subdevices: dict[tuple[str, str], SubdevicePlacement] = {}
    for entity_key in sorted(entity_keys):
        if scope := resolve_device_scope(entity_key):
            for identifier, placement in _scope_subdevices(coordinator, scope):
                subdevices.setdefault(identifier, placement)
    return subdevices


def expected_subdevice_identifiers(coordinator: IdmCoordinator) -> set[tuple[str, str]]:
    """Return subdevices justified by the current register and web-value set."""
    return set(expected_subdevices(coordinator))


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


def _hierarchy_devices_for_entry(registry: dr.DeviceRegistry, entry_id: str) -> list[Any]:
    """Return every device of this entry that can hold a hierarchy identifier.

    ``async_entries_for_config_entry`` returns ordinary devices only, so the
    child devices — which is what the heating circuits, modules and rooms are on
    Home Assistant 2026.9 and newer — have to be collected separately.
    """
    devices: list[Any] = list(dr.async_entries_for_config_entry(registry, entry_id))
    child_entries = getattr(dr, "async_child_entries_for_config_entry", None)
    if child_entries is not None:
        devices.extend(child_entries(registry, entry_id))
    return devices


def _detach_hierarchy_device(registry: dr.DeviceRegistry, device: Any, entry_id: str) -> None:
    """Drop one stale hierarchy device from this config entry.

    A child device belongs to its parent's config entry and has no membership of
    its own to remove, so it is deleted outright. Removing an ordinary device
    from its only config entry deletes it as well.
    """
    if getattr(device, "parent_device_id", None) is not None:
        registry.async_remove_device(device.id)
        return
    registry.async_update_device(
        device.id,
        remove_config_entry_id=entry_id,
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

    devices = _hierarchy_devices_for_entry(registry, entry_id)

    # Deleting an ordinary device cascades to its child devices, so a zone module
    # must not be collected while a room below it is still in use. Count the
    # children this config entry has per parent up front and decrement as they
    # are removed, rather than asking the registry again mid-pass: the count then
    # reflects this pass's own removals, so a module whose rooms all disappear in
    # the same run is still collected in that run.
    surviving_children: dict[str, int] = {}
    for device in devices:
        parent_device_id = getattr(device, "parent_device_id", None)
        if parent_device_id is not None:
            surviving_children[parent_device_id] = surviving_children.get(parent_device_id, 0) + 1

    # Children before parents, so the counts above are already settled when a
    # parent is considered.
    devices.sort(key=lambda device: getattr(device, "parent_device_id", None) is None)

    for device in devices:
        hierarchy_identifiers = {
            identifier for identifier in device.identifiers if _is_hierarchy_identifier(entry_id, identifier)
        }
        if not hierarchy_identifiers:
            continue

        parent_device_id = getattr(device, "parent_device_id", None)
        if parent_device_id is None and surviving_children.get(device.id):
            # A module that still carries rooms stays, even without an entity of
            # its own: the rooms below it are the reason it exists.
            continue

        stale = hierarchy_identifiers.isdisjoint(expected)
        # Sub-devices are pre-created without a name so the parent links resolve
        # regardless of platform order; the name arrives with the first entity.
        # One that never receives an entity — because its registers are filtered
        # out or its feature was turned off — would otherwise sit in the device
        # list forever as an unnamed, empty entry.
        if not stale and er.async_entries_for_device(entity_registry, device.id, include_disabled_entities=True):
            continue

        _detach_hierarchy_device(registry, device, entry_id)
        if parent_device_id is not None and parent_device_id in surviving_children:
            surviving_children[parent_device_id] -= 1


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


def cleanup_stale_web_sensor_entities(hass: HomeAssistant, coordinator: IdmCoordinator) -> None:
    """Remove orphaned sensor platform entities for keys migrated to binary_sensor."""
    config_entry = coordinator.config_entry
    if config_entry is None:
        return

    from .web_binary_sensors import WEB_BINARY_VALUE_KEYS

    entry_id = config_entry.entry_id
    registry = er.async_get(hass)
    stale_unique_ids = {f"{entry_id}_web_{key}" for key in WEB_BINARY_VALUE_KEYS}

    for entity in list(er.async_entries_for_config_entry(registry, entry_id)):
        if entity.domain == "sensor" and entity.unique_id in stale_unique_ids:
            _LOGGER.debug(
                "Removing orphaned web sensor entity %s (migrated to binary_sensor)",
                entity.entity_id,
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


def _subdevice_labels(coordinator: IdmCoordinator, scope: DeviceScope) -> tuple[str, str] | None:
    """Return the display name and model for one subdevice scope."""
    if scope.kind == "heating_circuit":
        circuit = scope.primary.upper()
        return f"Heizkreis {circuit}", "Heizkreis"
    if scope.kind in _MODULE_DEVICE_METADATA:
        _module, name, model = _MODULE_DEVICE_METADATA[scope.kind]
        return name, model

    zone = int(scope.primary)
    if scope.kind == "zone_module":
        return f"Zonenmodul {zone}", "Zonenmodul"
    if scope.secondary is None:
        return None
    return f"Zonenmodul {zone} Raum {scope.secondary}", "Raumregelung"


def build_subdevice_info(coordinator: IdmCoordinator, entity_key: str) -> DeviceInfo | None:
    """Build subdevice information when hierarchy mode is enabled.

    Returns a ``ChildDeviceInfo``-shaped mapping for the logical parts of a
    controller when Home Assistant supports child devices, and the classic
    ``via_device_id`` ``DeviceInfo`` otherwise. Both are typed as ``DeviceInfo``
    here because that is what every caller assigns to ``_attr_device_info``,
    which Home Assistant itself types as ``DeviceInfo | ChildDeviceInfo``.
    """
    if coordinator.device_hierarchy_enabled is not True:
        return None

    scope = resolve_device_scope(entity_key)
    if scope is None:
        return None

    labels = _subdevice_labels(coordinator, scope)
    if labels is None:
        return None
    name, model = labels

    identifier, placement = _scope_subdevices(coordinator, scope)[-1]
    parent_device_id = _via_device_id(coordinator, placement.parent)

    if placement.is_child_device and child_devices_supported() and parent_device_id is not None:
        # A child device carries no hardware metadata of its own — no
        # manufacturer, model, connections or via_device_id — because it is a
        # part of the parent product rather than a device in its own right.
        # Home Assistant rejects those fields here, so the model label is
        # dropped deliberately, not by oversight.
        child_info: dict[str, Any] = {
            "identifiers": {identifier},
            "name": name,
            "parent_device_id": parent_device_id,
        }
        return cast("DeviceInfo", child_info)

    info = DeviceInfo(
        identifiers={identifier},
        name=name,
        manufacturer=MANUFACTURER,
        model=model,
    )
    if parent_device_id is not None:
        info["via_device_id"] = parent_device_id
    return info
