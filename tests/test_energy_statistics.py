"""Tests for persistent IDM energy integration."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from custom_components.idm_heatpump.energy_statistics import EnergyStatistics


def test_snapshot_integration_and_cop():
    stats = EnergyStatistics(SimpleNamespace(), "entry", 30)
    start = datetime(2026, 1, 1, tzinfo=UTC)
    stats.process_snapshot(
        {"power_consumption_hp": 2.0, "thermal_power_flow_sensor": 6.0},
        now=start,
    )
    stats.process_snapshot(
        {"power_consumption_hp": 2.0, "thermal_power_flow_sensor": 6.0},
        now=start + timedelta(minutes=1),
    )

    assert stats.total_electrical_kwh == 2.0 / 60.0
    assert stats.total_thermal_kwh == 6.0 / 60.0
    assert stats.total_cop == 3.0
    assert stats.today_cop == 3.0


def test_invalid_sample_breaks_interval_instead_of_inventing_energy():
    stats = EnergyStatistics(SimpleNamespace(), "entry", 30)
    start = datetime(2026, 1, 1, tzinfo=UTC)
    stats.process_snapshot({"power_consumption_hp": 1.0, "thermal_power_flow_sensor": 3.0}, now=start)
    stats.process_snapshot({"power_consumption_hp": -1.0, "thermal_power_flow_sensor": 3.0}, now=start + timedelta(minutes=1))
    stats.process_snapshot({"power_consumption_hp": 1.0, "thermal_power_flow_sensor": 3.0}, now=start + timedelta(minutes=2))

    assert stats.total_electrical_kwh == 0.0
    assert stats.total_thermal_kwh == 0.0
