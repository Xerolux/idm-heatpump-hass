"""Shared read-only evidence for reports, predictive recommendations and Assist."""

from __future__ import annotations

import json
import logging
import math
import time
from collections.abc import Mapping
from datetime import UTC, datetime
from itertools import pairwise
from typing import Any

from homeassistant.helpers.storage import Store

from .advisor_inputs import room_temperature_celsius
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
_COUNTERS = ("total_electrical_kwh", "total_thermal_kwh")
_RETENTION = 28 * 86400
_MAX_RECORDS = 8066
_MAX_GAP = 900
_MAX_STORAGE_BYTES = 4 * 1024 * 1024
REVIEW_STATES = (
    "no_change_recorded",
    "collecting_after",
    "insufficient_data",
    "not_comparable",
    "observed_improvement",
    "observed_deterioration",
    "mixed_outcome",
    "no_clear_change",
)


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) else None


def summarize_period(records: list[dict[str, Any]], start: float, end: float) -> dict[str, Any]:
    """Sum only bounded, observed counter intervals; never extrapolate gaps."""
    # Persisted histories and a freshly appended snapshot may share a timestamp.
    # Sort and deduplicate before integrating so overlapping intervals cannot
    # inflate coverage or count the same energy more than once.
    points = list(
        {row["at"]: row for row in sorted(records, key=lambda row: row["at"]) if start <= row["at"] <= end}.values()
    )
    electrical = thermal = covered = 0.0
    intervals = 0
    starts = 0.0
    starts_covered = 0.0
    heating = dhw = mode_covered = 0.0
    comfort_sum = comfort_seconds = 0.0
    for before, after in pairwise(points):
        gap = after["at"] - before["at"]
        values = [before.get(key) for key in _COUNTERS] + [after.get(key) for key in _COUNTERS]
        if not 0 < gap <= 900 or not before["connected"] or not after["connected"]:
            continue
        if any(_number(value) is None for value in values):
            continue
        electric_delta = after[_COUNTERS[0]] - before[_COUNTERS[0]]
        thermal_delta = after[_COUNTERS[1]] - before[_COUNTERS[1]]
        if electric_delta < 0 or thermal_delta < 0:
            continue
        electrical += electric_delta
        thermal += thermal_delta
        covered += gap
        intervals += 1
        if before.get("mode") == after.get("mode") == 1:
            heating += gap
        elif before.get("mode") == after.get("mode") == 4:
            dhw += gap
        if before.get("mode") in (0, 1, 2, 4, 8) and after.get("mode") in (0, 1, 2, 4, 8):
            mode_covered += gap
        old_starts, new_starts = (
            _number(before.get("compressor_starts_total")),
            _number(after.get("compressor_starts_total")),
        )
        if old_starts is not None and new_starts is not None and 0 <= new_starts - old_starts <= 20:
            starts += new_starts - old_starts
            starts_covered += gap
        comfort = _number(after.get("room_deviation_abs_k"))
        if comfort is not None:
            comfort_sum += comfort * gap
            comfort_seconds += gap
    outdoor = [
        value
        for row in points
        if row.get("connected") is True and (value := _number(row.get("outdoor_temp"))) is not None
    ]
    return {
        "start_utc": datetime.fromtimestamp(start, UTC).isoformat(),
        "end_utc": datetime.fromtimestamp(end, UTC).isoformat(),
        "samples": len(points),
        "requested_hours": round(max(0.0, end - start) / 3600, 6),
        "valid_energy_intervals": intervals,
        "observed_energy_hours": round(covered / 3600, 2),
        "unobserved_energy_hours": round(max(0.0, end - start - covered) / 3600, 2),
        "first_observation_utc": datetime.fromtimestamp(points[0]["at"], UTC).isoformat() if points else None,
        "last_observation_utc": datetime.fromtimestamp(points[-1]["at"], UTC).isoformat() if points else None,
        "energy_counter_coverage_percent": round(100 * covered / (end - start), 1) if end > start else 0.0,
        "electrical_kwh_observed": round(electrical, 3) if intervals else None,
        "thermal_kwh_observed": round(thermal, 3) if intervals else None,
        "cop_observed": round(thermal / electrical, 2) if electrical > 0 else None,
        "outdoor_c_min": min(outdoor) if outdoor else None,
        "outdoor_c_max": max(outdoor) if outdoor else None,
        "outdoor_c_mean": round(sum(outdoor) / len(outdoor), 2) if outdoor else None,
        "compressor_starts_observed": int(starts) if starts_covered else None,
        "starts_coverage_percent": round(100 * starts_covered / (end - start), 1) if end > start else 0.0,
        "heating_hours_observed": round(heating / 3600, 2),
        "dhw_hours_observed": round(dhw / 3600, 2),
        "dhw_share_observed_percent": round(100 * dhw / covered, 1)
        if covered and mode_covered >= covered * 0.9
        else None,
        "mode_coverage_percent": round(100 * mode_covered / covered, 1) if covered else 0.0,
        "room_deviation_abs_k": round(comfort_sum / comfort_seconds, 2)
        if covered and comfort_seconds >= covered * 0.8
        else None,
    }


