"""Sensor platform for IDM Heatpump."""

from __future__ import annotations

# IDM Heatpump for Home Assistant
# © 2026 Xerolux — Inoffizielle Community-Integration für IDM Navigator 2.0 / 10 Wärmepumpen
# Erstellt von Xerolux | https://github.com/Xerolux/idm-heatpump-hass
# Lizenz: MIT

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory, EntityDescription  # type: ignore[attr-defined]
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from idm_heatpump import DataType, RegisterDef

try:
    import idm_heatpump as idm_api
except ImportError:
    WEB_VALUE_DESCRIPTIONS = {}
else:
    WEB_VALUE_DESCRIPTIONS = getattr(idm_api, "WEB_VALUE_DESCRIPTIONS", {})

from .const import CONF_TECHNICIAN_CODES
from .coordinator import IdmCoordinator
from .entity import (
    IdmCoordinatorEntityBase,
    IdmEntity,
    build_entity_unique_id,
    should_add_entity,
)
from .adapter_enums import get_bitflag_de_labels, get_slug_map_and_key
from .adapter_descriptions import get_icon_for_register, infer_sensor_classes
from .internal_messages import format_internal_message, internal_message_text
from .registers import entity_order_group, sort_entity_descriptions
from .technician_codes import calculate_codes


def _decode_bitflag(value: int, options: dict[int, str]) -> str:
    """Decode a bitfield value into a human-readable 'Flag1|Flag2' string."""
    if value == 0:
        return options.get(0, "Aus")
    active = [label for bit, label in options.items() if bit != 0 and (value & bit) == bit]
    return "|".join(active) if active else f"Unbekannt ({value})"


PARALLEL_UPDATES = 0


@dataclass(frozen=True)
class WebSensorDefinition:
    """Static metadata for one optional web supplement sensor."""

    key: str
    name: str
    unit: str | None = None
    device_class: SensorDeviceClass | None = None
    state_class: SensorStateClass | None = None
    icon: str | None = None
    entity_category: EntityCategory | None = None
    enabled_by_default: bool = True


_WEB_VALUE_NAMES: tuple[str, ...] = (
    "4way_valve_circuit1",
    "airsource_temperature",
    "battery_voltage_central_unit",
    "board_temperature",
    "cold_water_temperature",
    "compressor_1",
    "compressor_heating",
    "condenser_pressure",
    "condenser_temperature",
    "controller_online_hours",
    "current_electrical_power",
    "current_expected_power_cooling",
    "current_expected_power_heating",
    "current_expected_power_hotwater",
    "dewpoint_humidity_alarm",
    "evaporation_temperature",
    "evaporator_outlet_temperature",
    "ew_evu_lock_contact",
    "ext_hotwater_signal",
    "ext_switch_heating_cooling",
    "external_request",
    "failure_eheating",
    "flow_pump_on",
    "flow_pump_output",
    "flow_pump_percentage",
    "flow_temp_HK_A",
    "flow_temp_HK_C",
    "flow_temperature",
    "flowmeter",
    "heat_generator_2nd",
    "heat_generator_2nd_3rd",
    "heat_sink_intermediate_circuit_pump_signal",
    "heating_water_outlet_temperature",
    "heatpump_model",
    "heatstore_temperature",
    "high_pressure_error",
    "hotgas_temperature",
    "hotwater_circulation_heat_quantity",
    "hotwater_circulation_pump",
    "hotwater_station_flow_switch",
    "hotwater_station_flowmeter",
    "hotwater_station_pump_percentage",
    "hotwater_tapping_heat_quantity",
    "hotwater_temperature",
    "infosystem_notification_count",
    "infosystem_notifications",
    "liquid_line_temperature",
    "loading_temperature",
    "mixer_heating_circuitA",
    "myidm_id",
    "outside_air_temperature",
    "pump_heating_circuitA",
    "return_temperature",
    "room_temperature_HK_A",
    "runtime_cooling_hours",
    "runtime_defrosting_hours",
    "runtime_heating_hours",
    "runtime_hotwater_hours",
    "runtime_second_heat_generator_hours",
    "runtime_stage_1_hours",
    "siphon_heating",
    "software_version",
    "switch_cycles_second_heat_generator",
    "switch_cycles_stage_1",
    "valve_heating_hotwater",
    "ventilator_direction_1",
    "ventilator_voltage",
    "verdamper_pressure",
    "water_temp_bottom",
    "water_temp_top",
)

