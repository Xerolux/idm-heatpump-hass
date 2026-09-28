"""Home Assistant control entities for the web-only operating mode (Phase 4).

The WebSocket-first roadmap keeps Modbus as the write path for every
connection mode except ``web_only``: only there do the operating-mode select
and the acknowledge button exist, routed through the local Navigator 10 web
interface (``home/save`` / ``notification/save``). Payloads and response
frames are capture-confirmed (2026-09-28); the API client validates every
value before sending and raises on a controller rejection.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .adapter_enums import get_slug_map_and_key
from .const import CONNECTION_MODE_WEB_ONLY, resolve_connection_mode
from .coordinator import IdmCoordinator
from .entity import build_entity_unique_id

_SYSTEM_MODE_SLUGS, _SYSTEM_MODE_KEY = get_slug_map_and_key("system_mode")


def _web_control_active(coordinator: IdmCoordinator) -> bool:
    """Return whether this entry controls the plant through the web interface."""
    entry: ConfigEntry | None = coordinator.config_entry
    if entry is None:
        return False
    if resolve_connection_mode(entry.options, entry.data) != CONNECTION_MODE_WEB_ONLY:
        return False
    supplement = coordinator.web_supplement
    return supplement is not None and supplement.web_variant == "nav10"


def _system_mode_state(coordinator: IdmCoordinator) -> Any:
    supplement = coordinator.web_supplement
    if supplement is None:
        return None
    overview = supplement.home_overview
    return getattr(overview, "system_mode", None) if overview is not None else None


def web_control_select_entities(coordinator: IdmCoordinator) -> list[IdmWebSystemModeSelect]:
    """Create the web-only operating-mode select for a Navigator 10 entry."""
    if not _web_control_active(coordinator):
        return []
    return [IdmWebSystemModeSelect(coordinator)]


def web_control_number_entities(coordinator: IdmCoordinator) -> list[IdmWebDhwSetpointNumber]:
    """Create the web-only hot-water setpoint number for a Navigator 10 entry."""
    if not _web_control_active(coordinator):
        return []
    return [IdmWebDhwSetpointNumber(coordinator)]


def web_control_button_entities(coordinator: IdmCoordinator) -> list[IdmWebAcknowledgeErrorsButton]:
    """Create the web-only acknowledge button for a Navigator 10 entry."""
    if not _web_control_active(coordinator):
        return []
    return [IdmWebAcknowledgeErrorsButton(coordinator)]


class _IdmWebControlEntityBase(CoordinatorEntity[IdmCoordinator]):
    """Shared placement and availability for the web-only controls."""

    _attr_has_entity_name = True

    @property
    def available(self) -> bool:
        # Web controls are refreshed with the web supplement, independently
        # of the Modbus coordinator result (see IdmWebSensor.available).
        return self.coordinator.web_supplement is not None

    @property
    def device_info(self) -> DeviceInfo:
        from .entity import build_device_info

        return build_device_info(self.coordinator)


class IdmWebSystemModeSelect(_IdmWebControlEntityBase, SelectEntity):
    """Operating mode of a web-only entry, written through ``home/save``."""

    _attr_icon = "mdi:form-dropdown"

    def __init__(self, coordinator: IdmCoordinator) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        assert entry is not None
        self._attr_unique_id = build_entity_unique_id(entry.entry_id, "web_system_mode")
        self._attr_translation_key = _SYSTEM_MODE_KEY
        self._slug_reverse = {slug: value for value, slug in (_SYSTEM_MODE_SLUGS or {}).items()}

    @property
    def options(self) -> list[str]:
        state = _system_mode_state(self.coordinator)
        device_values = set(getattr(state, "options", None) or ())
        return [
            slug for value, slug in (_SYSTEM_MODE_SLUGS or {}).items() if value in (device_values or {0, 1, 2, 3, 4, 5})
        ]

    @property
    def current_option(self) -> str | None:
        state = _system_mode_state(self.coordinator)
        value = getattr(state, "value", None)
        if value is None:
            return None
        return (_SYSTEM_MODE_SLUGS or {}).get(value)

    async def async_select_option(self, slug: str) -> None:
        mode = self._slug_reverse.get(slug)
        if mode is None:
            raise ValueError(f"Unknown operating mode: {slug!r}")
        await self.coordinator.async_web_set_system_mode(mode)


class IdmWebAcknowledgeErrorsButton(_IdmWebControlEntityBase, ButtonEntity):
    """Acknowledge Navigator messages through ``notification/save``."""

    _attr_icon = "mdi:alert-circle-check"
    _attr_translation_key = "acknowledge_errors"

    def __init__(self, coordinator: IdmCoordinator) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        assert entry is not None
        self._attr_unique_id = build_entity_unique_id(entry.entry_id, "web_acknowledge_errors")

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.coordinator.async_web_acknowledge_notifications()


class IdmWebDhwSetpointNumber(_IdmWebControlEntityBase, NumberEntity):
    """Hot-water setpoint of a web-only entry, written through the web.

    Bounds, step and the current value come from the device's own declared
    parameter definition (setting 13256 / FW030); the write is validated
    against exactly that range before anything is sent.
    """

    _attr_icon = "mdi:thermometer-water"
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator: IdmCoordinator) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        assert entry is not None
        self._attr_unique_id = build_entity_unique_id(entry.entry_id, "web_dhw_setpoint")
        self._attr_translation_key = "web_dhw_setpoint"

    def _parameter(self) -> Any:
        supplement = self.coordinator.web_supplement
        if supplement is None:
            return None
        return supplement.dhw_setpoint

    @property
    def available(self) -> bool:
        return super().available and self._parameter() is not None

    @property
    def native_value(self) -> float | None:
        value = getattr(self._parameter(), "value", None)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        return float(value)

    @property
    def native_min_value(self) -> float:
        minimum = getattr(self._parameter(), "min_value", None)
        return float(minimum) if isinstance(minimum, (int, float)) else 30.0

    @property
    def native_max_value(self) -> float:
        maximum = getattr(self._parameter(), "max_value", None)
        return float(maximum) if isinstance(maximum, (int, float)) else 60.0

    @property
    def native_step(self) -> float:
        raw_increment = getattr(self._parameter(), "increment", None)
        if isinstance(raw_increment, str):
            raw_increment = raw_increment.strip()
        try:
            step = float(raw_increment)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            step = 0.5
        return step if step > 0 else 0.5

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_web_set_dhw_setpoint(value)