def compare_periods(period: dict[str, Any], previous: dict[str, Any]) -> dict[str, Any]:
    """Compare well-covered equal windows; never convert a trend into savings."""
    result: dict[str, Any] = {"status": "insufficient_coverage"}
    if any((_number(window.get("energy_counter_coverage_percent")) or 0) < 90 for window in (period, previous)):
        return result
    for window in (period, previous):
        if not window.get("valid_energy_intervals"):
            return result
    if period.get("requested_hours") != previous.get("requested_hours"):
        return {"status": "different_windows"}
    if abs(period["energy_counter_coverage_percent"] - previous["energy_counter_coverage_percent"]) > 2:
        return {"status": "different_coverage"}
    result = {"status": "observed_comparison"}
    for key in ("electrical_kwh_observed", "thermal_kwh_observed", "cop_observed"):
        current, baseline = _number(period.get(key)), _number(previous.get(key))
        result[f"{key}_change_percent"] = (
            round(100 * (current / baseline - 1), 1)
            if current is not None and baseline is not None and baseline > 0
            else None
        )
    current_outdoor, previous_outdoor = _number(period.get("outdoor_c_mean")), _number(previous.get("outdoor_c_mean"))
    result["outdoor_mean_change_k"] = (
        round(current_outdoor - previous_outdoor, 2)
        if current_outdoor is not None and previous_outdoor is not None
        else None
    )
    return result


def explain_recommendation(record: Mapping[str, Any], language: str = "en") -> dict[str, Any]:
    """Explain evidence and uncertainty without turning advice into a write."""
    de = language.startswith("de")
    category = record.get("category")
    confidence = _number(record.get("confidence")) or 0.0
    observations = {
        "heating_curve": (
            "Die Raumtemperatur weicht über mehrere Tage vom Soll ab.",
            "Room temperature differs from its target over several days.",
        ),
        "anomaly": (
            "Ein beobachteter Wert weicht von der eigenen Vergleichshistorie ab.",
            "An observed value differs from this plant's own baseline.",
        ),
        "dhw": (
            "Die Prognosen zeigen ein mögliches Warmwasser-Zeitfenster.",
            "Forecasts identify a possible hot-water window.",
        ),
        "electricity_price": (
            "Das geplante Zeitfenster überschneidet sich mit hohen prognostizierten Preisen.",
            "The suggested window overlaps high forecast prices.",
        ),
    }
    observation = observations.get(
        str(category),
        (
            "Der Berater hat einen Hinweis aus den verfügbaren Daten abgeleitet.",
            "The advisor derived a finding from available data.",
        ),
    )
    reasons = record.get("reasons", ())
    reasons = [reason for reason in reasons if isinstance(reason, str)] if isinstance(reasons, (list, tuple)) else []
    reason_texts = {
        "room_temperature_above_target": (
            "Räume lagen im Vergleichsverlauf über dem Sollwert.",
            "Rooms were above target in the observed baseline.",
        ),
        "room_temperature_below_target": (
            "Räume lagen im Vergleichsverlauf unter dem Sollwert.",
            "Rooms were below target in the observed baseline.",
        ),
        "heat_circle_flow_below_baseline": (
            "Der Durchfluss liegt unter dem eigenen Vergleichsbereich.",
            "Flow is below this plant's baseline range.",
        ),
        "spread_above_baseline": (
            "Die Vorlauf-/Rücklaufspreizung liegt über der eigenen Baseline.",
            "Flow/return temperature spread is above this plant's baseline.",
        ),
        "compressor_starts_above_baseline": (
            "Es wurden mehr Verdichterstarts als im Vergleichsverlauf erfasst.",
            "More compressor starts were observed than in the baseline.",
        ),
        "dhw_charge_time_above_baseline": (
            "Warmwasserladungen beanspruchen mehr Zeit als im Vergleichsverlauf.",
            "Hot-water charging takes more time than in the baseline.",
        ),
        "pv_forecast_surplus_window": (
            "Das Fenster hat hohe prognostizierte PV-Erzeugung; Überschuss nach Hausverbrauch ist nicht bestätigt.",
            "The window has high forecast PV generation; surplus after household load is unconfirmed.",
        ),
        "electricity_price_and_expected_cop": (
            "Der Vergleich nutzt prognostizierte Strompreise und einen geschätzten COP.",
            "The comparison uses forecast electricity prices and an estimated COP.",
        ),
    }
    return {
        "observation": observation[0 if de else 1],
        "current_value": record.get("current_value"),
        "suggested_value": record.get("recommended_value"),
        "unit": record.get("unit"),
        "reason_codes": reasons,
        "supporting_observations": [
            reason_texts[reason][0 if de else 1] for reason in reasons if reason in reason_texts
        ],
        "confidence_percent": round(100 * confidence),
        "confidence_explanation": (
            "Die Konfidenz beschreibt Datenumfang und Modellstützung, keine Wahrscheinlichkeit für einen Defekt."
            if de
            else "Confidence describes data coverage and model support, not the probability of a fault."
        ),
        "missing_evidence": (
            "Eine Wirkung ist erst nach einer getrennten Vorher-/Nachher-Auswertung bei ähnlichen Bedingungen beurteilbar."
            if de
            else "An effect requires a separate before/after review under similar conditions."
        ),
        "first_check": (
            "Zuerst Messwerte, Betriebsphase und die genannten Vergleichsbedingungen prüfen. Der Hinweis ändert nichts an der Anlage."
            if de
            else "First check readings, operating phase and the stated comparison conditions. This advice does not change the plant."
        ),
    }


