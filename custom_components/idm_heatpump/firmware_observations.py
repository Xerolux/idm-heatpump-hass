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
from .coordinator import IdmCoordinator, navigator_family
from .firmware_notice import clear_notices, ensure_notice
from .telemetry import _firmware_series, _label, _number

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
_VALID_COMPONENT_STATUS = frozenset({"reported_component", "unconfirmed_pro_product"})


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
            return False
        self._entry.async_on_unload(self.stop)
        self._entry.async_on_unload(self._entry.add_update_listener(self.async_options_updated))
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

    async def async_refresh_firmware(self) -> None:
        """Read only the catalog for this plant; never contact it after refusal."""
        if not self.enabled:
            return
        if self._firmware_task is not None:
            return
        self._firmware_task = asyncio.current_task()
        self._last_firmware_check = time.time()
        self._next_firmware_check = self._last_firmware_check + 21600 + secrets.randbelow(1801)
        coordinator = self._coordinator
        query = {
            "navigator": navigator_family(coordinator.model_name),
            "navigator_model": _label(coordinator.model_name),
            "heatpump_model": _label(coordinator.web_supplement.heatpump_model) if coordinator.web_supplement else None,
            "firmware": _label(coordinator.firmware_version),
        }
        try:
            async with async_get_clientsession(self._hass).post(
                FIRMWARE_URL,
                json=query,
                timeout=aiohttp.ClientTimeout(total=15),
                allow_redirects=False,
            ) as response:
                if response.status != 200:
                    return
                result = await response.json()
            if not self.enabled:
                return
            if (
                not isinstance(result, dict)
                or result.get("query") != query
                or result.get("source") != "community_telemetry"
            ):
                return
            firmware = result.get("latest_firmware")
            if firmware is not None:
                series = _firmware_series(query["firmware"])
                if (
                    _label(firmware) is None
                    or series is None
                    or _firmware_series(firmware) != series
                    or result.get("series") != series
                ):
                    return
            if result.get("status") not in {"observed", "insufficient_identity", "no_matching_observations"}:
                return
            self.firmware_result = {
                "latest_firmware": firmware,
                "installed_firmware": query["firmware"],
                "matching_model": query["heatpump_model"],
                "series": _label(result.get("series")),
                "status": result["status"],
                "model_scope": result.get("model_scope")
                if result.get("model_scope")
                in {"controller_series_only", "controller_and_plant_model", "unconfirmed_component"}
                else None,
                "component_status": result.get("component_status")
                if result.get("component_status") in {"reported_component", "unconfirmed_pro_component"}
                else None,
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
        except (aiohttp.ClientError, TimeoutError, OSError, ValueError):
            _LOGGER.debug("IDM firmware observations unavailable; local plant operation is unaffected")
        finally:
            self._firmware_task = None
            if self.enabled:
                self.firmware_result["next_check"] = datetime.fromtimestamp(self._next_firmware_check, UTC).isoformat()
                for listener in tuple(self._firmware_listeners):
                    listener()
