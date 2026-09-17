"""Forward selected Home Assistant energy sensors to IDM GLT registers."""

from __future__ import annotations

import asyncio
import logging
import math
from collections.abc import Mapping
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
    if number == -1:
        return -1.0
    if not 0.0 <= number <= 100.0 or number != round(number):
        return None
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
        self._unsub = None
        self._pending_task: asyncio.Task[None] | None = None

    async def async_run(self) -> None:
        self._unsub = async_track_state_change_event(
            self._hass,
            list(self._config.entities.values()),
            self._state_changed,
        )
        try:
            await self.async_forward()
            while True:
                await asyncio.sleep(max(30, self._config.interval))
                await self.async_forward()
        except asyncio.CancelledError:
            raise
        finally:
            if self._unsub is not None:
                self._unsub()
            if self._pending_task is not None:
                self._pending_task.cancel()

    @callback
    def _state_changed(self, _event: Any) -> None:
        if self._pending_task is not None and not self._pending_task.done():
            self._pending_task.cancel()

        async def _debounced() -> None:
            try:
                await asyncio.sleep(1)
                await self.async_forward()
            except asyncio.CancelledError:
                raise
            finally:
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
        if name == "battery_discharge":
            if self._config.battery_sign == "invert":
                value = -value
        return value

    async def async_forward(self) -> None:
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
            if value == -1 and name == "battery_soc":
                pass
            elif reg.min_val is not None and value < float(reg.min_val):
                _LOGGER.warning("Skipping %s: %.3f is below IDM minimum %.3f", name, value, float(reg.min_val))
                continue
            elif reg.max_val is not None and value > float(reg.max_val):
                _LOGGER.warning("Skipping %s: %.3f is above IDM maximum %.3f", name, value, float(reg.max_val))
                continue
            try:
                await self._coordinator.async_write_register(reg, value)
            except Exception as err:
                kind = classify_write_error(err)
                _LOGGER.warning(
                    "Could not forward %s from %s to %s: %s",
                    name,
                    entity_id,
                    reg.name,
                    friendly_write_error(kind, reg.name),
                )
                _LOGGER.debug("Technical external power forwarding error: %s", write_error_detail(err))