_WEB_ONLY_EXTRA_VALUE_NAMES: tuple[str, ...] = ("navigator_version",)

_WEB_MODBUS_DUPLICATE_VALUES: frozenset[str] = frozenset(
    {
        "current_electrical_power",
        "flow_temp_HK_A",
        "flow_temp_HK_C",
        "flow_temperature",
        "flowmeter",
        "heatstore_temperature",
        "hotwater_temperature",
        "outside_air_temperature",
        "return_temperature",
        "room_temperature_HK_A",
        "water_temp_bottom",
        "water_temp_top",
    }
)

_WEB_VALUE_UNITS: dict[str, str] = {
    "airsource_temperature": "°C",
    "battery_voltage_central_unit": "V",
    "board_temperature": "°C",
    "cold_water_temperature": "°C",
    "condenser_pressure": "bar",
    "condenser_temperature": "°C",
    "current_electrical_power": "kW",
    "current_expected_power_cooling": "kW",
    "current_expected_power_heating": "kW",
    "current_expected_power_hotwater": "kW",
    "evaporation_temperature": "°C",
    "evaporator_outlet_temperature": "°C",
    "flow_pump_percentage": "%",
    "flow_temperature": "°C",
    "flowmeter": "L/min",
    "heating_water_outlet_temperature": "°C",
    "hotgas_temperature": "°C",
    "hotwater_circulation_heat_quantity": "kWh",
    "hotwater_station_flowmeter": "L/min",
    "hotwater_station_pump_percentage": "%",
    "hotwater_tapping_heat_quantity": "kWh",
    "hotwater_temperature": "°C",
    "liquid_line_temperature": "°C",
    "loading_temperature": "°C",
    "return_temperature": "°C",
    "runtime_cooling_hours": "h",
    "runtime_defrosting_hours": "h",
    "runtime_heating_hours": "h",
    "runtime_hotwater_hours": "h",
    "runtime_second_heat_generator_hours": "h",
    "runtime_stage_1_hours": "h",
    "ventilator_voltage": "V",
    "verdamper_pressure": "bar",
}

