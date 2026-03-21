"""Service handlers for IDM Navigator Heatpump integration."""

import logging
from typing import Any

from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .modbus_client import DataType, RegisterDef

_LOGGER = logging.getLogger(__name__)

_SERVICES = ["set_system_mode", "acknowledge_errors", "write_register"]


async def async_setup_services(hass: HomeAssistant) -> None:
    """Register services only if not already registered."""
    if hass.services.has_service(DOMAIN, "set_system_mode"):
        return

    hass.services.async_register(
        DOMAIN,
        "set_system_mode",
        _handle_set_system_mode,
    )
    hass.services.async_register(
        DOMAIN,
        "acknowledge_errors",
        _handle_acknowledge_errors,
    )
    hass.services.async_register(
        DOMAIN,
        "write_register",
        _handle_write_register,
        supports_response=SupportsResponse.OPTIONAL,
    )


async def async_unload_services(hass: HomeAssistant) -> None:
    """Remove services only when no more IDM entries are configured."""
    if hass.data.get(DOMAIN):
        return
    for service in _SERVICES:
        hass.services.async_remove(DOMAIN, service)


async def _get_coordinator(hass: HomeAssistant, call: ServiceCall):
    from .coordinator import IdmCoordinator

    for entry_id, data in hass.data.get(DOMAIN, {}).items():
        coordinator = data.get("coordinator")
        if isinstance(coordinator, IdmCoordinator):
            return coordinator
    raise HomeAssistantError("No IDM heat pump configured")


async def _handle_set_system_mode(hass: HomeAssistant, call: ServiceCall) -> None:
    coordinator = await _get_coordinator(hass, call)

    mode_map = {
        # German
        "standby": 0,
        "automatik": 1,
        "abwesend": 2,
        "urlaub": 3,
        "nur warmwasser": 4,
        "nur heizung/kuehlung": 5,
        # English aliases
        "automatic": 1,
        "away": 2,
        "holiday": 3,
        "hot water only": 4,
        "heating/cooling only": 5,
    }

    mode_str = call.data.get("mode", "").lower()
    mode_val = mode_map.get(mode_str)

    if mode_val is None:
        raise HomeAssistantError(f"Invalid mode: {mode_str}")

    reg = RegisterDef(
        address=1005,
        datatype=DataType.UCHAR,
        name="system_mode",
        writable=True,
    )
    await coordinator.async_write_register(reg, mode_val)


async def _handle_acknowledge_errors(hass: HomeAssistant, call: ServiceCall) -> None:
    coordinator = await _get_coordinator(hass, call)
    reg = RegisterDef(
        address=1999,
        datatype=DataType.UCHAR,
        name="error_acknowledge",
        writable=True,
    )
    await coordinator.async_write_register(reg, 1)


async def _handle_write_register(
    hass: HomeAssistant, call: ServiceCall
) -> ServiceResponse:
    coordinator = await _get_coordinator(hass, call)

    if call.data.get("acknowledge_risk") is not True:
        raise HomeAssistantError("You must acknowledge the risk to use this service")

    address = int(call.data["address"])
    value = call.data["value"]

    try:
        value = int(value)
    except (ValueError, TypeError):
        try:
            value = float(value)
        except (ValueError, TypeError):
            pass

    reg = RegisterDef(
        address=address,
        datatype=DataType.UINT16,
        name=f"manual_{address}",
        writable=True,
    )

    try:
        await coordinator.client.write_register(reg, value)
        _LOGGER.warning("Manual register write: address=%d value=%s", address, value)
        return {"success": True, "address": address, "value": str(value)}
    except Exception as err:
        raise HomeAssistantError(f"Failed to write register: {err}") from err
