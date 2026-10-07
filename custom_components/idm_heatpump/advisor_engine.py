"""Producer orchestration: turns analytics and forecasts into recommendations.

Phases 3 and 6–9 of the predictive advisor roadmap. The engine is fed by a
coordinator listener (``observe``) and a slow forecast loop
(``async_refresh_forecasts``). It only ever calls ``PredictiveAdvisor.submit``
and ``retract`` — it has no write path to the heat pump, like every advisor
module.
"""

from __future__ import annotations

import asyncio
import logging
import math
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any, Final

from homeassistant.core import HomeAssistant

from .advisor_analytics import AdvisorAnalytics
from .predictive_advisor import (
    PredictiveAdvisor,
    Recommendation,
    RecommendationCategory,
    RecommendationSeverity,
    clamp_confidence,
)

_LOGGER = logging.getLogger(__name__)

_PRODUCER_INTERVAL: Final = timedelta(hours=6)
_COOLDOWN_MIN_HOURS: Final = 3.0
_COMPRESSOR_ON_KW: Final = 0.3
_WINDOW_HOURS: Final = 3
_PV_WINDOW_MIN_KWH: Final = 1.0
_CURVE_MIN_DAYS: Final = 7
_CURVE_DEVIATION_K: Final = 0.5
_CURVE_STEP: Final = 0.02
_CURVE_MIN: Final = 0.1
_CURVE_MAX: Final = 2.5
_FLOW_EXCESS_K: Final = 3.0

# Documented anomaly thresholds (spec section 10): today vs. own baseline.
_FLOW_LOW_PERCENT: Final = -15.0
_SPREAD_HIGH_K: Final = 2.0
_STARTS_HIGH_PERCENT: Final = 50.0
_DHW_CHARGE_HIGH_PERCENT: Final = 40.0

_FORECAST_HORIZON: Final = timedelta(hours=24)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    numeric = float(value)
    return numeric if math.isfinite(numeric) else None


def _day_stamp(now: datetime) -> str:
    return now.astimezone(UTC).date().strftime("%Y%m%d")


def _parse_hour(value: Any, now: datetime) -> datetime | None:
    """Parse one forecast timestamp: ISO string or hour-of-day int."""
    if isinstance(value, int) and not isinstance(value, bool):
        hour = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=value)
        return hour
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def parse_hourly_temperatures(
    forecast: Any,
    now: datetime,
    horizon: timedelta = _FORECAST_HORIZON,
) -> list[tuple[datetime, float]]:
    """Extract hourly temperatures from a ``weather.get_forecasts`` payload."""
    if not isinstance(forecast, list):
        return []
    temperatures: list[tuple[datetime, float]] = []
    for entry in forecast:
        if not isinstance(entry, Mapping):
            continue
        at = _parse_hour(entry.get("datetime"), now)
        value = _number(entry.get("temperature"))
        if at is not None and value is not None and now - timedelta(hours=1) <= at <= now + horizon:
            temperatures.append((at, value))
    return temperatures


def parse_pv_hourly_kwh(state: Any, now: datetime) -> list[tuple[datetime, float]]:
    """Extract expected hourly PV energy from a forecast sensor.

    Supported shapes: ``detailed_forecast`` (mapping of ISO hour or
    hour-offset to kWh — PVForecast style) and ``forecast``/``forecasts``
    (list with ``pv_estimate*`` in kW per hour — Solcast style).
    """
    attributes = getattr(state, "attributes", None)
    if not isinstance(attributes, Mapping):
        return []

    detailed = attributes.get("detailed_forecast")
    if isinstance(detailed, Mapping):
        parsed: list[tuple[datetime, float]] = []
        for key, value in detailed.items():
            at = _parse_hour(key, now)
            kwh = _number(value)
            if at is not None and kwh is not None and kwh > 0 and now <= at <= now + _FORECAST_HORIZON:
                parsed.append((at, kwh))
        return parsed

    for list_key in ("forecast", "forecasts"):
        entries = attributes.get(list_key)
        if not isinstance(entries, list):
            continue
        parsed = []
        for entry in entries:
            if not isinstance(entry, Mapping):
                continue
            at = None
            for time_key in ("datetime", "period_start", "start", "time"):
                at = _parse_hour(entry.get(time_key), now)
                if at is not None:
                    break
            kw = None
            for power_key in ("pv_estimate_kW", "pv_estimate", "power", "power_kw"):
                kw = _number(entry.get(power_key))
                if kw is not None:
                    break
            if (
                at is not None
                and kw is not None
                and kw > 0
                and now - timedelta(hours=1) <= at <= now + _FORECAST_HORIZON
            ):
                parsed.append((at, kw))  # kW averaged over one hour == kWh
        return parsed
    return []


