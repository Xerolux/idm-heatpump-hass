"""Tests for the persistent advisor analytics (baselines, COP map, building model)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from custom_components.idm_heatpump.advisor_analytics import AdvisorAnalytics

# Anchored to the real clock so the tests never decay: observation stages
# and status entities compare ``first_observed`` against ``datetime.now``,
# and a fixed past date flips those assertions one day after it is written.
T0 = datetime.now(UTC).replace(microsecond=0)


def _analytics(mock_hass=None) -> AdvisorAnalytics:
    return AdvisorAnalytics(mock_hass if mock_hass is not None else MagicMock(), "entry1")


def _day(offset: int) -> datetime:
    return T0 - timedelta(days=offset)


# ----------------------------------------------------------------------
# Daily metric baselines
# ----------------------------------------------------------------------


def test_metric_baseline_needs_three_prior_days() -> None:
    analytics = _analytics()
    assert analytics.metric_baseline("heat_sink_flow_rate", T0) is None
    analytics.observe_metric("heat_sink_flow_rate", 1.5, _day(2))
    analytics.observe_metric("heat_sink_flow_rate", 1.5, _day(1))
    assert analytics.metric_baseline("heat_sink_flow_rate", T0) is None
    analytics.observe_metric("heat_sink_flow_rate", 1.5, _day(3))
    analytics.observe_metric("heat_sink_flow_rate", 1.0, T0)
    baseline = analytics.metric_baseline("heat_sink_flow_rate", T0)
    assert baseline is not None
    assert baseline.days == 3
    assert baseline.median == 1.5
    assert baseline.today == 1.0
    assert baseline.deviation_percent == -33.3


def test_metric_baseline_ignores_invalid_samples_and_counts_mean() -> None:
    analytics = _analytics()
    for offset in (4, 3, 2):
        analytics.observe_metric("hp_temperature_spread", 4.0, _day(offset))
        analytics.observe_metric("hp_temperature_spread", 6.0, _day(offset))
    baseline = analytics.metric_baseline("hp_temperature_spread", T0)
    assert baseline is not None
    assert baseline.median == 5.0
    assert baseline.mad == 0.0  # MAD is across daily means; equal days have no spread
    assert baseline.today is None  # nothing observed today
    assert baseline.deviation_percent is None
    analytics.observe_metric("hp_temperature_spread", None, T0)
    analytics.observe_metric("hp_temperature_spread", float("nan"), T0)
    assert analytics.metric_baseline("hp_temperature_spread", T0).today is None


def test_metric_max_mode_keeps_running_counter_maximum() -> None:
    analytics = _analytics()
    for offset in (3, 2, 1):
        analytics.observe_metric("compressor_starts", 8, _day(offset), mode="max")
    analytics.observe_metric("compressor_starts", 5, T0, mode="max")
    analytics.observe_metric("compressor_starts", 19, T0 + timedelta(hours=12), mode="max")
    baseline = analytics.metric_baseline("compressor_starts", T0 + timedelta(hours=13))
    assert baseline is not None
    assert baseline.today == 19
    assert baseline.deviation_percent == 137.5


# ----------------------------------------------------------------------
# COP map
# ----------------------------------------------------------------------


def test_cop_map_learn_expected_and_observed() -> None:
    analytics = _analytics()
    assert analytics.expected_cop(5.0, 30.0) is None
    for _ in range(10):
        analytics.observe_cop_sample(5.0, 30.0, thermal_kw=4.8, electric_kw=1.2, hours=0.2)
    expected = analytics.expected_cop(5.0, 30.0)
    assert expected is not None
    assert expected.cop == 4.0
    assert expected.hours == 2.0
    # A far-away operating point is not covered by the neighbourhood.
    assert analytics.expected_cop(-15.0, 55.0) is None
    observed = analytics.observed_cop(now=T0)
    assert observed == 4.0


def test_cop_sample_rejects_invalid_input() -> None:
    analytics = _analytics()
    analytics.observe_cop_sample(None, 30.0, 4.0, 1.0, 0.2)
    analytics.observe_cop_sample(5.0, 30.0, 0.0, 1.0, 0.2)
    analytics.observe_cop_sample(5.0, 30.0, 4.0, 1.0, 0.0)
    assert analytics.expected_cop(5.0, 30.0) is None


def test_observed_cop_window_excludes_old_days() -> None:
    analytics = _analytics()
    analytics.observe_cop_sample(5.0, 30.0, 4.8, 1.2, 0.2)
    assert analytics.observed_cop(days=7, now=T0) is not None
    assert analytics.observed_cop(days=7, now=T0 + timedelta(days=30)) is None


# ----------------------------------------------------------------------
# Building model
# ----------------------------------------------------------------------


def test_heat_loss_regression() -> None:
    analytics = _analytics()
    assert analytics.heat_loss_w_per_k is None
    for delta in range(1, 61):
        analytics.observe_heating(float(delta), 0.2 * delta)  # 200 W/K
    heat_loss = analytics.heat_loss_w_per_k
    assert heat_loss is not None
    assert abs(heat_loss - 200.0) < 5.0


def test_heat_loss_rejects_invalid_samples() -> None:
    analytics = _analytics()
    analytics.observe_heating(float("nan"), 1.0)
    analytics.observe_heating(10.0, 0.0)
    assert analytics.heat_loss_w_per_k is None


def test_optimal_flow_regression_and_guards() -> None:
    analytics = _analytics()
    for outdoor in range(60):
        analytics.observe_flow_pair(float(outdoor), 40.0 - 0.5 * outdoor)
    optimal = analytics.optimal_flow_temp(0.0)
    assert optimal is not None
    assert abs(optimal - 40.0) < 1.0
    # Clamped into the documented flow range.
    assert analytics.optimal_flow_temp(-40.0) == 60.0
    # Rising fits are not heating curves.
    rising = _analytics()
    for outdoor in range(60):
        rising.observe_flow_pair(float(outdoor), 20.0 + 0.4 * outdoor)
    assert rising.optimal_flow_temp(0.0) is None


def test_cooldown_episodes_build_thermal_inertia() -> None:
    analytics = _analytics()
    assert analytics.thermal_inertia_kwh_per_k is None
    analytics.observe_cooldown_episode(0.05, 4.0)
    analytics.observe_cooldown_episode(0.06, 5.0)
    assert analytics.thermal_inertia_kwh_per_k is None  # needs three episodes
    analytics.observe_cooldown_episode(0.04, None)
    inertia = analytics.thermal_inertia_kwh_per_k
    assert inertia is not None
    assert 4.0 <= inertia <= 5.0


def test_cooldown_episode_rejects_implausible_rates() -> None:
    analytics = _analytics()
    analytics.observe_cooldown_episode(0.0, 5.0)
    analytics.observe_cooldown_episode(1.5, 5.0)
    assert analytics.building_model["cooldown_episodes"] == 0


# ----------------------------------------------------------------------
# Persistence
# ----------------------------------------------------------------------


async def test_persistence_round_trip(mock_hass=None) -> None:
    hass = mock_hass if mock_hass is not None else MagicMock()
    first = AdvisorAnalytics(hass, "entry1")
    for offset in (3, 2, 1):
        first.observe_metric("heat_sink_flow_rate", 1.5, _day(offset))
    for _ in range(6):
        first.observe_cop_sample(5.0, 30.0, 4.8, 1.2, 0.2)
    first.observe_heating(10.0, 2.0)
    first.observe_cooldown_episode(0.05, 4.0)

    second = AdvisorAnalytics(hass, "entry1")
    second._store.data = first._serialize()
    await second.async_load()
    assert second.metric_baseline("heat_sink_flow_rate", T0) is not None
    assert second.expected_cop(5.0, 30.0) is not None
    assert second.building_model["cooldown_episodes"] == 1
    assert second.observed_cop(now=T0) == 4.0


async def test_async_load_survives_malformed_data() -> None:
    analytics = _analytics()
    analytics._store.data = {"daily": "nope", "cop_map": [1, 2], "heat_fit": {"n": "x"}}
    await analytics.async_load()
    assert analytics.metric_baseline("heat_sink_flow_rate", T0) is None
    assert analytics.expected_cop(5.0, 30.0) is None


async def test_async_load_survives_store_error() -> None:
    analytics = _analytics()
    analytics._store.async_load = MagicMock(side_effect=OSError("disk"))
    await analytics.async_load()
    assert analytics.building_model["cop_buckets"] == 0


def test_daily_history_is_bounded() -> None:
    analytics = _analytics()
    for offset in range(2, 40):
        analytics.observe_metric("heat_sink_flow_rate", 1.5, _day(offset))
    analytics.observe_metric("heat_sink_flow_rate", 1.5, T0)
    baseline = analytics.metric_baseline("heat_sink_flow_rate", T0)
    assert baseline is not None
    assert baseline.days <= 30
