"""Calculated sensors derived from one IDM coordinator snapshot."""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.helpers.device_registry import DeviceInfo

from .coordinator import IdmCoordinator
from .device_hierarchy import build_subdevice_info
from .entity import IdmCoordinatorEntityBase, build_entity_unique_id


@dataclass(frozen=True)
class CalculatedSensorDefinition:
    """Metadata and calculation function for one derived sensor."""

    key: str
    name: str
    sources: tuple[str, ...]
    calculate: Callable[[Mapping[str, Any]], float | None]
    icon: str
    suggested_display_precision: int = 1
    native_unit_of_measurement: str | None = UnitOfTemperature.CELSIUS
    device_class: SensorDeviceClass | None = SensorDeviceClass.TEMPERATURE
    # Register name used to resolve the subdevice this sensor belongs to when
    # device hierarchy is enabled. ``None`` keeps the sensor on the main device.
    # Only set for sensors introduced together with this field: changing it for
    # an existing sensor would move an already-registered entity to a different
    # device.
    device_scope_source: str | None = None
    # When False, the sensor is created as soon as every source register is
    # present in the snapshot, even if a source currently reads its unused
    # sentinel. Required for sources that legitimately report a sentinel while
    # the heat pump is idle: creating the entity only when it happens to be
    # running would make its existence depend on the moment Home Assistant
    # restarts. Runtime availability still requires usable sources.
    require_sources_used: bool = True


def _temperature(data: Mapping[str, Any], key: str) -> float | None:
    """Return one finite, plausible decoded temperature."""
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    numeric = float(value)
    if not math.isfinite(numeric) or not -100.0 <= numeric <= 200.0:
        return None
    return numeric


# A circuit that is not currently asking for heat reports a flow setpoint of
# 0.0. That is a normal operating state, not a sentinel, so the central unused
# filter lets it through — subtracting it would publish the measured flow
# temperature as if it were a deviation.
_NO_FLOW_REQUEST: float = 0.0


def _flow_deviation(flow_key: str, setpoint_key: str) -> Callable[[Mapping[str, Any]], float | None]:
    """Build the flow deviation, suppressed while the circuit requests nothing."""

    def calculate(data: Mapping[str, Any]) -> float | None:
        setpoint = _temperature(data, setpoint_key)
        if setpoint is None or setpoint == _NO_FLOW_REQUEST:
            return None
        flow = _temperature(data, flow_key)
        if flow is None:
            return None
        return round(flow - setpoint, 2)

    return calculate


def _difference(first_key: str, second_key: str) -> Callable[[Mapping[str, Any]], float | None]:
    """Build a signed temperature-difference calculation."""

    def calculate(data: Mapping[str, Any]) -> float | None:
        first = _temperature(data, first_key)
        second = _temperature(data, second_key)
        if first is None or second is None:
            return None
        return round(first - second, 2)

    return calculate


# COP source registers verified against a live Navigator 10 (issue #135):
#   power_consumption_hp (4122) and thermal_power_flow_sensor (4126) are
# implemented and return plausible values. The road-map rule "no estimated
# values as measurements" (issue #135) is enforced inside _cop: while the
# heat pump is idle both sources report 0 kW and COP is suppressed (None).
#
# Broad 15-day field verification (Navigator 10, firmware NAV10_20.24,
# -7...+7 degC outdoor, 30 s sampling): the two source registers are stable
# in normal operation. Real thermal output reads in the unit's rated range
# 0..~16 kW for ~97% of samples (median ~6.7 kW, p99 ~13 kW); electrical
# input 0..~10 kW (p99 ~5 kW). The remaining samples sit outside that range
# during defrost / operating-state transitions and are measurement artefacts
# of the flow/delta-T calculation, NOT real power (e.g. isolated spikes to
# ~-48 kW). The "thermal <= 0" guard below correctly suppresses COP during
# these phases, and no smoothing is applied because estimating values is
# explicitly disallowed by issue #135.
_COP_ELECTRIC_POWER_REGISTER = "power_consumption_hp"
_COP_THERMAL_POWER_REGISTER = "thermal_power_flow_sensor"
# Very low electrical input (<50 W) indicates standby/commissioning rather
# than real operation; refuse to emit a (misleading) high COP ratio in that
# band. Real heating operation reads in the kW range.
_COP_MIN_RELEVANT_POWER_KW = 0.05


