"""Read-only predictive advisor framework: recommendations, confidence, capabilities.

Phase 1 of the predictive advisor roadmap (``docs/dev/predictive-advisor-roadmap.md``).
This module — and every producer built on top of it — works strictly in
READ / ANALYZE / RECOMMEND. It holds no write path to the heat pump: no register
writes, no coil writes, no web-settings writes. The Navigator controller stays
the leading regulator at all times. "Accepting" a recommendation only records
the user's acknowledgment; applying a change is always a separate, explicit
user action on the regular control entities.
"""

from __future__ import annotations

import logging
import math
from collections import deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, Final

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import (
    CONF_DYNAMIC_PRICE_ENTITY,
    CONF_EXTERNAL_POWER_FORWARDING_ENTITIES,
    CONF_HEATING_CIRCUITS,
    DOMAIN,
)
from .coordinator import IdmCoordinator

_LOGGER = logging.getLogger(__name__)

EVENT_IDM_ADVISOR_RECOMMENDATION: Final = "idm_advisor_recommendation"

_STORAGE_VERSION: Final = 1
_STORAGE_SAVE_DELAY: Final = 10.0
_MAX_HISTORY: Final = 50
_RECOMMENDATION_TTL: Final = timedelta(days=7)

# Observation stages (spec section 15): nothing is recommended until the
# advisor has seen the plant for a while. Day 1 is pure collection, days 1–7
# may surface hints, from day 7 on recommendations are allowed, and after 30
# days the long-term baselines are considered established.
_STAGE_COLLECTING: Final = "collecting"
_STAGE_EARLY_HINTS: Final = "early_hints"
_STAGE_RECOMMENDING: Final = "recommending"
_STAGE_ESTABLISHED: Final = "established"
ADVISOR_STAGES: Final = (_STAGE_COLLECTING, _STAGE_EARLY_HINTS, _STAGE_RECOMMENDING, _STAGE_ESTABLISHED)
_FULL_COVERAGE_DAYS: Final = 14.0
_ESTABLISHED_DAYS: Final = 30.0

# A value identical for this long on a continuous quantity is treated as a
# frozen sensor, not a measurement (spec section 26). Discrete states such as
# the smart-grid status legitimately sit still for hours and are exempt.
_FROZEN_AFTER: Final = timedelta(hours=3)

# Documented plausibility ranges for every watched key; a value outside its
# range is garbage, not a measurement. Non-numeric values are implausible.
_PLAUSIBILITY: Final[dict[str, tuple[float, float]]] = {
    "outdoor_temp": (-50.0, 60.0),
    "hp_flow_temp": (-30.0, 120.0),
    "hp_return_temp": (-30.0, 120.0),
    "dhw_temp_top": (-10.0, 95.0),
    "dhw_setpoint": (-10.0, 95.0),
    "power_consumption_hp": (0.0, 60.0),
    "thermal_power_flow_sensor": (0.0, 120.0),
    "heat_sink_flow_rate": (0.0, 15.0),
    "storage_temp": (-10.0, 120.0),
    "pv_surplus": (-60.0, 60.0),
    "smart_grid_status": (0.0, 8.0),
    "hp_operating_mode": (0.0, 16.0),
}

# Continuous quantities where a long constant nonzero run marks a frozen
# sensor path. Only power, thermal and flow values qualify: they physically
# fluctuate whenever the heat pump runs, and exactly 0.0 is never counted as
# frozen because idle zeros are legitimate for hours. Temperatures, setpoints
# and discrete states legitimately sit still and are exempt.
_FROZEN_SENSITIVE: Final = frozenset(
    {
        "power_consumption_hp",
        "thermal_power_flow_sensor",
        "heat_sink_flow_rate",
        "pv_surplus",
    }
)

_ROOM_TEMP_RANGE: Final = (0.0, 50.0)
_COMPRESSOR_KEYS: Final = tuple(f"compressor_status_{index}" for index in range(1, 5))


