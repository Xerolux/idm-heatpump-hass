"""Explicit opt-in telemetry to IDM Tools, using a fixed numeric allowlist.

No raw snapshot, entity ID, endpoint, exception text or credentials
crosses this boundary. Missing sources stay absent. Telemetry never adds polls
or writes, and a failed submission is not retried before the next daily slot.
"""

from __future__ import annotations

import asyncio
import logging
import math
import re
import time
import uuid
from datetime import datetime, timedelta
from typing import Any

import aiohttp
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store

from .const import (
    CONF_TELEMETRY,
    CONF_TELEMETRY_CONSENT_AT,
    CONF_TELEMETRY_POLICY,
    CONF_TELEMETRY_SERIAL,
    DOMAIN,
    resolve_connection_mode,
)
from .coordinator import IdmCoordinator, navigator_family

_LOGGER = logging.getLogger(__name__)
TELEMETRY_URL = "https://idmtools.xerolux.de/api/telemetry"
TELEMETRY_POLICY = "idm-telemetry-v1"
_INTERVAL = 86400


def valid_serial(value: object) -> bool:
    """Validate without normalizing, hashing or masking the entered serial."""
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 ./_-]{2,79}", value) is not None


def _version(value: object) -> str | None:
    """Accept version-shaped metadata only, never arbitrary device text."""
    if isinstance(value, str) and re.fullmatch(r"\d{1,4}(?:\.\d{1,4}){1,3}(?:-?(?:b|beta\.|rc\.?|a)\d{1,4})?", value):
        return value
    return None


def _label(value: object) -> str | None:
    """Keep controller metadata unchanged within the declared schema bounds."""
    return value if isinstance(value, str) and 0 < len(value) <= 80 and value.isprintable() else None


def _number(value: object) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= 1e12 and math.isfinite(value):
        return float(value)
    return None


