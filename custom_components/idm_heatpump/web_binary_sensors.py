"""Binary sensors backed by optional IDM Navigator web values."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.helpers.entity import EntityCategory  # type: ignore[attr-defined]

from .coordinator import IdmCoordinator
from .device_hierarchy import (
    HEATING_CIRCUIT_LETTERS,
    active_heating_circuits,
    build_subdevice_info,
)
from .entity import IdmCoordinatorEntityBase, build_device_info, build_entity_unique_id
from .entity_names import web_translation_for_value


@dataclass(frozen=True)
class WebBinarySensorDefinition:
    """Metadata for one boolean Navigator web value."""

    key: str
    icon: str
    device_class: BinarySensorDeviceClass | None = None
    entity_category: EntityCategory | None = None
    enabled_by_default: bool = True
    inverted: bool = False


WEB_BINARY_SENSOR_DEFINITIONS: tuple[WebBinarySensorDefinition, ...] = (
    WebBinarySensorDefinition(
        key="compressor_1",
        icon="mdi:engine",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    WebBinarySensorDefinition(
        key="compressor_heating",
        icon="mdi:heating-coil",
        device_class=BinarySensorDeviceClass.HEAT,
    ),
    WebBinarySensorDefinition(
        key="dewpoint_humidity_alarm",
        icon="mdi:water-alert",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        inverted=True,
    ),
    WebBinarySensorDefinition(
        # DeviceClass.LOCK means on=unlocked in HA. EVU "lock contact active"
        # is closer to a safety/grid-block state, so SAFETY is used (on=unsafe).
        key="ew_evu_lock_contact",
        icon="mdi:lock",
        device_class=BinarySensorDeviceClass.SAFETY,
        inverted=True,
    ),
    WebBinarySensorDefinition(
        key="ext_hotwater_signal",
        icon="mdi:water-boiler",
        device_class=BinarySensorDeviceClass.HEAT,
    ),
    WebBinarySensorDefinition(
        key="external_request",
        icon="mdi:connection",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    WebBinarySensorDefinition(
        key="failure_eheating",
        icon="mdi:alert-circle",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        inverted=True,
    ),
    WebBinarySensorDefinition(
        key="flow_pump_on",
        icon="mdi:pump",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    WebBinarySensorDefinition(
        key="heat_generator_2nd",
        icon="mdi:radiator",
        device_class=BinarySensorDeviceClass.HEAT,
    ),
    WebBinarySensorDefinition(
        key="heat_generator_2nd_3rd",
        icon="mdi:radiator-multiple",
        device_class=BinarySensorDeviceClass.HEAT,
    ),
    WebBinarySensorDefinition(
        key="high_pressure_error",
        icon="mdi:gauge-full",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    WebBinarySensorDefinition(
        key="hotwater_circulation_pump",
        icon="mdi:pump",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    WebBinarySensorDefinition(
        key="hotwater_station_flow_switch",
        icon="mdi:water-check",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    WebBinarySensorDefinition(
        key="siphon_heating",
        icon="mdi:heating-coil",
        device_class=BinarySensorDeviceClass.HEAT,
    ),
)


def _heating_circuit_pump_definition(letter: str) -> WebBinarySensorDefinition:
    """Return the pump definition for one heating circuit."""
    return WebBinarySensorDefinition(
        key=f"pump_heating_circuit{letter}",
        icon="mdi:pump",
        device_class=BinarySensorDeviceClass.RUNNING,
    )


# Every heating-circuit pump key must be known here so the sensor platform
# never creates a duplicate regular sensor for a circuit that is enabled later.
WEB_BINARY_VALUE_KEYS: frozenset[str] = frozenset(
    definition.key for definition in WEB_BINARY_SENSOR_DEFINITIONS
) | frozenset(f"pump_heating_circuit{letter}" for letter in HEATING_CIRCUIT_LETTERS)

_TRUE_TEXT_VALUES = frozenset(
    {
        "1",
        "an",
        "active",
        "aktiv",
        "ein",
        "enabled",
        "ja",
        "on",
        "running",
        "true",
    }
)
_FALSE_TEXT_VALUES = frozenset(
    {
        "0",
        "aus",
        "disabled",
        "false",
        "inaktiv",
        "inactive",
        "nein",
        "off",
        "stopped",
    }
)


def normalize_web_binary_value(value: Any) -> bool | None:
    """Normalize a Navigator web value without inventing an unknown state."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        if isinstance(value, float) and not math.isfinite(value):
            return None
        if value == 0:
            return False
        if value == 1:
            return True
        return None
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in _TRUE_TEXT_VALUES:
            return True
        if normalized in _FALSE_TEXT_VALUES:
            return False
    return None


def web_binary_sensor_entities(coordinator: IdmCoordinator) -> list[IdmWebBinarySensor]:
    """Create all web binary sensors when web is enabled.

    Heating-circuit pumps are created for every configured circuit, so a
    circuit enabled later in the options flow gets its web entities on the
    reload that follows.

    Values may arrive after the first successful web poll; entities stay
    unavailable until a normalized boolean value exists for their key.
    """
    definitions = [
        *WEB_BINARY_SENSOR_DEFINITIONS,
        *(_heating_circuit_pump_definition(letter) for letter in active_heating_circuits(coordinator)),
    ]
    return [IdmWebBinarySensor(coordinator, definition) for definition in definitions]


class IdmWebBinarySensor(IdmCoordinatorEntityBase, BinarySensorEntity):
    """Binary sensor backed by an optional local Navigator web value."""

    def __init__(self, coordinator: IdmCoordinator, definition: WebBinarySensorDefinition) -> None:
        super().__init__(coordinator)
        self._definition = definition
        entity_key = f"web_{definition.key}"
        entry_id = coordinator.config_entry.entry_id  # type: ignore[union-attr]
        self._attr_unique_id = build_entity_unique_id(entry_id, entity_key)
        translation_key, placeholders = web_translation_for_value(definition.key)
        if placeholders:
            self._attr_translation_placeholders = placeholders
        self.entity_description = BinarySensorEntityDescription(
            key=entity_key,
            translation_key=translation_key,
            icon=definition.icon,
            device_class=definition.device_class,
            entity_category=definition.entity_category,
            entity_registry_enabled_default=definition.enabled_by_default,
        )

    @property
    def device_info(self) -> Any:
        return build_subdevice_info(self.coordinator, self._definition.key) or build_device_info(self.coordinator)

    def _normalized_value(self) -> bool | None:
        supplement = self.coordinator.web_supplement
        if supplement is None:
            return None
        value = supplement.sensor_values.get(self._definition.key)
        if value is None:
            return None
        return normalize_web_binary_value(value.native_value)

    @property
    def available(self) -> bool:
        # Independent of Modbus last_update_success (see IdmWebSensor).
        return self.coordinator.web_supplement is not None and self._normalized_value() is not None

    @property
    def is_on(self) -> bool | None:
        val = self._normalized_value()
        if val is None:
            return None
        return not val if self._definition.inverted else val
