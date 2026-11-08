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
import secrets
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import aiohttp
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store

from .cloud_scheduler import entry_cloud_scheduler
from .const import (
    CONF_TELEMETRY,
    CONF_TELEMETRY_CONSENT_AT,
    CONF_TELEMETRY_MYIDM,
    CONF_TELEMETRY_POLICY,
    DOMAIN,
    resolve_connection_mode,
)
from .coordinator import IdmCoordinator, navigator_family
from .error_messages import scoped_issue_id

_LOGGER = logging.getLogger(__name__)
TELEMETRY_URL = "https://idmtools.xerolux.de/api/telemetry"
TELEMETRY_PRIVACY_URL = "https://idmtools.xerolux.de/telemetry.html"
TELEMETRY_POLICY = "idm-telemetry-v3"
_INTERVAL = 86400
_DURATIONS = {f"{mode}_seconds" for mode in ("heating", "cooling", "dhw", "defrost")}
# Local delivery outcome labels shared with the diagnostic status entity.
RESULT_ACCEPTED = "accepted"
RESULT_REJECTED = "rejected"
RESULT_UNAVAILABLE = "unavailable"
_RESULTS = {RESULT_ACCEPTED, RESULT_REJECTED, RESULT_UNAVAILABLE}
# One explicit manual submission per minute; the daily slot is unaffected.
MANUAL_COOLDOWN_SECONDS = 60.0
# A repair notice appears only after a full week of undelivered daily reports,
# so transient server outages never surface to the user.
REPAIR_AFTER_FAILED_ATTEMPTS = 7
_TELEMETRY_FAILING = "telemetry_failing"
_REPORT_ID = re.compile(r"[0-9a-f]{32}")


def valid_myidm(value: object) -> bool:
    """Validate without normalizing, hashing or masking the myIDM ID."""
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 ./_-]{2,79}", value) is not None


def _version(value: object) -> str | None:
    """Accept version-shaped metadata only, never arbitrary device text."""
    if isinstance(value, str) and re.fullmatch(r"\d{1,4}(?:\.\d{1,4}){1,3}(?:-?(?:b|beta\.|rc\.?|a)\d{1,4})?", value):
        return value
    return None


