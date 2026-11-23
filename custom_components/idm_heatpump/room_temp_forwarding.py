"""Forward Home Assistant sensor values to IDM GLT registers.

Two independent forwarder shapes live here:

- ``RoomTempForwarder`` — N keyed HA entities into N fixed target registers,
  looked up via an injectable ``register_for_key`` resolver. Used for
  per-heating-circuit room temperatures (``hc_{circuit}_ext_room_temp``, the
  default resolver) and for external storage temperatures
  (``glt_heat_storage_temp`` etc., via ``register_for_storage_temp_key``) — both
  are the same "N keys -> N registers, periodic + debounced" shape, so they
  share this implementation instead of duplicating it. Each key accepts
  several source entities (averaged to a fixed decimal precision), an
  additive offset and — with a ``persist_key`` — a restart-safe master
  switch, per-source switches and a season window that gate the writes.
- ``HumidityForwarder`` — a single HA entity into the one global
  ``ext_humidity`` register. Kept as its own small class rather than folded
  into the keyed shape above: humidity has no per-key loop or per-key
  tolerance keying, so unifying it would add indirection without a second
  concrete single-entity use case to justify it.
"""

from __future__ import annotations

import asyncio
import calendar
import logging
import math
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.storage import Store
from homeassistant.util.unit_conversion import TemperatureConverter

from idm_heatpump import RegisterDef

from .const import (
    CONF_ROOM_TEMP_FORWARDING_OFFSETS,
    CONF_ROOM_TEMP_FORWARDING_SEASON_END_DAY,
    CONF_ROOM_TEMP_FORWARDING_SEASON_END_MONTH,
    CONF_ROOM_TEMP_FORWARDING_SEASON_START_DAY,
    CONF_ROOM_TEMP_FORWARDING_SEASON_START_MONTH,
    MAX_ROOM_TEMP_FORWARDING_OFFSET,
    MIN_ROOM_TEMP_FORWARDING_OFFSET,
    ROOM_TEMP_FORWARDING_AVERAGING_DECIMALS,
)
from .coordinator import IdmCoordinator
from .error_messages import classify_write_error, friendly_write_error, write_error_detail

_LOGGER = logging.getLogger(__name__)

#: Temperature units a source sensor may report. Everything else means the user
#: picked an entity that is not a temperature at all.
_TEMPERATURE_UNITS = frozenset(
    {
        UnitOfTemperature.CELSIUS,
        UnitOfTemperature.FAHRENHEIT,
        UnitOfTemperature.KELVIN,
    }
)
#: Humidity units a source sensor may report.
_HUMIDITY_UNITS = frozenset({PERCENTAGE})


@dataclass(frozen=True)
class SeasonWindow:
    """Month/day window during which forwarding is active.

    A window whose start is after its end wraps the year end (for example
    October to April). The day is clamped into the real length of the month,
    so a configured "February 30" evaluates as the last day of February.
    """

    start: tuple[int, int]
    end: tuple[int, int]


def _normalized_month_day(month: int, day: int) -> tuple[int, int]:
    """Clamp the day into the month's real length in the current year."""
    last_day = calendar.monthrange(date.today().year, month)[1]
    return (month, min(max(day, 1), last_day))


def _season_border(month: int, day: int) -> tuple[int, int] | None:
    """Return one normalized season border, or ``None`` when it is unset.

    A border counts as set when its month or its day is valid. A half-filled
    border completes the way the options form completes it: a month without a
    day is the first of that month, a day without a month is a January date.
    """
    month_valid = 1 <= month <= 12
    day_valid = 1 <= day <= 31
    if not month_valid and not day_valid:
        return None
    return _normalized_month_day(month if month_valid else 1, day if day_valid else 1)


