"""Persistent energy and COP statistics derived from IDM power registers."""

from __future__ import annotations

import logging
import math
from datetime import UTC, datetime
from typing import Any

from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
_STORAGE_VERSION = 1
_MAX_INTERVAL_SECONDS = 180.0
_ELECTRIC_KEY = "power_consumption_hp"
_THERMAL_KEY = "thermal_power_flow_sensor"


def _power(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number >= 0 else None


class EnergyStatistics:
    """Integrate validated electrical and thermal power readings in kWh."""

    def __init__(
        self,
        hass: Any,
        entry_id: str,
        expected_poll_interval: float,
        *,
        price_per_kwh: float = 0.30,
        price_source: str | None = None,
        co2_g_per_kwh: float = 350.0,
        pv_source: str | None = None,
    ) -> None:
        self._hass = hass
        self.price_per_kwh = max(0.0, float(price_per_kwh))
        self.price_source = price_source
        self.co2_g_per_kwh = max(0.0, float(co2_g_per_kwh))
        self.pv_source = pv_source
        self._store: Store[dict[str, Any]] = Store(hass, _STORAGE_VERSION, f"{DOMAIN}.energy_statistics.{entry_id}")
        self._max_interval = max(_MAX_INTERVAL_SECONDS, expected_poll_interval * 3.0)
        self.total_electrical_kwh = 0.0
        self.total_thermal_kwh = 0.0
        self.today_electrical_kwh = 0.0
        self.today_thermal_kwh = 0.0
        self.month_electrical_kwh = 0.0
        self.month_thermal_kwh = 0.0
        self.total_pv_self_consumed_kwh = 0.0
        self.today_pv_self_consumed_kwh = 0.0
        self.month_pv_self_consumed_kwh = 0.0
        self.total_cost_eur = 0.0
        self.today_cost_eur = 0.0
        self.month_cost_eur = 0.0
        self.unpriced_energy_kwh = 0.0
        self._period_day: str | None = None
        self._period_month: str | None = None
        self._last_sample_at: datetime | None = None
        self._last_electric: float | None = None
        self._last_thermal: float | None = None

    async def async_load(self) -> None:
        try:
            stored = await self._store.async_load()
        except Exception:
            _LOGGER.warning("Could not load IDM energy statistics", exc_info=True)
            return
        if not isinstance(stored, dict):
            return
        for name in (
            "total_electrical_kwh",
            "total_thermal_kwh",
            "today_electrical_kwh",
            "today_thermal_kwh",
            "month_electrical_kwh",
            "month_thermal_kwh",
            "total_pv_self_consumed_kwh",
            "today_pv_self_consumed_kwh",
            "month_pv_self_consumed_kwh",
            "total_cost_eur",
            "today_cost_eur",
            "month_cost_eur",
            "unpriced_energy_kwh",
        ):
            value = _power(stored.get(name))
            if value is not None:
                setattr(self, name, value)
        # Older stores derived costs from the fixed price instead of storing
        # them. Preserve that estimate when switching to an hourly tariff.
        for cost_key, energy_key in (
            ("total_cost_eur", "total_electrical_kwh"),
            ("today_cost_eur", "today_electrical_kwh"),
            ("month_cost_eur", "month_electrical_kwh"),
        ):
            if cost_key not in stored:
                setattr(self, cost_key, getattr(self, energy_key) * self.price_per_kwh)
        self._period_day = stored.get("period_day") if isinstance(stored.get("period_day"), str) else None
        self._period_month = stored.get("period_month") if isinstance(stored.get("period_month"), str) else None

    def _serialize(self) -> dict[str, Any]:
        return {
            "total_electrical_kwh": self.total_electrical_kwh,
            "total_thermal_kwh": self.total_thermal_kwh,
            "today_electrical_kwh": self.today_electrical_kwh,
            "today_thermal_kwh": self.today_thermal_kwh,
            "month_electrical_kwh": self.month_electrical_kwh,
            "month_thermal_kwh": self.month_thermal_kwh,
            "total_pv_self_consumed_kwh": self.total_pv_self_consumed_kwh,
            "today_pv_self_consumed_kwh": self.today_pv_self_consumed_kwh,
            "month_pv_self_consumed_kwh": self.month_pv_self_consumed_kwh,
            "total_cost_eur": self.total_cost_eur,
            "today_cost_eur": self.today_cost_eur,
            "month_cost_eur": self.month_cost_eur,
            "unpriced_energy_kwh": self.unpriced_energy_kwh,
            "period_day": self._period_day,
            "period_month": self._period_month,
        }

    async def async_save(self) -> None:
        await self._store.async_save(self._serialize())

    def _ensure_periods(self, observed_at: datetime) -> None:
        local = dt_util.as_local(observed_at)
        day = local.date().isoformat()
        month = local.strftime("%Y-%m")
        if self._period_day != day:
            self.today_electrical_kwh = 0.0
            self.today_thermal_kwh = 0.0
            self.today_cost_eur = 0.0
            self._period_day = day
        if self._period_month != month:
            self.month_electrical_kwh = 0.0
            self.month_thermal_kwh = 0.0
            self.month_cost_eur = 0.0
            self.month_pv_self_consumed_kwh = 0.0
            self._period_month = month

    def process_snapshot(self, data: dict[str, Any], *, now: datetime | None = None) -> None:
        observed_at = (now or datetime.now(UTC)).astimezone(UTC)
        electric = _power(data.get(_ELECTRIC_KEY))
        thermal = _power(data.get(_THERMAL_KEY))
        self._ensure_periods(observed_at)
        if electric is None or thermal is None:
            self._last_sample_at = None
            self._last_electric = None
            self._last_thermal = None
            return
        if self._last_sample_at is not None and self._last_electric is not None and self._last_thermal is not None:
            elapsed = (observed_at - self._last_sample_at).total_seconds()
            if 0 < elapsed <= self._max_interval:
                hours = elapsed / 3600.0
                electrical = max(0.0, (self._last_electric + electric) / 2.0 * hours)
                thermal_energy = max(0.0, (self._last_thermal + thermal) / 2.0 * hours)
                pv_power = self._pv_power_kw()
                pv_energy = min(electrical, pv_power * hours) if pv_power is not None else 0.0
                self.total_electrical_kwh += electrical
                self.total_thermal_kwh += thermal_energy
                self.today_electrical_kwh += electrical
                self.today_thermal_kwh += thermal_energy
                self.month_electrical_kwh += electrical
                self.month_thermal_kwh += thermal_energy
                self.total_pv_self_consumed_kwh += pv_energy
                self.today_pv_self_consumed_kwh += pv_energy
                self.month_pv_self_consumed_kwh += pv_energy
                price = self._current_price()
                if price is None:
                    self.unpriced_energy_kwh += electrical
                else:
                    self.total_cost_eur += electrical * price
                    self.today_cost_eur += electrical * price
                    self.month_cost_eur += electrical * price
                self._store.async_delay_save(self._serialize, 10)
        self._last_sample_at = observed_at
        self._last_electric = electric
        self._last_thermal = thermal

    def _current_price(self) -> float | None:
        """Read an explicitly selected local HA tariff; reject stale units."""
        if not self.price_source:
            return self.price_per_kwh
        state = self._hass.states.get(self.price_source)
        if state is None or getattr(state, "state", None) in {"unknown", "unavailable"}:
            return None
        try:
            value = float(state.state)
        except (TypeError, ValueError):
            return None
        unit = getattr(state, "attributes", {}).get("unit_of_measurement")
        if unit in {"ct/kWh", "c/kWh"}:
            value /= 100.0
        elif unit not in {"€/kWh", "EUR/kWh"}:
            return None
        return value if math.isfinite(value) and 0.0 <= value <= 5.0 else None

    def _pv_power_kw(self) -> float | None:
        if not self.pv_source:
            return None
        state = self._hass.states.get(self.pv_source)
        if state is None or getattr(state, "state", None) in {"unknown", "unavailable"}:
            return None
        try:
            value = float(state.state)
        except (TypeError, ValueError):
            return None
        unit = getattr(state, "attributes", {}).get("unit_of_measurement")
        if not math.isfinite(value) or value < 0:
            return None
        if unit == "W":
            return value / 1000.0
        if unit == "MW":
            return value * 1000.0
        return value if unit == "kW" else None

    @staticmethod
    def _ratio(thermal: float, electric: float) -> float | None:
        if electric <= 0 or thermal <= 0:
            return None
        return round(thermal / electric, 2)

    @property
    def total_cop(self) -> float | None:
        return self._ratio(self.total_thermal_kwh, self.total_electrical_kwh)

    @property
    def today_cop(self) -> float | None:
        return self._ratio(self.today_thermal_kwh, self.today_electrical_kwh)

    @property
    def month_cop(self) -> float | None:
        return self._ratio(self.month_thermal_kwh, self.month_electrical_kwh)

    @property
    def total_cost(self) -> float:
        return round(self.total_cost_eur, 2)

    @property
    def today_cost(self) -> float:
        return round(self.today_cost_eur, 2)

    @property
    def month_cost(self) -> float:
        return round(self.month_cost_eur, 2)

    @property
    def total_co2_kg(self) -> float:
        return round(self.total_electrical_kwh * self.co2_g_per_kwh / 1000.0, 2)

    @property
    def month_co2_kg(self) -> float:
        return round(self.month_electrical_kwh * self.co2_g_per_kwh / 1000.0, 2)
