"""Device hierarchy helpers for IDM Heatpump entities."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN, MANUFACTURER

if TYPE_CHECKING:
    from .coordinator import IdmCoordinator

DeviceScopeKind = Literal["heating_circuit", "zone_module", "zone_room"]


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
    return None


def main_device_identifier(coordinator: IdmCoordinator) -> tuple[str, str]:
    """Return the stable main-device identifier."""
    return DOMAIN, coordinator.config_entry.entry_id  # type: ignore[union-attr]


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


def _scope_identifiers(coordinator: IdmCoordinator, scope: DeviceScope) -> set[tuple[str, str]]:
    """Return all device identifiers required by one entity scope."""
    if scope.kind == "heating_circuit":
        return {heating_circuit_identifier(coordinator, scope.primary)}

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

    identifiers: set[tuple[str, str]] = set()
    for entity_key in entity_keys:
        if scope := resolve_device_scope(entity_key):
            identifiers.update(_scope_identifiers(coordinator, scope))
    return identifiers


def _is_hierarchy_identifier(entry_id: str, identifier: tuple[str, str]) -> bool:
    """Return whether an identifier belongs to an IDM hierarchy subdevice."""
    domain, value = identifier
    return domain == DOMAIN and value.startswith((f"{entry_id}_heating_circuit_", f"{entry_id}_zone_module_"))


def cleanup_stale_hierarchy_devices(hass: HomeAssistant, coordinator: IdmCoordinator) -> None:
    """Detach stale hierarchy devices without touching entities or the main device."""
    config_entry = coordinator.config_entry
    if config_entry is None:
        return

    entry_id = config_entry.entry_id
    expected = expected_subdevice_identifiers(coordinator)
    registry = dr.async_get(hass)

    for device in dr.async_entries_for_config_entry(registry, entry_id):
        hierarchy_identifiers = {
            identifier for identifier in device.identifiers if _is_hierarchy_identifier(entry_id, identifier)
        }
        if hierarchy_identifiers and hierarchy_identifiers.isdisjoint(expected):
            registry.async_update_device(
                device.id,
                remove_config_entry_id=entry_id,
            )


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
        return DeviceInfo(
            identifiers={heating_circuit_identifier(coordinator, circuit)},
            name=f"Heizkreis {circuit}",
            manufacturer=MANUFACTURER,
            model="Heizkreis",
            via_device=main_identifier,
        )

    zone = int(scope.primary)
    if scope.kind == "zone_module":
        return DeviceInfo(
            identifiers={zone_module_identifier(coordinator, zone)},
            name=f"Zonenmodul {zone}",
            manufacturer=MANUFACTURER,
            model="Zonenmodul",
            via_device=main_identifier,
        )

    room = scope.secondary
    if room is None:
        return None
    return DeviceInfo(
        identifiers={zone_room_identifier(coordinator, zone, room)},
        name=f"Zonenmodul {zone} Raum {room}",
        manufacturer=MANUFACTURER,
        model="Raumregelung",
        via_device=zone_module_identifier(coordinator, zone),
    )