def _sample(coordinator: Any, circuits: tuple[str, ...], now: float) -> dict[str, Any]:
    """Capture numerical evidence only; never copy names, web text or options."""
    stats = getattr(coordinator, "poll_statistics", None)
    success = getattr(stats, "last_success", None)
    fresh = isinstance(success, datetime) and success.tzinfo is not None and 0 <= now - success.timestamp() <= _MAX_GAP
    connected = getattr(coordinator, "last_update_success", False) is True and fresh
    data = getattr(coordinator, "data", None)
    data = data if connected and isinstance(data, Mapping) else {}
    unused = getattr(coordinator, "unused_registers", ())
    unused = unused if isinstance(unused, (set, frozenset, tuple, list)) else ()
    result: dict[str, Any] = {"at": now, "connected": connected}
    for key in ("outdoor_temp", "hp_flow_temp", "hp_return_temp", "dhw_temp_top", "dhw_setpoint", "hp_operating_mode"):
        value = _number(data.get(key)) if key not in unused else None
        if value is not None and key != "hp_operating_mode" and not -60 <= value <= 120:
            value = None
        result["mode" if key == "hp_operating_mode" else key] = value
    energy = getattr(coordinator, "energy_statistics", None)
    for key in _COUNTERS:
        value = _number(getattr(energy, key, None)) if connected else None
        result[key] = value if value is not None and value >= 0 else None
    operation = getattr(coordinator, "operation_analysis", None)
    starts = (
        _number(getattr(operation, "total_compressor_starts", None))
        if connected and getattr(operation, "supports_compressor", False) is True
        else None
    )
    result["compressor_starts_total"] = starts
    entry = getattr(coordinator, "config_entry", None)
    options = getattr(entry, "options", {})
    mapped = options.get("advisor_room_temp_entities", {}) if isinstance(options, Mapping) else {}
    deviations: list[float] = []
    for circuit in circuits:
        for suffix in ("heating_curve", "room_setpoint_heat_normal"):
            key = f"hc_{circuit}_{suffix}"
            result[key] = _number(data.get(key)) if key not in unused else None
        room_key = f"hc_{circuit}_room_temp"
        room = _number(data.get(room_key)) if room_key not in unused else None
        if isinstance(mapped, Mapping) and isinstance(entity := mapped.get(circuit), str) and entity:
            room = _number(room_temperature_celsius(coordinator.hass.states.get(entity)))
        target = result[f"hc_{circuit}_room_setpoint_heat_normal"]
        deviation = (
            room - target if room is not None and target is not None and 0 <= room <= 50 and 5 <= target <= 35 else None
        )
        result[f"hc_{circuit}_room_deviation_k"] = deviation
        if deviation is not None:
            deviations.append(abs(deviation))
    result["room_deviation_abs_k"] = sum(deviations) / len(deviations) if deviations else None
    return result


