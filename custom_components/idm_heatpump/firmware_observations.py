"""Independent, explicitly consented firmware metadata queries without plant identity."""

from __future__ import annotations

import asyncio
import logging
import secrets
import time
from collections.abc import Callable
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
_LOGGER = logging.getLogger(__name__)


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
        # Delay startup queries too: HA updates/reconnections often happen together.
        self._next_firmware_check = time.time() + 1 + secrets.randbelow(1800)
        self.firmware_result = {
            "status": "scheduled",
            "next_check": datetime.fromtimestamp(self._next_firmware_check, UTC).isoformat(),
        }
        for listener in tuple(self._firmware_listeners):
            listener()
        self._entry.async_on_unload(entry_cloud_scheduler(self._hass, self._entry).subscribe(self.async_tick))
        return True

    async def async_tick(self, now: datetime) -> None:
        del now
        if self.enabled and time.time() >= self._next_firmware_check:
            await self.async_refresh_firmware()

    def stop(self) -> None:
        clear_notices(self._hass, self._entry.entry_id)
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
        except (aiohttp.ClientError, TimeoutError, OSError, ValueError):
            _LOGGER.debug("IDM firmware observations unavailable; local plant operation is unaffected")
        finally:
            self._firmware_task = None
            if self.enabled:
                self.firmware_result["next_check"] = datetime.fromtimestamp(self._next_firmware_check, UTC).isoformat()
                for listener in tuple(self._firmware_listeners):
                    listener()
