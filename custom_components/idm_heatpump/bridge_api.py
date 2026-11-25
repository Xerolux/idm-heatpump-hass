"""Scoped local API for one external IDM bridge."""

from __future__ import annotations

import math
from datetime import UTC, datetime
from hashlib import sha256
from hmac import compare_digest
from ipaddress import ip_address

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.helpers.http import KEY_HASS

from .const import CONF_DYNAMIC_PRICE_ENTITY, DOMAIN

CONF_BRIDGE_KEY_HASH = "bridge_key_hash"
BRIDGE_KEY_HEADER = "X-IDM-Bridge-Key"


def bridge_key_hash(key: str) -> str:
    return sha256(key.encode()).hexdigest()


class _IdmBridgeView(HomeAssistantView):
    """Authenticate an installation-scoped key before exposing data."""

    requires_auth = False

    def _authorized_entry(self, request: web.Request, entry_id: str) -> ConfigEntry:
        hass = request.app[KEY_HASS]
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry is None or entry.domain != DOMAIN:
            raise web.HTTPNotFound()
        digest = entry.options.get(CONF_BRIDGE_KEY_HASH)
        if not digest:
            raise web.HTTPNotFound()
        if not request.secure:
            try:
                loopback = ip_address(request.remote or "").is_loopback
            except ValueError:
                loopback = False
            if not loopback:
                raise web.HTTPForbidden()
        key = request.headers.get(BRIDGE_KEY_HEADER, "")
        if len(key) != 43 or not compare_digest(digest, bridge_key_hash(key)):
            raise web.HTTPUnauthorized()
        if entry.state is not ConfigEntryState.LOADED:
            raise web.HTTPServiceUnavailable()
        return entry


class IdmBridgePowerView(_IdmBridgeView):
    """Return the latest electrical power from the successful IDM poll."""

    url = "/api/idm_heatpump/bridge/v1/{entry_id}/power"
    name = "api:idm_heatpump:bridge:power"

    async def get(self, request: web.Request, entry_id: str) -> web.Response:
        entry = self._authorized_entry(request, entry_id)
        coordinator = entry.runtime_data.coordinator
        last_success = coordinator.poll_statistics.last_success
        if (
            not coordinator.last_update_success
            or last_success is None
            or not 0 <= (datetime.now(UTC) - last_success).total_seconds() <= 60
        ):
            raise web.HTTPServiceUnavailable()
        value = (coordinator.data or {}).get("power_consumption_hp")
        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not math.isfinite(value)
            or not 0 <= value < 2**53 / 1000
        ):
            raise web.HTTPServiceUnavailable()
        return web.json_response(
            {"electrical_power_w": round(value * 1000), "observed_at": last_success.isoformat()},
            headers={"Cache-Control": "no-store"},
        )


class IdmBridgePricesView(_IdmBridgeView):
    """Expose the configured dynamic tariff without exposing other HA states."""

    url = "/api/idm_heatpump/bridge/v1/{entry_id}/prices"
    name = "api:idm_heatpump:bridge:prices"

    async def get(self, request: web.Request, entry_id: str) -> web.Response:
        from .advisor_engine import parse_price_hourly

        entry = self._authorized_entry(request, entry_id)
        entity_id = entry.options.get(CONF_DYNAMIC_PRICE_ENTITY)
        state = request.app[KEY_HASS].states.get(entity_id) if entity_id else None
        if state is None:
            raise web.HTTPServiceUnavailable()
        unit = state.attributes.get("unit_of_measurement")
        scale = (
            {"EUR/kWh": 1.0, "€/kWh": 1.0, "ct/kWh": 0.01, "c/kWh": 0.01}.get(unit) if isinstance(unit, str) else None
        )
        if scale is None:
            raise web.HTTPServiceUnavailable()
        try:
            current = float(state.state) * scale
        except (TypeError, ValueError):
            raise web.HTTPServiceUnavailable() from None
        if not math.isfinite(current):
            raise web.HTTPServiceUnavailable()

        now = datetime.now(UTC)
        return web.json_response(
            {
                "currency": "EUR",
                "unit": "EUR/kWh",
                "current_price": current,
                "observed_at": state.last_updated.astimezone(UTC).isoformat(),
                "hourly_prices": [
                    {"start": start.astimezone(UTC).isoformat(), "price": price}
                    for start, price in parse_price_hourly(state, now)
                    if math.isfinite(price)
                ],
            },
            headers={"Cache-Control": "no-store"},
        )
