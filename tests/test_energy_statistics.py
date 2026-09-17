"""Tests for persistent IDM energy integration."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from custom_components.idm_heatpump import energy_statistics as module
from custom_components.idm_heatpump.energy_statistics import EnergyStatistics
from custom_components.idm_heatpump.energy_statistics_entities import energy_statistics_entities


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
    stats.process_snapshot(
        {"power_consumption_hp": -1.0, "thermal_power_flow_sensor": 3.0}, now=start + timedelta(minutes=1)
    )
    stats.process_snapshot(
        {"power_consumption_hp": 1.0, "thermal_power_flow_sensor": 3.0}, now=start + timedelta(minutes=2)
    )

    assert stats.total_electrical_kwh == 0.0
    assert stats.total_thermal_kwh == 0.0


async def test_persisted_totals_are_validated_and_restored() -> None:
    stats = EnergyStatistics(SimpleNamespace(), "entry", 30)
    stats._store.data = {
        "total_electrical_kwh": 3.5,
        "total_thermal_kwh": "bad",
        "today_electrical_kwh": 1.0,
        "period_day": "2026-09-17",
        "period_month": "2026-09",
    }
    await stats.async_load()
    assert stats.total_electrical_kwh == 3.5
    assert stats.total_thermal_kwh == 0.0
    assert stats.today_electrical_kwh == 1.0
    assert stats._period_day == "2026-09-17"
    await stats.async_save()
    assert stats._store.data["total_electrical_kwh"] == 3.5

    stats._store.async_load = AsyncMock(side_effect=OSError("disk"))
    await stats.async_load()
    assert stats.total_electrical_kwh == 3.5


def test_periods_roll_over_and_costs_follow_energy() -> None:
    stats = EnergyStatistics(SimpleNamespace(), "entry", 30, price_per_kwh=0.4, co2_g_per_kwh=500)
    start = datetime(2026, 1, 31, 12, 0, tzinfo=UTC)
    stats.process_snapshot({"power_consumption_hp": 2, "thermal_power_flow_sensor": 4}, now=start)
    stats.process_snapshot(
        {"power_consumption_hp": 2, "thermal_power_flow_sensor": 4}, now=start + timedelta(minutes=1)
    )
    assert stats.total_cost > 0
    assert stats.total_co2_kg >= 0
    assert stats.today_cop == 2
    stats.process_snapshot({"power_consumption_hp": 2, "thermal_power_flow_sensor": 4}, now=start + timedelta(days=2))
    assert stats.today_electrical_kwh == 0
    assert stats.month_electrical_kwh == 0
    assert stats.month_cop is None


def test_dynamic_price_integrates_observed_tariffs_and_skips_invalid_prices() -> None:
    price = SimpleNamespace(state="20", attributes={"unit_of_measurement": "ct/kWh"})
    hass = SimpleNamespace(states=SimpleNamespace(get=lambda _: price))
    stats = EnergyStatistics(hass, "entry", 30, price_source="sensor.tariff")
    start = datetime(2026, 1, 1, tzinfo=UTC)
    sample = {"power_consumption_hp": 3, "thermal_power_flow_sensor": 6}
    stats.process_snapshot(sample, now=start)
    stats.process_snapshot(sample, now=start + timedelta(minutes=1))
    price.state = "0.40"
    price.attributes["unit_of_measurement"] = "EUR/kWh"
    stats.process_snapshot(sample, now=start + timedelta(minutes=2))
    assert round(stats.total_cost_eur, 3) == 0.03
    price.state = "unavailable"
    stats.process_snapshot(sample, now=start + timedelta(minutes=3))
    assert stats.unpriced_energy_kwh == 3 / 60
    assert round(stats.total_electrical_kwh, 3) == 0.15
    assert round(stats.total_cost_eur, 3) == 0.03
    price.state = "-1"
    assert stats._current_price() is None
    price.state = "6"
    assert stats._current_price() is None
    price.state = "0.5"
    price.attributes["unit_of_measurement"] = "W"
    assert stats._current_price() is None
    price.attributes["unit_of_measurement"] = "€/kWh"
    assert stats._current_price() == 0.5


async def test_previous_fixed_price_cost_is_migrated_once() -> None:
    stats = EnergyStatistics(SimpleNamespace(), "entry", 30, price_per_kwh=0.4)
    stats._store.data = {"total_electrical_kwh": 10.0, "today_electrical_kwh": 2.0}
    await stats.async_load()
    assert stats.total_cost == 4.0
    assert stats.today_cost == 0.8
    await stats.async_save()
    again = EnergyStatistics(SimpleNamespace(), "entry", 30, price_per_kwh=0.6)
    again._store.data = stats._store.data
    await again.async_load()
    assert again.total_cost == 4.0


def test_pv_self_consumption_is_capped_and_bad_sources_ignored() -> None:
    state = SimpleNamespace(state="3000", attributes={"unit_of_measurement": "W"})
    hass = SimpleNamespace(states=SimpleNamespace(get=lambda _: state))
    stats = EnergyStatistics(hass, "entry", 30, pv_source="sensor.pv")
    start = datetime(2026, 1, 1, tzinfo=UTC)
    stats.process_snapshot({"power_consumption_hp": 1, "thermal_power_flow_sensor": 2}, now=start)
    stats.process_snapshot(
        {"power_consumption_hp": 1, "thermal_power_flow_sensor": 2}, now=start + timedelta(minutes=1)
    )
    assert stats.total_pv_self_consumed_kwh == stats.total_electrical_kwh
    assert stats.today_pv_self_consumed_kwh == stats.total_electrical_kwh
    state.state = "unknown"
    assert stats._pv_power_kw() is None
    state.state = -1
    assert stats._pv_power_kw() is None
    state.state = 1
    state.attributes["unit_of_measurement"] = "bad"
    assert stats._pv_power_kw() is None
    state.attributes["unit_of_measurement"] = "MW"
    assert stats._pv_power_kw() == 1000
    assert module._power(True) is None
    assert module._power("bad") is None
    assert stats._ratio(0, 1) is None


def test_energy_entities_require_sources_and_publish_all_metrics() -> None:
    coordinator = MagicMock()
    coordinator.config_entry.entry_id = "entry"
    coordinator.last_update_success = True
    coordinator.energy_statistics = None
    coordinator.data = {}
    assert energy_statistics_entities(coordinator) == []

    coordinator.energy_statistics = EnergyStatistics(SimpleNamespace(), "entry", 30)
    assert energy_statistics_entities(coordinator) == []
    coordinator.data = {"power_consumption_hp": 1, "thermal_power_flow_sensor": 3}
    entities = energy_statistics_entities(coordinator)
    assert len(entities) == 17
    assert entities[0].native_value == 0
    assert entities[0].available is True
    assert entities[6].native_value is None
    assert entities[6].available is False
    assert entities[0].entity_description.native_unit_of_measurement == "kWh"
    assert entities[9].entity_description.native_unit_of_measurement == "€"
