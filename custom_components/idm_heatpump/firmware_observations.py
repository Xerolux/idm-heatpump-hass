"""Independent, explicitly consented firmware metadata queries without plant identity."""

from __future__ import annotations

import asyncio
import logging
import secrets
import time
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any

import aiohttp
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .cloud_scheduler import entry_cloud_scheduler
from .const import CONF_FIRMWARE_CHECK, CONF_FIRMWARE_CONSENT_AT, CONF_FIRMWARE_POLICY
from .coordinator import IdmCoordinator
from .firmware_notice import clear_notices, ensure_notice
from .telemetry import _firmware_identity, _firmware_series, _label, _number, _plant_model, _reported_firmware

FIRMWARE_URL = "https://idmtools.xerolux.de/api/telemetry/firmware"
FIRMWARE_POLICY = "idm-firmware-v1"
#: entry.data key holding the last validated server answer so the firmware
#: entities survive a restart. Must stay listed in ``_DETECTION_ONLY_DATA_KEYS``
#: (see ``__init__``) so persisting it never reloads the entry.
FIRMWARE_RESULT_DATA_KEY = "firmware_observation_result"
_LOGGER = logging.getLogger(__name__)

#: Result keys that are worth restoring; scheduling keys are re-derived.
_PERSISTED_RESULT_KEYS = (
    "latest_firmware",
    "installed_firmware",
    "matching_model",
    "series",
    "status",
    "model_scope",
    "component_status",
    "source",
    "newer_observed",
    "observations",
    "last_checked",
)
_VALID_STATUS = frozenset({"observed", "insufficient_identity", "no_matching_observations"})
_VALID_MODEL_SCOPES = frozenset({"controller_series_only", "controller_and_plant_model", "unconfirmed_component"})
_VALID_COMPONENT_STATUS = frozenset({"reported_component", "unconfirmed_pro_component"})
#: Outcome of one catalog check. Local bookkeeping for the service response and
#: the diagnostic entity; never transmitted.
CHECK_COMPLETED = "completed"
CHECK_UNAVAILABLE = "unavailable"
CHECK_IN_PROGRESS = "in_progress"
CHECK_WITHDRAWN = "consent_required"
#: A changed firmware is checked at the next tick instead of after six hours,
#: but never more often than this, so a flickering source cannot hammer the catalog.
_RECHECK_SECONDS = 900.0


def _restorable_result(stored: Any) -> dict[str, Any] | None:
    """Return a validated copy of a persisted result, or ``None``.

    Restoring never trusts the stored shape: unknown or mistyped values fall
    back to ``None``, and a payload without the identity of a real answer
    (source, status, check time) is ignored entirely so a corrupted or
    hand-edited entry cannot fabricate a firmware observation.
    """
    if not isinstance(stored, Mapping):
        return None
    restored: dict[str, Any] = {key: None for key in _PERSISTED_RESULT_KEYS}
    for key in ("latest_firmware", "installed_firmware", "matching_model", "series", "last_checked"):
        value = stored.get(key)
        restored[key] = value if isinstance(value, str) else None
    status = stored.get("status")
    restored["status"] = status if status in _VALID_STATUS else None
    model_scope = stored.get("model_scope")
    restored["model_scope"] = model_scope if model_scope in _VALID_MODEL_SCOPES else None
    component_status = stored.get("component_status")
    restored["component_status"] = component_status if component_status in _VALID_COMPONENT_STATUS else None
    if stored.get("source") != "community_telemetry":
        return None
    newer = stored.get("newer_observed")
    restored["newer_observed"] = newer if isinstance(newer, bool) else None
    observations = stored.get("observations")
    restored["observations"] = (
        observations if isinstance(observations, int) and not isinstance(observations, bool) else None
    )
    if restored["status"] is None or restored["last_checked"] is None:
        return None
    return restored