def season_window_from_options(options: Mapping[str, Any]) -> SeasonWindow | None:
    """Build the season window from the flat option keys; None when unset.

    Both borders empty means year-round forwarding. A single border is an
    open-ended season, not no season: a start without an end runs to
    31 December and an end without a start runs from 1 January. Dropping the
    whole window for a half-configured pair (as 0.28.3 did) silently turned
    the restriction the user had typed into year-round forwarding, and the
    end fields are empty by default in the options form.
    """
    try:
        start_month = int(options.get(CONF_ROOM_TEMP_FORWARDING_SEASON_START_MONTH, 0) or 0)
        start_day = int(options.get(CONF_ROOM_TEMP_FORWARDING_SEASON_START_DAY, 0) or 0)
        end_month = int(options.get(CONF_ROOM_TEMP_FORWARDING_SEASON_END_MONTH, 0) or 0)
        end_day = int(options.get(CONF_ROOM_TEMP_FORWARDING_SEASON_END_DAY, 0) or 0)
    except (TypeError, ValueError):
        return None
    start = _season_border(start_month, start_day)
    end = _season_border(end_month, end_day)
    if start is None and end is None:
        return None
    return SeasonWindow(
        start if start is not None else (1, 1),
        end if end is not None else (12, 31),
    )


def date_in_season(today: date, window: SeasonWindow | None) -> bool:
    """Whether the date lies inside the window; no window means always."""
    if window is None:
        return True
    today_key = (today.month, today.day)
    if window.start <= window.end:
        return window.start <= today_key <= window.end
    # A window that wraps the year end: October .. April.
    return today_key >= window.start or today_key <= window.end


def normalize_sources(value: Any) -> list[str]:
    """Accept the legacy single entity id and a multi-source list alike.

    Stored options may hold either shape (the options flow used to persist
    one entity id per circuit), so both normalize to a de-duplicated list.
    """
    if isinstance(value, str):
        candidates: list[Any] = [value]
    elif isinstance(value, (list, tuple)):
        candidates = list(value)
    else:
        return []
    seen: set[str] = set()
    sources: list[str] = []
    for candidate in candidates:
        source = str(candidate).strip()
        if source and source not in seen:
            seen.add(source)
            sources.append(source)
    return sources


def offsets_from_options(options: Mapping[str, Any]) -> dict[str, float]:
    """Read the per-circuit offset option, clamped to the documented bounds."""
    raw = options.get(CONF_ROOM_TEMP_FORWARDING_OFFSETS)
    if not isinstance(raw, Mapping):
        return {}
    offsets: dict[str, float] = {}
    for key, value in raw.items():
        try:
            offset = float(value)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(offset) or offset == 0.0:
            continue
        offsets[str(key)] = min(max(offset, MIN_ROOM_TEMP_FORWARDING_OFFSET), MAX_ROOM_TEMP_FORWARDING_OFFSET)
    return offsets


@dataclass(frozen=True)
class RoomTempForwardingConfig:
    """Runtime configuration for room temperature forwarding."""

    entities: dict[str, str | list[str]]
    interval: int
    tolerance: float
    offsets: dict[str, float] = field(default_factory=dict)
    season: SeasonWindow | None = None


def _state_unit(state: Any) -> str | None:
    """Return the unit a Home Assistant state reports, if it declares one."""
    attributes = getattr(state, "attributes", None)
    if not isinstance(attributes, Mapping):
        return None
    unit = attributes.get(ATTR_UNIT_OF_MEASUREMENT)
    return unit if isinstance(unit, str) and unit else None


class UnexpectedSourceUnit(ValueError):
    """The configured source entity does not report the expected quantity."""

    def __init__(self, unit: str) -> None:
        super().__init__(unit)
        self.unit = unit


def _coerce_temperature(value: Any) -> float | None:
    try:
        temperature = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(temperature) or abs(temperature) == float("inf"):
        return None
    return temperature


def _coerce_humidity(value: Any) -> float | None:
    humidity = _coerce_temperature(value)  # same float-parse/NaN/inf guard
    if humidity is None:
        return None
    if not 0.0 <= humidity <= 100.0:
        return None
    return humidity