_WEB_VALUE_NAMES_DE: dict[str, str] = {
    "airsource_temperature": "Luftquellen Temperatur",
    "battery_voltage_central_unit": "Batteriespannung Zentraleinheit",
    "board_temperature": "Platinentemperatur",
    "cold_water_temperature": "Kaltwasser Temperatur",
    "compressor_1": "Verdichter 1",
    "compressor_heating": "Verdichter Heizung",
    "condenser_pressure": "Kondensator Druck",
    "condenser_temperature": "Kondensator Temperatur",
    "controller_online_hours": "Regler Online",
    "current_expected_power_cooling": "Momentane Leistung Kühlen",
    "current_expected_power_heating": "Momentane Leistung Heizen",
    "current_expected_power_hotwater": "Momentane Leistung Warmwasser",
    "dewpoint_humidity_alarm": "Taupunkt Feuchte Alarm",
    "evaporation_temperature": "Verdampfungstemperatur",
    "evaporator_outlet_temperature": "Verdampfer Austrittstemperatur",
    "ew_evu_lock_contact": "EVU Sperrkontakt",
    "ext_hotwater_signal": "Externe Vorrangladung",
    "ext_switch_heating_cooling": "Externe Umschaltung Heizen/Kühlen",
    "external_request": "Externe Anforderung",
    "failure_eheating": "Störung E-Heizung",
    "flow_pump_on": "Durchflusspumpe Ein",
    "flow_pump_output": "Durchflusspumpe Ausgang",
    "flow_pump_percentage": "Durchflusspumpe Signal",
    "heat_generator_2nd": "2. Wärmeerzeuger",
    "heat_generator_2nd_3rd": "2./3. Wärmeerzeuger",
    "heat_sink_intermediate_circuit_pump_signal": "Wärmesenke Zwischenkreispumpe Signal",
    "heating_water_outlet_temperature": "Heizwasser Austrittstemperatur",
    "heatpump_model": "Wärmepumpenmodell",
    "high_pressure_error": "Hochdruck Störung",
    "hotgas_temperature": "Heißgastemperatur",
    "hotwater_circulation_heat_quantity": "Wärmemenge Zirkulation",
    "hotwater_circulation_pump": "Warmwasser Zirkulationspumpe",
    "hotwater_station_flow_switch": "Warmwasserstation Strömungsschalter",
    "hotwater_station_flowmeter": "Warmwasserstation Durchfluss",
    "hotwater_station_pump_percentage": "Warmwasserstation Pumpe",
    "hotwater_tapping_heat_quantity": "Wärmemenge Zapfung",
    "infosystem_notification_count": "Infosystem Meldungen Anzahl",
    "infosystem_notifications": "Infosystem Meldungen",
    "liquid_line_temperature": "Flüssigkeitsleitung Temperatur",
    "loading_temperature": "Ladetemperatur",
    "mixer_heating_circuitA": "Mischer Heizkreis A",
    "myidm_id": "myIDM ID",
    "navigator_version": "Navigator Version",
    "pump_heating_circuitA": "Pumpe Heizkreis A",
    "runtime_cooling_hours": "Laufzeit Kühlen",
    "runtime_defrosting_hours": "Laufzeit Abtauen",
    "runtime_heating_hours": "Laufzeit Heizen",
    "runtime_hotwater_hours": "Laufzeit Warmwasser",
    "runtime_second_heat_generator_hours": "Laufzeit 2. Wärmeerzeuger",
    "runtime_stage_1_hours": "Laufzeit Stufe 1",
    "siphon_heating": "Siphonheizung",
    "software_version": "Software Version",
    "switch_cycles_second_heat_generator": "Schaltzyklen 2. Wärmeerzeuger",
    "switch_cycles_stage_1": "Schaltzyklen Stufe 1",
    "valve_heating_hotwater": "Ventil Heizung/Warmwasser",
    "ventilator_direction_1": "Ventilator Richtung 1",
    "ventilator_voltage": "Ventilator Spannung",
    "verdamper_pressure": "Verdampfer Druck",
}


def _humanize_web_name(key: str) -> str:
    return _WEB_VALUE_NAMES_DE.get(key, key.replace("_", " ").title())


def _web_metadata_value(metadata: object, attr: str) -> object:
    if isinstance(metadata, dict):
        return metadata.get(attr)
    return getattr(metadata, attr, None)


def _coerce_web_device_class(value: object) -> SensorDeviceClass | None:
    if value is None:
        return None
    try:
        return SensorDeviceClass(str(value))
    except ValueError:
        return None


def _coerce_web_state_class(value: object) -> SensorStateClass | None:
    if value is None:
        return None
    try:
        return SensorStateClass(str(value))
    except ValueError:
        return None


