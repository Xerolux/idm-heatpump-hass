"""Persistent advisor analytics: rolling baselines, COP map, building model.

Phases 3–5 of the predictive advisor roadmap. Everything here is passive
measurement: daily aggregates for anomaly baselines, an outdoor/flow COP map
and simple documented regressions for the building model. No value in this
module influences the heat pump; producers read from it and recommend.
"""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Final

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN
from .cop_plausibility import cop_interval_is_plausible

_LOGGER = logging.getLogger(__name__)

_STORAGE_VERSION: Final = 1
# 3: weighted and decayed regression statistics (they are not comparable
# with the unweighted sums of earlier versions; the fits relearn once).
_BUILDING_MODEL_VERSION: Final = 3
_STORAGE_SAVE_DELAY: Final = 30.0
# Aggregates arrive with every coordinator poll; persisting at that cadence
# writes the store roughly every scan interval for a few changed counters.
_SAVE_THROTTLE: Final = 300.0
_BASELINE_DAYS: Final = 30
_BASELINE_MIN_DAYS: Final = 3
# Half-width of the outdoor-temperature window (in kelvin) used to compare a
# day's metric only against prior days with similar weather, so a cold snap
# does not masquerade as an anomaly on weather-driven metrics.
_CONDITION_BIN_HALF: Final = 2.5
# Keep daily aggregates long enough to compare against the same calendar month
# of the previous year (seasonal baseline, #611); a rolling window is far too
# short to tell a seasonal transition apart from real drift.
_SEASONAL_RETENTION_DAYS: Final = 400
# A value inside this many seasonal-MADs of the same-month prior-year median is
# seasonally normal and must not fire a rolling-window anomaly.
_SEASONAL_BAND_Z: Final = 2.0
_COP_BIN_OUTDOOR: Final = 2.0
_COP_BIN_FLOW: Final = 4.0
_COP_NEIGHBOURHOOD: Final = 1  # 3x3 bins around the query point
_COP_MIN_HOURS: Final = 1.0
_COP_OBSERVED_DAYS: Final = 7
_REGRESSION_MIN_SAMPLES: Final = 60
# Effective observed hours required before a fit is trusted; one long
# evening at a single operating point must not be enough (the samples are
# autocorrelated at the scan interval).
_REGRESSION_MIN_HOURS: Final = 12.0
# Old samples lose half their weight per half-life so the models follow
# building changes (renovation, an applied heating-curve change) instead of
# averaging over the plant's whole history.
_REGRESSION_HALF_LIFE: Final = timedelta(days=30)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _day_key(now: datetime) -> str:
    return now.astimezone(UTC).date().isoformat()


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    numeric = float(value)
    return numeric if math.isfinite(numeric) else None


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def _mean_absolute_deviation(values: list[float], median: float) -> float:
    if not values:
        return 0.0
    return sum(abs(value - median) for value in values) / len(values)