def parse_price_hourly(state: Any, now: datetime) -> list[tuple[datetime, float]]:
    """Extract future hourly prices in EUR/kWh from a tariff sensor.

    Supported attribute shapes: ``today``/``tomorrow``/``data``/``prices``/
    ``raw_today``/``raw_tomorrow`` lists with a timestamp and a price.
    Cent prices are normalized when the state unit says ct/kWh.
    """
    attributes = getattr(state, "attributes", None)
    if not isinstance(attributes, Mapping):
        return []
    unit = attributes.get("unit_of_measurement")
    scale = 0.01 if unit in {"ct/kWh", "c/kWh"} else 1.0
    parsed: list[tuple[datetime, float]] = []
    for list_key in ("today", "tomorrow", "data", "prices", "raw_today", "raw_tomorrow"):
        entries = attributes.get(list_key)
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, Mapping):
                continue
            at = None
            for time_key in ("start", "datetime", "period_start", "time"):
                at = _parse_hour(entry.get(time_key), now)
                if at is not None:
                    break
            price = None
            for price_key in ("price", "value", "price_eur"):
                price = _number(entry.get(price_key))
                if price is not None:
                    break
            if at is not None and price is not None and now - timedelta(hours=1) <= at <= now + _FORECAST_HORIZON:
                parsed.append((at, price * scale))
    return parsed


def best_window(
    series: list[tuple[datetime, float]],
    *,
    hours: int = _WINDOW_HOURS,
    highest: bool,
) -> tuple[datetime, float, float] | None:
    """Best consecutive window: (start, mean value, sum) or None."""
    if len(series) < hours:
        return None
    ordered = sorted(series)
    best: tuple[datetime, float, float] | None = None
    for index in range(len(ordered) - hours + 1):
        window = ordered[index : index + hours]
        gaps = [(window[position + 1][0] - window[position][0]).total_seconds() for position in range(hours - 1)]
        if any(gap <= 0 or gap > 3600.0 for gap in gaps):
            continue  # not consecutive hours
        values = [value for _at, value in window]
        total = sum(values)
        mean = total / hours
        if best is None or (mean > best[1] if highest else mean < best[1]):
            best = (window[0][0], mean, total)
    return best