class RecommendationCategory(StrEnum):
    """What area of the plant a recommendation belongs to."""

    HEATING_CURVE = "heating_curve"
    DHW = "dhw"
    PV = "pv"
    ELECTRICITY_PRICE = "electricity_price"
    EFFICIENCY = "efficiency"
    ANOMALY = "anomaly"
    MAINTENANCE = "maintenance"


class RecommendationSeverity(StrEnum):
    """How strongly a recommendation should be surfaced."""

    INFO = "info"
    HINT = "hint"
    WARNING = "warning"


class RecommendationStatus(StrEnum):
    """Lifecycle of one recommendation.

    ``accepted`` records only that the user considers the recommendation
    sensible. It never triggers a write to the heat pump.
    """

    NEW = "new"
    VIEWED = "viewed"
    ACCEPTED = "accepted"
    DISMISSED = "dismissed"
    EXPIRED = "expired"
    OBSOLETE = "obsolete"


#: Statuses a user (or UI) may set through ``mark``.
_USER_STATUSES: Final = frozenset(
    {RecommendationStatus.VIEWED, RecommendationStatus.ACCEPTED, RecommendationStatus.DISMISSED}
)


class ConfidenceLevel(StrEnum):
    """Four documented confidence levels instead of pseudo-exact percentages."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


def _utcnow() -> datetime:
    """Return an aware UTC timestamp."""
    return datetime.now(UTC)


def _parse_datetime(value: Any) -> datetime | None:
    """Parse one persisted ISO timestamp defensively."""
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def clamp_confidence(value: float) -> float:
    """Clamp a confidence score to 0..1 with two decimals."""
    if math.isnan(value):
        return 0.0
    return round(max(0.0, min(1.0, value)), 2)


def confidence_level(confidence: float) -> ConfidenceLevel:
    """Map a 0..1 confidence score onto the four documented levels."""
    if confidence < 0.5:
        return ConfidenceLevel.LOW
    if confidence < 0.75:
        return ConfidenceLevel.MEDIUM
    if confidence < 0.9:
        return ConfidenceLevel.HIGH
    return ConfidenceLevel.VERY_HIGH


def evaluate_confidence(*, days_observed: float, usable_fraction: float | None) -> float:
    """Deterministic confidence score from observation coverage and data quality.

    The formula is deliberately simple and documented so no pseudo-precision
    is implied (spec section 14): full observation coverage is reached after
    14 observed days and contributes 60 %, the share of usable samples across
    the watched keys contributes 40 %. ``usable_fraction`` None (no samples
    yet) counts as zero quality.
    """
    coverage = max(0.0, min(1.0, days_observed / _FULL_COVERAGE_DAYS))
    quality = 0.0 if usable_fraction is None else max(0.0, min(1.0, usable_fraction))
    return clamp_confidence(0.6 * coverage + 0.4 * quality)


def observation_stage(first_observed: datetime | None, now: datetime) -> str:
    """Return the observation stage for a first-observed timestamp."""
    if first_observed is None:
        return _STAGE_COLLECTING
    days = max(0.0, (now - first_observed).total_seconds() / 86400.0)
    if days < 1.0:
        return _STAGE_COLLECTING
    if days < 7.0:
        return _STAGE_EARLY_HINTS
    if days < _ESTABLISHED_DAYS:
        return _STAGE_RECOMMENDING
    return _STAGE_ESTABLISHED


@dataclass(frozen=True)
class Recommendation:
    """One machine-composed, fully explainable recommendation.

    ``reasons`` carries snake_case reason codes (e.g.
    ``room_temperature_above_target``) so the UI can translate them; the
    rendered explanation always lists these reasons (spec section 13).
    """

    id: str
    category: RecommendationCategory
    severity: RecommendationSeverity
    title: str
    description: str = ""
    current_value: float | int | str | None = None
    recommended_value: float | int | str | None = None
    unit: str | None = None
    confidence: float = 0.0
    reasons: tuple[str, ...] = ()
    created_at: datetime = field(default_factory=_utcnow)
    status: RecommendationStatus = RecommendationStatus.NEW

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-serializable form used for storage and events."""
        return {
            "id": self.id,
            "category": str(self.category),
            "severity": str(self.severity),
            "title": self.title,
            "description": self.description,
            "current_value": self.current_value,
            "recommended_value": self.recommended_value,
            "unit": self.unit,
            "confidence": self.confidence,
            "reasons": list(self.reasons),
            "created_at": self.created_at.isoformat(),
            "status": str(self.status),
        }

    def summary(self) -> dict[str, Any]:
        """Return the compact form published as an entity attribute."""
        return {
            "id": self.id,
            "category": str(self.category),
            "severity": str(self.severity),
            "title": self.title,
            "current_value": self.current_value,
            "recommended_value": self.recommended_value,
            "unit": self.unit,
            "confidence": self.confidence,
            "confidence_level": str(confidence_level(self.confidence)),
            "reasons": list(self.reasons),
            "status": str(self.status),
            "created_at": self.created_at.isoformat(),
        }


