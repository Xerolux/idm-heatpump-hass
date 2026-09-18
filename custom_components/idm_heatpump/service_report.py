"""Privacy-safe, read-only installer report for downloaded diagnostics."""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any

from .health_monitor import HEALTH_CHECKS

_TEMPERATURE_KEYS = (
    "outdoor_temp",
    "hp_flow_temp",
    "hp_return_temp",
    "dhw_temp_top",
    "dhw_setpoint",
    "hc_a_flow_temp",
    "hc_a_setpoint_flow_temp",
)
_ENERGY_KEYS = (
    "total_electrical_kwh",
    "total_thermal_kwh",
    "today_electrical_kwh",
    "today_thermal_kwh",
    "month_electrical_kwh",
    "month_thermal_kwh",
)
_FAULT_KEYS = (
    "hp_sum_alarm",
    "fault_heat_source_circuit",
    "fault_heat_source_pressure",
    "fault_heat_source_pressure_switch",
    "fault_charging_pump_1_intermediate",
    "fault_charging_pump_2_intermediate",
    "booster_fault",
)


def _finite(value: Any) -> float | None:
    """Exclude unavailable sentinels and nonnumeric controller values."""
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number not in (-1.0, 65535.0) else None


def _fault_reading(value: Any) -> float | bool | None:
    return value if isinstance(value, bool) else _finite(value)


def build_service_report(coordinator: Any, versions: Any) -> dict[str, Any]:
    """Build a bounded report from known-safe fields, without connection data."""
    analysis = getattr(coordinator, "operation_analysis", None)
    statistics = getattr(coordinator, "energy_statistics", None)
    data = getattr(coordinator, "data", None) or {}
    poll = coordinator.poll_statistics
    checks = {check.key: check.evaluate(coordinator, analysis) for check in HEALTH_CHECKS}
    operation: dict[str, Any] = {}
    if analysis is not None:
        operation = {
            "compressor_starts_recorded": analysis.total_compressor_starts,
            "defrost_starts_recorded": analysis.total_defrost_starts,
            "alarm_starts_recorded": analysis.total_alarm_starts,
            "alarm_starts_last_7_days": analysis.alarm_starts_last_days(7),
            "compressor_starts_last_24_hours": analysis.compressor_starts_last_hours(24),
            "last_cycle_minutes": (
                round(analysis.last_cycle_duration / 60.0, 1) if analysis.last_cycle_duration is not None else None
            ),
            "average_cycle_minutes": analysis.average_cycle_minutes(),
            "operating_seconds_by_mode": dict(analysis.mode_durations),
        }
    energy = {key: _finite(getattr(statistics, key, None)) for key in _ENERGY_KEYS} if statistics else {}
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "scope": "observed_local_data_only",
        "prediction": False,
        "model": coordinator.model_name,
        "firmware": coordinator.firmware_version,
        "versions": {
            "integration": versions.integration,
            "idm_heatpump_api": versions.api,
            "modbus_connection": versions.modbus_connection,
            "tmodbus": versions.tmodbus,
            "home_assistant": versions.home_assistant,
            "python": versions.python,
        },
        "communication": {
            "last_poll_success": poll.last_success.isoformat() if poll.last_success else None,
            "consecutive_failures": poll.consecutive_failures,
            "total_polls": poll.total_polls,
            "total_failures": poll.total_failures,
        },
        "health_checks": checks,
        "active_health_checks": [key for key, active in checks.items() if active is True],
        "unavailable_health_checks": [key for key, active in checks.items() if active is None],
        "operation": operation,
        "energy_kwh": energy,
        "temperatures_c": {key: _finite(data[key]) for key in _TEMPERATURE_KEYS if key in data},
        "fault_register_readings": {key: _fault_reading(data[key]) for key in _FAULT_KEYS if key in data},
        "unsupported_registers": sorted(coordinator.unsupported_registers),
        "writes_performed_by_report": False,
    }