def _power(data: Mapping[str, Any], key: str) -> float | None:
    """Return one finite, plausible decoded power value in kW."""
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    numeric = float(value)
    if not math.isfinite(numeric) or numeric < 0.0:
        return None
    return numeric


def _cop(data: Mapping[str, Any]) -> float | None:
    """Coefficient of Performance = thermal power / electrical power.

    Returns None unless both source values are present, finite, and above
    the meaningful-operation threshold. This deliberately produces "no
    value" while the heat pump is idle (P_el = 0) so COP never exposes an
    estimated or division-by-zero value — see issue #135.
    """
    electric = _power(data, _COP_ELECTRIC_POWER_REGISTER)
    thermal = _power(data, _COP_THERMAL_POWER_REGISTER)
    if electric is None or thermal is None:
        return None
    if electric <= 0.0 or thermal <= 0.0:
        return None
    if electric < _COP_MIN_RELEVANT_POWER_KW:
        return None
    return round(thermal / electric, 2)


CALCULATED_SENSOR_DEFINITIONS: tuple[CalculatedSensorDefinition, ...] = (
    CalculatedSensorDefinition(
        key="calculated_hp_temperature_delta",
        name="Wärmepumpen-Spreizung",
        sources=("hp_flow_temp", "hp_return_temp"),
        calculate=_difference("hp_flow_temp", "hp_return_temp"),
        icon="mdi:thermometer-lines",
    ),
    CalculatedSensorDefinition(
        key="calculated_heat_source_temperature_delta",
        name="Wärmequellen-Spreizung",
        sources=("heat_source_inlet_temp", "heat_source_outlet_temp"),
        calculate=_difference("heat_source_inlet_temp", "heat_source_outlet_temp"),
        icon="mdi:thermometer-water",
    ),
    CalculatedSensorDefinition(
        key="calculated_dhw_setpoint_deviation",
        name="Warmwasser-Abweichung Ist zu Soll",
        sources=("dhw_temp_top", "dhw_setpoint"),
        calculate=_difference("dhw_temp_top", "dhw_setpoint"),
        icon="mdi:water-thermometer-outline",
    ),
    CalculatedSensorDefinition(
        key="calculated_cop",
        name="Jahresarbeitszahl (COP, momentan)",
        sources=(_COP_ELECTRIC_POWER_REGISTER, _COP_THERMAL_POWER_REGISTER),
        calculate=_cop,
        icon="mdi:gauge",
        suggested_display_precision=2,
        # COP is a dimensionless ratio: no unit and no device class.
        native_unit_of_measurement=None,
        device_class=None,
    ),
)


# Heating-circuit flow deviation = actual flow temperature minus the flow
# setpoint the controller currently requests for that circuit. Both source
# registers were verified on live Navigator 10 hardware (see
# docs/dev/open-work-audit.md): ``hc_{x}_setpoint_flow_temp`` (1378 ff., FLOAT,
# read-only) is the setpoint the heating curve computes for the circuit, and
# ``hc_{x}_flow_temp`` is the measured flow temperature of the same circuit.
#
# Scope note: this deliberately stays *per heating circuit*. The still-open
# roadmap item is the deviation at heat-pump level, which needs an unambiguous
# register for the flow setpoint the heat pump itself requests; heating-curve,
# mixer and maximum values must not be mixed there. Nothing is estimated here —
# both operands are decoded register values of one circuit.
#
# Values observed on real hardware: an unconfigured circuit reports -1.0 and an
# idle circuit reports 0.0. Only -1.0 is a declared sentinel, so the central
# ``is_register_unused`` filter catches that case and the sensor goes
# unavailable. The idle 0.0 is a normal operating state and passes that filter,
# which is why ``_flow_deviation`` suppresses it explicitly: without the guard
# the sensor published ``flow - 0`` and presented the measured flow temperature
# as a deviation. Suppressed means no value (state ``unknown``), matching how
# the COP sensor behaves while the heat pump is idle.
#
# Because the idle 0.0 is a normal operating state, the entity is created from
# register *presence* (``require_sources_used=False``) rather than from the
# momentary value.
FLOW_DEVIATION_CIRCUITS: tuple[str, ...] = ("a", "b", "c", "d", "e", "f", "g")


