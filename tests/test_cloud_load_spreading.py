"""Simultaneous opt-ins and reconnects spread load without actual network I/O."""

from __future__ import annotations

import random
from collections import Counter
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from test_firmware_observations import make_firmware
from test_telemetry import make_telemetry


async def test_500_simultaneous_opt_ins_are_spread_over_a_day_and_persisted():
    rng = random.Random(500)
    slots = []
    with (
        patch("custom_components.idm_heatpump.telemetry.time.time", return_value=1_800_000_000),
        patch("custom_components.idm_heatpump.telemetry.secrets.randbelow", side_effect=rng.randrange),
    ):
        for _ in range(500):
            client, _, _ = make_telemetry()
            assert await client.async_start()
            assert 86400 <= client._next_attempt - 1_800_000_000 <= 172800
            saved = client._store.async_save.call_args.args[0]
            assert saved["next_attempt"] == client._next_attempt
            slots.append(int((client._next_attempt - 1_800_000_000) // 60))
    assert len(set(slots)) > 400
    assert max(Counter(slots).values()) < 10


async def test_future_daily_slot_survives_reload_without_new_randomness():
    client, entry, _ = make_telemetry()
    client._store.async_load.return_value = {
        "consent_at": entry.options["telemetry_consent_at"],
        "last_attempt": 1_800_000_000,
        "next_attempt": 1_800_090_000,
    }
    with (
        patch("custom_components.idm_heatpump.telemetry.time.time", return_value=1_800_000_100),
        patch("custom_components.idm_heatpump.telemetry.secrets.randbelow") as randomizer,
    ):
        await client.async_start()
    assert client._next_attempt == 1_800_090_000
    randomizer.assert_not_called()


async def test_500_overdue_reconnections_do_not_upload_immediately():
    rng = random.Random(501)
    slots = []
    with (
        patch("custom_components.idm_heatpump.telemetry.time.time", return_value=1_800_000_000),
        patch("custom_components.idm_heatpump.telemetry.secrets.randbelow", side_effect=rng.randrange),
        patch("custom_components.idm_heatpump.telemetry.async_get_clientsession") as session,
    ):
        for _ in range(500):
            client, entry, _ = make_telemetry()
            client._store.async_load.return_value = {
                "consent_at": entry.options["telemetry_consent_at"],
                "last_attempt": 1_799_800_000,
                "next_attempt": 1_799_900_000,
            }
            await client.async_start()
            await client.async_tick(datetime.now(UTC))
            assert 1 <= client._next_attempt - 1_800_000_000 <= 3600
            slots.append(int((client._next_attempt - 1_800_000_000) // 60))
    session.assert_not_called()
    assert len(set(slots)) >= 59
    assert max(Counter(slots).values()) < 30


async def test_500_firmware_startups_are_delayed_and_never_contact_on_setup():
    """The startup check load-spreads within the first 15 minutes."""
    rng = random.Random(502)
    slots = []
    with (
        patch("custom_components.idm_heatpump.firmware_observations.time.time", return_value=1_800_000_000),
        patch("custom_components.idm_heatpump.firmware_observations.secrets.randbelow", side_effect=rng.randrange),
    ):
        for _ in range(500):
            client, _, _ = make_firmware()
            client.async_refresh_firmware = AsyncMock()
            await client.async_start()
            await client.async_tick(datetime.now(UTC))
            client.async_refresh_firmware.assert_not_awaited()
            assert 1 <= client._next_firmware_check - 1_800_000_000 <= 900
            slots.append(int((client._next_firmware_check - 1_800_000_000) // 60))
    assert len(set(slots)) >= 14
    assert max(Counter(slots).values()) < 80