def _enum_or_none(value: str, enum_cls: type[Any]) -> Any:
    try:
        return enum_cls(value)
    except ValueError:
        return None


def recommendation_from_dict(value: Any) -> Recommendation | None:
    """Parse one persisted recommendation, discarding malformed entries."""
    if not isinstance(value, Mapping):
        return None
    rec_id = value.get("id")
    category = _enum_or_none(str(value.get("category", "")), RecommendationCategory)
    severity = _enum_or_none(str(value.get("severity", "")), RecommendationSeverity)
    status_value = value.get("status", RecommendationStatus.NEW)
    try:
        status = RecommendationStatus(str(status_value))
    except ValueError:
        status = RecommendationStatus.NEW
    if not isinstance(rec_id, str) or not rec_id or category is None or severity is None:
        return None
    created_at = _parse_datetime(value.get("created_at"))
    confidence = value.get("confidence", 0.0)
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        confidence = 0.0
    reasons = value.get("reasons")
    if not isinstance(reasons, list):
        reasons = []
    return Recommendation(
        id=rec_id,
        category=category,
        severity=severity,
        title=str(value.get("title", rec_id)),
        description=str(value.get("description", "")),
        current_value=value.get("current_value"),
        recommended_value=value.get("recommended_value"),
        unit=value.get("unit") if isinstance(value.get("unit"), str) else None,
        confidence=clamp_confidence(float(confidence)),
        reasons=tuple(str(reason) for reason in reasons),
        created_at=created_at if created_at is not None else _utcnow(),
        status=status,
    )


def _same_recommendation_content(left: Recommendation, right: Recommendation) -> bool:
    """Whether two recommendations with the same id carry the same content."""
    return (
        left.category == right.category
        and left.severity == right.severity
        and left.title == right.title
        and left.description == right.description
        and left.current_value == right.current_value
        and left.recommended_value == right.recommended_value
        and left.unit == right.unit
        and left.confidence == right.confidence
        and left.reasons == right.reasons
    )


class SampleQuality(StrEnum):
    """Classification of one observed sample of a watched key."""

    USABLE = "usable"
    UNAVAILABLE = "unavailable"
    IMPLAUSIBLE = "implausible"
    FROZEN = "frozen"


def classify_sample(
    value: Any,
    *,
    low: float,
    high: float,
    previous_value: float | None,
    previous_changed: datetime | None,
    now: datetime,
    frozen_sensitive: bool,
) -> SampleQuality:
    """Classify one sample of a watched key (spec section 26).

    Every classification is exactly one of unavailable, implausible, frozen
    or usable, checked in that order. Frozen requires a frozen-sensitive
    nonzero quantity whose value has not moved for ``_FROZEN_AFTER``; idle
    zeros are legitimate constants and stay usable.
    """
    if value is None:
        return SampleQuality.UNAVAILABLE
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return SampleQuality.IMPLAUSIBLE
    numeric = float(value)
    if math.isnan(numeric) or math.isinf(numeric) or numeric < low or numeric > high:
        return SampleQuality.IMPLAUSIBLE
    if (
        frozen_sensitive
        and numeric != 0.0
        and previous_value is not None
        and previous_value != 0.0
        and previous_changed is not None
        and numeric == previous_value
        and (now - previous_changed) >= _FROZEN_AFTER
    ):
        return SampleQuality.FROZEN
    return SampleQuality.USABLE


