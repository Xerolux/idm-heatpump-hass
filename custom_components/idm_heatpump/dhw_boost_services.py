"""Home Assistant services for the safe IDM DHW boost."""

from __future__ import annotations

from collections.abc import Mapping
from functools import partial

import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .coordinator import IdmCoordinator
from .dhw_boost import (
    DhwBoostError,
    DhwBoostManager,
    async_get_dhw_boost_manager,
)

_START_SERVICE = "start_dhw_boost"
_CANCEL_SERVICE = "cancel_dhw_boost"

# Shape only: the ranges mirror services.yaml, while whether the registers
# allow a given target stays with DhwBoostManager, which answers with a
# translated message.
_START_SCHEMA = vol.Schema(
    {
        vol.Optional("entry_id"): cv.string,
        vol.Optional("target_temperature"): vol.All(vol.Coerce(int), vol.Range(min=35, max=65)),
        vol.Optional("timeout_minutes"): vol.All(vol.Coerce(int), vol.Range(min=5, max=240)),
    }
)
_CANCEL_SCHEMA = vol.Schema({vol.Optional("entry_id"): cv.string})


def _translate_boost_error(err: DhwBoostError) -> HomeAssistantError:
    """Convert a DhwBoostError into a translated HomeAssistantError."""
    if err.translation_key:
        return HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key=err.translation_key,
            translation_placeholders=err.translation_placeholders,
        )
    return HomeAssistantError(str(err))


async def _get_manager(
    hass: HomeAssistant,
    call: ServiceCall,
) -> DhwBoostManager:
    data = call.data if isinstance(call.data, Mapping) else {}
    requested_entry_id = str(data.get("entry_id", "")).strip() or None
    loaded_entries = [
        entry for entry in hass.config_entries.async_entries(DOMAIN) if entry.state == ConfigEntryState.LOADED
    ]
    if requested_entry_id is not None:
        loaded_entries = [entry for entry in loaded_entries if str(entry.entry_id) == requested_entry_id]
    if not loaded_entries:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="no_device_configured",
        )
    if requested_entry_id is None and len(loaded_entries) > 1:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="multiple_entries_select_entry",
        )
    runtime_data = loaded_entries[0].runtime_data
    coordinator = getattr(runtime_data, "coordinator", None)
    if not isinstance(coordinator, IdmCoordinator):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="no_device_configured",
        )
    return await async_get_dhw_boost_manager(coordinator)


async def _handle_start(hass: HomeAssistant, call: ServiceCall) -> None:
    manager = await _get_manager(hass, call)
    try:
        await manager.async_start(
            target_temperature=int(
                call.data.get(
                    "target_temperature",
                    manager.default_target_temperature,
                )
            ),
            timeout_minutes=int(
                call.data.get(
                    "timeout_minutes",
                    manager.default_timeout_minutes,
                )
            ),
        )
    except DhwBoostError as err:
        raise _translate_boost_error(err) from err
    except (TypeError, ValueError, OverflowError) as err:
        raise HomeAssistantError(str(err)) from err


async def _handle_cancel(hass: HomeAssistant, call: ServiceCall) -> None:
    manager = await _get_manager(hass, call)
    try:
        await manager.async_cancel()
    except DhwBoostError as err:
        raise _translate_boost_error(err) from err


async def async_setup_dhw_boost_services(hass: HomeAssistant) -> None:
    """Register boost services once for the domain."""
    if not hass.services.has_service(DOMAIN, _START_SERVICE):
        hass.services.async_register(
            DOMAIN,
            _START_SERVICE,
            partial(_handle_start, hass),
            schema=_START_SCHEMA,
        )
    if not hass.services.has_service(DOMAIN, _CANCEL_SERVICE):
        hass.services.async_register(
            DOMAIN,
            _CANCEL_SERVICE,
            partial(_handle_cancel, hass),
            schema=_CANCEL_SCHEMA,
        )
