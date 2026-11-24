"""DHW boost through the real service registry and coordinator listeners."""

from __future__ import annotations

import asyncio

from homeassistant.config_entries import ConfigEntryState


async def test_single_cancel_retries_both_writes(smoke_hass, patched_client, smoke_entry, fake_client):
    values = {"system_mode": 1, "dhw_setpoint": 52, "dhw_temp_top": 44, "demand_onetime_dhw": False}
    writes = []

    async def write(register, value):
        writes.append((register.name, value))
        values[register.name] = value

    fake_client.read_batch.side_effect = lambda regs: {reg.name: values.get(reg.name, 20.0) for reg in regs}
    fake_client.write_register.side_effect = write
    await smoke_hass.config_entries.async_add(smoke_entry)
    await smoke_hass.async_block_till_done()
    assert smoke_entry.state is ConfigEntryState.LOADED
    coordinator = smoke_entry.runtime_data.coordinator
    data = {"entry_id": smoke_entry.entry_id}
    try:
        await smoke_hass.services.async_call("idm_heatpump", "start_dhw_boost", data, blocking=True)
        manager = coordinator.dhw_boost_manager
        assert manager.active
        # Starting a one-hour boost must let HA finish draining its foreground work.
        async with asyncio.timeout(10):
            await smoke_hass.async_block_till_done()
        await smoke_hass.services.async_call("idm_heatpump", "cancel_dhw_boost", data, blocking=True)
        for address in coordinator._write_timestamps:
            coordinator._write_timestamps[address] -= 61
        coordinator.async_update_listeners()
        async with asyncio.timeout(8):
            while manager.active:
                await asyncio.sleep(0.03)
        assert writes == [
            ("dhw_setpoint", 60),
            ("demand_onetime_dhw", True),
            ("dhw_setpoint", 52),
            ("demand_onetime_dhw", False),
        ]
    finally:
        await smoke_hass.config_entries.async_unload(smoke_entry.entry_id)