def _firmware_series(value: object) -> str | None:
    """Reject cross-channel/major responses independently of the server."""
    if not isinstance(value, str):
        return None
    match = re.fullmatch(
        r"(?P<prefix>[A-Za-z][A-Za-z0-9_]*_)?(?P<major>\d{1,4})(?:\.\d{1,4}){1,3}(?:-\d{1,6}(?:-g[0-9a-fA-F]{4,40})?)?(?:\.iup)?",
        value,
    )
    return (match["prefix"] or "").casefold() + str(int(match["major"])) if match is not None else None


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
        self._next_attempt = 0.0
        self._started = time.monotonic()
        self._elapsed = 0.0
        self._duration_ready = True
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
        # Local delivery bookkeeping; never part of the transmitted schema.
        self._listeners: set[Callable[[], None]] = set()
        self._last_result: str | None = None
        self._last_result_at: float = 0.0
        self._failed_attempts = 0
        self._pending_report_id: str | None = None
        self._baseline = self._totals() if entry.options.get(CONF_TELEMETRY) is True else {}

    @property
    def enabled(self) -> bool:
        """Observations run while the explicit telemetry consent stands."""
        return not self._stopped and self._entry.options.get(CONF_TELEMETRY) is True

    @property
    def manual_cooldown(self) -> float:
        """Seconds an explicit submission must wait after the last attempt."""
        return max(0.0, MANUAL_COOLDOWN_SECONDS - (time.time() - self._last_attempt))

    def status(self) -> dict[str, Any]:
        """Local delivery status for the diagnostic entity; never transmitted."""
        return {
            "status": self._last_result or "not_sent",
            "last_attempt": (
                datetime.fromtimestamp(self._last_attempt, UTC).isoformat() if self._last_attempt > 0 else None
            ),
            "next_attempt": (
                datetime.fromtimestamp(self._next_attempt, UTC).isoformat() if self._next_attempt > 0 else None
            ),
            "last_result_at": (
                datetime.fromtimestamp(self._last_result_at, UTC).isoformat() if self._last_result_at > 0 else None
            ),
            "failed_attempts": self._failed_attempts,
            "pending_report": self._outbox is not None,
            "policy": TELEMETRY_POLICY,
        }

    def async_add_status_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Let the local diagnostic entity follow delivery changes."""
        self._listeners.add(listener)
        return lambda: self._listeners.discard(listener)

    def _notify(self) -> None:
        for listener in tuple(self._listeners):
            listener()

    def _record_result(self, result: str) -> None:
        """Keep the local delivery outcome, streak and repair notice in step."""
        self._last_result = result
        self._last_result_at = time.time()
        self._failed_attempts = 0 if result == RESULT_ACCEPTED else self._failed_attempts + 1
        self._update_repair()
        self._notify()

    def _update_repair(self) -> None:
        """Raise or clear the local delivery notice; never blocks sending."""
        if self._stopped:
            return
        issue_id = scoped_issue_id(self._entry.entry_id, _TELEMETRY_FAILING)
        if self._failed_attempts >= REPAIR_AFTER_FAILED_ATTEMPTS:
            ir.async_create_issue(
                self._hass,
                DOMAIN,
                issue_id,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key=_TELEMETRY_FAILING,
                translation_placeholders={"failed_attempts": str(self._failed_attempts)},
            )
        else:
            ir.async_delete_issue(self._hass, DOMAIN, issue_id)

    @property
    def myidm_id(self) -> str:
        """Use the controller's myIDM ID, with an explicit saved ID as fallback."""
        detected = self._coordinator.myidm_id
        if valid_myidm(detected):
            return str(detected)
        return str(self._entry.options.get(CONF_TELEMETRY_MYIDM, ""))

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

    def _schedule_save(self) -> None:
        """Coalesce persistence of slowly changing local observations."""
        if not self._save_scheduled:
            self._save_scheduled = True
            self._store.async_delay_save(self._delayed_snapshot, 60)

    def observe(self) -> None:
        """Count observed alarm-code transitions without retaining raw history."""
        if self._stopped or self._entry.options.get(CONF_TELEMETRY) is not True:
            return
        self._schedule_save()
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
        if not self._duration_ready:
            counters = {key: value for key, value in counters.items() if key not in _DURATIONS}
        counters["web_outages"] = self._web_outages
        info = coordinator.model_info
        capabilities = {key: bool(getattr(info, f"has_{key}", False)) for key in ("solar", "pv", "cascade", "isc")}
        return {
            "schema": 1,
            "myidm_id": self.myidm_id,
            "consent_at": self._entry.options.get(CONF_TELEMETRY_CONSENT_AT, ""),
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
            or not valid_myidm(self.myidm_id)
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
            # Independent analysis stores may be newer than this checkpoint.
            # Backfilling their extra increments without matching elapsed time
            # makes runtime exceed the observation window after reloads.
            # Resume the saved counters and elapsed pair at current baselines.
            self._duration_ready = stored.get("timebase") == 2 and stored.get("duration_ready") is True
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
            saved_result = stored.get("last_result")
            self._last_result = saved_result if saved_result in _RESULTS else None
            self._last_result_at = _number(stored.get("last_result_at")) or 0.0
            saved_failures = stored.get("failed_attempts")
            self._failed_attempts = (
                saved_failures
                if isinstance(saved_failures, int)
                and not isinstance(saved_failures, bool)
                and 0 <= saved_failures <= 10000
                else 0
            )
            saved_report_id = stored.get("pending_report_id")
            self._pending_report_id = (
                saved_report_id if isinstance(saved_report_id, str) and _REPORT_ID.fullmatch(saved_report_id) else None
            )
            outbox = stored.get("outbox")
            if (
                isinstance(outbox, dict)
                and set(outbox) == {*self.payload(), "report_id"}
                and outbox.get("myidm_id") == self.myidm_id
            ):
                self._outbox = outbox
                self._outbox_elapsed = _number(stored.get("outbox_elapsed")) or 0.0
            elif isinstance(outbox, dict) and isinstance(outbox.get("report_id"), str):
                # A schema change invalidated the frozen report. Keep its ID, so
                # a report the server already stored under it is never counted
                # twice when the recomposed report is submitted.
                report_id = outbox["report_id"]
                if self._pending_report_id is None and _REPORT_ID.fullmatch(report_id):
                    self._pending_report_id = report_id
        else:
            self._last_attempt = now
        scheduled = (
            _number(stored.get("next_attempt"))
            if stored.get("consent_at") == self._entry.options.get(CONF_TELEMETRY_CONSENT_AT)
            else None
        )
        if (
            scheduled is not None
            and now < scheduled <= now + 2 * _INTERVAL
            and scheduled >= self._last_attempt + _INTERVAL
        ):
            self._next_attempt = scheduled
        elif scheduled is not None and scheduled <= now:
            # Reconnect after downtime without synchronizing every overdue client.
            self._next_attempt = max(now + 1 + secrets.randbelow(3600), self._last_attempt + _INTERVAL)
        else:
            # First activation and migration spread reports across a full day.
            self._next_attempt = max(now, self._last_attempt + _INTERVAL) + secrets.randbelow(_INTERVAL + 1)
        await self._store.async_save(self._serialize())
        self._save_scheduled = False
        self._entry.async_on_unload(self.stop)
        self._entry.async_on_unload(self._entry.add_update_listener(self.async_options_updated))
        self._entry.async_on_unload(self._coordinator.async_add_listener(self.observe))
        self._entry.async_on_unload(entry_cloud_scheduler(self._hass, self._entry).subscribe(self.async_tick))
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
            "next_attempt": self._next_attempt,
            "counters": self.payload()["counters"],
            "totals": self._totals(),
            "observed_seconds": self._elapsed + time.monotonic() - self._started,
            "timebase": 2,
            "duration_ready": self._duration_ready,
            "error_transitions": dict(self._errors),
            "last_error": self._last_error,
            "last_result": self._last_result,
            "last_result_at": self._last_result_at,
            "failed_attempts": self._failed_attempts,
            "pending_report_id": self._pending_report_id,
            "outbox": self._outbox,
            "outbox_elapsed": self._outbox_elapsed,
        }

    async def async_stop(self) -> None:
        """Flush on clean reload/shutdown; withdrawal deletes all local aggregates."""
        state = self._serialize() if self._entry.options.get(CONF_TELEMETRY) is True else None
        tasks = {self._active_task}
        self.stop()
        for active in tasks:
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
        self._listeners.clear()
        ir.async_delete_issue(self._hass, DOMAIN, scoped_issue_id(self._entry.entry_id, _TELEMETRY_FAILING))
        if self._active_task is not None:
            self._active_task.cancel()

    async def async_options_updated(self, hass: Any, entry: Any) -> None:
        """Withdraw immediately while the ordinary reload is being scheduled."""
        del hass
        if entry.options.get(CONF_TELEMETRY) is not True:
            await self.async_stop()

    async def async_send_now(self) -> bool:
        """Explicitly submit one report, retaining consent and a one-minute cooldown."""
        before = self._last_attempt
        await self.async_tick(datetime.now().astimezone(), manual=True)
        return self._last_attempt != before and self._outbox is None

    async def async_tick(self, now: datetime, *, manual: bool = False) -> None:
        """Send in the reserved daily slot, or on an explicit manual request."""
        del now
        if (
            self._stopped
            or self._entry.options.get(CONF_TELEMETRY) is not True
            or self._entry.options.get(CONF_TELEMETRY_POLICY) != TELEMETRY_POLICY
            or not self._entry.options.get(CONF_TELEMETRY_CONSENT_AT)
            or not valid_myidm(self.myidm_id)
            or self._lock.locked()
        ):
            return
        async with self._lock:
            current = time.time()
            if (manual and current - self._last_attempt < MANUAL_COOLDOWN_SECONDS) or (
                not manual and (current < self._next_attempt or current - self._last_attempt < _INTERVAL)
            ):
                return
            self._last_attempt = current
            # Reserve the next daily slot before any I/O, including failed attempts.
            self._next_attempt = current + _INTERVAL + secrets.randbelow(3601)
            self._active_task = asyncio.current_task()
            try:
                # Freeze and persist before I/O. A lost receipt can be retried
                # with the same report ID without double counting server-side;
                # a recomposed report after a schema change keeps that ID too.
                if self._outbox is None:
                    report_id = self._pending_report_id or uuid.uuid4().hex
                    self._outbox = {**self.payload(), "report_id": report_id}
                    self._pending_report_id = report_id
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
                        if 400 <= response.status < 500 and response.status != 429:
                            # Permanent rejection: retrying this exact report
                            # daily can never succeed, so drop it and let the
                            # next slot compose a fresh one.
                            _LOGGER.warning(
                                "IDM telemetry report was rejected (HTTP %s); discarding it for a fresh daily report",
                                response.status,
                            )
                            self._outbox = None
                            self._outbox_elapsed = 0
                            self._pending_report_id = None
                            self._record_result(RESULT_REJECTED)
                            await self._store.async_save(self._serialize())
                            self._save_scheduled = False
                        else:
                            # Throttling and server-side faults stay retryable
                            # with the frozen report in the next daily slot.
                            _LOGGER.debug("IDM telemetry was not accepted (HTTP %s)", response.status)
                            self._record_result(RESULT_UNAVAILABLE)
                            self._schedule_save()
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
                self._duration_ready = True
                self._outbox = None
                self._outbox_elapsed = 0
                self._pending_report_id = None
                self._record_result(RESULT_ACCEPTED)
                await self._store.async_save(self._serialize())
                self._save_scheduled = False
            except (aiohttp.ClientError, TimeoutError, OSError):
                _LOGGER.debug("IDM telemetry submission unavailable; retaining the report for the next daily slot")
                self._record_result(RESULT_UNAVAILABLE)
                self._schedule_save()
            finally:
                self._active_task = None