def _web_sensor_definition(key: str) -> WebSensorDefinition:
    metadata = WEB_VALUE_DESCRIPTIONS.get(key) if isinstance(WEB_VALUE_DESCRIPTIONS, dict) else None
    preferred_unit = _web_metadata_value(metadata, "preferred_unit")
    unit = str(preferred_unit) if preferred_unit else _WEB_VALUE_UNITS.get(key)
    device_class = _coerce_web_device_class(_web_metadata_value(metadata, "device_class"))
    state_class = _coerce_web_state_class(_web_metadata_value(metadata, "state_class"))
    if device_class is None and state_class is None:
        device_class, state_class = infer_sensor_classes(key, unit)
    if unit == "h":
        state_class = SensorStateClass.TOTAL_INCREASING
    if key.startswith("switch_cycles"):
        state_class = SensorStateClass.TOTAL_INCREASING
    enabled_by_default = _web_metadata_value(metadata, "enabled_by_default")
    entity_category = (
        EntityCategory.DIAGNOSTIC
        if key
        in {
            "heatpump_model",
            "infosystem_notification_count",
            "infosystem_notifications",
            "myidm_id",
            "navigator_version",
            "software_version",
        }
        else None
    )
    return WebSensorDefinition(
        key=key,
        name=f"{_humanize_web_name(key)} (Web)",
        unit=unit,
        device_class=device_class,
        state_class=state_class,
        icon=get_icon_for_register(key, unit),
        entity_category=entity_category,
        enabled_by_default=bool(enabled_by_default) if enabled_by_default is not None else True,
    )


def _web_sensor_definitions(coordinator: IdmCoordinator) -> list[WebSensorDefinition]:
    modbus_register_names = {reg.name for reg in getattr(coordinator, "_registers", [])}
    has_modbus = len(modbus_register_names) > 0
    definitions = []
    for key in (*_WEB_VALUE_NAMES, *_WEB_ONLY_EXTRA_VALUE_NAMES):
        if key in modbus_register_names:
            continue
        if has_modbus and key in _WEB_MODBUS_DUPLICATE_VALUES:
            continue
        definitions.append(_web_sensor_definition(key))
    return sorted(definitions, key=_web_sensor_sort_key)


def _web_sensor_sort_key(definition: WebSensorDefinition) -> tuple[int, int, str]:
    category_rank = 2 if definition.entity_category == EntityCategory.DIAGNOSTIC else 1
    return (entity_order_group(definition.key), category_rank, definition.name.casefold())


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: IdmCoordinator = entry.runtime_data.coordinator
    entities: list[IdmSensor | IdmTechnicianCodeSensor | IdmWebSensor] = []
    if entry.options.get(CONF_TECHNICIAN_CODES, False):
        entities += _technician_code_entities(coordinator)
    entities += [
        IdmSensor(coordinator, desc_info["register"], desc_info["description"])
        for desc_info in sort_entity_descriptions(coordinator.sensor_descriptions)
        if should_add_entity(coordinator, desc_info["register"])
        and not (
            desc_info["register"].enum_options
            and desc_info["register"].datatype == DataType.UCHAR
            and desc_info["register"].writable
        )
    ]
    if getattr(coordinator, "web_enabled", False) is True:
        entities += [IdmWebSensor(coordinator, definition) for definition in _web_sensor_definitions(coordinator)]
    async_add_entities(entities)


def _technician_code_entities(coordinator: IdmCoordinator) -> list[IdmTechnicianCodeSensor]:
    return [
        IdmTechnicianCodeSensor(coordinator, "level_1"),
        IdmTechnicianCodeSensor(coordinator, "level_2"),
    ]


