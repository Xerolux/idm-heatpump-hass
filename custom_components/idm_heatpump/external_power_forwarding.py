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
from .const import EXTERNAL_POWER_GRID_KEY
from .coordinator import IdmCoordinator
from .error_messages import classify_write_error, friendly_write_error, write_error_detail

_LOGGER = logging.getLogger(__name__)
_POWER_UNITS = frozenset({"W", "kW", "MW"})
_POWER_NAMES = frozenset(name for name in EXTERNAL_POWER_MEASUREMENT_NAMES if name != "battery_soc")

#: Retain the conservative cyclic GLT RAM refresh used while investigating
#: #493. The reporter observed a missing battery display between writes, but
#: that does not establish a controller watchdog or a universal input TTL.
#: Refreshing every three seconds is a mitigation, not proof that the
#: Navigator's processed value or display remains continuously valid.
_RAM_INPUT_REFRESH_SECONDS = 3.0


def grid_meter_is_usable(entities: Mapping[str, str]) -> bool:
    """Return whether any derivation can consume a mapped grid meter.

    The grid meter derives pv_surplus unless that register has an explicit
    source, and house_consumption unless that register has an explicit source
    *and* a PV production source is mapped for the site balance.
    """
    return "pv_surplus" not in entities or ("house_consumption" not in entities and "pv_production" in entities)


@dataclass(frozen=True)
class ExternalPowerForwardingConfig:
    """Runtime configuration for external power forwarding."""

    entities: dict[str, str]
    interval: int = 60
    battery_sign: str = "as_is"
    #: Sign convention of the ``grid_power`` mapping key: "import" means the
    #: source reports grid draw positive, "export" means feed-in positive.
    grid_sign: str = "import"


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


def _soc(value: Any, unit: str | None) -> int | None:
    number = _number(value)
    if number is None or unit not in (None, PERCENTAGE):
        return None
    if not 0.0 <= number <= 100.0:
        return None
    # The GLT input is an integer percentage; HA battery aggregates may be
    # fractional. Validate first, then round to an integer instead of sending
    # floats (e.g. 92.0) that cause continuous int-vs-float state toggling in HA.
    return round(number)