@dataclass(frozen=True)
class DailyBaseline:
    """Baseline of one metric: median of prior full days vs. today's mean."""

    key: str
    days: int
    median: float
    mad: float
    today: float | None
    seasonal_days: int = 0
    seasonal_median: float | None = None
    seasonal_mad: float = 0.0

    @property
    def deviation_percent(self) -> float | None:
        """Today's relative deviation from the baseline median."""
        if self.today is None or self.median == 0:
            return None
        return round((self.today - self.median) / abs(self.median) * 100.0, 1)

    @property
    def z_score(self) -> float | None:
        """Today's deviation in units of the prior days' mean absolute deviation.

        Robust, self-calibrating alternative to the fixed percentage/Kelvin
        thresholds: a plant with naturally high variance only alarms on real
        outliers, while a very repeatable plant still reports subtle drift.
        A perfectly flat baseline (``mad == 0``) is rare and means the metric
        is extremely repeatable; a small fraction of the median then stands in
        as the scale so genuine drift stays measurable.
        """
        if self.today is None or self.median is None:
            return None
        scale = self.mad
        if scale <= 0:
            scale = abs(self.median) * 0.05
            if scale <= 0:
                return None
        return round((self.today - self.median) / scale, 2)

    @property
    def seasonal_z_score(self) -> float | None:
        """Today's deviation from the same-month prior-year median in MAD units.

        ``None`` while the seasonal baseline is not established (fewer than
        ``_BASELINE_MIN_DAYS`` same-month prior-year days), in which case the
        rolling baseline stays the only reference.
        """
        if self.today is None or self.seasonal_median is None or self.seasonal_days < _BASELINE_MIN_DAYS:
            return None
        scale = self.seasonal_mad
        if scale <= 0:
            scale = abs(self.seasonal_median) * 0.05
            if scale <= 0:
                return None
        return round((self.today - self.seasonal_median) / scale, 2)

    @property
    def is_seasonal_normal(self) -> bool:
        """Whether today sits within the same-month prior-year normal band.

        False whenever the seasonal baseline is not established, so a missing
        same-month history never suppresses a rolling-window anomaly.
        """
        z = self.seasonal_z_score
        return z is not None and abs(z) <= _SEASONAL_BAND_Z


@dataclass(frozen=True)
class ExpectedCop:
    """Expected COP for one operating point from the learned map."""

    cop: float
    hours: float
    buckets: int


@dataclass(frozen=True)
class LinearFit:
    """Ordinary least squares fit with the sample count behind it."""

    slope: float
    intercept: float
    samples: int


@dataclass
class _OnlineRegression:
    """Sufficient statistics of a weighted, exponentially decayed OLS fit.

    ``sx``…``sxy`` are decayed weighted sums, ``w`` their total weight and
    ``n`` the raw sample count. Samples arrive at the scan interval and are
    strongly autocorrelated, so each sample carries the hours it represents
    as its weight, and every observe step first shrinks the accumulated
    statistics by a half-life decay so the fit follows building changes
    instead of averaging over the plant's whole history.
    """

    n: int = 0
    w: float = 0.0
    sx: float = 0.0
    sy: float = 0.0
    sxx: float = 0.0
    sxy: float = 0.0

    def observe(self, x: float, y: float, *, weight: float = 1.0, decay: float = 1.0) -> _OnlineRegression:
        if weight <= 0:
            return self
        return _OnlineRegression(
            n=self.n + 1,
            w=self.w * decay + weight,
            sx=self.sx * decay + weight * x,
            sy=self.sy * decay + weight * y,
            sxx=self.sxx * decay + weight * x * x,
            sxy=self.sxy * decay + weight * x * y,
        )

    def fit(self) -> LinearFit | None:
        """Slope/intercept once enough independent samples accumulated."""
        if self.n < _REGRESSION_MIN_SAMPLES or self.w < _REGRESSION_MIN_HOURS:
            return None
        denominator = self.w * self.sxx - self.sx * self.sx
        if abs(denominator) < 1e-9:
            return None
        slope = (self.w * self.sxy - self.sx * self.sy) / denominator
        intercept = (self.sy - slope * self.sx) / self.w
        return LinearFit(slope=slope, intercept=intercept, samples=self.n)

    def to_dict(self) -> dict[str, float]:
        return {
            "n": self.n,
            "w": self.w,
            "sx": self.sx,
            "sy": self.sy,
            "sxx": self.sxx,
            "sxy": self.sxy,
        }

    @classmethod
    def from_dict(cls, value: Any) -> _OnlineRegression:
        if not isinstance(value, dict):
            return cls()
        stats = cls()
        for name in ("n", "w", "sx", "sy", "sxx", "sxy"):
            numeric = _number(value.get(name))
            if numeric is None or numeric < 0:
                return cls()
            setattr(stats, name, numeric)
        if stats.n == 0:
            return cls()
        return stats


