"""Tests for the bounded installer diagnostics export."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

from custom_components.idm_heatpump.service_report import build_service_report
from custom_components.idm_heatpump.versions import RuntimeVersions


def test_installer_report_collects_observations_without_secrets_or_writes() -> None:
    coordinator = MagicMock()
    coordinator.data = {
        "outdoor_temp": -1,
        "hp_flow_temp": 35.5,
        "dhw_temp_top": 40,
        "dhw_setpoint": 50,
        "hp_sum_alarm": True,
        "host": "private.example",
        "web_pin": "secret",
    }
    coordinator.model_name = "Navigator 10"
    coordinator.firmware_version = "NAV10"
    coordinator.poll_statistics = SimpleNamespace(
        last_success=datetime(2026, 9, 17, tzinfo=UTC), consecutive_failures=3, total_polls=30, total_failures=4
    )
    coordinator.operation_analysis = SimpleNamespace(
        supports_compressor=True,
        supports_alarm=True,
        compressor_starts_last_hours=lambda hours: 7 if hours == 2 else 10,
        total_compressor_starts=40,
        total_defrost_starts=3,
        total_alarm_starts=4,
        alarm_starts_last_days=lambda days: 3,
        last_cycle_duration=600.0,
        average_cycle_minutes=lambda: 15.0,
        mode_durations={"heating": 3600.0},
        current_defrost_minutes=lambda: 0.0,
        completed_cycle_durations=[1800.0] * 20,
    )
    coordinator.energy_statistics = SimpleNamespace(
        total_electrical_kwh=12.5,
        total_thermal_kwh=30.0,
        today_electrical_kwh=1.0,
        today_thermal_kwh=2.0,
        month_electrical_kwh=5.0,
        month_thermal_kwh=10.0,
    )
    coordinator.unsupported_registers = {"firmware_version"}
    versions = RuntimeVersions("0.17.2-b1", "2.1.2", "4.12.1", "0.6.2")

    report = build_service_report(coordinator, versions)

    assert report["versions"]["idm_heatpump_api"] == "2.1.2"
    assert report["communication"]["total_failures"] == 4
    assert report["operation"]["compressor_starts_last_24_hours"] == 10
    assert report["operation"]["alarm_starts_last_7_days"] == 3
    assert report["energy_kwh"]["total_electrical_kwh"] == 12.5
    assert report["temperatures_c"]["outdoor_temp"] is None
    assert report["temperatures_c"]["hp_flow_temp"] == 35.5
    assert report["fault_register_readings"]["hp_sum_alarm"] is True
    assert "health_communication" in report["active_health_checks"]
    assert "private.example" not in str(report)
    assert "secret" not in str(report)
    assert report["prediction"] is False
    coordinator.async_write_register.assert_not_called()


def test_installer_report_handles_unavailable_analysis_and_bad_values() -> None:
    coordinator = MagicMock()
    coordinator.data = {"hp_flow_temp": "unknown", "dhw_temp_top": float("nan")}
    coordinator.operation_analysis = None
    coordinator.energy_statistics = None
    coordinator.poll_statistics = SimpleNamespace(
        last_success=None, consecutive_failures=0, total_polls=0, total_failures=0
    )
    coordinator.unsupported_registers = set()

    report = build_service_report(coordinator, RuntimeVersions("0", "unknown", "unknown", "unknown"))

    assert report["operation"] == {}
    assert report["energy_kwh"] == {}
    assert report["temperatures_c"] == {"hp_flow_temp": None, "dhw_temp_top": None}