class IdmSensor(IdmEntity, SensorEntity):
    def __init__(
        self,
        coordinator: IdmCoordinator,
        reg: RegisterDef,
        entity_desc: EntityDescription,
    ) -> None:
        super().__init__(coordinator, reg, entity_desc)
        # Cache enum lookups: the register name never changes after setup, so
        # avoid re-running regex matches on every state update (mirrors IdmSelect).
        self._enum_slug_map, _ = get_slug_map_and_key(reg.name)
        self._enum_bitflag_labels = get_bitflag_de_labels(reg.name)

    @property
    def native_value(self) -> str | float | int | None:
        if not self.coordinator.data:
            return None
        value = self.coordinator.data.get(self._register.name)
        if value is None:
            return None
        if self._register.name == "internal_message":
            return format_internal_message(value)
        if self._register.enum_options:
            try:
                int_value = int(value)
            except (TypeError, ValueError):
                return value
            if self._register.datatype == DataType.BITFLAG:
                return _decode_bitflag(int_value, self._enum_bitflag_labels or self._register.enum_options)
            if self._enum_slug_map is not None:
                return self._enum_slug_map.get(int_value)
            return self._register.enum_options.get(int_value, f"Unbekannt ({value})")
        return value

    @property
    def extra_state_attributes(self) -> dict[str, str | int] | None:
        if self._register.name != "internal_message":
            return None
        if not self.coordinator.data:
            return None
        value = self.coordinator.data.get(self._register.name)
        if value is None:
            return None
        message_text = internal_message_text(value)
        if message_text is None:
            return None
        try:
            message_code = int(value)
        except (TypeError, ValueError):
            return None
        return {
            "message_code": message_code,
            "message_text": message_text,
        }


class IdmWebSensor(IdmCoordinatorEntityBase, SensorEntity):
    """Sensor backed by optional local Navigator web data."""

    def __init__(self, coordinator: IdmCoordinator, definition: WebSensorDefinition) -> None:
        super().__init__(coordinator)
        self._definition = definition
        entity_key = f"web_{definition.key}"
        entry_id = coordinator.config_entry.entry_id  # type: ignore[union-attr]
        self._attr_unique_id = build_entity_unique_id(entry_id, entity_key)
        self.entity_description = SensorEntityDescription(
            key=entity_key,
            name=definition.name,
            native_unit_of_measurement=definition.unit,
            device_class=definition.device_class,
            state_class=definition.state_class,
            icon=definition.icon,
            entity_category=definition.entity_category,
            entity_registry_enabled_default=definition.enabled_by_default,
        )

    @property
    def available(self) -> bool:
        if not super().available:
            return False
        if self._definition.key == "navigator_version":
            return self.coordinator.web_supplement is not None and bool(
                self.coordinator.web_supplement.navigator_version
            )
        return (
            self.coordinator.web_supplement is not None
            and self._definition.key in self.coordinator.web_supplement.sensor_values
        )

    @property
    def native_value(self) -> str | float | None:
        web_supplement = self.coordinator.web_supplement
        if web_supplement is None:
            return None
        if self._definition.key == "navigator_version":
            return web_supplement.navigator_version
        value = web_supplement.sensor_values.get(self._definition.key)
        if value is None:
            return None
        return value.native_value


class IdmTechnicianCodeBaseSensor(IdmCoordinatorEntityBase, SensorEntity):
    """Refresh technician-code entities on the minute without coordinator polling."""

    _attr_entity_registry_enabled_default = True
    _cancel_timer: Callable[[], None] | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._cancel_timer = async_track_time_interval(self.hass, self._async_refresh, timedelta(seconds=60))

    async def async_will_remove_from_hass(self) -> None:
        if self._cancel_timer:
            self._cancel_timer()
            self._cancel_timer = None

    @callback
    def _async_refresh(self, _now: object = None) -> None:
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        return True


class IdmTechnicianCodeSensor(
    IdmTechnicianCodeBaseSensor,
):
    """Sensor that shows one current Fachmann Ebene access code."""

    _attr_icon = "mdi:key-variant"

    _NAMES = {
        "level_1": "00 Fachmann Ebene 1",
        "level_2": "00 Fachmann Ebene 2",
    }

    def __init__(self, coordinator: IdmCoordinator, level: str) -> None:
        super().__init__(coordinator)
        self._level = level
        entry_id = coordinator.config_entry.entry_id  # type: ignore[union-attr]
        self._attr_unique_id = build_entity_unique_id(entry_id, f"technician_{level}")
        self._attr_name = self._NAMES[level]

    @property
    def native_value(self) -> str:
        return calculate_codes()[self._level]