class ExternalPowerForwarder:
    """Periodically mirror selected HA sensors into IDM GLT input registers.

    Invalid or unavailable source states are skipped. In particular, no zero is
    written as a fallback because that would actively overwrite valid values
    supplied by another energy manager.

    A bidirectional grid meter (the ``grid_power`` mapping key) is a source for
    derivations instead of a register of its own: it drives ``pv_surplus``
    (normalized to the IDM convention of positive = export) and, together with
    a valid PV production source, ``house_consumption`` including mapped battery
    flow. An explicitly mapped surplus or house sensor wins over the derivation;
    the grid meter alone is never treated as household consumption.
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
        # One WARNING per connection outage: the RAM refresh cadence retries
        # every few seconds and would otherwise repeat the same delivery
        # failure per register per pass for the whole outage.
        self._connection_down = False
        if "battery_soc" in self._config.entities and "battery_discharge" not in self._config.entities:
            _LOGGER.info(
                "IDM external power forwarding has battery_soc mapped (%s), but battery_discharge is unmapped. "
                "Navigator 10 displays the battery widget with both power and SoC; consider mapping your "
                "battery power sensor (or 0 W) to battery_discharge to keep the battery widget fully populated",
                self._config.entities["battery_soc"],
            )
        if self._config.entities.get(EXTERNAL_POWER_GRID_KEY) and not grid_meter_is_usable(self._config.entities):
            _LOGGER.warning(
                "IDM external power forwarding has a grid meter mapped (%s), but every register it could "
                "derive has an explicit source (pv_surplus, and house_consumption or a missing PV production "
                "source). The grid meter value is not used",
                self._config.entities[EXTERNAL_POWER_GRID_KEY],
            )

    async def async_run(self) -> None:
        self._unsub = async_track_state_change_event(
            self._hass,
            list(self._config.entities.values()),
            self._state_changed,
        )
        try:
            await self.async_forward()
            while True:
                # Keep cyclic GLT refresh even with quiet sources (#493).
                # This takes precedence over the configured fallback interval;
                # controller-side retention/processing remains unverified.
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

    def _value(self, name: str, state: Any) -> float | int | None:
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

    def _source_state(self, entity_id: str) -> Any:
        state = self._hass.states.get(entity_id)
        if state is None or getattr(state, "state", None) in ("unknown", "unavailable", "none"):
            return None
        return state

    def _source_kw(self, name: str) -> float | None:
        entity_id = self._config.entities.get(name)
        if not entity_id:
            return None
        state = self._source_state(entity_id)
        if state is None:
            return None
        return _power_kw(state.state, _unit(state))

    def _grid_import_kw(self) -> float | None:
        """Return the grid meter reading normalized to import-positive kW."""
        raw = self._source_kw(EXTERNAL_POWER_GRID_KEY)
        if raw is None:
            return None
        return -raw if self._config.grid_sign == "export" else raw

    def _derived_measurements(self) -> dict[str, float]:
        """Derive pv_surplus and house_consumption from the mapped grid meter.

        An explicit pv_surplus or house_consumption source wins over its
        derivation. House consumption needs the PV production source; the
        grid meter alone is never treated as household consumption because
        self-consumption is missing from it while PV generates.
        """
        grid_import = self._grid_import_kw()
        if grid_import is None:
            return {}
        derived: dict[str, float] = {}
        entities = self._config.entities
        if "pv_surplus" not in entities:
            # IDM pv_surplus: positive = export/surplus, negative = grid draw.
            derived["pv_surplus"] = -grid_import
        if "house_consumption" not in entities:
            production = self._source_kw("pv_production")
            if production is not None:
                # Site balance: house = PV production + grid import, with the
                # mapped battery flow added (charging counts negative).
                house = production + grid_import
                if entities.get("battery_discharge"):
                    discharge = self._value("battery_discharge", self._source_state(entities["battery_discharge"]))
                    if discharge is None:
                        return derived
                    house += float(discharge)
                # Valid sources can still be mutually inconsistent (an
                # inverter reporting zero while the battery feeds the grid);
                # household consumption has no meaningful negative value.
                derived["house_consumption"] = max(house, 0.0)
        return derived

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
            await self._async_write_measurement(name, value, entity_id)
        grid_entity = self._config.entities.get(EXTERNAL_POWER_GRID_KEY, "")
        for name, value in self._derived_measurements().items():
            await self._async_write_measurement(name, value, f"{grid_entity} (derived)")

    async def _async_write_measurement(self, name: str, value: float, source: str) -> None:
        reg: RegisterDef | None = self._coordinator.get_register(name)
        if reg is None or not reg.writable:
            _LOGGER.warning("Skipping IDM external power forwarding: register %s is unavailable or read-only", name)
            return
        if isinstance(value, float):
            # Quantize to the register's read resolution before writing. The
            # API decodes FLOAT registers rounded to two decimals, so writing
            # the raw float would publish its arithmetic noise (e.g. a derived
            # 0.3569999999999999 kW) as the optimistic state and then flip the
            # entity to the rounded readback on the next poll (#519). A
            # quantized write also keeps the written payload stable while the
            # sources wiggle below the 10 W resolution.
            value = round(value, 2)
            if value == 0:
                value = 0.0  # normalize -0.0
        if reg.min_val is not None and value < float(reg.min_val):
            _LOGGER.warning("Skipping %s: %.3f is below IDM minimum %.3f", name, value, float(reg.min_val))
            return
        if reg.max_val is not None and value > float(reg.max_val):
            _LOGGER.warning("Skipping %s: %.3f is above IDM maximum %.3f", name, value, float(reg.max_val))
            return
        try:
            await self._coordinator.async_write_register(reg, value)
            # Successful GLT writes stay visible in debug logs: the write
            # cadence separates integration-side throttling from a
            # device-side clearing of the RAM inputs (#493).
            _LOGGER.debug("Forwarded external power %s = %s", name, value)
            self._connection_down = False
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
                return
            if kind == "write_connection_failed" and self._connection_down:
                # Already reported for this outage; every retry would only
                # repeat it (observed as warning spam during a proxy
                # outage at the #493 refresh cadence).
                _LOGGER.debug("External power forwarding still paused: no Modbus connection")
                return
            if kind == "write_connection_failed":
                self._connection_down = True
                # One gray line per outage: the coordinator announces the
                # outage itself (or stays quiet inside its short-outage
                # window); a warning here only produced panic reports for
                # blips that self-healed.
                _LOGGER.info(
                    "Could not forward %s from %s to %s: %s",
                    name,
                    source,
                    reg.name,
                    friendly_write_error(kind, reg.name),
                )
            else:
                _LOGGER.warning(
                    "Could not forward %s from %s to %s: %s",
                    name,
                    source,
                    reg.name,
                    friendly_write_error(kind, reg.name),
                )
            _LOGGER.debug("Technical external power forwarding error: %s", write_error_detail(err))
