"""Persistent advisor analytics: rolling baselines, COP map, building model.

Phases 3–5 of the predictive advisor roadmap. Everything here is passive
measurement: daily aggregates for anomaly baselines, an outdoor/flow COP map
and simple documented regressions for the building model. No value in this
module influences the heat pump; producers read from it and recommend.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Final

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

_STORAGE_VERSION: Final = 1
_STORAGE_SAVE_DELAY: Final = 30.0
_BASELINE_DAYS: Final = 30
_BASELINE_MIN_DAYS: Final = 3
_COP_BIN_OUTDOOR: Final = 2.0
_COP_BIN_FLOW: Final = 4.0
_COP_NEIGHBOURHOOD: Final = 1  # 3x3 bins around the query point
_COP_MIN_HOURS: Final = 1.0
_COP_OBSERVED_DAYS: Final = 7
_REGRESSION_MIN_SAMPLES: Final = 60


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

    @property
    def deviation_percent(self) -> float | None:
        """Today's relative deviation from the baseline median."""
        if self.today is None or self.median == 0:
            return None
        return round((self.today - self.median) / abs(self.median) * 100.0, 1)


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
    """Sufficient statistics of an online OLS regression."""

    n: int = 0
    sx: float = 0.0
    sy: float = 0.0
    sxx: float = 0.0
    sxy: float = 0.0

    def observe(self, x: float, y: float) -> _OnlineRegression:
        return _OnlineRegression(
            n=self.n + 1,
            sx=self.sx + x,
            sy=self.sy + y,
            sxx=self.sxx + x * x,
            sxy=self.sxy + x * y,
        )

    def fit(self) -> LinearFit | None:
        """Slope/intercept once enough independent samples accumulated."""
        if self.n < _REGRESSION_MIN_SAMPLES:
            return None
        denominator = self.n * self.sxx - self.sx * self.sx
        if abs(denominator) < 1e-9:
            return None
        slope = (self.n * self.sxy - self.sx * self.sy) / denominator
        intercept = (self.sy - slope * self.sx) / self.n
        return LinearFit(slope=slope, intercept=intercept, samples=self.n)

    def to_dict(self) -> dict[str, float]:
        return {"n": self.n, "sx": self.sx, "sy": self.sy, "sxx": self.sxx, "sxy": self.sxy}

    @classmethod
    def from_dict(cls, value: Any) -> _OnlineRegression:
        if not isinstance(value, dict):
            return cls()
        stats = cls()
        for name in ("n", "sx", "sy", "sxx", "sxy"):
            numeric = _number(value.get(name))
            if numeric is None:
                return cls()
            setattr(stats, name, numeric)
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
        # cop bin -> [electric_kwh, thermal_kwh, hours]
        self._cop_map: dict[str, list[float]] = {}
        # day -> [electric_kwh, thermal_kwh] for the observed-COP window
        self._cop_days: dict[str, list[float]] = {}
        self._heat_fit = _OnlineRegression()
        self._flow_fit = _OnlineRegression()
        self._cooldown_count = 0
        self._cooldown_rate_1_per_h: float | None = None
        self._capacity_kwh_per_k: float | None = None
        self._last_day: str | None = None

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
    ) -> None:
        """Aggregate one usable sample of a metric into its daily value.

        ``mode="mean"`` keeps the day's mean (flow rate, spread); ``max``
        keeps the day's maximum for monotonic running counters (compressor
        starts, DHW charge minutes), where a mean over partial counts would
        understate the day.
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
        self._schedule_save()

    def metric_baseline(self, key: str, now: datetime | None = None) -> DailyBaseline | None:
        """Compare today's mean against the median of the prior days."""
        current = now or _utcnow()
        days = self._daily.get(key, {})
        today_key = _day_key(current)
        prior = [
            mean
            for day, (total, count) in sorted(days.items())
            if day < today_key and count > 0 and (mean := total / count) is not None
        ]
        prior = prior[-_BASELINE_DAYS:]
        if len(prior) < _BASELINE_MIN_DAYS:
            return None
        median = _median(prior)
        if median is None:
            return None
        today_total, today_count = days.get(today_key, (0.0, 0.0))
        today = today_total / today_count if today_count else None
        return DailyBaseline(
            key=key,
            days=len(prior),
            median=round(median, 3),
            mad=round(_mean_absolute_deviation(prior, median), 3),
            today=round(today, 3) if today is not None else None,
        )

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
    ) -> None:
        """Integrate one operating interval into the outdoor/flow COP map."""
        if outdoor is None or flow is None or hours <= 0 or electric_kw <= 0 or thermal_kw <= 0:
            return
        hours = min(hours, 0.5)
        key = _cop_bin_key(outdoor, flow)
        electric, thermal, mapped = self._cop_map.get(key, [0.0, 0.0, 0.0])
        self._cop_map[key] = [electric + electric_kw * hours, thermal + thermal_kw * hours, mapped + hours]
        day = self._cop_days.setdefault(_day_key(_utcnow()), [0.0, 0.0])
        day[0] += electric_kw * hours
        day[1] += thermal_kw * hours
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

    def observed_cop(self, days: int = _COP_OBSERVED_DAYS, now: datetime | None = None) -> float | None:
        """COP actually observed over the last N days of map samples."""
        if not self._cop_days:
            return None
        current = now or _utcnow()
        cutoff = (current - timedelta(days=days)).date().isoformat()
        electric = sum(total[0] for day, total in self._cop_days.items() if day >= cutoff)
        thermal = sum(total[1] for day, total in self._cop_days.items() if day >= cutoff)
        if electric <= 0 or thermal <= 0:
            return None
        return round(thermal / electric, 2)

    # ------------------------------------------------------------------
    # Building model (phase 5)
    # ------------------------------------------------------------------

    def observe_heating(self, indoor_outdoor_delta_k: float, thermal_kw: float) -> None:
        """Feed the heat-loss regression (thermal power vs. temperature delta)."""
        if not math.isfinite(indoor_outdoor_delta_k) or thermal_kw <= 0:
            return
        self._heat_fit = self._heat_fit.observe(indoor_outdoor_delta_k, thermal_kw)
        self._schedule_save()

    @property
    def heat_loss_w_per_k(self) -> float | None:
        """Building heat loss in W/K from the thermal regression slope."""
        fit = self._heat_fit.fit()
        if fit is None or fit.slope <= 0:
            return None
        return round(fit.slope * 1000.0, 1)

    def observe_flow_pair(self, outdoor: float, flow: float) -> None:
        """Feed the flow-temperature regression while the room holds target."""
        self._flow_fit = self._flow_fit.observe(outdoor, flow)
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
        cutoff = (now - timedelta(days=_BASELINE_DAYS + 2)).date().isoformat()
        for days in self._daily.values():
            for key in [key for key in days if key < cutoff]:
                days.pop(key)
        self._cop_days = {key: value for key, value in self._cop_days.items() if key >= cutoff}
        if len(self._cop_map) > 512:
            # Drop the least-used bins; the map relearns quickly.
            for key, _hours in sorted(self._cop_map.items(), key=lambda item: item[1][2])[: len(self._cop_map) - 512]:
                self._cop_map.pop(key)

    def _serialize(self) -> dict[str, Any]:
        return {
            "version": _STORAGE_VERSION,
            "daily": self._daily,
            "cop_map": self._cop_map,
            "cop_days": self._cop_days,
            "heat_fit": self._heat_fit.to_dict(),
            "flow_fit": self._flow_fit.to_dict(),
            "cooldown_count": self._cooldown_count,
            "cooldown_rate_1_per_h": self._cooldown_rate_1_per_h,
            "capacity_kwh_per_k": self._capacity_kwh_per_k,
            "last_day": self._last_day,
        }

    def _schedule_save(self) -> None:
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
        cop_map = stored.get("cop_map")
        if isinstance(cop_map, dict):
            self._cop_map = {
                str(key): list(values)
                for key, values in cop_map.items()
                if isinstance(values, list) and len(values) == 3
            }
        cop_days = stored.get("cop_days")
        if isinstance(cop_days, dict):
            self._cop_days = {str(key): list(values) for key, values in cop_days.items() if isinstance(values, list)}
        self._heat_fit = _OnlineRegression.from_dict(stored.get("heat_fit"))
        self._flow_fit = _OnlineRegression.from_dict(stored.get("flow_fit"))
        count = stored.get("cooldown_count")
        self._cooldown_count = count if isinstance(count, int) and count >= 0 else 0
        self._cooldown_rate_1_per_h = _number(stored.get("cooldown_rate_1_per_h"))
        self._capacity_kwh_per_k = _number(stored.get("capacity_kwh_per_k"))
        last_day = stored.get("last_day")
        self._last_day = last_day if isinstance(last_day, str) else None

    async def async_save(self) -> None:
        await self._store.async_save(self._serialize())