def _temperature_in_celsius(value: Any, unit: str | None) -> float | None:
    """Return the source reading as degrees Celsius, or None when unusable.

    The GLT registers are defined in °C by the API. A source sensor reporting
    °F used to have its bare number written through: 68 °F arrived as 68 °C,
    which the register bounds cannot catch because 68 is a plausible Celsius
    value. The controller then saw a room more than 40 K too warm and stopped
    heating that circuit.

    A missing unit is treated as Celsius. Template sensors frequently omit it,
    and that was the behaviour before this conversion existed, so assuming
    anything else would silently change what those installations forward.

    Raises ``UnexpectedSourceUnit`` when the entity reports some other
    quantity: that is a misconfiguration the user has to see, not a value to
    convert.
    """
    temperature = _coerce_temperature(value)
    if temperature is None:
        return None
    if unit is None or unit == UnitOfTemperature.CELSIUS:
        return temperature
    if unit not in _TEMPERATURE_UNITS:
        raise UnexpectedSourceUnit(unit)
    return TemperatureConverter.convert(temperature, unit, UnitOfTemperature.CELSIUS)


def _humidity_in_percent(value: Any, unit: str | None) -> float | None:
    """Return the source reading as a relative humidity percentage.

    Humidity has one unit, so there is nothing to convert; an entity reporting
    anything else is the wrong entity and is reported as such.
    """
    if unit is not None and unit not in _HUMIDITY_UNITS:
        raise UnexpectedSourceUnit(unit)
    return _coerce_humidity(value)


def _register_for_circuit(coordinator: IdmCoordinator, circuit: str) -> RegisterDef | None:
    register_name = f"hc_{circuit}_ext_room_temp"
    # O(1) lookup via the coordinator's cached name index instead of a linear
    # scan over all number descriptions on every forward write.
    return coordinator.get_register(register_name)


# Fixed GLT storage-temperature registers, keyed the same way heating
# circuits are keyed for room temperature forwarding above.
STORAGE_TEMP_REGISTER_NAMES: dict[str, str] = {
    "heat_storage": "glt_heat_storage_temp",
    "cold_storage": "glt_cold_storage_temp",
    "dhw_bottom": "glt_dhw_temp_bottom",
    "dhw_top": "glt_dhw_temp_top",
}


def register_for_storage_temp_key(coordinator: IdmCoordinator, key: str) -> RegisterDef | None:
    register_name = STORAGE_TEMP_REGISTER_NAMES.get(key)
    if register_name is None:
        return None
    return coordinator.get_register(register_name)