class AnalysisHistory:
    """Bounded restart-safe evidence, shared by every read-only consumer."""

    def __init__(self, hass: Any, entry_id: str, coordinator: Any, circuits: tuple[str, ...]) -> None:
        self.coordinator = coordinator
        self.circuits = circuits
        self.records: list[dict[str, Any]] = []
        self.changes: list[dict[str, Any]] = []
        self._store: Store[dict[str, Any]] = Store(hass, 1, f"{DOMAIN}.advisor_evidence.{entry_id}")
        self._cache: dict[tuple[float, int], dict[str, Any]] = {}
        self._curve_values: dict[str, float] = {}

    @property
    def required_registers(self) -> tuple[str, ...]:
        return (
            "outdoor_temp",
            "hp_operating_mode",
            *(
                f"hc_{c}_{suffix}"
                for c in self.circuits
                for suffix in ("heating_curve", "room_temp", "room_setpoint_heat_normal")
            ),
        )

    async def async_load(self) -> None:
        try:
            payload = await self._store.async_load()
        except Exception:
            _LOGGER.warning("Could not load shared advisor evidence", exc_info=True)
            return
        if not isinstance(payload, dict):
            return
        now = time.time()
        allowed = set(_sample(self.coordinator, self.circuits, now))
        records = payload.get("records", [])
        if isinstance(records, list):
            for row in records[-_MAX_RECORDS:]:
                if (
                    isinstance(row, dict)
                    and (at := _number(row.get("at"))) is not None
                    and now - _RETENTION <= at <= now
                ):
                    self.records.append(
                        {key: row.get(key) is True if key == "connected" else _number(row.get(key)) for key in allowed}
                    )
            self.records = list({row["at"]: row for row in sorted(self.records, key=lambda row: row["at"])}.values())
        changes = payload.get("changes", [])
        if isinstance(changes, list):
            for change in changes[-50:]:
                if not isinstance(change, dict) or change.get("circuit") not in self.circuits:
                    continue
                values = {key: _number(change.get(key)) for key in ("at", "before", "after")}
                if (
                    all(value is not None for value in values.values())
                    and (at := values["at"]) is not None
                    and now - _RETENTION <= at <= now
                ):
                    self.changes.append({**values, "circuit": change["circuit"]})

    def import_legacy_records(self, records: list[dict[str, Any]], now: float) -> None:
        """Backfill existing AI measurements without inventing new evidence fields."""
        allowed = set(_sample(self.coordinator, self.circuits, now))
        imported: dict[float, dict[str, Any]] = {}
        for row in records[-_MAX_RECORDS:]:
            at = _number(row.get("at"))
            if at is None or not now - _RETENTION <= at <= now:
                continue
            imported[at] = {
                key: row.get(key) is True if key == "connected" else _number(row.get(key)) for key in allowed
            }
        # The shared history is authoritative at timestamps it already knows.
        imported.update({row["at"]: row for row in self.records})
        merged = sorted(imported.values(), key=lambda row: row["at"])[-_MAX_RECORDS:]
        if merged != self.records:
            self.records = merged
            self._cache.clear()
            self._store.async_delay_save(self._serialize, 30)

    def observe(self, now: float | None = None) -> None:
        current = time.time() if now is None else now
        previous = self.records[-1] if self.records else None
        if previous is not None and current < previous["at"]:
            return
        sample = _sample(self.coordinator, self.circuits, current)
        # Detect readback changes even between five-minute history points.
        for circuit in self.circuits:
            key = f"hc_{circuit}_heating_curve"
            before = self._curve_values.get(circuit)
            if before is None:
                before = _number(previous.get(key)) if previous is not None else None
                latest_change = next((row for row in reversed(self.changes) if row["circuit"] == circuit), None)
                if latest_change is not None and (previous is None or latest_change["at"] >= previous["at"]):
                    before = latest_change["after"]
            after = _number(sample.get(key))
            if (
                before is not None
                and after is not None
                and 0.1 <= before <= 2.5
                and 0.1 <= after <= 2.5
                and not math.isclose(before, after, abs_tol=0.001)
            ):
                self.changes.append({"at": current, "circuit": circuit, "before": before, "after": after})
            if after is not None and 0.1 <= after <= 2.5:
                self._curve_values[circuit] = after
        self.changes = [row for row in self.changes[-50:] if row["at"] >= current - _RETENTION]
        if (
            previous is not None
            and 0 <= current - previous["at"] < 300
            and previous.get("connected") == sample["connected"]
        ):
            if self.changes and self.changes[-1]["at"] == current:
                self._cache.clear()
                self._store.async_delay_save(self._serialize, 30)
            return
        self.records.append(sample)
        self.records = [row for row in self.records[-_MAX_RECORDS:] if row["at"] >= current - _RETENTION]
        self._cache.clear()
        self._store.async_delay_save(self._serialize, 30)

    def _serialize(self) -> dict[str, Any]:
        payload = {"records": self.records, "changes": self.changes}
        while self.records and len(json.dumps(payload, ensure_ascii=True, indent=4).encode()) > _MAX_STORAGE_BYTES:
            del self.records[: max(1, len(self.records) // 10)]
            self._cache.clear()
        return payload

    async def async_save(self) -> None:
        await self._store.async_save(self._serialize())

    def analysis(self, now: float | None = None, *, days: int = 1) -> dict[str, Any]:
        current = time.time() if now is None else now
        # Shared five-minute anchor keeps reports, entity attributes and Assist
        # on the same window rather than recomputing drifting percentages.
        current = math.floor(current / 300) * 300
        days = 7 if days == 7 else 1
        key = (current, days)
        if key in self._cache:
            return self._cache[key]
        duration = days * 86400
        period = summarize_period(self.records, current - duration, current)
        previous = summarize_period(self.records, current - 2 * duration, current - duration)
        comparison = compare_periods(period, previous)
        changes: list[dict[str, Any]] = []
        if comparison.get("status") == "observed_comparison":
            for metric in ("electrical_kwh_observed", "thermal_kwh_observed", "cop_observed"):
                delta = comparison.get(f"{metric}_change_percent")
                if delta is not None and abs(delta) >= 0.1:
                    changes.append(
                        {
                            "metric": metric,
                            "change_percent": delta,
                            "current": period[metric],
                            "previous": previous[metric],
                        }
                    )
            for metric, coverage_key in (
                ("compressor_starts_observed", "starts_coverage_percent"),
                ("dhw_share_observed_percent", None),
                ("room_deviation_abs_k", None),
            ):
                old, new = _number(previous.get(metric)), _number(period.get(metric))
                if (
                    old is not None
                    and new is not None
                    and abs(new - old) >= 0.05
                    and (coverage_key is None or min(period[coverage_key], previous[coverage_key]) >= 90)
                ):
                    changes.append(
                        {"metric": metric, "change_absolute": round(new - old, 2), "current": new, "previous": old}
                    )
        missing = []
        if period["energy_counter_coverage_percent"] < 90:
            missing.append("energy_history")
        if previous["energy_counter_coverage_percent"] < 90:
            missing.append("previous_period")
        if comparison.get("status") in ("different_coverage", "different_windows"):
            missing.append("comparable_windows")
        if period["outdoor_c_mean"] is None:
            missing.append("outdoor_temperature")
        if period["room_deviation_abs_k"] is None:
            missing.append("room_temperature_and_target")
        if period["compressor_starts_observed"] is None:
            missing.append("compressor_history")
        result = {
            "period": period,
            "previous_period": previous,
            "comparison": comparison,
            "changes": changes,
            "missing_evidence": missing,
            "optimization_review": self.optimization_review(current),
            "write_actions": False,
        }
        self._cache = {cache_key: value for cache_key, value in self._cache.items() if cache_key[0] == current}
        self._cache[key] = result
        return result

    def optimization_review(self, now: float) -> dict[str, Any]:
        if not self.changes:
            return {"status": "no_change_recorded", "reason": "no_observed_heating_curve_change"}
        change = self.changes[-1]
        result: dict[str, Any] = {
            **change,
            "status": "collecting_after",
            "cause_verified": False,
            "minimum_days_per_side": 3,
            "settling_hours": 6,
        }
        at = change["at"]
        if now < at + 78 * 3600:
            return result
        if any(other["at"] > at - 72 * 3600 and other is not change for other in self.changes):
            return {**result, "status": "not_comparable", "reason": "overlapping_changes"}
        coverage = [
            summarize_period(self.records, start, end)["energy_counter_coverage_percent"]
            for start, end in ((at - 72 * 3600, at), (at + 6 * 3600, at + 78 * 3600))
        ]
        result["coverage_before_percent"], result["coverage_after_percent"] = coverage
        if min(coverage) < 80:
            return {**result, "status": "insufficient_data", "reason": "period_coverage"}
        before = self._matched_intervals(at - 72 * 3600, at, change["circuit"])
        after = self._matched_intervals(at + 6 * 3600, at + 78 * 3600, change["circuit"])
        hours_before = sum(row["hours"] for row in before.values())
        hours_after = sum(row["hours"] for row in after.values())
        result.update(heating_hours_before=round(hours_before, 2), heating_hours_after=round(hours_after, 2))
        common = set(before) & set(after)
        matched = sum(min(before[key]["hours"], after[key]["hours"]) for key in common)
        result["matched_heating_hours"] = round(matched, 2)
        if matched < 6 or min(hours_before, hours_after) <= 0:
            return {**result, "status": "insufficient_data", "reason": "matched_heating_history"}
        if matched / max(hours_before, hours_after) < 0.6:
            return {**result, "status": "not_comparable", "reason": "weather_distribution"}
        normalized: list[dict[str, float | None]] = []
        for groups in (before, after):
            totals = {name: 0.0 for name in ("electric", "thermal", "comfort", "starts", "target")}
            comfort_hours = starts_hours = 0.0
            for key in common:
                row = groups[key]
                weight = min(before[key]["hours"], after[key]["hours"])
                for metric in totals:
                    totals[metric] += row[metric] / row["hours"] * weight
                comfort_hours += row["comfort_hours"] / row["hours"] * weight
                starts_hours += row["starts_hours"] / row["hours"] * weight
            normalized.append(
                {
                    "cop": totals["thermal"] / totals["electric"] if totals["electric"] > 0 else None,
                    "electric_kw": totals["electric"] / matched,
                    "comfort_k": totals["comfort"] / comfort_hours if comfort_hours >= matched * 0.8 else None,
                    "starts_per_hour": totals["starts"] / starts_hours if starts_hours >= matched * 0.8 else None,
                    "room_target_c": totals["target"] / matched,
                }
            )
        old, new = normalized
        result.update(before_metrics=old, after_metrics=new)
        if abs((new["room_target_c"] or 0.0) - (old["room_target_c"] or 0.0)) > 0.5:
            return {**result, "status": "not_comparable", "reason": "room_target_changed"}
        if (
            old["cop"] is None
            or new["cop"] is None
            or old["cop"] <= 0
            or old["comfort_k"] is None
            or new["comfort_k"] is None
        ):
            return {**result, "status": "insufficient_data", "reason": "energy_or_comfort"}
        cop_change = 100 * (new["cop"] / old["cop"] - 1)
        comfort_change = new["comfort_k"] - old["comfort_k"]
        result.update(cop_change_percent=round(cop_change, 1), comfort_change_k=round(comfort_change, 2))
        old_starts, new_starts = old["starts_per_hour"], new["starts_per_hour"]
        cycling_worse = (
            old_starts is not None and new_starts is not None and new_starts - old_starts > max(0.2, old_starts * 0.2)
        )
        if old_starts is not None and new_starts is not None:
            result["cycling_change_per_hour"] = round(new_starts - old_starts, 2)
        status = "no_clear_change"
        if cop_change >= 5:
            status = "observed_improvement" if comfort_change <= 0.3 and not cycling_worse else "mixed_outcome"
        elif cop_change <= -5:
            status = "observed_deterioration" if comfort_change >= -0.3 else "mixed_outcome"
        elif comfort_change > 0.3 or cycling_worse:
            status = "observed_deterioration"
        result["status"] = status
        return result

    def _matched_intervals(self, start: float, end: float, circuit: str) -> dict[int, dict[str, float]]:
        points = [row for row in self.records if start <= row["at"] <= end]
        groups: dict[int, dict[str, float]] = {}
        for before, after in pairwise(points):
            gap = after["at"] - before["at"]
            if (
                not 0 < gap <= _MAX_GAP
                or not before.get("connected")
                or not after.get("connected")
                or before.get("mode") != 1
                or after.get("mode") != 1
            ):
                continue
            outdoor = _number(after.get("outdoor_temp"))
            target = _number(after.get(f"hc_{circuit}_room_setpoint_heat_normal"))
            counters = [_number(row.get(key)) for row in (before, after) for key in _COUNTERS]
            if outdoor is None or target is None or any(value is None for value in counters):
                continue
            electric = after[_COUNTERS[0]] - before[_COUNTERS[0]]
            thermal = after[_COUNTERS[1]] - before[_COUNTERS[1]]
            if electric <= 0 or thermal <= 0 or not 0.5 <= thermal / electric <= 12 or electric * 3600 / gap > 60:
                continue
            row = groups.setdefault(
                math.floor(outdoor / 2),
                {
                    name: 0.0
                    for name in (
                        "hours",
                        "electric",
                        "thermal",
                        "comfort",
                        "comfort_hours",
                        "starts",
                        "starts_hours",
                        "target",
                    )
                },
            )
            hours = gap / 3600
            row["hours"] += hours
            row["electric"] += electric
            row["thermal"] += thermal
            row["target"] += target * hours
            comfort = _number(after.get(f"hc_{circuit}_room_deviation_k"))
            if comfort is not None:
                row["comfort"] += abs(comfort) * hours
                row["comfort_hours"] += hours
            starts_before, starts_after = (
                _number(before.get("compressor_starts_total")),
                _number(after.get("compressor_starts_total")),
            )
            if starts_before is not None and starts_after is not None and 0 <= starts_after - starts_before <= 20:
                row["starts"] += starts_after - starts_before
                row["starts_hours"] += hours
        return groups


async def async_ensure_analysis(hass: Any, entry: Any, coordinator: Any) -> AnalysisHistory:
    """Install one entry-owned history with no task and no device write path."""
    existing = getattr(coordinator, "analysis_history", None)
    if isinstance(existing, AnalysisHistory):
        return existing
    options = entry.options
    circuits = tuple(
        dict.fromkeys(
            str(c).lower()
            for c in options.get("heating_circuits", ["a"])
            if str(c).lower() in "abcdefg" and len(str(c)) == 1
        )
    ) or ("a",)
    history = AnalysisHistory(hass, entry.entry_id, coordinator, circuits)
    await history.async_load()
    coordinator.analysis_history = history
    coordinator.register_required_registers("advisor_evidence", history.required_registers)
    entry.async_on_unload(coordinator.async_add_listener(history.observe))
    history.observe()
    return history


def render_analysis(analysis: Mapping[str, Any], language: str = "en", *, topic: str = "changes") -> str:
    """Use the same concise, localized evidence text in Assist and reports."""
    de = language.startswith("de")

    def text(german: str, english: str) -> str:
        return german if de else english

    def number(value: Any, decimals: int = 1) -> str:
        numeric = _number(value)
        if numeric is None:
            return text("unbekannt", "unknown")
        rendered = f"{numeric:.{decimals}f}"
        return rendered.replace(".", ",") if de else rendered

    missing_names = {
        "energy_history": ("ausreichend erfasste Energieintervalle", "sufficient observed energy intervals"),
        "previous_period": ("ein ausreichend erfasstes vorheriges Fenster", "a sufficiently covered previous window"),
        "outdoor_temperature": ("Außentemperatur", "outdoor temperature"),
        "room_temperature_and_target": ("Raumtemperatur mit Sollwert", "room temperature with target"),
        "compressor_history": ("Verdichterstart-Historie", "compressor-start history"),
        "comparable_windows": ("gleich lange Fenster mit ähnlicher Abdeckung", "equal windows with similar coverage"),
    }
    if topic == "data_quality":
        missing = analysis.get("missing_evidence", [])
        if not missing:
            return text(
                "Für den aktuellen Vergleich sind Energie-, Temperatur- und Taktungsdaten vorhanden. Das bestätigt keine Fehlerfreiheit.",
                "Energy, temperature and cycling data are available for this comparison. This does not establish fault-free operation.",
            )
        return (
            text("Für belastbarere Aussagen fehlen: ", "More reliable findings require: ")
            + "; ".join(text(*missing_names[key]) for key in missing if key in missing_names)
            + "."
        )
    if topic == "optimization":
        review = analysis.get("optimization_review", {})
        status = review.get("status")
        labels = {
            "no_change_recorded": (
                "Noch keine Heizkurvenänderung beobachtet.",
                "No heating-curve change has been observed yet.",
            ),
            "collecting_after": (
                "Die Änderung ist erfasst; für die Bewertung werden drei Tage davor und danach sowie sechs Stunden Beruhigungszeit benötigt.",
                "The change is recorded; review needs three days before and after plus six settling hours.",
            ),
            "insufficient_data": (
                "Die Wirkung bleibt offen: Es fehlen ausreichend abgedeckte und vergleichbare Heizintervalle oder Komfortwerte.",
                "The effect remains open: sufficiently covered matched heating intervals or comfort readings are missing.",
            ),
            "not_comparable": (
                "Die Wirkung bleibt offen: Die Bedingungen sind nicht vergleichbar oder weitere Änderungen überlagern den Vergleich.",
                "The effect remains open: conditions are not comparable or additional changes overlap the review.",
            ),
            "observed_improvement": (
                "Unter ähnlichen Bedingungen wurde ein höherer COP ohne deutliche Verschlechterung der Raumabweichung beobachtet.",
                "Similar conditions show a higher COP without a marked increase in room-temperature deviation.",
            ),
            "observed_deterioration": (
                "Unter ähnlichen Bedingungen hat sich COP, Raumkomfort oder Taktung verschlechtert.",
                "COP, room comfort or cycling deteriorated under similar conditions.",
            ),
            "mixed_outcome": (
                "COP, Raumkomfort oder Taktung zeigen Zielkonflikte; es gibt keinen eindeutigen Gesamtnutzen.",
                "COP, room comfort or cycling show trade-offs; there is no clear overall benefit.",
            ),
            "no_clear_change": (
                "Unter ähnlichen Bedingungen zeigt sich bisher keine klare Veränderung.",
                "Similar conditions show no clear change so far.",
            ),
        }
        lines = [text(*labels.get(status, labels["insufficient_data"]))]
        if "cop_change_percent" in review:
            lines.append(text("COP-Änderung: ", "COP change: ") + number(review["cop_change_percent"]) + " %.")
            lines.append(
                text("Änderung der absoluten Raumabweichung: ", "Change in absolute room deviation: ")
                + number(review["comfort_change_k"], 2)
                + " K."
            )
        lines.append(
            text(
                "Dies ist ein beobachteter Vergleich, kein Nachweis der Ursache oder einer Einsparung. Es wird nichts automatisch geändert.",
                "This is an observed comparison, not proof of causality or savings. Nothing is changed automatically.",
            )
        )
        return " ".join(lines)
    period = analysis.get("period", {})
    if topic == "cycling":
        starts = period.get("compressor_starts_observed")
        if starts is None:
            return text(
                "Für die Taktungsentwicklung fehlen beobachtete Verdichterstarts.",
                "Cycling trends require observed compressor starts, which are missing.",
            )
        answer = text("Beobachtete Verdichterstarts: ", "Observed compressor starts: ") + number(starts, 0)
        answer += (
            text(" bei ", " with ")
            + number(period.get("starts_coverage_percent"))
            + text(" % Zeitabdeckung. ", "% time coverage. ")
        )
        previous = analysis.get("previous_period", {})
        if (
            analysis.get("comparison", {}).get("status") == "observed_comparison"
            and previous.get("compressor_starts_observed") is not None
            and min(period.get("starts_coverage_percent", 0), previous.get("starts_coverage_percent", 0)) >= 90
        ):
            answer += (
                text("Im vorherigen Fenster: ", "Previous window: ")
                + number(previous["compressor_starts_observed"], 0)
                + "."
            )
        else:
            answer += text(
                "Ein belastbarer Verlaufvergleich fehlt noch.", "A reliable trend comparison is not available yet."
            )
        return answer
    changes = analysis.get("changes", [])
    if not changes:
        if analysis.get("comparison", {}).get("status") == "observed_comparison":
            return text(
                "Im ausreichend erfassten Vergleich zeigen sich keine deutlichen Änderungen. ",
                "The sufficiently covered comparison shows no marked changes. ",
            ) + render_analysis(analysis, language, topic="data_quality")
        return text(
            "Noch kein belastbarer Zeitraumvergleich: Gleich lange Fenster benötigen jeweils mindestens 90 % und eine ähnliche Datenabdeckung. ",
            "No reliable period comparison yet: equal windows each need at least 90% and similar coverage. ",
        ) + render_analysis(analysis, language, topic="data_quality")
    metric_names = {
        "electrical_kwh_observed": ("Elektrische Energie", "Electrical energy"),
        "thermal_kwh_observed": ("Thermische Energie", "Thermal energy"),
        "cop_observed": ("Beobachteter COP", "Observed COP"),
        "compressor_starts_observed": ("Verdichterstarts", "Compressor starts"),
        "dhw_share_observed_percent": ("Warmwasser-Zeitanteil", "Hot-water time share"),
        "room_deviation_abs_k": ("Absolute Raumabweichung", "Absolute room deviation"),
    }
    lines = [text("Änderungen zum vorherigen Fenster:", "Changes from the previous window:")]
    for change in changes:
        metric = change["metric"]
        unit = (
            " %"
            if "change_percent" in change
            else " K"
            if metric == "room_deviation_abs_k"
            else text(" Prozentpunkte", " percentage points")
            if metric == "dhw_share_observed_percent"
            else ""
        )
        delta = change.get("change_percent", change.get("change_absolute"))
        lines.append(text(*metric_names[metric]) + ": " + number(delta) + unit + ".")
    outdoor = analysis.get("comparison", {}).get("outdoor_mean_change_k")
    if outdoor is not None:
        lines.append(
            text("Änderung der mittleren Außentemperatur: ", "Change in mean outdoor temperature: ")
            + number(outdoor)
            + " K."
        )
    lines.append(
        text(
            "Wetter, Warmwasserbedarf und Nutzung können mitwirken; daraus folgt keine bestätigte Ursache oder Einsparung.",
            "Weather, hot-water demand and usage may contribute; this does not establish a cause or savings.",
        )
    )
    return " ".join(lines)