@dataclass
class _KeyQuality:
    """Mutable per-key sample statistics; one row per watched register."""

    samples: int = 0
    usable: int = 0
    unavailable: int = 0
    implausible: int = 0
    frozen: int = 0
    last_value: float | None = None
    last_changed: datetime | None = None

    def record(self, classification: SampleQuality, value: Any, now: datetime) -> None:
        """Count one classified sample and maintain the frozen-run baseline.

        Only usable and frozen samples keep the baseline alive; unavailable or
        implausible samples reset it so a sensor gap never masquerades as a
        frozen run.
        """
        self.samples += 1
        if classification is SampleQuality.USABLE:
            self.usable += 1
            numeric = float(value)  # guaranteed numeric by classify_sample
            if self.last_value is None or numeric != self.last_value:
                self.last_value = numeric
                self.last_changed = now
        elif classification is SampleQuality.FROZEN:
            self.frozen += 1  # keep the baseline so the frozen run continues to count
        elif classification is SampleQuality.UNAVAILABLE:
            self.unavailable += 1
            self.last_value = None
            self.last_changed = None
        else:
            self.implausible += 1
            self.last_value = None
            self.last_changed = None

    @property
    def usable_fraction(self) -> float | None:
        """Share of usable samples; None before the first sample."""
        if self.samples == 0:
            return None
        return round(self.usable / self.samples, 3)

    def to_dict(self) -> dict[str, Any]:
        """Return the persisted form (ISO timestamps, primitives only)."""
        return {
            "samples": self.samples,
            "usable": self.usable,
            "unavailable": self.unavailable,
            "implausible": self.implausible,
            "frozen": self.frozen,
            "last_value": self.last_value,
            "last_changed": self.last_changed.isoformat() if self.last_changed is not None else None,
        }

    @classmethod
    def from_dict(cls, value: Any) -> _KeyQuality:
        """Restore persisted statistics, discarding malformed fields."""
        quality = cls()
        if not isinstance(value, Mapping):
            return quality
        for name in ("samples", "usable", "unavailable", "implausible", "frozen"):
            raw = value.get(name)
            if isinstance(raw, bool) or not isinstance(raw, int) or raw < 0:
                continue
            setattr(quality, name, raw)
        last_value = value.get("last_value")
        if (
            not isinstance(last_value, bool)
            and isinstance(last_value, (int, float))
            and math.isfinite(float(last_value))
        ):
            quality.last_value = float(last_value)
        quality.last_changed = _parse_datetime(value.get("last_changed"))
        return quality


@dataclass(frozen=True)
class AdvisorCapabilities:
    """Which data sources this plant actually provides (spec section 25).

    Every advisor feature is capability-based: it activates only when the
    values it needs are present, so plants without a heat meter, flow sensor
    or PV signal simply never see those recommendations.
    """

    has_power_meter: bool
    has_heat_meter: bool
    has_room_temperature: bool
    has_flow_sensor: bool
    has_compressor: bool
    has_pv_signal: bool
    has_power_limit: bool
    has_buffer: bool
    has_demand_reason: bool
    has_dynamic_price_source: bool
    has_pv_source: bool

    def as_dict(self) -> dict[str, bool]:
        return {
            "power_meter": self.has_power_meter,
            "heat_meter": self.has_heat_meter,
            "room_temperature": self.has_room_temperature,
            "flow_sensor": self.has_flow_sensor,
            "compressor": self.has_compressor,
            "pv_signal": self.has_pv_signal,
            "power_limit": self.has_power_limit,
            "buffer": self.has_buffer,
            "demand_reason": self.has_demand_reason,
            "dynamic_price_source": self.has_dynamic_price_source,
            "pv_source": self.has_pv_source,
        }


