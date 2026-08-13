"""Base entity for IDM Heatpump integration."""

from __future__ import annotations

# IDM Heatpump for Home Assistant
# © 2026 Xerolux — Inoffizielle Community-Integration für IDM Navigator 2.0 / 10 Wärmepumpen
# Erstellt von Xerolux | https://github.com/Xerolux/idm-heatpump-hass
# Lizenz: MIT
import logging
from typing import Any

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from idm_heatpump import RegisterDef

from .const import DOMAIN, MANUFACTURER
from .coordinator import IdmCoordinator
from .device_hierarchy import build_subdevice_info
from .error_messages import classify_write_error, write_error_placeholders

_LOGGER = logging.getLogger(__name__)


def build_entity_unique_id(entry_id: str, entity_key: str) -> str:
    """Build a stable entity unique ID independent of connection settings."""
    return f"{entry_id}_{entity_key}"


def build_device_info(coordinator: IdmCoordinator) -> DeviceInfo:
    """Build device info from the latest coordinator model metadata.

    Cached by a lightweight metadata fingerprint (model, firmware, serial,
    config-entry title) so this stays cheap even when HA calls it for every
    entity on every state update, while still picking up changes the
    fingerprint covers — e.g. a config-entry rename, which only updates
    ``entry.title`` and does not trigger a full coordinator/entry reload.
    """
    cache_key = (
        coordinator.model_name,
        coordinator.firmware_version,
        coordinator.myidm_id,
        coordinator.config_entry.title if coordinator.config_entry is not None else None,
    )
    cache = getattr(coordinator, "_device_info_cache", None)
    if cache is not None and cache[0] == cache_key:
        return cache[1]
    device_info = DeviceInfo(
        identifiers={(DOMAIN, coordinator.config_entry.entry_id)},  # type: ignore[union-attr]
        name=coordinator.config_entry.title,  # type: ignore[union-attr]
        manufacturer=MANUFACTURER,
        model=coordinator.model_name,
    )
    if coordinator.firmware_version:
        device_info["sw_version"] = coordinator.firmware_version
    if coordinator.myidm_id:
        device_info["serial_number"] = coordinator.myidm_id
    coordinator._device_info_cache = (cache_key, device_info)
    return device_info


def should_add_entity(
    coordinator: IdmCoordinator,
    register: RegisterDef,
    *,
    as_writable_control: bool = False,
) -> bool:
    """Return whether a register should be exposed as an entity.

    When ``as_writable_control`` is True and the register is writable, a present
    writable target is still exposed even if its current value is an unset
    sentinel (#172): external inputs must remain addressable when unset. Absent
    and Illegal-Data-Address registers are never exposed.
    """
    if not coordinator.hide_unused:
        return True

    data = coordinator.data
    if not data:
        return True
    if register.name not in data:
        return False
    if as_writable_control and getattr(register, "writable", False):
        # Unsupported (Illegal Data Address) registers are never exposed, even
        # as writable controls; a present, supported writable target stays.
        return register.name not in getattr(coordinator, "unsupported_registers", ())
    return not coordinator.is_register_unused(register.name, data.get(register.name))


class IdmCoordinatorEntityBase(CoordinatorEntity[IdmCoordinator]):
    """Common base for coordinator entities that are not register-backed.

    Provides the shared device_info so non-Modbus entities (web sensors,
    technician-code sensors) stay in sync with the device-info contract
    instead of each re-declaring it.
    """

    _attr_has_entity_name = True

    @property
    def device_info(self) -> DeviceInfo:
        return build_device_info(self.coordinator)


class IdmEntity(IdmCoordinatorEntityBase):
    """Base class for all register-backed IDM Heatpump entities."""

    _writable_control: bool = False

    def __init__(
        self,
        coordinator: IdmCoordinator,
        reg: RegisterDef,
        entity_desc: EntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self._register = reg
        self.entity_description = entity_desc
        entry_id = coordinator.config_entry.entry_id  # type: ignore[union-attr]
        self._attr_unique_id = build_entity_unique_id(entry_id, reg.name)

    @property
    def device_info(self) -> DeviceInfo:
        """Return a subdevice only when hierarchy mode is enabled."""
        return build_subdevice_info(self.coordinator, self._register.name) or build_device_info(self.coordinator)

    async def _async_write_register(self, value: Any, *, action_label: str) -> None:
        """Write a value to this entity's register with centralized error handling.

        All writable platforms route through here so the write-failed translation
        contract (log + raise HomeAssistantError with the write_failed key) stays
        identical across number/select/switch.
        """
        try:
            await self.coordinator.async_write_register(self._register, value)
        except Exception as err:
            translation_key = classify_write_error(err)
            _LOGGER.error(
                "Could not %s %s; Home Assistant will show the actionable %s message",
                action_label,
                self._register.name,
                translation_key,
            )
            _LOGGER.debug("Technical IDM register write error", exc_info=True)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key=translation_key,
                translation_placeholders=write_error_placeholders(self._register.name),
            ) from err

    def is_writable_control(self) -> bool:
        """Whether this entity is a writable control that stays available under sentinel."""
        return self._writable_control and bool(getattr(self._register, "writable", False))

    def _value_is_sentinel(self) -> bool:
        """Return True if the current register value is an unset sentinel.

        Reuses ``is_register_unused`` so no new sentinel literals are introduced
        and the read-only filter stays the single authority. Returns False when
        ``hide_unused`` is off (the user has opted into showing raw values).
        """
        data = self.coordinator.data
        if not data:
            return False
        return self.coordinator.is_register_unused(self._register.name, data.get(self._register.name))

    @property
    def available(self) -> bool:
        if not super().available:
            return False
        if not self.coordinator.data or self._register.name not in self.coordinator.data:
            return False
        if self.is_writable_control():
            # A present writable control stays available even when its value is
            # an unset sentinel; it reports unknown state instead of going
            # unavailable (#172).
            return True
        # The coordinator precomputes the set of unused registers on every
        # successful poll (see IdmCoordinator._async_update_data). Reusing that
        # set here is O(1) and avoids recomputing the unused check for every
        # entity on every state update.
        return self._register.name not in self.coordinator.unused_registers