def flow_deviation_definition(circuit: str) -> CalculatedSensorDefinition:
    """Build the flow-deviation definition for one heating circuit."""
    flow_register = f"hc_{circuit}_flow_temp"
    setpoint_register = f"hc_{circuit}_setpoint_flow_temp"
    return CalculatedSensorDefinition(
        key=f"calculated_hc_{circuit}_flow_deviation",
        name=f"Heizkreis {circuit.upper()} Vorlauf-Abweichung",
        sources=(flow_register, setpoint_register),
        # Positive = flow runs above the requested setpoint (overshoot),
        # negative = the circuit does not reach its requested setpoint.
        calculate=_flow_deviation(flow_register, setpoint_register),
        icon="mdi:thermometer-chevron-up",
        # Belongs next to the other values of its circuit, not on the main device.
        device_scope_source=flow_register,
        require_sources_used=False,
    )


FLOW_DEVIATION_DEFINITIONS: tuple[CalculatedSensorDefinition, ...] = tuple(
    flow_deviation_definition(circuit) for circuit in FLOW_DEVIATION_CIRCUITS
)


def _definition_supported(coordinator: IdmCoordinator, definition: CalculatedSensorDefinition) -> bool:
    """Return whether all required source registers exist on this installation."""
    data = coordinator.data
    if not data:
        return False
    if not definition.require_sources_used:
        return all(source in data for source in definition.sources)
    unused = coordinator.unused_registers
    return all(source in data and source not in unused for source in definition.sources)


def calculated_sensor_entities(coordinator: IdmCoordinator) -> list[IdmCalculatedSensor]:
    """Create only calculated sensors supported by the detected installation."""
    return [
        IdmCalculatedSensor(coordinator, definition)
        for definition in (*CALCULATED_SENSOR_DEFINITIONS, *FLOW_DEVIATION_DEFINITIONS)
        if _definition_supported(coordinator, definition)
    ]


class IdmCalculatedSensor(IdmCoordinatorEntityBase, SensorEntity):
    """Sensor calculated exclusively from the current coordinator snapshot."""

    def __init__(self, coordinator: IdmCoordinator, definition: CalculatedSensorDefinition) -> None:
        super().__init__(coordinator)
        self._definition = definition
        entry_id = coordinator.config_entry.entry_id  # type: ignore[union-attr]
        self._attr_unique_id = build_entity_unique_id(entry_id, definition.key)
        self.entity_description = SensorEntityDescription(
            key=definition.key,
            name=definition.name,
            native_unit_of_measurement=definition.native_unit_of_measurement,
            device_class=definition.device_class,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=definition.suggested_display_precision,
            icon=definition.icon,
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Place the sensor on its subdevice when the definition names one."""
        scope_source = self._definition.device_scope_source
        if scope_source is not None and (subdevice := build_subdevice_info(self.coordinator, scope_source)):
            return subdevice
        return super().device_info

    def _sources_available(self) -> bool:
        """Return True when every source register is present, not unused, and finite.

        A calculated sensor is 'available' as long as its sources exist and are
        not in an unused/sentinel state; the calculated value may still be None
        (e.g. COP is suppressed while the heat pump is idle), in which case the
        state is 'unknown' rather than 'unavailable' (BL-003).
        """
        data = self.coordinator.data
        if not data:
            return False
        for source in self._definition.sources:
            if source not in data or source in self.coordinator.unused_registers:
                return False
            value = data[source]
            if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
                return False
        return True

    def _calculate(self) -> float | None:
        if not self._sources_available():
            return None
        return self._definition.calculate(self.coordinator.data)

    @property
    def available(self) -> bool:
        return super().available and self._sources_available()

    @property
    def native_value(self) -> float | None:
        return self._calculate()