class RoomTempForwarder:
    """Copies selected HA temperature sensors into N fixed GLT registers.

    ``register_for_key`` resolves each configured key (a heating circuit
    letter by default) to its target register; pass
    ``register_for_storage_temp_key`` to reuse this same class for the fixed
    storage-temperature registers instead.

    Each key may list several source entities; their converted readings are
    averaged (rounded to the averaging grid) before the key's offset is
    added and the value is written. A key whose sources are all unavailable
    or switched off receives the register's documented "no value" sentinel
    instead, so the controller falls back to its own regulation instead of
    trusting a stale room temperature. With ``persist_key`` set, the master
    switch and the per-source switches survive restarts through a Home
    Assistant storage collection; forwarding then only runs while the master
    switch is on and today lies inside the configured season window.
    """

    _CONTROLS_STORAGE_VERSION = 1

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: IdmCoordinator,
        config: RoomTempForwardingConfig,
        *,
        register_for_key: Callable[[IdmCoordinator, str], RegisterDef | None] = _register_for_circuit,
        key_label: str = "HK",
        value_label: str = "room temperature",
        convert: Callable[[Any, str | None], float | None] = _temperature_in_celsius,
        persist_key: str | None = None,
    ) -> None:
        self._hass = hass
        self._coordinator = coordinator
        self._config = config
        self._register_for_key = register_for_key
        self._key_label = key_label
        self._value_label = value_label
        self._convert = convert
        self._sources: dict[str, list[str]] = {
            str(key): normalize_sources(value) for key, value in config.entities.items()
        }
        self._sources = {key: sources for key, sources in self._sources.items() if sources}
        self._offsets: dict[str, float] = {str(key): float(value) for key, value in (config.offsets or {}).items()}
        self._season = config.season
        self._store: Store[dict[str, Any]] | None = (
            Store(hass, self._CONTROLS_STORAGE_VERSION, persist_key) if persist_key else None
        )
        self._master_enabled = True
        self._disabled_sources: set[tuple[str, str]] = set()
        self._controls_loaded = False
        self._reported_unit_mismatches: set[str] = set()
        self._last_written: dict[str, float] = {}
        self._last_write_monotonic: dict[str, float] = {}
        self._unsub_state: list[Callable[[], None]] = []
        self._pending_forward_tasks: dict[str, asyncio.Task[None]] = {}
        self._forward_again: set[str] = set()
        self._forward_lock = asyncio.Lock()
        # One WARNING per connection outage; retries during the outage stay
        # at debug (see ExternalPowerForwarder._connection_down).
        self._connection_down = False
        self._debounce_seconds = 1.0

    async def async_run(self) -> None:
        """Run forwarding until cancelled."""
        await self.async_load_controls()
        entity_ids = [source for sources in self._sources.values() for source in sources]
        if entity_ids:
            self._unsub_state.append(async_track_state_change_event(self._hass, entity_ids, self._handle_state_change))
        try:
            await self.async_forward_all()
            while True:
                await asyncio.sleep(self._config.interval)
                try:
                    await self.async_forward_all()
                except Exception:
                    _LOGGER.exception("IDM %s forwarding cycle failed; retrying next interval", self._value_label)
        finally:
            tasks = list(self._pending_forward_tasks.values())
            self._pending_forward_tasks.clear()
            for task in tasks:
                task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            for unsub in self._unsub_state:
                unsub()
            self._unsub_state.clear()

    @callback
    def _handle_state_change(self, event: Any) -> None:
        """Schedule a debounced forward for the entity that changed.

        ``@callback`` is required, not decorative: Home Assistant builds a
        ``HassJob`` from this listener, and a plain function without the marker
        is classified as an executor job and run in a worker thread. From there
        ``hass.async_create_task`` is a thread-safety violation that Home
        Assistant reports and that can corrupt loop state (#237).
        """
        entity_id = event.data.get("entity_id")
        if not isinstance(entity_id, str):
            return
        existing = self._pending_forward_tasks.get(entity_id)
        if existing is not None and not existing.done():
            self._forward_again.add(entity_id)
            return

        async def _debounced() -> None:
            try:
                while True:
                    # Coalesce bursts without cancelling an in-flight Modbus
                    # request: cancelling a task that is already writing can
                    # abort the FC16 transaction mid-flight and starve the
                    # write (#493, same race #495 fixed for external power).
                    # Events during a write schedule another pass that reads
                    # the latest state.
                    await asyncio.sleep(self._debounce_seconds)
                    self._forward_again.discard(entity_id)
                    await self.async_forward_entity(entity_id)
                    if entity_id not in self._forward_again:
                        break
            finally:
                if self._pending_forward_tasks.get(entity_id) is asyncio.current_task():
                    self._pending_forward_tasks.pop(entity_id, None)

        self._pending_forward_tasks[entity_id] = self._hass.async_create_task(_debounced())

    async def async_forward_all(self) -> None:
        async with self._forward_lock:
            for circuit in self._sources:
                await self._async_forward_circuit_locked(circuit)

    async def async_forward_entity(self, entity_id: str) -> None:
        async with self._forward_lock:
            for circuit, sources in self._sources.items():
                if entity_id in sources:
                    await self._async_forward_circuit_locked(circuit)

    async def async_forward_circuit(self, circuit: str) -> None:
        """Forward one configured key immediately (runtime control path)."""
        async with self._forward_lock:
            await self._async_forward_circuit_locked(circuit)

    async def _async_forward_circuit_locked(self, circuit: str) -> None:
        if not self._forwarding_active():
            _LOGGER.debug(
                "IDM %s forwarding for %s %s paused (switched off or outside the season window)",
                self._value_label,
                self._key_label,
                circuit,
            )
            return

        sources = [
            source for source in self._sources.get(circuit, []) if (circuit, source) not in self._disabled_sources
        ]
        values: list[float] = []
        for source in sources:
            state = self._hass.states.get(source)
            try:
                value = self._convert(getattr(state, "state", None), _state_unit(state))
            except UnexpectedSourceUnit as err:
                self._warn_once_about_unit(source, err.unit)
                continue
            if value is None:
                _LOGGER.debug("Skipping IDM %s forwarding from %s: invalid state", self._value_label, source)
                continue
            values.append(value)

        if not values:
            # Every configured source of this key is unavailable, invalid or
            # switched off. Leaving the last value in the register would have
            # the controller trust a stale room temperature forever, so the
            # documented "no value" sentinel hands the key back to the
            # controller's own regulation instead.
            await self._async_write_circuit(circuit, None, "no usable source")
            return

        averaged = round(sum(values) / len(values), ROOM_TEMP_FORWARDING_AVERAGING_DECIMALS)
        offset = self._offsets.get(circuit, 0.0)
        origin = ", ".join(sources)
        await self._async_write_circuit(circuit, averaged + offset, origin)

    def _forwarding_active(self) -> bool:
        if not self._master_enabled:
            return False
        return date_in_season(date.today(), self._season)

    def _warn_once_about_unit(self, entity_id: str, unit: str) -> None:
        """Report a source entity that measures the wrong quantity, once.

        This is a configuration mistake that never fixes itself, so repeating it
        on every cycle would only bury the first message.
        """
        if entity_id in self._reported_unit_mismatches:
            return
        self._reported_unit_mismatches.add(entity_id)
        _LOGGER.warning(
            "Not forwarding IDM %s from %s: it reports %s, which is not a %s. "
            "Select a different entity in the integration options",
            self._value_label,
            entity_id,
            unit,
            self._value_label,
        )

    async def _async_write_circuit(self, circuit: str, temperature: float | None, origin: str) -> None:
        reg = self._register_for_key(self._coordinator, circuit)
        if reg is None:
            _LOGGER.warning(
                "Skipping IDM %s forwarding for %s %s: register not available",
                self._value_label,
                self._key_label,
                circuit,
            )
            return

        if temperature is None:
            sentinels = reg.sentinel_values or ()
            if not sentinels:
                _LOGGER.debug(
                    "IDM %s forwarding for %s %s has no usable source and register %s documents no sentinel; skipping",
                    self._value_label,
                    self._key_label,
                    circuit,
                    reg.name,
                )
                return
            temperature = float(sentinels[0])
        else:
            if reg.min_val is not None and temperature < float(reg.min_val):
                _LOGGER.warning(
                    "Skipping IDM %s forwarding from %s to %s: %.2f is below %.2f",
                    self._value_label,
                    origin,
                    reg.name,
                    temperature,
                    float(reg.min_val),
                )
                return
            if reg.max_val is not None and temperature > float(reg.max_val):
                _LOGGER.warning(
                    "Skipping IDM %s forwarding from %s to %s: %.2f is above %.2f",
                    self._value_label,
                    origin,
                    reg.name,
                    temperature,
                    float(reg.max_val),
                )
                return

        last = self._last_written.get(circuit)
        # GLT RAM inputs are volatile: a controller or Modbus-service restart
        # wipes them (observed live on a Navigator 10: the external room
        # temperature and humidity registers sat at the -1 sentinel for a
        # quarter hour because the tolerance guard suppressed every rewrite of
        # an unchanged value). The tolerance skip may therefore only bridge
        # the gap between two periodic refreshes; each interval pass rewrites
        # the register even when the source value has not moved.
        last_write = self._last_write_monotonic.get(circuit)
        refreshed_recently = last_write is not None and time.monotonic() - last_write < self._config.interval
        if last is not None and refreshed_recently and abs(last - temperature) < self._config.tolerance:
            return

        try:
            await self._coordinator.async_write_register(reg, temperature)
            self._connection_down = False
        except Exception as err:
            error_kind = classify_write_error(err)
            if error_kind == "write_cooldown_active":
                _LOGGER.debug(
                    "Skipping IDM %s forwarding from %s to %s: write cooldown active (%s)",
                    self._value_label,
                    origin,
                    reg.name,
                    write_error_detail(err),
                )
                return
            if error_kind == "write_connection_failed" and self._connection_down:
                _LOGGER.debug("IDM %s forwarding still paused: no Modbus connection", self._value_label)
                return
            if error_kind == "write_connection_failed":
                self._connection_down = True
                # One gray line per outage: the coordinator announces the
                # outage itself (or stays quiet inside its short-outage
                # window); a warning here only produced panic reports for
                # blips that self-healed.
                _LOGGER.info(
                    "Could not forward %s %.2f from %s to %s because %s. "
                    "Check the source sensor and integration configuration",
                    self._value_label,
                    temperature,
                    origin,
                    reg.name,
                    friendly_write_error(error_kind, reg.name),
                )
            else:
                _LOGGER.warning(
                    "Could not forward %s %.2f from %s to %s because %s. "
                    "Check the source sensor and integration configuration",
                    self._value_label,
                    temperature,
                    origin,
                    reg.name,
                    friendly_write_error(error_kind, reg.name),
                )
            _LOGGER.debug("Technical IDM write error for %s: %s", reg.name, write_error_detail(err))
            _LOGGER.debug("Technical %s forwarding error", self._value_label, exc_info=True)
            return

        self._last_written[circuit] = temperature
        self._last_write_monotonic[circuit] = time.monotonic()
        _LOGGER.debug("Forwarded %s %.2f from %s to %s", self._value_label, temperature, origin, reg.name)

    # ------------------------------------------------------------------
    # Runtime controls (master switch, per-source switches, persistence)
    # ------------------------------------------------------------------

    @property
    def circuits(self) -> dict[str, list[str]]:
        """The configured sources per key, for the runtime control entities."""
        return {circuit: list(sources) for circuit, sources in self._sources.items()}

    @property
    def master_enabled(self) -> bool:
        """Whether the master switch allows forwarding at all."""
        return self._master_enabled

    @property
    def season(self) -> SeasonWindow | None:
        """The configured season window, or None when forwarding is year-round."""
        return self._season

    def season_active(self, today: date | None = None) -> bool:
        """Whether the given day (default today) lies inside the season window."""
        return date_in_season(today if today is not None else date.today(), self._season)

    @property
    def forwarding_active(self) -> bool:
        """Whether forwarding is currently effective (switch and season)."""
        return self._master_enabled and self.season_active()

    def source_enabled(self, circuit: str, source: str) -> bool:
        """Whether one source contributes to its key's average."""
        return (circuit, source) not in self._disabled_sources

    async def async_set_master_enabled(self, enabled: bool) -> None:
        """Turn forwarding on or off without reloading the config entry."""
        self._master_enabled = bool(enabled)
        await self._async_save_controls()
        if enabled:
            # Resume with one immediate pass instead of waiting out the interval.
            await self.async_forward_all()

    async def async_set_source_enabled(self, circuit: str, source: str, enabled: bool) -> None:
        """Include or exclude one source from its key's average.

        The key is re-forwarded immediately so the register matches the
        switch positions without waiting out the interval; switching the
        last source off therefore writes the "no value" sentinel right away
        instead of leaving a stale average in the controller.
        """
        if source not in self._sources.get(circuit, []):
            return
        if enabled:
            self._disabled_sources.discard((circuit, source))
        else:
            self._disabled_sources.add((circuit, source))
        await self._async_save_controls()
        if self._forwarding_active():
            await self.async_forward_circuit(circuit)

    async def async_load_controls(self) -> None:
        """Load the persisted switch states once; defaults keep it simple."""
        if self._controls_loaded or self._store is None:
            return
        self._controls_loaded = True
        try:
            stored = await self._store.async_load()
        except Exception:
            _LOGGER.warning("Could not load persisted IDM %s forwarding controls", self._value_label, exc_info=True)
            return
        if not isinstance(stored, dict):
            return
        self._master_enabled = stored.get("master") is not False
        disabled = stored.get("disabled_sources")
        if isinstance(disabled, list):
            configured = {(circuit, source) for circuit, sources in self._sources.items() for source in sources}
            for entry in disabled:
                if isinstance(entry, (list, tuple)) and len(entry) == 2:
                    key = (str(entry[0]), str(entry[1]))
                    if key in configured:
                        self._disabled_sources.add(key)

    async def _async_save_controls(self) -> None:
        if self._store is None:
            return
        try:
            await self._store.async_save(
                {
                    "master": self._master_enabled,
                    "disabled_sources": sorted(list(key) for key in self._disabled_sources),
                }
            )
        except Exception:
            _LOGGER.warning("Could not persist IDM %s forwarding controls", self._value_label, exc_info=True)