def detect_capabilities(
    data: Mapping[str, Any],
    *,
    register_getter: Callable[[str], Any | None],
    web_variant: str | None,
    price_source: str | None,
    pv_source: str | None,
) -> AdvisorCapabilities:
    """Detect plant capabilities from one coordinator snapshot and options."""
    has_room_temperature = any(
        key.startswith("hc_") and key.endswith("_room_temp") and data.get(key) is not None for key in data
    )
    return AdvisorCapabilities(
        has_power_meter="power_consumption_hp" in data,
        has_heat_meter="thermal_power_flow_sensor" in data,
        has_room_temperature=has_room_temperature,
        has_flow_sensor="heat_sink_flow_rate" in data,
        has_compressor=any(key in data for key in _COMPRESSOR_KEYS),
        has_pv_signal="pv_surplus" in data or "smart_grid_status" in data,
        has_power_limit=register_getter("power_limit_hp") is not None,
        has_buffer="storage_temp" in data,
        has_demand_reason=web_variant == "nav10",
        has_dynamic_price_source=bool(price_source),
        has_pv_source=bool(pv_source),
    )


def _entry_options(coordinator: IdmCoordinator) -> Mapping[str, Any]:
    """Return the entry options defensively (unit tests pass mock entries)."""
    options = getattr(getattr(coordinator, "config_entry", None), "options", None)
    return options if isinstance(options, Mapping) else {}


def _configured_circuits(coordinator: IdmCoordinator) -> tuple[str, ...]:
    """Return the configured heating-circuit letters, lower-cased."""
    raw = _entry_options(coordinator).get(CONF_HEATING_CIRCUITS, ["a"])
    if isinstance(raw, (str, bytes)) or not isinstance(raw, (list, tuple)):
        return ("a",)
    return tuple(str(circuit).lower() for circuit in raw if str(circuit).strip())


def _room_temp_key(circuit: str) -> str:
    return f"hc_{circuit}_room_temp"


