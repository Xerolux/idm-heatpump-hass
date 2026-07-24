"""Restart-safe domestic hot-water boost control."""

from __future__ import annotations

import asyncio
import logging
import math
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any, Final

from homeassistant.helpers.storage import Store

from .const import DOMAIN
from .coordinator import IdmCoordinator

_LOGGER = logging.getLogger(__name__)

_STORAGE_VERSION: Final = 1
_DEFAULT_TARGET: Final = 60
_DEFAULT_TIMEOUT_MINUTES: Final = 60
_MIN_TARGET: Final = 35
_MAX_TARGET: Final = 65
_MIN_TIMEOUT: Final = 5
_MAX_TIMEOUT: Final = 240
_HOT_WATER_ONLY_MODE: Final = 4


class DhwBoostError(RuntimeError):
    """Raised when a DHW boost cannot be started or restored safely.

    Carries a Home Assistant translation key + placeholders so the service
    handlers and button entities can surface a localized error instead of
    the raw German developer message.
    """

    def __init__(
        self,
        message: str,
        *,
        translation_key: str | None = None,
        translation_placeholders: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.translation_key = translation_key
        self.translation_placeholders = translation_placeholders or {}


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _finite_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    result = float(value)
    return result if math.isfinite(result) else None


class DhwBoostManager:
    """Temporarily prioritize DHW and restore the exact previous state."""

    def __init__(self, coordinator: IdmCoordinator) -> None:
        config_entry = coordinator.config_entry
        if config_entry is None:
            raise DhwBoostError(
                "Der Konfigurationseintrag ist nicht verfügbar",
                translation_key="dhw_boost_no_entry",
            )
        self.coordinator = coordinator
        self._entry = config_entry
        self._store: Store[dict[str, Any]] = Store(
            coordinator.hass,
            _STORAGE_VERSION,
            f"{DOMAIN}.dhw_boost.{config_entry.entry_id}",
        )
        self._lock = asyncio.Lock()
        self._timeout_task: asyncio.Task[None] | None = None
        self._evaluation_task: asyncio.Task[None] | None = None
        self._evaluation_in_progress = False
        self._unsub_coordinator: Callable[[], None] | None = None
        self._setup_complete = False

        self.active = False
        self.status = "idle"
        self.target_temperature: int | None = None
        self.timeout_minutes: int | None = None
        self.started_at: datetime | None = None
        self.deadline: datetime | None = None
        self.previous_mode: int | None = None
        self.previous_setpoint: int | None = None
        self.last_reason: str | None = None

    @property
    def default_target_temperature(self) -> int:
        return _DEFAULT_TARGET

    @property
    def default_timeout_minutes(self) -> int:
        return _DEFAULT_TIMEOUT_MINUTES

    @property
    def supported(self) -> bool:
        mode = self.coordinator.get_register("system_mode")
        setpoint = self.coordinator.get_register("dhw_setpoint")
        current = self.coordinator.get_register("dhw_temp_top")
        return bool(mode and mode.writable and setpoint and setpoint.writable and current)

    async def async_setup(self) -> None:
        """Load persisted recovery data and subscribe to coordinator updates."""
        if self._setup_complete:
            return
        self._setup_complete = True
        self._unsub_coordinator = self.coordinator.async_add_listener(self._handle_coordinator_update)
        try:
            stored = await self._store.async_load()
        except Exception:
            _LOGGER.warning("Could not load persisted IDM DHW boost state", exc_info=True)
            return
        if not isinstance(stored, dict) or stored.get("active") is not True:
            return

        self.active = True
        self.status = "recovery_required"
        self.target_temperature = self._safe_int(stored.get("target_temperature"))
        self.timeout_minutes = self._safe_int(stored.get("timeout_minutes"))
        self.started_at = _parse_datetime(stored.get("started_at"))
        self.deadline = _parse_datetime(stored.get("deadline"))
        self.previous_mode = self._safe_int(stored.get("previous_mode"))
        self.previous_setpoint = self._safe_int(stored.get("previous_setpoint"))
        self.last_reason = "startup_recovery"

        async with self._lock:
            try:
                await self._async_restore_locked("startup_recovery")
            except Exception:
                _LOGGER.exception(
                    "IDM DHW boost recovery could not restore the previous state; "
                    "the integration will retry on coordinator updates",
                )
        self._notify()

    async def async_start(
        self,
        *,
        target_temperature: int = _DEFAULT_TARGET,
        timeout_minutes: int = _DEFAULT_TIMEOUT_MINUTES,
    ) -> None:
        """Persist the snapshot, then activate DHW priority and target."""
        async with self._lock:
            if self.active:
                raise DhwBoostError(
                    "Der Warmwasser-Boost ist bereits aktiv; zuerst abbrechen",
                    translation_key="dhw_boost_already_active",
                )
            if not self.supported:
                raise DhwBoostError(
                    "Die benötigten Warmwasser- und Systemmodusregister sind nicht verfügbar",
                    translation_key="dhw_boost_unsupported",
                )

            target = self._validated_target(target_temperature)
            timeout = self._validated_timeout(timeout_minutes)
            data = self.coordinator.data or {}
            current_temperature = _finite_number(data.get("dhw_temp_top"))
            if current_temperature is None:
                raise DhwBoostError(
                    "Die aktuelle Warmwassertemperatur ist nicht verfügbar",
                    translation_key="dhw_boost_no_current_temp",
                )
            if current_temperature >= target:
                self.status = "idle"
                self.last_reason = "target_already_reached"
                self.target_temperature = target
                self.timeout_minutes = timeout
                self._notify()
                return

            previous_mode = self._safe_int(data.get("system_mode"))
            previous_setpoint = self._safe_int(data.get("dhw_setpoint"))
            if previous_mode is None or previous_setpoint is None:
                raise DhwBoostError(
                    "Systemmodus oder bisheriger Warmwasser-Sollwert ist nicht verfügbar",
                    translation_key="dhw_boost_no_previous_state",
                )

            now = _utcnow()
            self.active = True
            self.status = "starting"
            self.target_temperature = target
            self.timeout_minutes = timeout
            self.started_at = now
            self.deadline = now + timedelta(minutes=timeout)
            self.previous_mode = previous_mode
            self.previous_setpoint = previous_setpoint
            self.last_reason = None

            # Persist before the first device write. This is the recovery
            # contract if Home Assistant stops between the two writes.
            await self._async_save()
            self._notify()

            try:
                await self._async_write("dhw_setpoint", target)
                await self._async_write("system_mode", _HOT_WATER_ONLY_MODE)
            except Exception as err:
                self.status = "start_failed"
                self.last_reason = "start_failed"
                await self._async_save()
                try:
                    await self._async_restore_locked("start_failed_rollback")
                except Exception:  # noqa: BLE001
                    raise DhwBoostError(
                        "Boost-Start fehlgeschlagen und der vorherige Zustand konnte "
                        "noch nicht vollständig wiederhergestellt werden",
                        translation_key="dhw_boost_start_failed_rollback_incomplete",
                    ) from err
                raise DhwBoostError(
                    "Boost-Start fehlgeschlagen; der vorherige Zustand wurde wiederhergestellt",
                    translation_key="dhw_boost_start_failed_rolled_back",
                ) from err

            self.status = "active"
            await self._async_save()
            self._schedule_timeout()
            self._notify()

    async def async_cancel(self) -> None:
        """Cancel an active boost and restore the exact saved snapshot."""
        async with self._lock:
            if not self.active:
                self.status = "idle"
                self.last_reason = "not_active"
                self._notify()
                return
            await self._async_restore_locked("manual_cancel")

    async def async_shutdown(self) -> None:
        """Restore before platform unload while the Modbus connection is alive."""
        async with self._lock:
            if self.active:
                try:
                    await self._async_restore_locked("integration_unload")
                except Exception:
                    _LOGGER.exception(
                        "Could not restore IDM DHW boost state during unload; persisted recovery remains active",
                    )
            self._cancel_timeout()
            if self._evaluation_task is not None:
                self._evaluation_task.cancel()
                self._evaluation_task = None
            if self._unsub_coordinator is not None:
                self._unsub_coordinator()
                self._unsub_coordinator = None

    def _handle_coordinator_update(self) -> None:
        if not self.active or self._evaluation_in_progress or self._evaluation_task is not None:
            return
        self._evaluation_task = self.coordinator.hass.async_create_task(self._async_evaluate())

    async def _async_evaluate(self) -> None:
        if self._evaluation_in_progress:
            return
        self._evaluation_in_progress = True
        try:
            async with self._lock:
                if not self.active:
                    return
                if self.status == "recovery_required":
                    try:
                        await self._async_restore_locked(self.last_reason or "recovery_retry")
                    except Exception:
                        _LOGGER.warning(
                            "IDM DHW boost recovery retry failed; retrying on next update",
                            exc_info=True,
                        )
                    return

                now = _utcnow()
                if self.deadline is not None and now >= self.deadline:
                    try:
                        await self._async_restore_locked("timeout")
                    except DhwBoostError:
                        _LOGGER.warning(
                            "IDM DHW boost timed out and the previous state could not be fully "
                            "restored yet; recovery will retry on the next coordinator update",
                            exc_info=True,
                        )
                    return

                data = self.coordinator.data or {}
                current_temperature = _finite_number(data.get("dhw_temp_top"))
                if (
                    current_temperature is not None
                    and self.target_temperature is not None
                    and current_temperature >= self.target_temperature
                ):
                    try:
                        await self._async_restore_locked("target_reached")
                    except DhwBoostError:
                        _LOGGER.warning(
                            "IDM DHW boost target reached and the previous state could not be fully "
                            "restored yet; recovery will retry on the next coordinator update",
                            exc_info=True,
                        )
                    return

                # Boost owns only these two values until cancel/end. PV/SG and
                # all unrelated registers are deliberately untouched.
                try:
                    if data.get("dhw_setpoint") != self.target_temperature:
                        await self._async_write(
                            "dhw_setpoint",
                            self.target_temperature,
                        )
                    if data.get("system_mode") != _HOT_WATER_ONLY_MODE:
                        await self._async_write("system_mode", _HOT_WATER_ONLY_MODE)
                except Exception:
                    self.status = "enforcement_failed"
                    self.last_reason = "enforcement_failed"
                    await self._async_save()
                    _LOGGER.warning(
                        "Could not re-apply IDM DHW boost priority; retrying on next update",
                        exc_info=True,
                    )
        finally:
            # Notify while the recursion guard is still active. Otherwise the
            # manager would schedule itself again from its own status update.
            self._notify()
            self._evaluation_in_progress = False
            if self._evaluation_task is asyncio.current_task():
                self._evaluation_task = None

    async def _async_timeout(self) -> None:
        if self.deadline is None:
            return
        delay = max(0.0, (self.deadline - _utcnow()).total_seconds())
        await asyncio.sleep(delay)
        await self._async_evaluate()

    def _schedule_timeout(self) -> None:
        self._cancel_timeout()
        self._timeout_task = self.coordinator.hass.async_create_task(self._async_timeout())

    def _cancel_timeout(self) -> None:
        task = self._timeout_task
        if task is not None and task is not asyncio.current_task():
            task.cancel()
        self._timeout_task = None

    async def _async_restore_locked(self, reason: str) -> None:
        if self.previous_setpoint is None or self.previous_mode is None:
            self.status = "recovery_invalid"
            self.last_reason = "invalid_recovery_state"
            self.active = False
            await self._async_save()
            self._notify()
            raise DhwBoostError(
                "Gespeicherter Wiederherstellungszustand ist unvollständig",
                translation_key="dhw_boost_invalid_recovery_state",
            )

        self.status = "restoring"
        self.last_reason = reason
        await self._async_save()
        try:
            await self._async_write("dhw_setpoint", self.previous_setpoint)
            await self._async_write("system_mode", self.previous_mode)
        except Exception as err:
            self.status = "recovery_required"
            await self._async_save()
            self._notify()
            raise DhwBoostError(
                "Der vorherige Warmwasserzustand konnte noch nicht vollständig wiederhergestellt werden",
                translation_key="dhw_boost_restore_failed",
            ) from err

        self._cancel_timeout()
        self.active = False
        self.status = "idle"
        self.last_reason = reason
        await self._async_save()
        self._notify()

    async def _async_write(self, register_name: str, value: Any) -> None:
        register = self.coordinator.get_register(register_name)
        if register is None or not register.writable:
            raise DhwBoostError(
                f"Register {register_name} ist nicht schreibbar",
                translation_key="dhw_boost_register_not_writable",
                translation_placeholders={"register": register_name},
            )
        await self.coordinator.async_write_register(register, value)

    async def _async_save(self) -> None:
        await self._store.async_save(
            {
                "active": self.active,
                "status": self.status,
                "target_temperature": self.target_temperature,
                "timeout_minutes": self.timeout_minutes,
                "started_at": self._iso(self.started_at),
                "deadline": self._iso(self.deadline),
                "previous_mode": self.previous_mode,
                "previous_setpoint": self.previous_setpoint,
                "last_reason": self.last_reason,
            }
        )

    def _notify(self) -> None:
        self.coordinator.async_update_listeners()

    @staticmethod
    def _iso(value: datetime | None) -> str | None:
        return value.isoformat() if value is not None else None

    @staticmethod
    def _safe_int(value: Any) -> int | None:
        if isinstance(value, bool):
            return None
        try:
            return int(value)
        except (TypeError, ValueError, OverflowError):
            return None

    def _validated_target(self, value: Any) -> int:
        target = self._safe_int(value)
        register = self.coordinator.get_register("dhw_setpoint")
        if target is None or register is None:
            raise DhwBoostError(
                "Ungültige Warmwasser-Zieltemperatur",
                translation_key="dhw_boost_invalid_target",
            )
        minimum = max(
            _MIN_TARGET,
            int(register.min_val) if register.min_val is not None else _MIN_TARGET,
        )
        maximum = min(
            _MAX_TARGET,
            int(register.max_val) if register.max_val is not None else _MAX_TARGET,
        )
        if not minimum <= target <= maximum:
            raise DhwBoostError(
                f"Warmwasser-Zieltemperatur muss zwischen {minimum} und {maximum} °C liegen",
                translation_key="dhw_boost_target_out_of_range",
                translation_placeholders={"minimum": str(minimum), "maximum": str(maximum)},
            )
        return target

    @staticmethod
    def _validated_timeout(value: Any) -> int:
        timeout = DhwBoostManager._safe_int(value)
        if timeout is None or not _MIN_TIMEOUT <= timeout <= _MAX_TIMEOUT:
            raise DhwBoostError(
                f"Boost-Laufzeit muss zwischen {_MIN_TIMEOUT} und {_MAX_TIMEOUT} Minuten liegen",
                translation_key="dhw_boost_timeout_out_of_range",
                translation_placeholders={"minimum": str(_MIN_TIMEOUT), "maximum": str(_MAX_TIMEOUT)},
            )
        return timeout

    @property
    def state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data or {}
        current_temperature = _finite_number(data.get("dhw_temp_top"))
        return {
            "active": self.active,
            "status": self.status,
            "target_temperature": self.target_temperature,
            "current_temperature": current_temperature,
            "timeout_minutes": self.timeout_minutes,
            "started_at": self.started_at,
            "deadline": self.deadline,
            "last_reason": self.last_reason,
            "priority": "dhw_setpoint_and_hot_water_only_until_end_or_cancel",
        }


async def async_get_dhw_boost_manager(
    coordinator: IdmCoordinator,
) -> DhwBoostManager:
    """Return one configured manager per coordinator."""
    existing = getattr(coordinator, "_dhw_boost_manager", None)
    if isinstance(existing, DhwBoostManager):
        await existing.async_setup()
        return existing
    manager = DhwBoostManager(coordinator)
    coordinator._dhw_boost_manager = manager
    await manager.async_setup()
    return manager