class AdvisorEngine:
    """Runs the advisor producers; owns anomaly, curve and forecast state."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: Any,
        advisor: PredictiveAdvisor,
        analytics: AdvisorAnalytics,
        *,
        circuits: tuple[str, ...] = ("a",),
        weather_entity: str | None = None,
        pv_forecast_entity: str | None = None,
        price_entity: str | None = None,
    ) -> None:
        self._hass = hass
        self._coordinator = coordinator
        self._advisor = advisor
        self._analytics = analytics
        self._circuits = circuits
        self._weather_entity = weather_entity
        self._pv_forecast_entity = pv_forecast_entity
        self._price_entity = price_entity

        self._last_sample_at: datetime | None = None
        self._compressor_on: bool | None = None
        self._cooldown_recorded = True
        self._off_since: datetime | None = None
        self._off_room_temp: float | None = None
        self._off_outdoor_temp: float | None = None
        self._last_producer_run: datetime | None = None

        self._weather_hours: list[tuple[datetime, float]] = []
        self._pv_hours: list[tuple[datetime, float]] = []
        self._price_hours: list[tuple[datetime, float]] = []
        self._dhw_window: dict[str, Any] | None = None
        self._plan: dict[str, Any] | None = None
        self._curve_recommendations: dict[str, dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Snapshot feeding (coordinator listener)
    # ------------------------------------------------------------------

    def observe(self, now: datetime | None = None) -> None:
        """Feed analytics from one snapshot and run due sync producers."""
        data = getattr(self._coordinator, "data", None)
        if not isinstance(data, Mapping) or not data:
            return
        current = now if now is not None else _utcnow()
        outdoor = _number(data.get("outdoor_temp"))
        power = _number(data.get("power_consumption_hp"))
        thermal = _number(data.get("thermal_power_flow_sensor"))
        flow = _number(data.get("hp_flow_temp"))
        return_temp = _number(data.get("hp_return_temp"))
        room, _circuit = self._primary_room_temp(data)
        compressor_on = power is not None and power >= _COMPRESSOR_ON_KW

        if compressor_on:
            self._observe_running(current, data, outdoor, power, thermal, flow, return_temp, room)
            self._cooldown_recorded = False
            self._off_since = None
        else:
            self._observe_idle(current, room, outdoor)

        for value_circuit in self._circuits:
            room_temp = _number(data.get(f"hc_{value_circuit}_room_temp"))
            room_setpoint = _number(data.get(f"hc_{value_circuit}_room_setpoint_heat_normal"))
            if room_temp is not None and room_setpoint is not None and room_setpoint > 5.0:
                self._analytics.observe_metric(f"room_deviation_{value_circuit}", room_temp - room_setpoint, current)

        analysis = getattr(self._coordinator, "operation_analysis", None)
        starts = _number(analysis.compressor_starts_today()) if analysis is not None else None
        if starts is not None:
            self._analytics.observe_metric("compressor_starts", starts, current, mode="max")
        if analysis is not None:
            share = _number(analysis.operating_share("dhw"))
            if share is not None and share > 0:
                self._analytics.observe_metric("dhw_charge_minutes", share / 100.0 * 1440.0, current, mode="max")

        self._compressor_on = compressor_on
        self._last_sample_at = current
        self._maybe_run_sync_producers(current)

    def _primary_room_temp(self, data: Mapping[str, Any]) -> tuple[float | None, str | None]:
        for circuit in self._circuits:
            room = _number(data.get(f"hc_{circuit}_room_temp"))
            if room is not None:
                return room, circuit
        return None, None

    def _observe_running(
        self,
        current: datetime,
        data: Mapping[str, Any],
        outdoor: float | None,
        power: float | None,
        thermal: float | None,
        flow: float | None,
        return_temp: float | None,
        room: float | None,
    ) -> None:
        flow_rate = _number(data.get("heat_sink_flow_rate"))
        if flow_rate is not None and flow_rate > 0.05:
            self._analytics.observe_metric("heat_sink_flow_rate", flow_rate, current)
        if flow is not None and return_temp is not None:
            self._analytics.observe_metric("hp_temperature_spread", flow - return_temp, current)
        if outdoor is not None and flow is not None and thermal and power:
            hours = 0.0
            if self._last_sample_at is not None and self._compressor_on:
                hours = (current - self._last_sample_at).total_seconds() / 3600.0
            self._analytics.observe_cop_sample(outdoor, flow, thermal, power, hours)
        if room is not None and outdoor is not None and thermal is not None and thermal > 0.5:
            self._analytics.observe_heating(room - outdoor, thermal)
        for circuit in self._circuits:
            room_temp = _number(data.get(f"hc_{circuit}_room_temp"))
            room_setpoint = _number(data.get(f"hc_{circuit}_room_setpoint_heat_normal"))
            circuit_flow = _number(data.get(f"hc_{circuit}_flow_temp"))
            if (
                outdoor is not None
                and room_temp is not None
                and room_setpoint is not None
                and abs(room_temp - room_setpoint) <= 0.6
                and circuit_flow is not None
            ):
                self._analytics.observe_flow_pair(outdoor, circuit_flow)

    def _observe_idle(self, current: datetime, room: float | None, outdoor: float | None) -> None:
        """Track compressor-off episodes to estimate thermal inertia."""
        if self._compressor_on is True:
            self._off_since = current
            self._off_room_temp = room
            self._off_outdoor_temp = outdoor
            self._cooldown_recorded = False
            return
        if self._cooldown_recorded or self._off_since is None or self._off_room_temp is None:
            return
        hours = (current - self._off_since).total_seconds() / 3600.0
        if hours < _COOLDOWN_MIN_HOURS or room is None:
            return
        drop = self._off_room_temp - room
        if drop < 0.2:
            self._cooldown_recorded = True
            return
        outdoor_mean = outdoor if outdoor is not None else self._off_outdoor_temp
        delta_t = ((self._off_room_temp + room) / 2.0 - outdoor_mean) if outdoor_mean is not None else None
        if delta_t is None or delta_t < 1.0:
            return
        rate_per_h = drop / hours / delta_t
        heat_loss_kw = (
            self._analytics.heat_loss_w_per_k / 1000.0 if self._analytics.heat_loss_w_per_k is not None else None
        )
        capacity = heat_loss_kw / rate_per_h if heat_loss_kw is not None else None
        self._analytics.observe_cooldown_episode(round(rate_per_h, 4), capacity)
        self._cooldown_recorded = True

    def _maybe_run_sync_producers(self, current: datetime) -> None:
        if self._last_producer_run is not None and current - self._last_producer_run < _PRODUCER_INTERVAL:
            return
        self._last_producer_run = current
        stage = self._advisor.stage
        if stage in ("early_hints", "recommending", "established"):
            self._produce_anomalies(current)
        if stage in ("recommending", "established"):
            self._produce_heating_curve(current)

    # ------------------------------------------------------------------
    # Anomaly producer (phase 3)
    # ------------------------------------------------------------------

    def _produce_anomalies(self, current: datetime) -> None:
        # key -> (strong, message, reason, baseline_days)
        found: dict[str, tuple[bool, str, str, int]] = {}
        flow = self._analytics.metric_baseline("heat_sink_flow_rate", current)
        if flow is not None and flow.deviation_percent is not None and flow.deviation_percent <= _FLOW_LOW_PERCENT:
            found["anomaly_flow_rate_low"] = (
                flow.deviation_percent <= 2 * _FLOW_LOW_PERCENT,
                f"Heat-circle flow is {abs(flow.deviation_percent):.0f}% below its {flow.days}-day baseline",
                "heat_circle_flow_below_baseline",
                flow.days,
            )
        spread = self._analytics.metric_baseline("hp_temperature_spread", current)
        if (
            spread is not None
            and spread.today is not None
            and spread.median is not None
            and spread.today - spread.median >= _SPREAD_HIGH_K
        ):
            found["anomaly_spread_high"] = (
                spread.today - spread.median >= 2 * _SPREAD_HIGH_K,
                f"Flow/return spread is {spread.today - spread.median:.1f} K above its baseline",
                "spread_above_baseline",
                spread.days,
            )
        starts = self._analytics.metric_baseline("compressor_starts", current)
        if (
            starts is not None
            and starts.deviation_percent is not None
            and starts.median >= 4.0
            and starts.deviation_percent >= _STARTS_HIGH_PERCENT
        ):
            found["anomaly_compressor_starts"] = (
                starts.deviation_percent >= 2 * _STARTS_HIGH_PERCENT,
                f"Compressor starts are {starts.deviation_percent:.0f}% above the {starts.days}-day baseline",
                "compressor_starts_above_baseline",
                starts.days,
            )
        dhw = self._analytics.metric_baseline("dhw_charge_minutes", current)
        if (
            dhw is not None
            and dhw.deviation_percent is not None
            and dhw.median >= 30.0
            and dhw.deviation_percent >= _DHW_CHARGE_HIGH_PERCENT
        ):
            found["anomaly_dhw_charge_long"] = (
                dhw.deviation_percent >= 2 * _DHW_CHARGE_HIGH_PERCENT,
                f"Hot-water charging takes {dhw.deviation_percent:.0f}% longer than usual",
                "dhw_charge_time_above_baseline",
                dhw.days,
            )

        stamp = _day_stamp(current)
        quality = self._advisor.usable_fraction
        for key, (strong, message, reason, baseline_days) in found.items():
            self._advisor.submit(
                Recommendation(
                    id=f"{key}_{stamp}",
                    category=RecommendationCategory.ANOMALY,
                    severity=RecommendationSeverity.WARNING if strong else RecommendationSeverity.HINT,
                    title=message,
                    reasons=(reason,),
                    confidence=clamp_confidence(
                        (0.5 + 0.05 * min(baseline_days, 8) + (0.1 if strong else 0.0))
                        * (quality if quality is not None else 1.0)
                    ),
                )
            )
        # Withdraw the anomaly recommendations that no longer hold.
        for rec in list(self._advisor.active_recommendations):
            if rec.category is RecommendationCategory.ANOMALY and rec.id.rsplit("_", 1)[0] not in found:
                self._advisor.retract(rec.id)

    # ------------------------------------------------------------------
    # Heating-curve producer (phase 6)
    # ------------------------------------------------------------------

    def _produce_heating_curve(self, current: datetime) -> None:
        data = self._coordinator.data if isinstance(self._coordinator.data, Mapping) else {}
        outdoor = _number(data.get("outdoor_temp"))
        quality = self._advisor.usable_fraction
        recommended_circuits: dict[str, dict[str, Any]] = {}
        for circuit in self._circuits:
            key = f"heating_curve_{circuit}_{_day_stamp(current)}"
            baseline = self._analytics.metric_baseline(f"room_deviation_{circuit}", current)
            curve = _number(data.get(f"hc_{circuit}_heating_curve"))
            active = False
            if baseline is not None and baseline.days >= _CURVE_MIN_DAYS and curve is not None:
                deviation = baseline.median
                reasons: list[str] = []
                recommended: float | None = None
                if deviation >= _CURVE_DEVIATION_K:
                    recommended = round(max(_CURVE_MIN, curve - _CURVE_STEP), 2)
                    reasons = ["room_temperature_above_target", f"mean_deviation_{deviation:+.1f}K"]
                elif deviation <= -_CURVE_DEVIATION_K:
                    recommended = round(min(_CURVE_MAX, curve + _CURVE_STEP), 2)
                    reasons = ["room_temperature_below_target", f"mean_deviation_{deviation:+.1f}K"]
                if recommended is not None and recommended != curve:
                    optimal = self._analytics.optimal_flow_temp(outdoor) if outdoor is not None else None
                    flow = _number(data.get(f"hc_{circuit}_flow_temp"))
                    if optimal is not None and flow is not None and flow - optimal >= _FLOW_EXCESS_K:
                        reasons.append("flow_temperature_above_estimated_requirement")
                    self._advisor.submit(
                        Recommendation(
                            id=key,
                            category=RecommendationCategory.HEATING_CURVE,
                            severity=RecommendationSeverity.HINT,
                            title=f"Review heating curve HC {circuit.upper()}: {curve:.2f} -> {recommended:.2f}",
                            current_value=curve,
                            recommended_value=recommended,
                            confidence=clamp_confidence(
                                (0.35 + 0.04 * min(baseline.days, 14) + 0.1 * min(abs(deviation), 2.0))
                                * (quality if quality is not None else 1.0)
                            ),
                            reasons=tuple(reasons),
                        )
                    )
                    active = True
                    recommended_circuits[circuit] = {
                        "current": curve,
                        "recommended": recommended,
                        "mean_room_deviation_k": round(deviation, 2),
                        "baseline_days": baseline.days,
                    }
            if not active:
                self._advisor.retract(key)
        self._curve_recommendations = recommended_circuits

    # ------------------------------------------------------------------
    # Forecast refresh (phases 7-9): PV, price, weather
    # ------------------------------------------------------------------

    async def async_refresh_forecasts(self, now: datetime | None = None) -> None:
        """Fetch external forecasts and derive DHW window plus 24 h plan."""
        current = now if now is not None else _utcnow()
        self._weather_hours = await self._fetch_weather_forecast(current)
        self._pv_hours = self._fetch_pv_forecast(current)
        self._price_hours = self._fetch_price_forecast(current)
        self._compute_dhw_window(current)
        self._compute_plan(current)

    async def _fetch_weather_forecast(self, current: datetime) -> list[tuple[datetime, float]]:
        if not self._weather_entity:
            return []
        try:
            async with asyncio.timeout(30):
                result = await self._hass.services.async_call(
                    "weather",
                    "get_forecasts",
                    {"entity_id": self._weather_entity, "type": "hourly"},
                    blocking=True,
                    return_response=True,
                )
        except Exception:
            _LOGGER.debug("IDM advisor weather forecast unavailable", exc_info=True)
            return []
        item = result.get(self._weather_entity) if isinstance(result, Mapping) else None
        forecast = item.get("forecast") if isinstance(item, Mapping) else None
        return parse_hourly_temperatures(forecast, current)

    def _fetch_pv_forecast(self, current: datetime) -> list[tuple[datetime, float]]:
        if not self._pv_forecast_entity:
            return []
        return parse_pv_hourly_kwh(self._hass.states.get(self._pv_forecast_entity), current)

    def _fetch_price_forecast(self, current: datetime) -> list[tuple[datetime, float]]:
        if not self._price_entity:
            return []
        return parse_price_hourly(self._hass.states.get(self._price_entity), current)

    def _expected_cop_for_hour(self, at: datetime) -> float | None:
        """Expected COP for a future hour: weather temp + typical flow."""
        temperature = None
        for forecast_at, value in self._weather_hours:
            if forecast_at == at:
                temperature = value
                break
        if temperature is None:
            return None
        expected = self._analytics.expected_cop(temperature, 35.0)
        return expected.cop if expected is not None else None

    def _compute_dhw_window(self, current: datetime) -> None:
        self._dhw_window = None
        if self._advisor.stage not in ("recommending", "established"):
            self._advisor.retract(f"dhw_window_{_day_stamp(current)}")
            return
        window: dict[str, Any] | None = None
        if self._pv_hours:
            best = best_window(self._pv_hours, highest=True)
            if best is not None and best[2] >= _PV_WINDOW_MIN_KWH:
                window = {
                    "source": "pv_surplus_forecast",
                    "start": best[0].isoformat(),
                    "hours": _WINDOW_HOURS,
                    "expected_pv_kwh": round(best[2], 2),
                }
        if window is None and self._price_hours:
            scored: list[tuple[datetime, float]] = []
            for at, price in self._price_hours:
                cop = self._expected_cop_for_hour(at) or 3.5
                scored.append((at, price / cop))
            best = best_window(scored, highest=False)
            if best is not None:
                window = {
                    "source": "electricity_price_forecast",
                    "start": best[0].isoformat(),
                    "hours": _WINDOW_HOURS,
                    "heat_cost_eur_per_kwh": round(best[1], 4),
                }
        self._dhw_window = window
        key = f"dhw_window_{_day_stamp(current)}"
        if window is None:
            self._advisor.retract(key)
            return
        start = datetime.fromisoformat(window["start"])
        start_local = start.strftime("%H:%M")
        end_local = (start + timedelta(hours=_WINDOW_HOURS)).strftime("%H:%M")
        window_text = f"{start_local}-{end_local}"
        if window["source"] == "pv_surplus_forecast":
            title = f"Charge hot water {window_text}: expected PV surplus {window['expected_pv_kwh']} kWh"
            reasons = ("pv_forecast_surplus_window",)
        else:
            title = f"Charge hot water {window_text}: cheapest heat cost {window['heat_cost_eur_per_kwh']:.3f} €/kWh"
            reasons = ("electricity_price_and_expected_cop",)
        self._advisor.submit(
            Recommendation(
                id=key,
                category=RecommendationCategory.DHW,
                severity=RecommendationSeverity.INFO,
                title=title,
                recommended_value=window_text,
                confidence=clamp_confidence(0.55 * (self._advisor.usable_fraction or 1.0) + 0.25),
                reasons=reasons,
            )
        )

    def _compute_plan(self, current: datetime) -> None:
        plan: dict[str, Any] = {}
        heat_loss = self._analytics.heat_loss_w_per_k
        data = self._coordinator.data if isinstance(self._coordinator.data, Mapping) else {}
        room, _circuit = self._primary_room_temp(data)
        if heat_loss is not None and self._weather_hours:
            indoor = room if room is not None else 21.0
            deltas = [indoor - temperature for _at, temperature in self._weather_hours[:24]]
            if deltas:
                plan["predicted_heat_demand_kwh"] = round(heat_loss / 1000.0 * (sum(deltas) / len(deltas)) * 24.0, 1)
        if self._pv_hours:
            plan["expected_pv_kwh"] = round(sum(value for _at, value in self._pv_hours[:24]), 2)
        if self._price_hours:
            expensive = best_window(self._price_hours, highest=True)
            if expensive is not None:
                plan["expensive_hours"] = {
                    "start": expensive[0].isoformat(),
                    "hours": _WINDOW_HOURS,
                    "mean_price_eur_per_kwh": round(expensive[1], 4),
                }
        if self._dhw_window is not None and "expensive_hours" in plan:
            dhw_start = datetime.fromisoformat(self._dhw_window["start"])
            avoid_start = datetime.fromisoformat(plan["expensive_hours"]["start"])
            avoid_end = avoid_start + timedelta(hours=plan["expensive_hours"]["hours"])
            if avoid_start <= dhw_start < avoid_end:
                plan["dhw_window_conflicts_with_expensive_hours"] = True
                self._advisor.submit(
                    Recommendation(
                        id=f"plan_{_day_stamp(current)}",
                        category=RecommendationCategory.ELECTRICITY_PRICE,
                        severity=RecommendationSeverity.WARNING,
                        title="Recommended hot-water window overlaps the most expensive hours",
                        reasons=("dhw_window_inside_expensive_hours",),
                        confidence=clamp_confidence(0.6 * (self._advisor.usable_fraction or 1.0) + 0.2),
                    )
                )
            else:
                self._advisor.retract(f"plan_{_day_stamp(current)}")
        else:
            self._advisor.retract(f"plan_{_day_stamp(current)}")
        self._plan = plan or None

    # ------------------------------------------------------------------
    # Derived scores for entities
    # ------------------------------------------------------------------

    @property
    def circuits(self) -> tuple[str, ...]:
        return self._circuits

    @property
    def analytics(self) -> AdvisorAnalytics:
        return self._analytics

    @property
    def demand_reason_label(self) -> str | None:
        """Human-readable web demand reason when the web supplement has one."""
        supplement = getattr(self._coordinator, "web_supplement", None)
        detail = getattr(supplement, "demand_reason", None)
        if detail is None:
            return None
        from .web_demand_reason import demand_reason_label

        return demand_reason_label(detail)

    @property
    def anomaly_findings(self) -> list[dict[str, Any]]:
        """Active anomaly recommendations as compact findings."""
        return [
            {
                "id": rec.id,
                "severity": str(rec.severity),
                "title": rec.title,
                "confidence": rec.confidence,
            }
            for rec in self._advisor.active_recommendations
            if rec.category is RecommendationCategory.ANOMALY
        ]

    @property
    def anomaly_active(self) -> bool:
        return bool(self.anomaly_findings)

    @property
    def health(self) -> dict[str, Any]:
        """Health components with a documented composition (spec section 11).

        Each domain scores 100 minus 30 per warning or 12 per hint finding;
        the overall score is the mean of the available domains and is only
        published when at least two domains have data.
        """
        findings = [
            rec.title.lower()
            for rec in self._advisor.active_recommendations
            if rec.category is RecommendationCategory.ANOMALY
        ]
        components: dict[str, Any] = {}
        if self._analytics.metric_baseline("heat_sink_flow_rate") is not None:
            penalty = (
                30.0
                if any("flow is" in title for title in findings)
                else (12.0 if any("spread" in title for title in findings) else 0.0)
            )
            components["hydraulics"] = round(max(0.0, 100.0 - penalty), 0)
        if self._analytics.metric_baseline("compressor_starts") is not None:
            penalty = 30.0 if any("starts" in title for title in findings) else 0.0
            components["compressor"] = round(max(0.0, 100.0 - penalty), 0)
        if self._analytics.metric_baseline("dhw_charge_minutes") is not None:
            penalty = 30.0 if any("hot-water" in title for title in findings) else 0.0
            components["dhw"] = round(max(0.0, 100.0 - penalty), 0)
        efficiency = self.efficiency
        if efficiency["expected_cop"] is not None and efficiency["observed_cop"] is not None:
            ratio = efficiency["observed_cop"] / efficiency["expected_cop"]
            components["efficiency"] = round(max(0.0, min(100.0, 100.0 - max(0.0, (1.0 - ratio)) * 200.0)), 0)
        score = round(sum(components.values()) / len(components)) if len(components) >= 2 else None
        return {"score": score, "components": components, "write_actions": False}

    @property
    def efficiency(self) -> dict[str, Any]:
        """Current operating point vs. the learned COP map (phase 4)."""
        data = self._coordinator.data if isinstance(self._coordinator.data, Mapping) else {}
        outdoor = _number(data.get("outdoor_temp"))
        flow = _number(data.get("hp_flow_temp"))
        expected = self._analytics.expected_cop(outdoor, flow) if outdoor is not None and flow is not None else None
        observed = self._analytics.observed_cop()
        deviation = (
            round((observed - expected.cop) / expected.cop * 100.0, 1)
            if expected is not None and observed is not None and expected.cop > 0
            else None
        )
        score = None
        if expected is not None and observed is not None and expected.cop > 0:
            ratio = observed / expected.cop
            score = round(max(0.0, min(100.0, 100.0 - max(0.0, 1.0 - ratio) * 200.0)), 0)
        return {
            "expected_cop": expected.cop if expected is not None else None,
            "expected_cop_hours": expected.hours if expected is not None else None,
            "observed_cop": observed,
            "deviation_percent": deviation,
            "score": score,
            "write_actions": False,
        }

    @property
    def dhw_window(self) -> dict[str, Any] | None:
        return self._dhw_window

    @property
    def plan(self) -> dict[str, Any] | None:
        return self._plan

    @property
    def curve_recommendations(self) -> dict[str, dict[str, Any]]:
        return getattr(self, "_curve_recommendations", {})

    @property
    def weather_hours(self) -> list[tuple[datetime, float]]:
        return self._weather_hours

    @property
    def pv_hours(self) -> list[tuple[datetime, float]]:
        return self._pv_hours

    @property
    def price_hours(self) -> list[tuple[datetime, float]]:
        return self._price_hours


async def advisor_forecast_loop(engine: AdvisorEngine, interval_seconds: float) -> None:
    """Refresh external forecasts periodically; one loop per config entry."""
    while True:
        try:
            await engine.async_refresh_forecasts()
        except Exception:  # pragma: no cover - defensive: the loop must survive
            _LOGGER.debug("IDM advisor forecast refresh failed", exc_info=True)
        await asyncio.sleep(interval_seconds)