class Telemetry:
    """Observe only already available statistics while consent remains enabled."""

    def __init__(self, hass: Any, entry: Any, coordinator: IdmCoordinator, version: str) -> None:
        self._hass = hass
        self._entry = entry
        self._coordinator = coordinator
        self._version = _version(version)
        self._store: Store[dict[str, Any]] = Store(
            hass, 1, f"{DOMAIN}.telemetry.{entry.entry_id}", serialize_in_event_loop=True
        )
        self._last_attempt = 0.0
        self._started = time.monotonic()
        self._elapsed = 0.0
        self._pending: dict[str, float] = {}
        self._outbox: dict[str, Any] | None = None
        self._outbox_elapsed = 0.0
        self._lock = asyncio.Lock()
        self._stopped = False
        self._save_scheduled = False
        self._active_task: asyncio.Task[Any] | None = None
        self._errors: dict[str, int] = {}
        self._last_error: int | None = None
        self._last_web_alive: bool | None = None
        self._web_outages = 0
        self._baseline = self._totals() if entry.options.get(CONF_TELEMETRY) is True else {}

    def _totals(self) -> dict[str, float]:
        coordinator = self._coordinator
        stats = coordinator.poll_statistics
        sources: dict[str, object] = {
            "modbus_polls": stats.total_polls,
            "modbus_failures": stats.total_failures,
        }
        analysis = coordinator.operation_analysis
        if analysis is not None:
            sources["compressor_starts"] = analysis.total_compressor_starts
            for mode in ("heating", "cooling", "dhw", "defrost"):
                sources[f"{mode}_seconds"] = analysis.mode_durations.get(mode)
        energy = coordinator.energy_statistics
        if energy is not None:
            sources["electrical_kwh"] = energy.total_electrical_kwh
            sources["thermal_kwh"] = energy.total_thermal_kwh
        return {key: number for key, value in sources.items() if (number := _number(value)) is not None}

    def observe(self) -> None:
        """Count observed alarm-code transitions without retaining raw history."""
        if self._stopped or self._entry.options.get(CONF_TELEMETRY) is not True:
            return
        if not self._save_scheduled:
            self._save_scheduled = True
            self._store.async_delay_save(self._delayed_snapshot, 60)
        alive = self._coordinator.web_alive
        if isinstance(alive, bool):
            if alive is False and self._last_web_alive is True:
                self._web_outages += 1
            self._last_web_alive = alive
        if not self._coordinator.last_update_success:
            return
        value = (self._coordinator.data or {}).get("error_number")
        if "error_number" in self._coordinator.unused_registers:
            return
        number = _number(value)
        if number is None or not number.is_integer() or number > 65535:
            return
        code = int(number)
        if code and code != self._last_error:
            key = str(code)
            # Bounded even if a broken source cycles through arbitrary codes.
            if key in self._errors or len(self._errors) < 64:
                self._errors[key] = min(self._errors.get(key, 0) + 1, 1000000)
        self._last_error = code

    def payload(self) -> dict[str, Any]:
        """Compose the complete schema; no fallback to raw diagnostic exports."""
        coordinator = self._coordinator
        totals = self._totals()
        counters = {
            key: round(self._pending.get(key, 0) + value - self._baseline[key], 2)
            for key, value in totals.items()
            if key in self._baseline and value >= self._baseline[key]
        }
        for key, value in self._pending.items():
            counters.setdefault(key, value)
        counters["web_outages"] = self._web_outages
        info = coordinator.model_info
        capabilities = {key: bool(getattr(info, f"has_{key}", False)) for key in ("solar", "pv", "cascade", "isc")}
        return {
            "schema": 1,
            "serial_number": self._entry.options[CONF_TELEMETRY_SERIAL],
            "consent_at": self._entry.options[CONF_TELEMETRY_CONSENT_AT],
            "policy": TELEMETRY_POLICY,
            "integration_version": self._version,
            "navigator": navigator_family(coordinator.model_name),
            "navigator_model": _label(coordinator.model_name),
            "heatpump_model": _label(coordinator.web_supplement.heatpump_model) if coordinator.web_supplement else None,
            "firmware": _label(coordinator.firmware_version),
            "connection_mode": resolve_connection_mode(self._entry.options, self._entry.data),
            "web_variant": coordinator.web_variant if coordinator.web_variant in ("nav10", "nav20") else None,
            "capabilities": capabilities if info is not None else {},
            "register_count": min(len(coordinator.data or {}), 10000),
            "observed_hours": round(min((self._elapsed + time.monotonic() - self._started) / 3600, 8760), 2),
            "counters": counters,
            "error_transitions": dict(self._errors),
        }

    async def async_start(self) -> bool:
        """Persist the daily slot before installing unload-managed callbacks."""
        if (
            self._entry.options.get(CONF_TELEMETRY) is not True
            or not valid_serial(self._entry.options.get(CONF_TELEMETRY_SERIAL))
            or not self._entry.options.get(CONF_TELEMETRY_CONSENT_AT)
            or self._entry.options.get(CONF_TELEMETRY_POLICY) != TELEMETRY_POLICY
        ):
            return False
        stored = await self._store.async_load() or {}
        now = time.time()
        self._baseline = self._totals()
        if stored.get("consent_at") == self._entry.options.get(CONF_TELEMETRY_CONSENT_AT):
            previous = _number(stored.get("last_attempt"))
            self._last_attempt = min(previous, now) if previous is not None else now
            self._pending = self._numeric_mapping(stored.get("counters"))
            self._elapsed = _number(stored.get("observed_seconds")) or 0.0
            saved_totals = self._numeric_mapping(stored.get("totals"))
            for key, value in saved_totals.items():
                # API polling totals restart at zero; plant analysis/energy
                # counters are themselves persistent and continue across boots.
                if (
                    key not in ("modbus_polls", "modbus_failures")
                    and key in self._baseline
                    and value <= self._baseline[key]
                ):
                    self._baseline[key] = value
            saved_errors = stored.get("error_transitions", {})
            if isinstance(saved_errors, dict):
                self._errors = {
                    key: int(value)
                    for key, value in saved_errors.items()
                    if isinstance(key, str)
                    and re.fullmatch(r"[1-9][0-9]{0,4}", key)
                    and isinstance(value, int)
                    and not isinstance(value, bool)
                    and 0 < value <= 1000000
                }
            self._web_outages = int(self._pending.pop("web_outages", 0))
            last_error = _number(stored.get("last_error"))
            self._last_error = int(last_error) if last_error is not None else None
            outbox = stored.get("outbox")
            if (
                isinstance(outbox, dict)
                and set(outbox) == {*self.payload(), "report_id"}
                and outbox.get("serial_number") == self._entry.options[CONF_TELEMETRY_SERIAL]
            ):
                self._outbox = outbox
                self._outbox_elapsed = _number(stored.get("outbox_elapsed")) or 0.0
        else:
            self._last_attempt = now
        await self._store.async_save(self._serialize())
        self._save_scheduled = False
        self._entry.async_on_unload(self.stop)
        self._entry.async_on_unload(self._entry.add_update_listener(self.async_options_updated))
        self._entry.async_on_unload(self._coordinator.async_add_listener(self.observe))
        self._entry.async_on_unload(async_track_time_interval(self._hass, self.async_tick, timedelta(hours=1)))
        self.observe()
        return True

    @staticmethod
    def _numeric_mapping(value: object) -> dict[str, float]:
        if not isinstance(value, dict):
            return {}
        allowed = {
            "modbus_polls",
            "modbus_failures",
            "compressor_starts",
            "heating_seconds",
            "cooling_seconds",
            "dhw_seconds",
            "defrost_seconds",
            "electrical_kwh",
            "thermal_kwh",
            "web_outages",
        }
        return {key: number for key, item in value.items() if key in allowed and (number := _number(item)) is not None}

    def _delayed_snapshot(self) -> dict[str, Any]:
        """Do not postpone persistence indefinitely while observations keep arriving."""
        self._save_scheduled = False
        return self._serialize()

    def _serialize(self) -> dict[str, Any]:
        """One bounded aggregate and one frozen report, never a raw history."""
        if self._stopped or self._entry.options.get(CONF_TELEMETRY) is not True:
            return {}
        return {
            "consent_at": self._entry.options.get(CONF_TELEMETRY_CONSENT_AT),
            "last_attempt": self._last_attempt,
            "counters": self.payload()["counters"],
            "totals": self._totals(),
            "observed_seconds": self._elapsed + time.monotonic() - self._started,
            "error_transitions": dict(self._errors),
            "last_error": self._last_error,
            "outbox": self._outbox,
            "outbox_elapsed": self._outbox_elapsed,
        }

    async def async_stop(self) -> None:
        """Flush on clean reload/shutdown; withdrawal deletes all local aggregates."""
        state = self._serialize() if self._entry.options.get(CONF_TELEMETRY) is True else None
        active = self._active_task
        self.stop()
        if active is not None and active is not asyncio.current_task():
            try:
                await active
            except asyncio.CancelledError:
                pass
        if state is not None:
            await self._store.async_save(state)
        else:
            await self._store.async_remove()

    def stop(self) -> None:
        """Cancel an in-flight attempt and erase in-memory observations on unload."""
        self._stopped = True
        self._errors.clear()
        self._baseline.clear()
        self._web_outages = 0
        self._pending.clear()
        self._outbox = None
        if self._active_task is not None:
            self._active_task.cancel()

    async def async_options_updated(self, hass: Any, entry: Any) -> None:
        """Withdraw immediately while the ordinary reload is being scheduled."""
        del hass
        if entry.options.get(CONF_TELEMETRY) is not True:
            await self.async_stop()

    async def async_tick(self, now: datetime) -> None:
        """Send at most once per 24 hours, including across entry reloads."""
        del now
        if self._stopped or self._entry.options.get(CONF_TELEMETRY) is not True or self._lock.locked():
            return
        async with self._lock:
            current = time.time()
            if current - self._last_attempt < _INTERVAL:
                return
            self._last_attempt = current
            self._active_task = asyncio.current_task()
            try:
                # Freeze and persist before I/O. A lost receipt can be retried
                # with the same report ID without double counting server-side.
                if self._outbox is None:
                    self._outbox = {**self.payload(), "report_id": uuid.uuid4().hex}
                    self._outbox_elapsed = self._elapsed + time.monotonic() - self._started
                await self._store.async_save(self._serialize())
                self._save_scheduled = False
                if self._stopped or self._entry.options.get(CONF_TELEMETRY) is not True:
                    return
                async with async_get_clientsession(self._hass).post(
                    TELEMETRY_URL,
                    json=self._outbox,
                    timeout=aiohttp.ClientTimeout(total=15),
                    allow_redirects=False,
                ) as response:
                    if response.status != 201:
                        _LOGGER.debug("IDM telemetry was not accepted (HTTP %s)", response.status)
                        return
                current_counters = self.payload()["counters"]
                self._pending = {
                    key: max(0.0, value - self._outbox["counters"].get(key, 0))
                    for key, value in current_counters.items()
                }
                self._errors = {
                    key: value - self._outbox["error_transitions"].get(key, 0)
                    for key, value in self._errors.items()
                    if value > self._outbox["error_transitions"].get(key, 0)
                }
                self._web_outages = int(self._pending.pop("web_outages", 0))
                self._elapsed = max(0, self._elapsed + time.monotonic() - self._started - self._outbox_elapsed)
                self._started = time.monotonic()
                self._baseline = self._totals()
                self._outbox = None
                self._outbox_elapsed = 0
                await self._store.async_save(self._serialize())
                self._save_scheduled = False
            except (aiohttp.ClientError, TimeoutError, OSError):
                _LOGGER.debug("IDM telemetry submission unavailable; retaining the report for the next daily slot")
            finally:
                self._active_task = None