def _cop_bin_key(outdoor: float, flow: float) -> str:
    return f"{math.floor(outdoor / _COP_BIN_OUTDOOR):+d}:{math.floor(flow / _COP_BIN_FLOW):+d}"


class AdvisorAnalytics:
    """Owns every long-lived statistical model the advisor producers use."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store: Store[dict[str, Any]] = Store(
            hass,
            _STORAGE_VERSION,
            f"{DOMAIN}.advisor_analytics.{entry_id}",
        )
        # metric/circuit -> day -> [sum, count] of usable sample values
        self._daily: dict[str, dict[str, list[float]]] = {}
        # day -> [sum, count] of observed outdoor temperatures, used to match
        # weather-sensitive metrics against prior days of similar weather.
        self._day_outdoor: dict[str, list[float]] = {}
        # cop bin -> [electric_kwh, thermal_kwh, hours]
        self._cop_map: dict[str, list[float]] = {}
        # day -> [electric_kwh, thermal_kwh] for the observed-COP window
        self._cop_days: dict[str, list[float]] = {}
        # Per-domain day totals: pure space heating and pure DHW charging
        # have different COPs; mixing them hides both (discussion #540).
        self._cop_days_heating: dict[str, list[float]] = {}
        self._cop_days_dhw: dict[str, list[float]] = {}
        self._heat_fit = _OnlineRegression()
        self._flow_fit = _OnlineRegression()
        self._heat_fit_at: datetime | None = None
        self._flow_fit_at: datetime | None = None
        self._cooldown_count = 0
        self._cooldown_rate_1_per_h: float | None = None
        self._capacity_kwh_per_k: float | None = None
        self._last_day: str | None = None
        self._last_save_schedule: float | None = None

    # ------------------------------------------------------------------
    # Daily metric aggregates and baselines
    # ------------------------------------------------------------------

    def observe_metric(
        self,
        key: str,
        value: float | None,
        now: datetime | None = None,
        *,
        mode: str = "mean",
        outdoor: float | None = None,
    ) -> None:
        """Aggregate one usable sample of a metric into its daily value.

        ``mode="mean"`` keeps the day's mean (flow rate, spread); ``max``
        keeps the day's maximum for monotonic running counters (compressor
        starts, DHW charge minutes), where a mean over partial counts would
        understate the day. ``outdoor`` optionally records the matching
        outdoor temperature so weather-sensitive baselines can later be
        compared like-for-like.
        """
        if value is None or not math.isfinite(value):
            return
        current = now or _utcnow()
        self._rollover(current)
        day = self._daily.setdefault(key, {}).setdefault(_day_key(current), [0.0, 0.0])
        if mode == "max":
            day[0] = max(day[0], value)
            day[1] = 1.0
        else:
            day[0] += value
            day[1] += 1.0
        if outdoor is not None and math.isfinite(outdoor):
            outdoor_day = self._day_outdoor.setdefault(_day_key(current), [0.0, 0.0])
            outdoor_day[0] += outdoor
            outdoor_day[1] += 1.0
        self._schedule_save()

    def metric_today_samples(self, key: str, now: datetime | None = None) -> int:
        """Today's usable sample count for one metric key.

        The engine uses this to tell which demand reason dominates the day
        before picking the like-for-like baseline (#607); the count alone is
        available even when ``metric_baseline`` returns ``None`` because the
        prior-days floor is not reached yet.
        """
        current = now or _utcnow()
        _total, count = self._daily.get(key, {}).get(_day_key(current), (0.0, 0.0))
        return int(count)

    def _day_outdoor_mean(self, day: str) -> float | None:
        total, count = self._day_outdoor.get(day, (0.0, 0.0))
        return total / count if count > 0 else None

    def metric_baseline(
        self,
        key: str,
        now: datetime | None = None,
        *,
        condition_outdoor: bool = False,
    ) -> DailyBaseline | None:
        """Compare today's mean against the median of the prior days.

        ``condition_outdoor=True`` restricts the prior days to those whose
        mean outdoor temperature sat within ``_CONDITION_BIN_HALF`` kelvin of
        today's, so a cold snap cannot masquerade as a weather-driven anomaly;
        without enough matching days it stays silent instead of comparing
        across weather regimes.
        """
        current = now or _utcnow()
        days = self._daily.get(key, {})
        today_key = _day_key(current)
        today_outdoor = self._day_outdoor_mean(today_key) if condition_outdoor else None
        prior = [
            total / count
            for day, (total, count) in sorted(days.items())
            if day < today_key
            and count > 0
            and (
                not condition_outdoor
                or today_outdoor is None
                or (
                    (prior_outdoor := self._day_outdoor_mean(day)) is not None
                    and abs(prior_outdoor - today_outdoor) <= _CONDITION_BIN_HALF
                )
            )
        ]
        prior = prior[-_BASELINE_DAYS:]
        if len(prior) < _BASELINE_MIN_DAYS:
            return None
        median = _median(prior)
        if median is None:
            return None
        today_total, today_count = days.get(today_key, (0.0, 0.0))
        today = today_total / today_count if today_count else None
        seasonal = self._seasonal_baseline(days, today_key)
        return DailyBaseline(
            key=key,
            days=len(prior),
            median=round(median, 3),
            mad=round(_mean_absolute_deviation(prior, median), 3),
            today=round(today, 3) if today is not None else None,
            seasonal_days=seasonal[0],
            seasonal_median=seasonal[1],
            seasonal_mad=seasonal[2],
        )

    @staticmethod
    def _seasonal_baseline(days: dict[str, list[float]], today_key: str) -> tuple[int, float | None, float]:
        """Same-calendar-month prior-year median/MAD for one metric (#611).

        The rolling window already contains the current month's recent days, so
        the seasonal reference is the same month of *previous* years: the value
        that tells a seasonal transition apart from real drift. Returns
        ``(days, median, mad)``; ``median`` is None until enough same-month
        prior-year days exist.
        """
        today_month = today_key[5:7]
        today_year = today_key[0:4]
        prior = [
            total / count
            for day, (total, count) in sorted(days.items())
            if day < today_key and day[5:7] == today_month and day[0:4] != today_year and count > 0
        ]
        if len(prior) < _BASELINE_MIN_DAYS:
            return 0, None, 0.0
        median = _median(prior)
        if median is None:
            return 0, None, 0.0
        return len(prior), round(median, 3), round(_mean_absolute_deviation(prior, median), 3)

    # ------------------------------------------------------------------
    # COP map (phase 4)
    # ------------------------------------------------------------------

    def observe_cop_sample(
        self,
        outdoor: float | None,
        flow: float | None,
        thermal_kw: float,
        electric_kw: float,
        hours: float,
        *,
        domain: str = "total",
    ) -> None:
        """Integrate one operating interval into the COP statistics.

        ``domain`` additionally files the interval under ``"heating"`` or
        ``"dhw"`` when the operating mode was unambiguous (pure space
        heating / pure hot-water charging); mixed, defrost, cooling and
        unknown modes only feed the all-mode totals.
        """
        if outdoor is None or flow is None or hours <= 0:
            return
        # Shared plausibility guard (#610): the COP ratio and implied power
        # are validated by the same predicate ai_learning uses, so a spurious
        # counter spike cannot bias one map while the other rejects it.
        if not cop_interval_is_plausible(thermal_kw, electric_kw, electric_kw=electric_kw):
            return
        hours = min(hours, 0.5)
        key = _cop_bin_key(outdoor, flow)
        electric, thermal, mapped = self._cop_map.get(key, [0.0, 0.0, 0.0])
        self._cop_map[key] = [electric + electric_kw * hours, thermal + thermal_kw * hours, mapped + hours]
        day = _day_key(_utcnow())
        totals = self._cop_days.setdefault(day, [0.0, 0.0])
        totals[0] += electric_kw * hours
        totals[1] += thermal_kw * hours
        if domain in ("heating", "dhw"):
            domain_days = (self._cop_days_heating if domain == "heating" else self._cop_days_dhw).setdefault(
                day, [0.0, 0.0]
            )
            domain_days[0] += electric_kw * hours
            domain_days[1] += thermal_kw * hours
        self._schedule_save()

    def expected_cop(self, outdoor: float, flow: float) -> ExpectedCop | None:
        """Expected COP from the 3x3 bin neighbourhood, None while unlearned."""
        outdoor_bin = math.floor(outdoor / _COP_BIN_OUTDOOR)
        flow_bin = math.floor(flow / _COP_BIN_FLOW)
        thermal = 0.0
        electric = 0.0
        hours = 0.0
        buckets = 0
        for o in range(outdoor_bin - _COP_NEIGHBOURHOOD, outdoor_bin + _COP_NEIGHBOURHOOD + 1):
            for f in range(flow_bin - _COP_NEIGHBOURHOOD, flow_bin + _COP_NEIGHBOURHOOD + 1):
                entry = self._cop_map.get(f"{o:+d}:{f:+d}")
                if not entry or entry[2] < 0.25 or entry[0] <= 0:
                    continue
                thermal += entry[1]
                electric += entry[0]
                hours += entry[2]
                buckets += 1
        if buckets == 0 or hours < _COP_MIN_HOURS:
            return None
        return ExpectedCop(cop=round(thermal / electric, 2), hours=round(hours, 2), buckets=buckets)

    def observed_cop(
        self, days: int = _COP_OBSERVED_DAYS, now: datetime | None = None, *, domain: str = "total"
    ) -> float | None:
        """COP actually observed over the last N days of map samples.

        ``domain="heating"``/``"dhw"`` evaluates only the pure-mode intervals
        of that domain; the all-mode total stays available as ``"total"``.
        """
        source = self._cop_days
        if domain == "heating":
            source = self._cop_days_heating
        elif domain == "dhw":
            source = self._cop_days_dhw
        if not source:
            return None
        current = now or _utcnow()
        cutoff = (current - timedelta(days=days)).date().isoformat()
        electric = sum(total[0] for day, total in source.items() if day >= cutoff)
        thermal = sum(total[1] for day, total in source.items() if day >= cutoff)
        if electric <= 0 or thermal <= 0:
            return None
        return round(thermal / electric, 2)

    # ------------------------------------------------------------------
    # Building model (phase 5)
    # ------------------------------------------------------------------

    def observe_heating(self, indoor_outdoor_delta_k: float, thermal_kw: float, now: datetime | None = None) -> None:
        """Feed the heat-loss regression (thermal power vs. temperature delta).

        Each sample is weighted by the hours it represents (capped at half an
        hour so a polling gap cannot turn one point into hours of evidence)
        and the accumulated statistics decay with a 30-day half-life.
        """
        if not math.isfinite(indoor_outdoor_delta_k) or thermal_kw <= 0:
            return
        current = now or _utcnow()
        weight, decay = self._sample_weight_and_decay(self._heat_fit_at, current)
        self._heat_fit_at = current
        self._heat_fit = self._heat_fit.observe(indoor_outdoor_delta_k, thermal_kw, weight=weight, decay=decay)
        self._schedule_save()

    def _sample_weight_and_decay(self, previous_at: datetime | None, current: datetime) -> tuple[float, float]:
        """Interval hours as sample weight plus the decay since the last sample."""
        if previous_at is None:
            return 1.0, 1.0
        elapsed = (current - previous_at).total_seconds()
        if elapsed <= 0:
            return 0.0, 1.0
        hours = elapsed / 3600.0
        weight = min(hours, 0.5)
        decay = 0.5 ** (hours / (_REGRESSION_HALF_LIFE.total_seconds() / 3600.0))
        return weight, decay

    @property
    def heat_loss_w_per_k(self) -> float | None:
        """Building heat loss in W/K from the thermal regression slope."""
        fit = self._heat_fit.fit()
        if fit is None or fit.slope <= 0:
            return None
        return round(fit.slope * 1000.0, 1)

    def observe_flow_pair(self, outdoor: float, flow: float, now: datetime | None = None) -> None:
        """Feed the flow-temperature regression while the room holds target."""
        current = now or _utcnow()
        weight, decay = self._sample_weight_and_decay(self._flow_fit_at, current)
        self._flow_fit_at = current
        self._flow_fit = self._flow_fit.observe(outdoor, flow, weight=weight, decay=decay)
        self._schedule_save()

    def optimal_flow_temp(self, outdoor: float) -> float | None:
        """Flow temperature the learned curve produced at this outdoor temp."""
        fit = self._flow_fit.fit()
        if fit is None or fit.slope >= 0:
            # A rising or missing fit is not a heating curve; refuse to guess.
            return None
        return round(min(60.0, max(15.0, fit.intercept + fit.slope * outdoor)), 1)

    def observe_cooldown_episode(self, decay_rate_1_per_h: float, capacity_kwh_per_k: float | None) -> None:
        """Record one overnight-style cooldown episode estimate."""
        if decay_rate_1_per_h <= 0 or decay_rate_1_per_h > 1.0:
            return
        count = self._cooldown_count
        self._cooldown_rate_1_per_h = (
            decay_rate_1_per_h
            if self._cooldown_rate_1_per_h is None
            else round((self._cooldown_rate_1_per_h * count + decay_rate_1_per_h) / (count + 1), 4)
        )
        if capacity_kwh_per_k is not None and 0.5 <= capacity_kwh_per_k <= 200.0:
            previous = self._capacity_kwh_per_k
            self._capacity_kwh_per_k = (
                round(capacity_kwh_per_k, 2)
                if previous is None
                else round((previous * count + capacity_kwh_per_k) / (count + 1), 2)
            )
        self._cooldown_count = count + 1
        self._schedule_save()

    @property
    def thermal_inertia_kwh_per_k(self) -> float | None:
        """Effective building heat capacity estimate from cooldown episodes."""
        return self._capacity_kwh_per_k if self._cooldown_count >= 3 else None

    @property
    def building_model(self) -> dict[str, Any]:
        """Compact model snapshot for entities and diagnostics."""
        return {
            "heat_loss_w_per_k": self.heat_loss_w_per_k,
            "thermal_inertia_kwh_per_k": self.thermal_inertia_kwh_per_k,
            "cooldown_episodes": self._cooldown_count,
            "flow_curve_samples": self._flow_fit.n,
            "heat_fit_samples": self._heat_fit.n,
            "cop_buckets": len(self._cop_map),
        }

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _rollover(self, now: datetime) -> None:
        """Bound daily history; a no-op except across midnight."""
        day = _day_key(now)
        if self._last_day == day:
            return
        self._last_day = day
        # Daily metric aggregates live long enough for a same-month prior-year
        # comparison (#611); the COP day totals and regressions only need the
        # rolling window.
        seasonal_cutoff = (now - timedelta(days=_SEASONAL_RETENTION_DAYS)).date().isoformat()
        cutoff = (now - timedelta(days=_BASELINE_DAYS + 2)).date().isoformat()
        for days in self._daily.values():
            for key in [key for key in days if key < seasonal_cutoff]:
                days.pop(key)
        self._day_outdoor = {key: value for key, value in self._day_outdoor.items() if key >= seasonal_cutoff}
        self._cop_days = {key: value for key, value in self._cop_days.items() if key >= cutoff}
        self._cop_days_heating = {key: value for key, value in self._cop_days_heating.items() if key >= cutoff}
        self._cop_days_dhw = {key: value for key, value in self._cop_days_dhw.items() if key >= cutoff}
        if len(self._cop_map) > 512:
            # Drop the least-used bins; the map relearns quickly.
            for key, _hours in sorted(self._cop_map.items(), key=lambda item: item[1][2])[: len(self._cop_map) - 512]:
                self._cop_map.pop(key)
        self._schedule_save(force=True)

    def _serialize(self) -> dict[str, Any]:
        return {
            "version": _STORAGE_VERSION,
            "building_model_version": _BUILDING_MODEL_VERSION,
            "daily": self._daily,
            "day_outdoor": self._day_outdoor,
            "cop_map": self._cop_map,
            "cop_days": self._cop_days,
            "cop_days_heating": self._cop_days_heating,
            "cop_days_dhw": self._cop_days_dhw,
            "heat_fit": self._heat_fit.to_dict(),
            "flow_fit": self._flow_fit.to_dict(),
            "cooldown_count": self._cooldown_count,
            "cooldown_rate_1_per_h": self._cooldown_rate_1_per_h,
            "capacity_kwh_per_k": self._capacity_kwh_per_k,
            "last_day": self._last_day,
        }

    def _schedule_save(self, *, force: bool = False) -> None:
        """Schedule a store write at most every few minutes between rollovers."""
        now = time.monotonic()
        if not force and self._last_save_schedule is not None and now - self._last_save_schedule < _SAVE_THROTTLE:
            return
        self._last_save_schedule = now
        self._store.async_delay_save(self._serialize, _STORAGE_SAVE_DELAY)

    async def async_load(self) -> None:
        try:
            stored = await self._store.async_load()
        except Exception:
            _LOGGER.warning("Could not load persisted IDM advisor analytics", exc_info=True)
            return
        if not isinstance(stored, dict):
            return
        daily = stored.get("daily")
        if isinstance(daily, dict):
            self._daily = {
                str(key): {str(day): list(values) for day, values in days.items() if isinstance(values, list)}
                for key, days in daily.items()
                if isinstance(days, dict)
            }
        day_outdoor = stored.get("day_outdoor")
        if isinstance(day_outdoor, dict):
            self._day_outdoor = {
                str(day): list(values) for day, values in day_outdoor.items() if isinstance(values, list)
            }
        cop_map = stored.get("cop_map")
        if isinstance(cop_map, dict):
            self._cop_map = {
                str(key): list(values)
                for key, values in cop_map.items()
                if isinstance(values, list) and len(values) == 3
            }
        cop_days = stored.get("cop_days")
        if isinstance(cop_days, dict):
            self._cop_days = {str(day): list(values) for day, values in cop_days.items() if isinstance(values, list)}
        for attr, key in ((self._cop_days_heating, "cop_days_heating"), (self._cop_days_dhw, "cop_days_dhw")):
            domain_days = stored.get(key)
            if isinstance(domain_days, dict):
                attr.clear()
                attr.update({str(day): list(values) for day, values in domain_days.items() if isinstance(values, list)})
        self._heat_fit = _OnlineRegression.from_dict(stored.get("heat_fit"))
        self._flow_fit = _OnlineRegression.from_dict(stored.get("flow_fit"))
        count = stored.get("cooldown_count")
        self._cooldown_count = count if isinstance(count, int) and count >= 0 else 0
        self._cooldown_rate_1_per_h = _number(stored.get("cooldown_rate_1_per_h"))
        self._capacity_kwh_per_k = _number(stored.get("capacity_kwh_per_k"))
        if stored.get("building_model_version") != _BUILDING_MODEL_VERSION:
            # Regression statistics from an earlier model generation (mode
            # separation in v2, weighting and decay in v3) are not comparable
            # with the current ones. Relearn only the affected models (#546).
            self._heat_fit = _OnlineRegression()
            self._flow_fit = _OnlineRegression()
            self._capacity_kwh_per_k = None
            self._schedule_save(force=True)
        last_day = stored.get("last_day")
        self._last_day = last_day if isinstance(last_day, str) else None

    async def async_save(self) -> None:
        await self._store.async_save(self._serialize())