class FirmwareObservations:
    """Query a public cohort without telemetry consent, identity or a local queue."""

    def __init__(self, hass: Any, entry: Any, coordinator: IdmCoordinator) -> None:
        self._hass = hass
        self._entry = entry
        self._coordinator = coordinator
        self._stopped = False
        self._firmware_task: asyncio.Task[Any] | None = None
        self._last_firmware_check = 0.0
        self._next_firmware_check = 0.0
        self._firmware_listeners: set[Callable[[], None]] = set()
        self.firmware_result: dict[str, Any] = {}
        self._last_check_outcome: str | None = None
        #: The firmware sent in the last query; a later different value is a change.
        self._queried_firmware: str | None = None

    @property
    def enabled(self) -> bool:
        """Never inherit consent from the analytics switch or an old notice."""
        return (
            not self._stopped
            and self._entry.options.get(CONF_FIRMWARE_CHECK) is True
            and self._entry.options.get(CONF_FIRMWARE_POLICY) == FIRMWARE_POLICY
            and bool(self._entry.options.get(CONF_FIRMWARE_CONSENT_AT))
        )

    async def async_start(self) -> bool:
        if not self.enabled:
            # The stored answer and its notice belong to a consent that no
            # longer holds; they must not outlive it until a later disable.
            clear_notices(self._hass, self._entry.entry_id)
            self._forget_stored_result()
            return False
        self._entry.async_on_unload(self.stop)
        self._entry.async_on_unload(self._entry.add_update_listener(self.async_options_updated))
        self._entry.async_on_unload(self._coordinator.async_add_listener(self.observe_firmware))
        # The firmware known at startup is not a change; only a later one is.
        self._queried_firmware = _reported_firmware(self._coordinator)
        # Startup queries keep their load spreading, but within the first
        # 15 minutes (random) instead of 30: HA updates/reconnections often
        # happen together, and the restored last answer bridges the window.
        self._next_firmware_check = time.time() + 1 + secrets.randbelow(900)
        # The load-spreading delay stays, but the last validated answer now
        # survives the restart: the sensor keeps showing it (with its true
        # last_checked time) while the delayed first check runs, and a failed
        # check keeps it until the next one succeeds.
        self.firmware_result = self._restored_result() or {"status": "scheduled"}
        self.firmware_result["next_check"] = datetime.fromtimestamp(self._next_firmware_check, UTC).isoformat()
        for listener in tuple(self._firmware_listeners):
            listener()
        self._entry.async_on_unload(entry_cloud_scheduler(self._hass, self._entry).subscribe(self.async_tick))
        return True

    def _restored_result(self) -> dict[str, Any] | None:
        """Read the persisted last answer from the config entry."""
        data = getattr(self._entry, "data", None)
        if not isinstance(data, Mapping):
            return None
        return _restorable_result(data.get(FIRMWARE_RESULT_DATA_KEY))

    def _persist_result(self) -> None:
        """Store the last validated answer so a restart does not blank it."""
        entry = self._entry
        data = getattr(entry, "data", None)
        if not isinstance(data, Mapping):
            return
        payload = {key: self.firmware_result.get(key) for key in _PERSISTED_RESULT_KEYS}
        update = getattr(getattr(self._hass, "config_entries", None), "async_update_entry", None)
        if not callable(update):
            return
        try:
            update(entry, data={**data, FIRMWARE_RESULT_DATA_KEY: payload})
        except Exception:
            _LOGGER.debug("Failed to persist the IDM firmware observation result", exc_info=True)

    def _forget_stored_result(self) -> None:
        """Drop the persisted answer together with its consent."""
        entry = self._entry
        data = getattr(entry, "data", None)
        if not isinstance(data, Mapping) or FIRMWARE_RESULT_DATA_KEY not in data:
            return
        update = getattr(getattr(self._hass, "config_entries", None), "async_update_entry", None)
        if not callable(update):
            return
        try:
            update(entry, data={key: value for key, value in data.items() if key != FIRMWARE_RESULT_DATA_KEY})
        except Exception:
            _LOGGER.debug("Failed to remove the stored IDM firmware observation result", exc_info=True)

    async def async_tick(self, now: datetime) -> None:
        del now
        if self.enabled and time.time() >= self._next_firmware_check:
            await self.async_refresh_firmware()

    def observe_firmware(self) -> None:
        """Check a changed firmware at the next tick instead of after six hours."""
        # Before the first scheduled check nothing is a change: the random
        # startup slot must survive a firmware that arrives late or at once.
        if not self.enabled or self._firmware_task is not None or not self._last_firmware_check:
            return
        current = _reported_firmware(self._coordinator)
        if current is None or current == self._queried_firmware:
            return
        if time.time() - self._last_firmware_check < _RECHECK_SECONDS:
            return
        self._next_firmware_check = 0.0

    @property
    def check_state(self) -> str:
        """Local outcome of the last check since startup; never transmitted."""
        return self._last_check_outcome or "not_checked"

    def check_status(self) -> dict[str, Any]:
        """Local check bookkeeping for the diagnostic entity; never transmitted."""
        return {
            "last_outcome": self._last_check_outcome or "not_checked",
            "last_check": (
                datetime.fromtimestamp(self._last_firmware_check, UTC).isoformat()
                if self._last_firmware_check > 0
                else None
            ),
            "next_check": self.firmware_result.get("next_check"),
            "firmware_checked": self._queried_firmware,
        }

    def stop(self) -> None:
        # The persistent repairs notice deliberately survives an ordinary
        # unload (restart, reload): Home Assistant keeps its dismissed state,
        # and re-creating it with the same issue id preserves a dismissal.
        # Wiping it here would resurrect "newer firmware observed" after every
        # restart. Cleanup happens on consent withdrawal (async_options_updated)
        # and through the issue's config_entry_id when the entry is removed.
        self._stopped = True
        self.firmware_result.clear()
        self._firmware_listeners.clear()
        if self._firmware_task is not None:
            self._firmware_task.cancel()

    async def async_stop(self) -> None:
        task = self._firmware_task
        self.stop()
        if task is not None and task is not asyncio.current_task():
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def async_options_updated(self, hass: Any, entry: Any) -> None:
        del hass, entry
        if not self.enabled:
            # Consent is gone: notice and stored answer follow it out.
            clear_notices(self._hass, self._entry.entry_id)
            self._forget_stored_result()
            await self.async_stop()

    def async_add_firmware_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Subscribe the opt-in firmware entity without notifying other consumers."""
        self._firmware_listeners.add(listener)
        return lambda: self._firmware_listeners.discard(listener)

    async def async_refresh_firmware(self) -> str:
        """Read only the catalog for this plant; return what this check achieved."""
        if not self.enabled:
            return CHECK_WITHDRAWN
        if self._firmware_task is not None:
            return CHECK_IN_PROGRESS
        self._firmware_task = asyncio.current_task()
        self._last_firmware_check = time.time()
        self._next_firmware_check = self._last_firmware_check + 21600 + secrets.randbelow(1801)
        coordinator = self._coordinator
        installed = _reported_firmware(coordinator)
        family, model = _firmware_identity(coordinator.model_name, installed)
        query = {
            "navigator": family,
            "navigator_model": model,
            "heatpump_model": _plant_model(coordinator, self._entry.options),
            "firmware": installed,
        }
        # Whatever this check achieves, this is the firmware the catalog was asked about.
        self._queried_firmware = installed
        outcome = CHECK_UNAVAILABLE
        try:
            async with async_get_clientsession(self._hass).post(
                FIRMWARE_URL,
                json=query,
                timeout=aiohttp.ClientTimeout(total=15),
                allow_redirects=False,
            ) as response:
                status = response.status
                result = await response.json() if status == 200 else None
            if not self.enabled:
                # Consent was withdrawn while the request was in flight.
                return CHECK_WITHDRAWN
            if status != 200:
                _LOGGER.debug(
                    "IDM firmware catalog answered with HTTP %s; the last observation is kept",
                    status,
                )
                return outcome
            if (
                not isinstance(result, dict)
                or result.get("query") != query
                or result.get("source") != "community_telemetry"
            ):
                _LOGGER.debug("IDM firmware catalog answer does not belong to this query; the last observation is kept")
                return outcome
            firmware = result.get("latest_firmware")
            if firmware is not None:
                series = _firmware_series(query["firmware"])
                if (
                    _label(firmware) is None
                    or series is None
                    or _firmware_series(firmware) != series
                    or result.get("series") != series
                ):
                    _LOGGER.debug("IDM firmware catalog answer left the installed series; the last observation is kept")
                    return outcome
            if result.get("status") not in _VALID_STATUS:
                _LOGGER.debug("IDM firmware catalog answer carries an unknown status; the last observation is kept")
                return outcome
            self.firmware_result = {
                "latest_firmware": firmware,
                "installed_firmware": query["firmware"],
                "matching_model": query["heatpump_model"],
                "series": _label(result.get("series")),
                "status": result["status"],
                "model_scope": result.get("model_scope") if result.get("model_scope") in _VALID_MODEL_SCOPES else None,
                "component_status": (
                    result.get("component_status")
                    if result.get("component_status") in _VALID_COMPONENT_STATUS
                    else None
                ),
                "source": "community_telemetry",
                "newer_observed": result.get("newer_observed")
                if isinstance(result.get("newer_observed"), bool)
                and result.get("model_scope") != "unconfirmed_component"
                else None,
                "observations": _number(result.get("observations")),
                "last_checked": datetime.fromtimestamp(self._last_firmware_check, UTC).isoformat(),
            }
            ensure_notice(self._hass, self._entry, self.firmware_result)
            self._persist_result()
            outcome = CHECK_COMPLETED
        except (aiohttp.ClientError, TimeoutError, OSError, ValueError) as error:
            # Exception text can carry endpoint details, so only its type is logged.
            _LOGGER.debug(
                "IDM firmware observations unavailable (%s); local plant operation is unaffected",
                type(error).__name__,
            )
        finally:
            self._firmware_task = None
            self._last_check_outcome = outcome
            if self.enabled:
                self.firmware_result["next_check"] = datetime.fromtimestamp(self._next_firmware_check, UTC).isoformat()
                for listener in tuple(self._firmware_listeners):
                    listener()
        return outcome
