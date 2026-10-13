"""Forward selected Home Assistant energy sensors to IDM GLT registers."""

from __future__ import annotations

import asyncio
import logging
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, PERCENTAGE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event

from idm_heatpump import RegisterDef

from .adapter_glt import EXTERNAL_POWER_MEASUREMENT_NAMES
from .coordinator import IdmCoordinator
from .error_messages import classify_write_error, friendly_write_error, write_error_detail

_LOGGER = logging.getLogger(__name__)
_POWER_UNITS = frozenset({"W", "kW", "MW"})
_POWER_NAMES = frozenset(name for name in EXTERNAL_POWER_MEASUREMENT_NAMES if name != "battery_soc")

#: Some Navigator firmwares clear GLT RAM inputs roughly ten seconds after
#: the last write (observed on NAV10_20.23-903, #493: the battery rows appear
#: for ~10 s after each write and disappear until the next one). Sensor-driven
#: forwards naturally refresh faster; the fallback periodic pass must stay
#: below that hold window or the values vanish between passes. The per-register
#: write cooldown still throttles the actual writes.
_RAM_INPUT_REFRESH_SECONDS = 5.0


@dataclass(frozen=True)
class ExternalPowerForwardingConfig:
    """Runtime configuration for external power forwarding."""

    entities: dict[str, str]
    interval: int
    battery_sign: str = "as_is"


def _unit(state: Any) -> str | None:
    attrs = getattr(state, "attributes", None)
    if not isinstance(attrs, Mapping):
        return None
    value = attrs.get(ATTR_UNIT_OF_MEASUREMENT)
    return value if isinstance(value, str) and value else None


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _power_kw(value: Any, unit: str | None) -> float | None:
    number = _number(value)
    if number is None or unit not in _POWER_UNITS:
        return None
    if unit == "W":
        return number / 1000.0
    if unit == "MW":
        return number * 1000.0
    return number


def _soc(value: Any, unit: str | None) -> float | None:
    number = _number(value)
    if number is None or unit not in (None, PERCENTAGE):
        return None
    if not 0.0 <= number <= 100.0:
        return None
    # The GLT input is an integer percentage; HA battery aggregates may be
    # fractional. Validate first, then round instead of dropping the sample.
    return float(round(number))


class ExternalPowerForwarder:
    """Periodically mirror selected HA sensors into IDM GLT input registers.

    Invalid or unavailable source states are skipped. In particular, no zero is
    written as a fallback because that would actively overwrite valid values
    supplied by another energy manager.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: IdmCoordinator,
        config: ExternalPowerForwardingConfig,
    ) -> None:
        self._hass = hass
        self._coordinator = coordinator
        self._config = config
        self._unsub: Callable[[], None] | None = None
        self._pending_task: asyncio.Task[None] | None = None
        self._forward_again = False
        self._forward_lock = asyncio.Lock()

    async def async_run(self) -> None:
        self._unsub = async_track_state_change_event(
            self._hass,
            list(self._config.entities.values()),
            self._state_changed,
        )
        try:
            await self.async_forward()
            while True:
                # Refresh below the controller's RAM hold window (#493), not
                # at the configured fallback interval: a 30-60 s pass lets the
                # controller forget the values between writes.
                await asyncio.sleep(_RAM_INPUT_REFRESH_SECONDS)
                await self.async_forward()
        finally:
            if self._unsub is not None:
                self._unsub()
            if self._pending_task is not None:
                self._pending_task.cancel()
                await asyncio.gather(self._pending_task, return_exceptions=True)

    @callback
    def _state_changed(self, _event: Any) -> None:
        if self._pending_task is not None and not self._pending_task.done():
            self._forward_again = True
            return

        async def _debounced() -> None:
            try:
                while True:
                    # Coalesce bursts without postponing the first write or
                    # cancelling an in-flight Modbus request. Events during
                    # a write schedule another pass with the latest states.
                    await asyncio.sleep(1)
                    self._forward_again = False
                    await self.async_forward()
                    if not self._forward_again:
                        break
            finally:
                if self._pending_task is asyncio.current_task():
                    self._pending_task = None

        self._pending_task = self._hass.async_create_task(_debounced())

    def _value(self, name: str, state: Any) -> float | None:
        if state is None or getattr(state, "state", None) in ("unknown", "unavailable", "none"):
            return None
        if name == "battery_soc":
            return _soc(state.state, _unit(state))
        value = _power_kw(state.state, _unit(state))
        if value is None:
            return None
        if name == "battery_discharge" and self._config.battery_sign == "invert":
            value = -value
        return value

    async def async_forward(self) -> None:
        async with self._forward_lock:
            await self._async_forward_locked()

    async def _async_forward_locked(self) -> None:
        for name, entity_id in self._config.entities.items():
            if name not in EXTERNAL_POWER_MEASUREMENT_NAMES:
                continue
            state = self._hass.states.get(entity_id)
            value = self._value(name, state)
            if value is None:
                _LOGGER.debug("Skipping IDM external power forwarding from %s: invalid state or unit", entity_id)
                continue
            reg: RegisterDef | None = self._coordinator.get_register(name)
            if reg is None or not reg.writable:
                _LOGGER.warning("Skipping IDM external power forwarding: register %s is unavailable or read-only", name)
                continue
            if reg.min_val is not None and value < float(reg.min_val):
                _LOGGER.warning("Skipping %s: %.3f is below IDM minimum %.3f", name, value, float(reg.min_val))
                continue
            elif reg.max_val is not None and value > float(reg.max_val):
                _LOGGER.warning("Skipping %s: %.3f is above IDM maximum %.3f", name, value, float(reg.max_val))
                continue
            try:
                await self._coordinator.async_write_register(reg, value)
                # Successful GLT writes stay visible in debug logs: the write
                # cadence separates integration-side throttling from a
                # device-side clearing of the RAM inputs (#493).
                _LOGGER.debug("Forwarded external power %s = %s", name, value)
            except Exception as err:  # noqa: BLE001 - transport and API errors share no common base
                kind = classify_write_error(err)
                if kind == "write_cooldown_active":
                    # Expected self-throttling: sensor-driven forwards fire on
                    # every source update, the coordinator drops those inside
                    # the per-register cooldown. Not a device problem (issue
                    # #471: this used to log "rejected the value" per cycle).
                    _LOGGER.debug(
                        "External power forwarding to %s skipped: %s",
                        reg.name,
                        friendly_write_error(kind, reg.name),
                    )
                    continue
                _LOGGER.warning(
                    "Could not forward %s from %s to %s: %s",
                    name,
                    entity_id,
                    reg.name,
                    friendly_write_error(kind, reg.name),
                )
                _LOGGER.debug("Technical external power forwarding error: %s", write_error_detail(err))