class PredictiveAdvisor:
    """Owns recommendations, observation state and data quality. Read-only.

    Producers (later roadmap phases) call :meth:`submit` with fully composed
    :class:`Recommendation` objects; the manager deduplicates them, keeps a
    bounded history, fires ``idm_advisor_recommendation`` events and persists
    everything restart-safe. The class intentionally has no method that
    writes to the heat pump.
    """

    def __init__(self, coordinator: IdmCoordinator) -> None:
        self._coordinator = coordinator
        self._hass: HomeAssistant = coordinator.hass
        entry_id = str(getattr(getattr(coordinator, "config_entry", None), "entry_id", "") or "")
        self._store: Store[dict[str, Any]] = Store(
            self._hass,
            _STORAGE_VERSION,
            f"{DOMAIN}.predictive_advisor.{entry_id}",
        )
        options = _entry_options(coordinator)
        self._price_source = str(options.get(CONF_DYNAMIC_PRICE_ENTITY, "")).strip() or None
        forwarding = options.get(CONF_EXTERNAL_POWER_FORWARDING_ENTITIES, {})
        pv_source = forwarding.get("pv_production") if isinstance(forwarding, Mapping) else None
        self._pv_source = str(pv_source).strip() or None if isinstance(pv_source, str) else None
        self._circuits = _configured_circuits(coordinator)
        room_keys = frozenset(_room_temp_key(circuit) for circuit in self._circuits)
        self._watched_keys: tuple[str, ...] = tuple(_PLAUSIBILITY) + tuple(sorted(room_keys))
        self._room_keys = room_keys

        self._first_observed: datetime | None = None
        self._active: dict[str, Recommendation] = {}
        self._history: deque[Recommendation] = deque(maxlen=_MAX_HISTORY)
        self._quality: dict[str, _KeyQuality] = {}

    # ------------------------------------------------------------------
    # Observation and data quality
    # ------------------------------------------------------------------

    @property
    def required_registers(self) -> tuple[str, ...]:
        """Registers the advisor watches; declare them for entity-aware polling."""
        return self._watched_keys

    @property
    def first_observed(self) -> datetime | None:
        """When the advisor saw its first non-empty coordinator snapshot."""
        return self._first_observed

    @property
    def observation_days(self) -> float | None:
        """Days of observation, or None before the first snapshot."""
        if self._first_observed is None:
            return None
        return round(max(0.0, (_utcnow() - self._first_observed).total_seconds() / 86400.0), 2)

    @property
    def stage(self) -> str:
        """Current observation stage."""
        return observation_stage(self._first_observed, _utcnow())

    def observe(self, now: datetime | None = None) -> None:
        """Consume one coordinator snapshot: quality stats and TTL expiry.

        Registered as a coordinator listener during entry setup, so the
        cadence is the scan interval. Empty snapshots (startup, outage) are
        skipped; they must not count as unavailable samples.
        """
        data = getattr(self._coordinator, "data", None)
        if not isinstance(data, Mapping) or not data:
            return
        current = now if now is not None else _utcnow()
        if self._first_observed is None:
            self._first_observed = current
        for key in self._watched_keys:
            low, high = _ROOM_TEMP_RANGE if key in self._room_keys else _PLAUSIBILITY[key]
            quality = self._quality.setdefault(key, _KeyQuality())
            classification = classify_sample(
                data.get(key),
                low=low,
                high=high,
                previous_value=quality.last_value,
                previous_changed=quality.last_changed,
                now=current,
                frozen_sensitive=key in _FROZEN_SENSITIVE,
            )
            quality.record(classification, data.get(key), current)
        self._expire_recommendations(current)
        self._schedule_save()

    def quality_summary(self) -> dict[str, dict[str, Any]]:
        """Return per-key sample statistics for diagnostics."""
        return {
            key: {
                "samples": quality.samples,
                "usable": quality.usable,
                "unavailable": quality.unavailable,
                "implausible": quality.implausible,
                "frozen": quality.frozen,
                "usable_fraction": quality.usable_fraction,
            }
            for key, quality in sorted(self._quality.items())
        }

    @property
    def usable_fraction(self) -> float | None:
        """Share of usable samples across all watched keys; None before data."""
        samples = sum(quality.samples for quality in self._quality.values())
        if samples == 0:
            return None
        usable = sum(quality.usable for quality in self._quality.values())
        return round(usable / samples, 3)

    @property
    def confidence(self) -> float:
        """Current framework-level confidence (observation x data quality)."""
        return evaluate_confidence(
            days_observed=self.observation_days or 0.0,
            usable_fraction=self.usable_fraction,
        )

    @property
    def capabilities(self) -> AdvisorCapabilities:
        """Capabilities of the plant behind the last snapshot."""
        return detect_capabilities(
            self._coordinator.data if isinstance(self._coordinator.data, Mapping) else {},
            register_getter=self._coordinator.get_register,
            web_variant=getattr(self._coordinator, "web_variant", None),
            price_source=self._price_source,
            pv_source=self._pv_source,
        )

    # ------------------------------------------------------------------
    # Recommendation lifecycle
    # ------------------------------------------------------------------

    @property
    def active_recommendations(self) -> tuple[Recommendation, ...]:
        """Active recommendations, oldest first."""
        return tuple(sorted(self._active.values(), key=lambda rec: (rec.created_at, rec.id)))

    @property
    def history(self) -> tuple[Recommendation, ...]:
        """Finished (expired, obsolete, dismissed) recommendations, newest last."""
        return tuple(self._history)

    @property
    def recommendation_count(self) -> int:
        return len(self._active)

    @property
    def optimization_available(self) -> bool:
        """Whether at least one unhandled recommendation is active."""
        return any(
            rec.status in (RecommendationStatus.NEW, RecommendationStatus.VIEWED) for rec in self._active.values()
        )

    def submit(self, recommendation: Recommendation) -> bool:
        """Register a recommendation; True when it is new or changed.

        An unchanged resubmission is a no-op so daily producer runs do not
        spam events. A changed replacement inherits ``created_at`` and the
        user status of its predecessor; the predecessor moves to history as
        obsolete.
        """
        rec = replace(recommendation, confidence=clamp_confidence(recommendation.confidence))
        existing = self._active.get(rec.id)
        if existing is not None and _same_recommendation_content(existing, rec):
            return False
        if existing is not None:
            self._append_history(replace(existing, status=RecommendationStatus.OBSOLETE))
            rec = replace(
                rec,
                created_at=existing.created_at,
                status=existing.status if existing.status in _USER_STATUSES else RecommendationStatus.NEW,
            )
        self._active[rec.id] = rec
        self._fire("new" if existing is None else "updated", rec)
        self._schedule_save()
        return True

    def mark(self, recommendation_id: str, status: RecommendationStatus) -> bool:
        """Set a user status (viewed, accepted, dismissed) on a recommendation.

        ``accepted`` is an acknowledgment only — nothing is written to the
        heat pump, here or anywhere in this class. Returns False for unknown
        ids or statuses outside the user set.
        """
        rec = self._active.get(recommendation_id)
        if rec is None or status not in _USER_STATUSES or rec.status == status:
            return False
        updated = replace(rec, status=status)
        if status is RecommendationStatus.DISMISSED:
            self._active.pop(recommendation_id)
            self._append_history(updated)
        else:
            self._active[recommendation_id] = updated
        self._fire("status", updated)
        self._schedule_save()
        return True

    def _expire_recommendations(self, now: datetime) -> None:
        """Move recommendations older than the TTL to history as expired."""
        expired = [
            replace(rec, status=RecommendationStatus.EXPIRED)
            for rec in self._active.values()
            if now - rec.created_at >= _RECOMMENDATION_TTL
        ]
        for rec in expired:
            self._active.pop(rec.id, None)
            self._append_history(rec)

    def _append_history(self, rec: Recommendation) -> None:
        self._history.append(rec)

    def _fire(self, action: str, rec: Recommendation) -> None:
        """Fire the recommendation event, tolerating stub event buses."""
        fire = getattr(getattr(self._hass, "bus", None), "async_fire", None)
        if not callable(fire):
            return
        try:
            fire(
                EVENT_IDM_ADVISOR_RECOMMENDATION,
                {"action": action, **rec.to_dict(), "confidence_level": str(confidence_level(rec.confidence))},
            )
        except Exception:  # pragma: no cover - defensive against broken test doubles
            _LOGGER.debug("Could not fire %s", EVENT_IDM_ADVISOR_RECOMMENDATION, exc_info=True)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _serialize(self) -> dict[str, Any]:
        """Return JSON-serializable advisor state."""
        return {
            "version": _STORAGE_VERSION,
            "first_observed": self._first_observed.isoformat() if self._first_observed is not None else None,
            "active": [rec.to_dict() for rec in self._active.values()],
            "history": [rec.to_dict() for rec in self._history],
            "quality": {key: quality.to_dict() for key, quality in self._quality.items()},
        }

    def _schedule_save(self) -> None:
        """Coalesce frequent updates into a delayed storage write."""
        self._store.async_delay_save(self._serialize, _STORAGE_SAVE_DELAY)

    async def async_load(self) -> None:
        """Restore persisted advisor state; malformed data never blocks setup."""
        try:
            stored = await self._store.async_load()
        except Exception:
            _LOGGER.warning("Could not load persisted IDM predictive advisor state", exc_info=True)
            return
        if not isinstance(stored, Mapping):
            return

        self._first_observed = _parse_datetime(stored.get("first_observed"))
        active = stored.get("active")
        if isinstance(active, list):
            self._active = {}
            for item in active:
                rec = recommendation_from_dict(item)
                if rec is not None:
                    self._active[rec.id] = rec
        history = stored.get("history")
        if isinstance(history, list):
            self._history = deque(
                (rec for rec in (recommendation_from_dict(item) for item in history) if rec is not None),
                maxlen=_MAX_HISTORY,
            )
        quality = stored.get("quality")
        if isinstance(quality, Mapping):
            self._quality = {str(key): _KeyQuality.from_dict(value) for key, value in quality.items()}
        self._expire_recommendations(_utcnow())

    async def async_save(self) -> None:
        """Persist advisor state immediately during config-entry unload."""
        await self._store.async_save(self._serialize())
