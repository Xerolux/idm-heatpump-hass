"""Optional local energy manager for safe IDM domestic hot-water charging."""

from __future__ import annotations

import asyncio
import logging
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN, SystemMode
from .dhw_boost import DhwBoostError, _finite_number, _parse_datetime, async_get_dhw_boost_manager

_LOGGER = logging.getLogger(__name__)
_POWER_UNITS = frozenset({"W", "kW", "MW"})
_REHEAT_HYSTERESIS_C = 5.0


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class EnergyManagerConfig:
    """Configuration for the conservative first energy-manager strategy."""

    sources: dict[str, str]
    minimum_surplus_kw: float = 1.0
    minimum_battery_soc: float = 20.0
    target_temperature: int = 55
    timeout_minutes: int = 90
    cooldown_minutes: int = 60


def _unit(state: Any) -> str | None:
    attributes = getattr(state, "attributes", None)
    if not isinstance(attributes, Mapping):
        return None
    unit = attributes.get(ATTR_UNIT_OF_MEASUREMENT)
    return unit if isinstance(unit, str) else None


def _number(state: Any) -> float | None:
    if state is None or getattr(state, "state", None) in {"unknown", "unavailable", "none"}:
        return None
    try:
        value = float(state.state)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _power_kw(state: Any) -> float | None:
    value = _number(state)
    unit = _unit(state)
    if value is None or unit not in _POWER_UNITS:
        return None
    if unit == "W":
        return value / 1000.0
    if unit == "MW":
        return value * 1000.0
    return value


def _soc(state: Any) -> float | None:
    value = _number(state)
    unit = _unit(state)
    if value is None or unit not in (None, PERCENTAGE) or value == -1:
        return None
    return value if 0.0 <= value <= 100.0 else None


class EnergyManager:
    """Use surplus energy for DHW without changing normal heating operation.

    The manager is deliberately fail-closed: missing or invalid inputs result
    in no write. It never writes PV registers and it never competes with the
    existing external-power forwarder. Its only automatic device action is the
    existing transactional DHW boost manager.
    """

    def __init__(self, hass: HomeAssistant, coordinator: Any, config: EnergyManagerConfig) -> None:
        self._hass = hass
        self._coordinator = coordinator
        self._config = config
        self._store: Store[dict[str, Any]] = Store(
            hass, 1, f"{DOMAIN}.energy_manager.{coordinator.config_entry.entry_id}"
        )
        self._loaded = False
        self._waiting_for_end = False
        self._blocked_until: datetime | None = None
        self._lock = asyncio.Lock()
        self._release_demand: Callable[[], None] | None = None
        self._task: asyncio.Task[None] | None = None

    def start(self) -> asyncio.Task[None]:
        """Start the periodic evaluation loop."""
        if self._task is None or self._task.done():
            if self._release_demand is None:
                self._release_demand = self._coordinator.register_required_registers(
                    "energy_manager", {"dhw_temp_top", "dhw_setpoint", "system_mode"}
                )
            self._task = self._hass.async_create_task(self._run())
        return self._task

    async def async_stop(self) -> None:
        """Stop the manager without cancelling an active DHW boost."""
        if self._release_demand is not None:
            self._release_demand()
            self._release_demand = None
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    def _surplus_kw(self) -> float | None:
        surplus_entity = self._config.sources.get("pv_surplus")
        if surplus_entity:
            # A configured net-surplus source is authoritative, including failure.
            return self._power_kw(surplus_entity)
        production = self._power_kw(self._config.sources.get("pv_production"))
        consumption = self._power_kw(self._config.sources.get("house_consumption"))
        if production is None or consumption is None or production < 0 or consumption < 0:
            return None
        return production - consumption

    def _power_kw(self, entity_id: str | None) -> float | None:
        return _power_kw(self._hass.states.get(entity_id)) if entity_id else None

    def _ready(self) -> bool:
        surplus = self._surplus_kw()
        if surplus is None or surplus < self._config.minimum_surplus_kw:
            return False
        soc_entity = self._config.sources.get("battery_soc")
        if soc_entity:
            soc = _soc(self._hass.states.get(soc_entity))
            if soc is None or soc < self._config.minimum_battery_soc:
                return False
        return True

    async def async_evaluate_once(self) -> bool:
        """Evaluate once; return whether a boost was started."""
        async with self._lock:
            return await self._async_evaluate_locked()

    async def _async_save(self) -> None:
        await self._store.async_save(
            {
                "waiting_for_end": self._waiting_for_end,
                "blocked_until": self._blocked_until.isoformat() if self._blocked_until else None,
            }
        )

    async def _async_evaluate_locked(self) -> bool:
        if not self._loaded:
            stored = await self._store.async_load()
            if isinstance(stored, dict):
                self._waiting_for_end = stored.get("waiting_for_end") is True
                self._blocked_until = _parse_datetime(stored.get("blocked_until"))
            self._loaded = True
        manager = await async_get_dhw_boost_manager(self._coordinator)
        if manager.active:
            return False
        now = _utcnow()
        if self._waiting_for_end:
            # Observe completion even without sun. A reload conservatively starts
            # a full cooldown after recovery, rather than forgetting the boost.
            self._blocked_until = now + timedelta(minutes=self._config.cooldown_minutes)
            await self._store.async_save(
                {
                    "waiting_for_end": False,
                    "blocked_until": self._blocked_until.isoformat(),
                }
            )
            self._waiting_for_end = False
        if self._blocked_until is not None and now < self._blocked_until:
            return False
        if not self._ready() or not self._coordinator.last_update_success:
            return False
        data = self._coordinator.data or {}
        temperature = _finite_number(data.get("dhw_temp_top"))
        if temperature is None or temperature > self._config.target_temperature - _REHEAT_HYSTERESIS_C:
            return False
        if data.get("system_mode") not in (SystemMode.AUTOMATIC, SystemMode.HOT_WATER_ONLY):
            return False
        # Persist the reservation before any device write. Storage failures and
        # interrupted/failed starts cannot erase the automatic anti-cycle guard.
        self._waiting_for_end = True
        await self._async_save()
        try:
            await manager.async_start(
                target_temperature=self._config.target_temperature,
                timeout_minutes=self._config.timeout_minutes,
                preserve_system_mode=True,
            )
        except DhwBoostError as err:
            _LOGGER.warning("IDM energy manager could not start DHW boost: %s", err)
            return False
        if not manager.active:
            return False
        _LOGGER.info("IDM energy manager started DHW boost using %.2f kW surplus", self._surplus_kw() or 0.0)
        return True

    async def _run(self) -> None:
        while True:
            try:
                await self.async_evaluate_once()
            except Exception:
                _LOGGER.warning("IDM energy manager evaluation failed", exc_info=True)
            await asyncio.sleep(30)