@dataclass(frozen=True)
class HumidityForwardingConfig:
    """Runtime configuration for external humidity forwarding."""

    entity_id: str
    interval: int
    tolerance: float


class HumidityForwarder:
    """Copies one HA humidity sensor into the global IDM ext_humidity GLT register."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: IdmCoordinator,
        config: HumidityForwardingConfig,
    ) -> None:
        self._hass = hass
        self._coordinator = coordinator
        self._config = config
        self._reported_unit_mismatch = False
        self._last_written: float | None = None
        self._last_write_monotonic: float | None = None
        self._unsub_state: Callable[[], None] | None = None
        self._pending_forward_task: asyncio.Task[None] | None = None
        self._forward_again = False
        self._forward_lock = asyncio.Lock()
        self._connection_down = False
        self._debounce_seconds = 1.0

    async def async_run(self) -> None:
        """Run forwarding until cancelled."""
        if self._config.entity_id:
            self._unsub_state = async_track_state_change_event(
                self._hass, [self._config.entity_id], self._handle_state_change
            )
        try:
            await self.async_forward()
            while True:
                await asyncio.sleep(self._config.interval)
                try:
                    await self.async_forward()
                except Exception:
                    _LOGGER.exception("IDM humidity forwarding cycle failed; retrying next interval")
        finally:
            if self._pending_forward_task is not None:
                self._pending_forward_task.cancel()
                await asyncio.gather(self._pending_forward_task, return_exceptions=True)
            self._pending_forward_task = None
            if self._unsub_state is not None:
                self._unsub_state()
                self._unsub_state = None

    @callback
    def _handle_state_change(self, event: Any) -> None:
        """Schedule a debounced humidity forward.

        ``@callback`` is required, not decorative: Home Assistant builds a
        ``HassJob`` from this listener, and a plain function without the marker
        is classified as an executor job and run in a worker thread. From there
        ``hass.async_create_task`` is a thread-safety violation that Home
        Assistant reports and that can corrupt loop state (#237).
        """
        entity_id = event.data.get("entity_id")
        if not isinstance(entity_id, str):
            return
        if self._pending_forward_task is not None and not self._pending_forward_task.done():
            self._forward_again = True
            return

        async def _debounced() -> None:
            try:
                while True:
                    # Coalesce bursts without cancelling an in-flight Modbus
                    # request (#493, same race #495 fixed for external power).
                    await asyncio.sleep(self._debounce_seconds)
                    self._forward_again = False
                    await self.async_forward()
                    if not self._forward_again:
                        break
            finally:
                if self._pending_forward_task is asyncio.current_task():
                    self._pending_forward_task = None

        self._pending_forward_task = self._hass.async_create_task(_debounced())

    async def async_forward(self) -> None:
        async with self._forward_lock:
            await self._async_forward_locked()

    async def _async_forward_locked(self) -> None:
        entity_id = self._config.entity_id
        if not entity_id:
            return
        state = self._hass.states.get(entity_id)
        try:
            humidity = _humidity_in_percent(getattr(state, "state", None), _state_unit(state))
        except UnexpectedSourceUnit as err:
            if not self._reported_unit_mismatch:
                self._reported_unit_mismatch = True
                _LOGGER.warning(
                    "Not forwarding IDM humidity from %s: it reports %s, which is not a relative humidity. "
                    "Select a different entity in the integration options",
                    entity_id,
                    err.unit,
                )
            return
        if humidity is None:
            _LOGGER.debug("Skipping IDM humidity forwarding from %s: invalid state", entity_id)
            return

        reg = self._coordinator.get_register("ext_humidity")
        if reg is None:
            _LOGGER.warning("Skipping IDM humidity forwarding: ext_humidity register not available")
            return

        if reg.min_val is not None and humidity < float(reg.min_val):
            _LOGGER.warning(
                "Skipping IDM humidity forwarding from %s to %s: %.2f is below %.2f",
                entity_id,
                reg.name,
                humidity,
                float(reg.min_val),
            )
            return
        if reg.max_val is not None and humidity > float(reg.max_val):
            _LOGGER.warning(
                "Skipping IDM humidity forwarding from %s to %s: %.2f is above %.2f",
                entity_id,
                reg.name,
                humidity,
                float(reg.max_val),
            )
            return

        # Same volatile-RAM reasoning as the temperature forwarder: the
        # tolerance skip only bridges the gap between two periodic refreshes,
        # so a wiped register is rewritten on the next interval pass even with
        # an unchanged source value.
        refreshed_recently = self._last_write_monotonic is not None and (
            time.monotonic() - self._last_write_monotonic < self._config.interval
        )
        if (
            self._last_written is not None
            and refreshed_recently
            and abs(self._last_written - humidity) < self._config.tolerance
        ):
            return

        try:
            await self._coordinator.async_write_register(reg, humidity)
            self._connection_down = False
        except Exception as err:
            error_kind = classify_write_error(err)
            if error_kind == "write_cooldown_active":
                _LOGGER.debug(
                    "Skipping IDM humidity forwarding from %s to %s: write cooldown active (%s)",
                    entity_id,
                    reg.name,
                    write_error_detail(err),
                )
                return
            if error_kind == "write_connection_failed" and self._connection_down:
                _LOGGER.debug("IDM humidity forwarding still paused: no Modbus connection")
                return
            if error_kind == "write_connection_failed":
                self._connection_down = True
                # Same quiet-outage reasoning as the temperature forwarder:
                # one gray line per outage instead of a panic warning.
                _LOGGER.info(
                    "Could not forward humidity %.2f from %s to %s because %s. "
                    "Check the source sensor and integration configuration",
                    humidity,
                    entity_id,
                    reg.name,
                    friendly_write_error(error_kind, reg.name),
                )
            else:
                _LOGGER.warning(
                    "Could not forward humidity %.2f from %s to %s because %s. "
                    "Check the source sensor and integration configuration",
                    humidity,
                    entity_id,
                    reg.name,
                    friendly_write_error(error_kind, reg.name),
                )
            _LOGGER.debug("Technical IDM write error for %s: %s", reg.name, write_error_detail(err))
            _LOGGER.debug("Technical humidity forwarding error", exc_info=True)
            return

        self._last_written = humidity
        self._last_write_monotonic = time.monotonic()
        _LOGGER.debug("Forwarded humidity %.2f from %s to %s", humidity, entity_id, reg.name)
