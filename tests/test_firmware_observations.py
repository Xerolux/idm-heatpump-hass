"""Independent firmware consent and minimal metadata privacy boundary."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from test_telemetry import make_telemetry

from custom_components.idm_heatpump.const import (
    CONF_FIRMWARE_CHECK,
    CONF_FIRMWARE_CONSENT_AT,
    CONF_FIRMWARE_POLICY,
    CONF_TELEMETRY,
)
from custom_components.idm_heatpump.firmware_observations import FIRMWARE_POLICY, FirmwareObservations


def make_firmware(enabled=True):
    _, entry, coordinator = make_telemetry(False)
    entry.options.update(
        {
            CONF_FIRMWARE_CHECK: enabled,
            CONF_FIRMWARE_POLICY: FIRMWARE_POLICY,
            CONF_FIRMWARE_CONSENT_AT: "2026-11-05T10:00:00+00:00",
        }
    )
    entry.options.pop("telemetry_myidm_id", None)
    coordinator.myidm_id = None
    return FirmwareObservations(MagicMock(), entry, coordinator), entry, coordinator


async def test_no_firmware_query_without_consent():
    telemetry, _, _ = make_firmware(False)
    with patch("custom_components.idm_heatpump.firmware_observations.async_get_clientsession") as session:
        await FirmwareObservations.async_refresh_firmware(telemetry)
    session.assert_not_called()


async def test_firmware_response_is_bound_to_requested_plant_metadata():
    telemetry, _, _ = make_firmware()
    telemetry._coordinator.firmware_version = "NAV10_20.24-9"
    response = MagicMock(status=200)
    query = {
        "navigator": "navigator_10",
        "navigator_model": "Navigator 10",
        "heatpump_model": "AERO ALM",
        "firmware": "NAV10_20.24-9",
    }
    response.json = AsyncMock(
        return_value={
            "query": query,
            "source": "community_telemetry",
            "status": "observed",
            "latest_firmware": "NAV10_20.24-11",
            "series": "nav10_20",
            "observations": 2,
            "newer_observed": True,
        }
    )
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=response)
    context.__aexit__ = AsyncMock(return_value=False)
    session = MagicMock()
    session.post.return_value = context
    listener = MagicMock()
    remove = telemetry.async_add_firmware_listener(listener)
    with patch("custom_components.idm_heatpump.firmware_observations.async_get_clientsession", return_value=session):
        await FirmwareObservations.async_refresh_firmware(telemetry)
    assert session.post.call_args.kwargs["json"] == query
    assert telemetry._entry.options[CONF_TELEMETRY] is False
    assert telemetry.firmware_result["latest_firmware"] == "NAV10_20.24-11"
    listener.assert_called_once()
    remove()
    response.json.return_value["query"] = query | {"heatpump_model": "OTHER MODEL"}
    telemetry.firmware_result = {}
    with patch("custom_components.idm_heatpump.firmware_observations.async_get_clientsession", return_value=session):
        await FirmwareObservations.async_refresh_firmware(telemetry)
    assert telemetry.firmware_result.get("latest_firmware") is None
    assert set(telemetry.firmware_result) == {"next_check"}


async def test_withdrawal_cancels_firmware_request_as_well_as_upload():
    telemetry, entry, _ = make_firmware()
    started = asyncio.Event()

    async def wait_forever():
        started.set()
        await asyncio.Future()

    context = MagicMock()
    context.__aenter__ = AsyncMock(side_effect=wait_forever)
    context.__aexit__ = AsyncMock(return_value=False)
    session = MagicMock()
    session.post.return_value = context
    with patch("custom_components.idm_heatpump.firmware_observations.async_get_clientsession", return_value=session):
        task = asyncio.create_task(FirmwareObservations.async_refresh_firmware(telemetry))
        await asyncio.wait_for(started.wait(), timeout=2)
        entry.options[CONF_FIRMWARE_CHECK] = False
        await telemetry.async_options_updated(None, entry)
        with pytest.raises(asyncio.CancelledError):
            await task
    assert telemetry._firmware_task is None


def test_firmware_series_keeps_test_and_stable_channels_separate():
    from custom_components.idm_heatpump.telemetry import _firmware_series

    assert _firmware_series("T_NAV10_20.24-1580-g02a20b66f") == "t_nav10_20"
    assert _firmware_series("NAV10_20.24-1580.iup") == "nav10_20"
    assert _firmware_series("m_20.23-165") == "m_20"
    assert _firmware_series("unknown") is None
    assert _firmware_series(None) is None


@pytest.mark.parametrize(
    "options",
    [{}, {"firmware_check": True}, {"firmware_check": True, "firmware_policy": "old", "firmware_consent_at": "yes"}],
)
async def test_firmware_refusal_has_no_timer_storage_or_contact(options):
    client, entry, _ = make_firmware()
    entry.options = options
    with (
        patch("custom_components.idm_heatpump.cloud_scheduler.async_track_time_interval") as timer,
        patch("custom_components.idm_heatpump.firmware_observations.async_get_clientsession") as session,
    ):
        assert await client.async_start() is False
        await client.async_tick(datetime.now(UTC))
    timer.assert_not_called()
    session.assert_not_called()
    assert not hasattr(client, "_store")


async def test_firmware_has_independent_lifecycle_and_six_hour_timer():
    client, entry, _ = make_firmware()
    client.async_refresh_firmware = AsyncMock()
    with patch("custom_components.idm_heatpump.cloud_scheduler.async_track_time_interval") as timer:
        assert await client.async_start()
        assert timer.call_args.args[2].total_seconds() == 60
    client.async_refresh_firmware.assert_not_awaited()
    client._next_firmware_check = 0
    await client.async_tick(datetime.now(UTC))
    assert client.async_refresh_firmware.await_count == 1
    entry.options[CONF_TELEMETRY] = False
    await client.async_options_updated(None, entry)
    assert client.enabled
    entry.options[CONF_FIRMWARE_CHECK] = False
    await client.async_options_updated(None, entry)
    assert not client.enabled


async def test_unknown_firmware_consent_never_contacts_server():
    firmware, entry, _ = make_firmware()
    entry.options[CONF_FIRMWARE_POLICY] = "unsupported-policy"
    with patch("custom_components.idm_heatpump.firmware_observations.async_get_clientsession") as session:
        await firmware.async_refresh_firmware()
    assert not firmware.enabled
    session.assert_not_called()


@pytest.mark.parametrize("scope,expected", [("controller_and_plant_model", False), ("unconfirmed_component", None)])
async def test_existing_consent_and_single_report_show_latest_without_update_notice(scope, expected):
    firmware, entry, coordinator = make_firmware()
    assert entry.options[CONF_FIRMWARE_POLICY] == "idm-firmware-v1"
    coordinator.firmware_version = "NAV10_20.24-9"
    query = {"navigator": "navigator_10", "navigator_model": "Navigator 10", "heatpump_model": "AERO ALM", "firmware": coordinator.firmware_version}
    response = MagicMock(status=200)
    response.json = AsyncMock(return_value={"query": query, "source": "community_telemetry", "status": "observed", "latest_firmware": query["firmware"], "series": "nav10_20", "observations": 1, "newer_observed": scope == "unconfirmed_component", "model_scope": scope, "component_status": "reported_component"})
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=response)
    context.__aexit__ = AsyncMock(return_value=False)
    session = MagicMock()
    session.post.return_value = context
    with patch("custom_components.idm_heatpump.firmware_observations.async_get_clientsession", return_value=session):
        await firmware.async_refresh_firmware()
    assert firmware.enabled
    assert firmware.firmware_result["latest_firmware"] == query["firmware"]
    assert firmware.firmware_result["newer_observed"] is expected
    assert firmware.firmware_result["component_status"] == "reported_component"
