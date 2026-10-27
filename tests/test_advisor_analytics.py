"""Tests for the persistent advisor analytics (baselines, COP map, building model)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from custom_components.idm_heatpump import advisor_analytics
from custom_components.idm_heatpump.advisor_analytics import (
    AdvisorAnalytics,
    _mean_absolute_deviation,
    _median,
)

# Anchored to the real clock so the tests never decay: observation stages
# and status entities compare ``first_observed`` against ``datetime.now``,
# and a fixed past date flips those assertions one day after it is written.
T0 = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)


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


def test_metric_today_samples_counts_even_without_baseline() -> None:
    analytics = _analytics()
    assert analytics.metric_today_samples("heat_sink_flow_rate:heating", T0) == 0
    analytics.observe_metric("heat_sink_flow_rate:heating", 22.0, T0)
    analytics.observe_metric("heat_sink_flow_rate:heating", 24.0, T0)
    # No three prior days yet, so metric_baseline returns None — the sample
    # count is still what tells the engine which demand reason dominates.
    assert analytics.metric_baseline("heat_sink_flow_rate:heating", T0) is None
    assert analytics.metric_today_samples("heat_sink_flow_rate:heating", T0) == 2


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


def test_baseline_z_score_scales_by_mad() -> None:
    analytics = _analytics()
    # Prior days vary a little around a median of 10.0 with MAD 0.05.
    for offset, value in ((4, 9.925), (3, 10.0), (2, 10.075)):
        analytics.observe_metric("heat_sink_flow_rate", value, _day(offset))
    analytics.observe_metric("heat_sink_flow_rate", 9.85, T0)
    baseline = analytics.metric_baseline("heat_sink_flow_rate", T0)
    assert baseline is not None
    assert baseline.mad == 0.05
    assert baseline.z_score == -3.0  # (9.85 - 10.0) / 0.05


def test_baseline_z_score_falls_back_on_flat_baseline() -> None:
    analytics = _analytics()
    for offset in (4, 3, 2):
        analytics.observe_metric("heat_sink_flow_rate", 20.0, _day(offset))
    analytics.observe_metric("heat_sink_flow_rate", 18.0, T0)
    baseline = analytics.metric_baseline("heat_sink_flow_rate", T0)
    assert baseline is not None
    assert baseline.mad == 0.0
    # A perfectly flat baseline uses 5 % of the median as the scale.
    assert baseline.z_score == -2.0  # (18 - 20) / (20 * 0.05)


def test_metric_baseline_conditions_on_outdoor() -> None:
    analytics = _analytics()
    for offset in (4, 3, 2):
        analytics.observe_metric("compressor_starts", 8.0, _day(offset), mode="max", outdoor=10.0)
    analytics.observe_metric("compressor_starts", 30.0, _day(1), mode="max", outdoor=-5.0)
    # Mild today: the cold day is outside the weather window and must not count.
    analytics.observe_metric("compressor_starts", 8.0, T0, mode="max", outdoor=10.0)
    conditioned = analytics.metric_baseline("compressor_starts", T0, condition_outdoor=True)
    assert conditioned is not None
    assert conditioned.days == 3
    assert conditioned.median == 8.0


def test_metric_baseline_stays_silent_without_matching_weather() -> None:
    analytics = _analytics()
    for offset in (4, 3, 2):
        analytics.observe_metric("compressor_starts", 8.0, _day(offset), mode="max", outdoor=10.0)
    analytics.observe_metric("compressor_starts", 30.0, T0, mode="max", outdoor=-5.0)
    assert analytics.metric_baseline("compressor_starts", T0, condition_outdoor=True) is None
    # The unconditional baseline still sees the mild history.
    assert analytics.metric_baseline("compressor_starts", T0) is not None


def test_seasonal_baseline_matches_same_month_prior_year() -> None:
    analytics = _analytics()
    now = datetime(2026, 10, 27, tzinfo=UTC)
    # Same month last year at 20.0: the seasonal norm.
    for day in (24, 25, 26, 27):
        analytics.observe_metric("compressor_starts", 20.0, datetime(2025, 10, day, tzinfo=UTC), mode="max")
    # Enough recent days that the 30-day rolling window drops the old year.
    for offset in range(1, 36):
        analytics.observe_metric("compressor_starts", 8.0, now - timedelta(days=offset), mode="max")
    baseline = analytics.metric_baseline("compressor_starts", now)
    assert baseline is not None
    assert baseline.median == 8.0  # rolling window ignores the old year
    assert baseline.seasonal_days == 4
    assert baseline.seasonal_median == 20.0


def test_seasonal_baseline_ignores_wrong_month_and_current_year() -> None:
    analytics = _analytics()
    now = datetime(2026, 10, 27, tzinfo=UTC)
    for offset in (4, 3, 2):
        analytics.observe_metric("compressor_starts", 8.0, now - timedelta(days=offset), mode="max")
    # A prior-year day in a different month must not count as seasonal.
    analytics.observe_metric("compressor_starts", 99.0, datetime(2025, 9, 15, tzinfo=UTC), mode="max")
    baseline = analytics.metric_baseline("compressor_starts", now)
    assert baseline is not None
    assert baseline.seasonal_days == 0
    assert baseline.seasonal_median is None


def test_seasonal_z_score_and_normal_band() -> None:
    analytics = _analytics()
    now = datetime(2026, 10, 27, tzinfo=UTC)
    for day in (24, 25, 26, 27):
        analytics.observe_metric("compressor_starts", 20.0, datetime(2025, 10, day, tzinfo=UTC), mode="max")
    for offset in (4, 3, 2):
        analytics.observe_metric("compressor_starts", 8.0, now - timedelta(days=offset), mode="max")
    analytics.observe_metric("compressor_starts", 20.0, now, mode="max")  # today equals the seasonal norm
    baseline = analytics.metric_baseline("compressor_starts", now)
    assert baseline is not None
    assert baseline.seasonal_z_score == 0.0
    assert baseline.is_seasonal_normal is True


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


def test_cop_sample_rejects_implausible_cop_and_power() -> None:
    analytics = _analytics()
    # A COP of 20 (counter artefact) must not enter the map (#610).
    analytics.observe_cop_sample(5.0, 30.0, thermal_kw=20.0, electric_kw=1.0, hours=0.2)
    assert analytics.expected_cop(5.0, 30.0) is None
    # A 2 MW instantaneous draw is a corrupted counter, not a heat pump.
    analytics.observe_cop_sample(5.0, 30.0, thermal_kw=4.0, electric_kw=2000.0, hours=0.2)
    assert analytics.expected_cop(5.0, 30.0) is None


def test_observed_cop_window_excludes_old_days() -> None:
    analytics = _analytics()
    analytics.observe_cop_sample(5.0, 30.0, 4.8, 1.2, 0.2)
    assert analytics.observed_cop(days=7, now=T0) is not None
    assert analytics.observed_cop(days=7, now=T0 + timedelta(days=30)) is None


def test_observed_cop_splits_heating_and_dhw_domains() -> None:
    analytics = _analytics()
    # Heating: COP 4.0; DHW: COP 2.0; mixed mode feeds only the total.
    for _ in range(10):
        analytics.observe_cop_sample(5.0, 30.0, thermal_kw=4.0, electric_kw=1.0, hours=0.2, domain="heating")
        analytics.observe_cop_sample(5.0, 60.0, thermal_kw=2.0, electric_kw=1.0, hours=0.2, domain="dhw")
        analytics.observe_cop_sample(5.0, 45.0, thermal_kw=6.0, electric_kw=1.0, hours=0.2, domain="total")
    assert analytics.observed_cop(now=T0) == pytest.approx(4.0)  # all-mode: 12/3
    assert analytics.observed_cop(now=T0, domain="heating") == 4.0
    assert analytics.observed_cop(now=T0, domain="dhw") == 2.0


async def test_per_domain_cop_days_survive_the_round_trip() -> None:
    first = _analytics()
    first.observe_cop_sample(5.0, 30.0, 4.0, 1.0, 0.2, domain="heating")
    first.observe_cop_sample(5.0, 60.0, 2.0, 1.0, 0.2, domain="dhw")
    second = _analytics()
    second._store.data = first._serialize()
    await second.async_load()
    assert second.observed_cop(now=T0, domain="heating") == 4.0
    assert second.observed_cop(now=T0, domain="dhw") == 2.0


# ----------------------------------------------------------------------
# Building model
# ----------------------------------------------------------------------


def test_heat_loss_regression() -> None:
    analytics = _analytics()
    assert analytics.heat_loss_w_per_k is None
    for delta in range(1, 61):
        # Advancing timestamps: the fit needs effective observed hours, not
        # just raw sample counts (scan-interval samples are autocorrelated).
        analytics.observe_heating(float(delta), 0.2 * delta, T0 + timedelta(minutes=12 * delta))  # 200 W/K
    heat_loss = analytics.heat_loss_w_per_k
    assert heat_loss is not None
    assert abs(heat_loss - 200.0) < 5.0


def test_regression_without_effective_hours_stays_unlearned() -> None:
    analytics = _analytics()
    # Sixty samples at one instant carry no observed hours; one long evening
    # at a single operating point must not be enough evidence.
    for delta in range(1, 61):
        analytics.observe_heating(float(delta), 0.2 * delta, T0)
    assert analytics.heat_loss_w_per_k is None


def test_regression_decays_older_regimes() -> None:
    analytics = _analytics()
    for delta in range(1, 61):
        analytics.observe_heating(float(delta), 0.2 * delta, T0 + timedelta(minutes=12 * delta))  # 200 W/K
    # A regime change (e.g. the user applied a recommended curve change),
    # observed three half-lives later at 400 W/K.
    later = T0 + timedelta(days=100)
    for delta in range(1, 61):
        analytics.observe_heating(float(delta), 0.4 * delta, later + timedelta(minutes=12 * delta))
    heat_loss = analytics.heat_loss_w_per_k
    assert heat_loss is not None
    # The old regime keeps a decayed vote, not a permanent veto.
    assert heat_loss > 350.0


def test_heat_loss_rejects_invalid_samples() -> None:
    analytics = _analytics()
    analytics.observe_heating(float("nan"), 1.0)
    analytics.observe_heating(10.0, 0.0)
    assert analytics.heat_loss_w_per_k is None


def test_optimal_flow_regression_and_guards() -> None:
    analytics = _analytics()
    for outdoor in range(60):
        analytics.observe_flow_pair(float(outdoor), 40.0 - 0.5 * outdoor, T0 + timedelta(minutes=12 * outdoor))
    optimal = analytics.optimal_flow_temp(0.0)
    assert optimal is not None
    assert abs(optimal - 40.0) < 1.0
    # Clamped into the documented flow range.
    assert analytics.optimal_flow_temp(-40.0) == 60.0
    # Rising fits are not heating curves.
    rising = _analytics()
    for outdoor in range(60):
        rising.observe_flow_pair(float(outdoor), 20.0 + 0.4 * outdoor, T0 + timedelta(minutes=12 * outdoor))
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


def test_median_and_mad_helpers_handle_empty_input() -> None:
    assert _median([]) is None
    assert _mean_absolute_deviation([], 2.0) == 0.0
    assert _median([3.0, 1.0, 2.0]) == 2.0
    assert _median([1.0, 2.0, 3.0, 4.0]) == 2.5
    assert _mean_absolute_deviation([1.0, 3.0], 2.0) == 1.0


def test_optimal_flow_refuses_constant_outdoor_samples() -> None:
    """Enough samples but zero spread in x: the regression cannot identify a slope."""
    analytics = _analytics()
    for index in range(60):
        analytics.observe_flow_pair(5.0, 30.0, T0 + timedelta(minutes=12 * index))

    assert analytics.optimal_flow_temp(5.0) is None


def test_metric_baseline_survives_a_failing_median(monkeypatch) -> None:
    """Defensive guard: a median that cannot be computed yields no baseline."""
    analytics = _analytics()
    for offset in (3, 2, 1):
        analytics.observe_metric("heat_sink_flow_rate", 1.5, _day(offset))
    monkeypatch.setattr(advisor_analytics, "_median", lambda values: None)

    assert analytics.metric_baseline("heat_sink_flow_rate", T0) is None


def test_observed_cop_is_none_before_any_map_sample() -> None:
    assert _analytics().observed_cop(now=T0) is None


def test_rollover_prunes_the_cop_map_to_512_bins() -> None:
    analytics = _analytics()
    for index in range(520):
        analytics.observe_cop_sample(float(index * 2), 35.0, 4.8, 1.2, 0.1)
    # One clearly dominant bucket must survive the prune.
    for _ in range(10):
        analytics.observe_cop_sample(0.0, 35.0, 4.8, 1.2, 0.5)
    assert analytics.building_model["cop_buckets"] == 520

    # Any observation on a new day runs the rollover, which bounds the map.
    analytics.observe_metric("rollover_trigger", 1.0, T0)

    assert analytics.building_model["cop_buckets"] == 512
    assert "+0:+8" in analytics._cop_map


async def test_async_load_ignores_an_absent_payload() -> None:
    analytics = _analytics()
    analytics._store.data = None

    await analytics.async_load()

    assert analytics.building_model["cop_buckets"] == 0
    assert analytics.metric_baseline("heat_sink_flow_rate", T0) is None


async def test_async_save_persists_the_serialized_state() -> None:
    analytics = _analytics()
    analytics.observe_metric("heat_sink_flow_rate", 1.5, T0)
    analytics.observe_cooldown_episode(0.05, 4.0)

    await analytics.async_save()

    stored = analytics._store.data
    assert stored is not None
    assert stored["version"] == 1
    assert stored["daily"]["heat_sink_flow_rate"][T0.date().isoformat()] == [1.5, 1.0]
    assert stored["cooldown_count"] == 1
    assert stored["capacity_kwh_per_k"] == 4.0
    assert stored["last_day"] == T0.date().isoformat()


async def test_legacy_building_models_are_reset_without_losing_other_analytics() -> None:
    first = _analytics()
    first.observe_heating(16.0, 8.0)
    first.observe_flow_pair(5.0, 24.0)
    first.observe_cop_sample(5.0, 30.0, 4.8, 1.2, 0.2)
    first.observe_metric("heat_sink_flow_rate", 1.5, T0)
    first.observe_cooldown_episode(0.05, 4.0)
    legacy = first._serialize()
    legacy.pop("building_model_version")
    second = _analytics()
    second._store.data = legacy
    await second.async_load()
    assert second.building_model["heat_fit_samples"] == 0
    assert second.building_model["flow_curve_samples"] == 0
    assert second.thermal_inertia_kwh_per_k is None
    assert second._daily == first._daily
    assert second._cop_map == first._cop_map
    assert second._cop_days == first._cop_days
    assert second.building_model["cooldown_episodes"] == 1
    second.observe_heating(16.0, 4.0)
    second.observe_flow_pair(5.0, 30.0)
    third = _analytics()
    third._store.data = second._serialize()
    await third.async_load()
    assert third.building_model["heat_fit_samples"] == 1
    assert third.building_model["flow_curve_samples"] == 1


async def test_unweighted_legacy_regression_dicts_are_reset() -> None:
    """A v2 document (unweighted sufficient statistics) relearns, not mixes."""
    first = _analytics()
    legacy = {
        "version": 1,
        "building_model_version": 2,
        "heat_fit": {"n": 500.0, "sx": 1.0, "sy": 2.0, "sxx": 3.0, "sxy": 4.0},
        "flow_fit": {"n": 500.0, "sx": 1.0, "sy": 2.0, "sxx": 3.0, "sxy": 4.0},
    }
    first._store.data = legacy
    await first.async_load()
    assert first.building_model["heat_fit_samples"] == 0
    assert first.building_model["flow_curve_samples"] == 0
