"""Verify the IDM bridge API is scoped and can be revoked."""

import json
from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from aiohttp import web
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers.http import KEY_HASS

from custom_components.idm_heatpump.bridge_api import (
    BRIDGE_KEY_HEADER,
    CONF_BRIDGE_KEY_HASH,
    IdmBridgePowerView,
    IdmBridgePricesView,
    bridge_key_hash,
)
from custom_components.idm_heatpump.config_flow import IdmHeatpumpOptionsFlow
from custom_components.idm_heatpump.const import CONF_DYNAMIC_PRICE_ENTITY, DOMAIN


@pytest.mark.asyncio
async def test_bridge_read_requires_current_key_and_fresh_power():
    key = token_urlsafe(32)
    coordinator = SimpleNamespace(
        last_update_success=True,
        poll_statistics=SimpleNamespace(last_success=datetime.now(UTC)),
        data={"power_consumption_hp": 4.09},
    )
    entry = SimpleNamespace(
        domain=DOMAIN,
        options={CONF_BRIDGE_KEY_HASH: bridge_key_hash(key)},
        state=ConfigEntryState.LOADED,
        runtime_data=SimpleNamespace(coordinator=coordinator),
    )
    hass = MagicMock()
    hass.config_entries.async_get_entry.return_value = entry
    request = SimpleNamespace(app={KEY_HASS: hass}, headers={BRIDGE_KEY_HEADER: key}, secure=True, remote="192.0.2.4")
    view = IdmBridgePowerView()
    request.secure = False
    with pytest.raises(web.HTTPForbidden):
        await view.get(request, "entry")
    request.secure = True
    response = await view.get(request, "entry")
    assert response.status == 200
    assert '"electrical_power_w": 4090' in response.text
    assert response.headers["Cache-Control"] == "no-store"
    coordinator.poll_statistics.last_success -= timedelta(seconds=61)
    with pytest.raises(web.HTTPServiceUnavailable):
        await view.get(request, "entry")
    entry.options[CONF_BRIDGE_KEY_HASH] = bridge_key_hash(token_urlsafe(32))
    with pytest.raises(web.HTTPUnauthorized):
        await view.get(request, "entry")
    entry.options.clear()
    with pytest.raises(web.HTTPNotFound):
        await view.get(request, "entry")


@pytest.mark.asyncio
async def test_options_store_only_hash_and_revoke():
    flow = IdmHeatpumpOptionsFlow()
    flow.config_entry = MagicMock()
    flow.config_entry.entry_id = "entry"
    flow.config_entry.options = {"existing": True}
    await flow.async_step_init()
    flow.async_show_form = MagicMock(wraps=flow.async_show_form)
    await flow.async_step_bridge_api()
    key = flow.async_show_form.call_args.kwargs["description_placeholders"]["bridge_key"]
    result = await flow.async_step_bridge_api({"enable": True})
    assert result["data"] == {"existing": True, CONF_BRIDGE_KEY_HASH: bridge_key_hash(key)}
    result = await flow.async_step_bridge_api({"enable": False})
    assert result["data"] == {"existing": True}


@pytest.mark.asyncio
async def test_bridge_prices_use_only_configured_tariff_and_normalize_cents():
    key = token_urlsafe(32)
    now = datetime.now(UTC)
    entry = SimpleNamespace(
        domain=DOMAIN,
        state=ConfigEntryState.LOADED,
        options={CONF_BRIDGE_KEY_HASH: bridge_key_hash(key), CONF_DYNAMIC_PRICE_ENTITY: "sensor.idm_tariff"},
    )
    hass = MagicMock()
    hass.config_entries.async_get_entry.return_value = entry
    hass.states.get.return_value = SimpleNamespace(
        state="-10",
        last_updated=now,
        attributes={
            "unit_of_measurement": "ct/kWh",
            "prices": [{"start": (now + timedelta(hours=1)).isoformat(), "price": 25}],
        },
    )
    request = SimpleNamespace(app={KEY_HASS: hass}, headers={}, secure=True)
    view = IdmBridgePricesView()
    with pytest.raises(web.HTTPUnauthorized):
        await view.get(request, "entry")
    hass.states.get.assert_not_called()
    request.headers[BRIDGE_KEY_HEADER] = key
    data = json.loads((await view.get(request, "entry")).text)
    assert data["unit"] == "EUR/kWh"
    assert data["current_price"] == pytest.approx(-0.1)
    assert [slot["price"] for slot in data["hourly_prices"]] == [0.25]
    hass.states.get.assert_called_once_with("sensor.idm_tariff")

    hass.states.get.return_value.attributes["unit_of_measurement"] = "USD/kWh"
    with pytest.raises(web.HTTPServiceUnavailable):
        await view.get(request, "entry")
