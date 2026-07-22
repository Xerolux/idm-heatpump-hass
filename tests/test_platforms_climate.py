"""Tests for button, water_heater and climate platforms.

These three platforms are registered in ``PLATFORMS`` (see ``__init__.py``)
but previously had no unit tests at all (0 % coverage). The behaviour is
purely coordinator-driven, so the tests follow the same MagicMock-coordinator
pattern used in ``test_platforms.py``.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from idm_heatpump import DataType, RegisterDef

from custom_components.idm_heatpump.const import (
    REGISTER_ADDRESS_ERROR_ACKNOWLEDGE,
    CircuitMode,
    HeatPumpStatus,
    RoomMode,
)


# ---------------------------------------------------------------------------
# Shared helpers (mirror the style of test_platforms.py)
# ---------------------------------------------------------------------------


def _make_register(name="temp", address=100, writable=False, **kwargs):
    return RegisterDef(
        address=address, datatype=kwargs.pop("datatype", DataType.FLOAT), name=name, writable=writable, **kwargs
    )


def _make_coordinator(data=None, last_update_success=True):
    coord = MagicMock()
    coord.data = data if data is not None else {}
    coord.last_update_success = last_update_success
    coord.client = MagicMock()
    coord.client.write_register = AsyncMock()
    coord.config_entry = MagicMock()
    coord.config_entry.entry_id = "test_entry"
    coord.config_entry.title = "IDM"
    coord.async_write_register = AsyncMock()
    coord.async_request_refresh = AsyncMock()
    coord.unused_registers = set()
    # climate.py iterates the coordinator's private register list directly
    coord._registers = []
    coord.get_register = MagicMock(return_value=None)
    coord.model_name = "Navigator 2.0 / 10"
    coord.firmware_version = None
    coord.myidm_id = None
    return coord


def _entry(coord):
    entry = MagicMock()
    entry.runtime_data.coordinator = coord
    return entry


# ---------------------------------------------------------------------------
# Button platform
# ---------------------------------------------------------------------------


class TestButtonAsyncSetupEntry:
    async def test_creates_acknowledge_errors_button(self):
        from custom_components.idm_heatpump.button import IdmAcknowledgeErrorsButton, async_setup_entry

        coord = _make_coordinator()
        added = []
        await async_setup_entry(MagicMock(), _entry(coord), lambda e: added.extend(e))

        assert len(added) == 1
        assert isinstance(added[0], IdmAcknowledgeErrorsButton)
        assert added[0]._attr_unique_id == "test_entry_acknowledge_errors"


class TestIdmAcknowledgeErrorsButton:
    def test_init_attributes(self):
        from custom_components.idm_heatpump.button import IdmAcknowledgeErrorsButton

        coord = _make_coordinator()
        button = IdmAcknowledgeErrorsButton(coord)
        assert button._attr_translation_key == "acknowledge_errors"
        assert button._attr_icon == "mdi:alert-circle-check"
        # Button targets the centralized acknowledge register
        assert button._register.address == REGISTER_ADDRESS_ERROR_ACKNOWLEDGE
        assert button._register.writable is True

    async def test_async_press_writes_one(self):
        from custom_components.idm_heatpump.button import IdmAcknowledgeErrorsButton

        coord = _make_coordinator()
        button = IdmAcknowledgeErrorsButton(coord)
        await button.async_press()
        coord.async_write_register.assert_awaited_once()
        written_reg, written_value = coord.async_write_register.await_args.args
        assert written_reg is button._register
        assert written_value == 1

    async def test_async_press_raises_translated_error(self):
        from homeassistant.exceptions import HomeAssistantError

        from custom_components.idm_heatpump.button import IdmAcknowledgeErrorsButton

        coord = _make_coordinator()
        coord.async_write_register = AsyncMock(side_effect=Exception("write failed"))
        button = IdmAcknowledgeErrorsButton(coord)

        with pytest.raises(HomeAssistantError) as exc_info:
            await button.async_press()
        # classify_write_error produces a write_* translation key
        assert exc_info.value.translation_key.startswith("write_")
        assert exc_info.value.translation_placeholders == {"register": "error_acknowledge"}


# ---------------------------------------------------------------------------
# Water heater platform
# ---------------------------------------------------------------------------


class TestWaterHeaterAsyncSetupEntry:
    async def test_creates_entity_when_dhw_registers_present(self):
        from custom_components.idm_heatpump.water_heater import IdmWaterHeater, async_setup_entry

        coord = _make_coordinator()
        current = _make_register("dhw_temp_top", 100)
        target = _make_register("dhw_setpoint", 200)
        coord.get_register = MagicMock(side_effect=lambda name: {"dhw_temp_top": current, "dhw_setpoint": target}[name])

        added = []
        await async_setup_entry(MagicMock(), _entry(coord), lambda e: added.extend(e))
        assert len(added) == 1
        assert isinstance(added[0], IdmWaterHeater)

    async def test_no_entity_when_registers_missing(self):
        from custom_components.idm_heatpump.water_heater import async_setup_entry

        coord = _make_coordinator()
        coord.get_register = MagicMock(return_value=None)

        added = []
        await async_setup_entry(MagicMock(), _entry(coord), lambda e: added.extend(e))
        assert added == []


class TestIdmWaterHeater:
    def _make(self, data=None, current=None, target=None):
        from custom_components.idm_heatpump.water_heater import IdmWaterHeater

        coord = _make_coordinator(data=data)
        current = current or _make_register("dhw_temp_top", 100)
        target = target or _make_register("dhw_setpoint", 200)
        return IdmWaterHeater(coord, current, target), coord

    def test_unique_id(self):
        wh, _ = self._make()
        assert wh._attr_unique_id == "test_entry_water_heater"

    def test_current_temperature(self):
        wh, _ = self._make(data={"dhw_temp_top": 52.5})
        assert wh.current_temperature == 52.5

    def test_current_temperature_none_when_missing(self):
        wh, _ = self._make(data={})
        assert wh.current_temperature is None

    def test_current_temperature_none_when_data_none(self):
        wh, _ = self._make(data=None)
        assert wh.current_temperature is None

    def test_target_temperature(self):
        wh, _ = self._make(data={"dhw_setpoint": 55.0})
        assert wh.target_temperature == 55.0

    def test_min_max_temp_from_register_bounds(self):
        target = _make_register("dhw_setpoint", 200, min_val=45.0, max_val=65.0)
        wh, _ = self._make(target=target)
        assert wh.min_temp == 45.0
        assert wh.max_temp == 65.0

    def test_min_max_temp_defaults_without_register_bounds(self):
        wh, _ = self._make()
        assert wh.min_temp == 30.0
        assert wh.max_temp == 65.0

    async def test_async_set_temperature_routes_through_coordinator(self):
        wh, coord = self._make(data={"dhw_setpoint": 50.0})
        await wh.async_set_temperature(temperature=55.0)
        # Writes go through the centralized coordinator path (alias handling,
        # repair issue, background refresh) rather than the raw client.
        coord.async_write_register.assert_awaited_once_with(wh._target_reg, 55.0)
        coord.client.write_register.assert_not_awaited()

    async def test_async_set_temperature_noop_without_temperature(self):
        wh, coord = self._make(data={"dhw_setpoint": 50.0})
        await wh.async_set_temperature()  # no temperature kwarg
        coord.async_write_register.assert_not_awaited()

    async def test_async_set_temperature_propagates_write_error(self):
        from homeassistant.exceptions import HomeAssistantError

        wh, coord = self._make(data={"dhw_setpoint": 50.0})
        coord.async_write_register = AsyncMock(side_effect=RuntimeError("boom"))
        # Writable platforms wrap communication failures as translated HomeAssistantError.
        with pytest.raises(HomeAssistantError):
            await wh.async_set_temperature(temperature=55.0)


# ---------------------------------------------------------------------------
# Climate platform
# ---------------------------------------------------------------------------


def _hc_registers(circuit="a"):
    """Build the register triple the climate platform needs for one heating circuit."""
    mode = _make_register(f"hc_{circuit}_mode", 1405, writable=True, datatype=DataType.UCHAR)
    target = _make_register(f"hc_{circuit}_room_setpoint_heat_normal", 1406)
    current = _make_register(f"hc_{circuit}_room_temp", 1402)
    return mode, target, current


class TestClimateAsyncSetupEntry:
    async def test_creates_heating_circuit_climates(self):
        from custom_components.idm_heatpump.climate import IdmHeatingCircuitClimate, async_setup_entry

        coord = _make_coordinator()
        mode, target, current = _hc_registers("a")
        mode_b, target_b, current_b = _hc_registers("b")
        coord._registers = [mode, target, current, mode_b, target_b, current_b]

        def _get(name):
            for reg in coord._registers:
                if reg.name == name:
                    return reg
            return None

        coord.get_register = MagicMock(side_effect=_get)

        added = []
        await async_setup_entry(MagicMock(), _entry(coord), lambda e: added.extend(e))
        assert len(added) == 2
        assert all(isinstance(e, IdmHeatingCircuitClimate) for e in added)
        circuits = {e._circuit for e in added}
        assert circuits == {"A", "B"}

    async def test_skips_circuit_without_mode_or_target(self):
        from custom_components.idm_heatpump.climate import async_setup_entry

        coord = _make_coordinator()
        mode, target, current = _hc_registers("a")
        # circuit b has only a current_temp register — no mode/target pair
        only_current_b = _make_register("hc_b_room_temp", 1422)
        coord._registers = [mode, target, current, only_current_b]
        coord.get_register = MagicMock(
            side_effect=lambda name: next((r for r in coord._registers if r.name == name), None)
        )

        added = []
        await async_setup_entry(MagicMock(), _entry(coord), lambda e: added.extend(e))
        assert len(added) == 1
        assert added[0]._circuit == "A"

    async def test_creates_zone_room_climates(self):
        from custom_components.idm_heatpump.climate import IdmZoneRoomClimate, async_setup_entry

        coord = _make_coordinator()
        z1_mode = _make_register("zm1_room1_mode", 3000, datatype=DataType.UCHAR, writable=True)
        z1_target = _make_register("zm1_room1_setpoint", 3001)
        z1_current = _make_register("zm1_room1_temp", 3002)
        coord._registers = [z1_mode, z1_target, z1_current]
        coord.get_register = MagicMock(
            side_effect=lambda name: next((r for r in coord._registers if r.name == name), None)
        )

        added = []
        await async_setup_entry(MagicMock(), _entry(coord), lambda e: added.extend(e))
        assert len(added) == 1
        assert isinstance(added[0], IdmZoneRoomClimate)
        assert added[0]._zone == 1
        assert added[0]._room == 1

    async def test_no_entities_without_matching_registers(self):
        from custom_components.idm_heatpump.climate import async_setup_entry

        coord = _make_coordinator()
        coord._registers = [_make_register("outdoor_temp", 1000)]
        coord.get_register = MagicMock(return_value=None)

        added = []
        await async_setup_entry(MagicMock(), _entry(coord), lambda e: added.extend(e))
        assert added == []


class TestIdmHeatingCircuitClimate:
    def _make(self, data=None):
        from custom_components.idm_heatpump.climate import IdmHeatingCircuitClimate

        coord = _make_coordinator(data=data)
        mode, target, current = _hc_registers("a")
        return IdmHeatingCircuitClimate(coord, "a", mode, target, current), coord

    def test_unique_id_and_translation(self):
        climate, _ = self._make()
        assert climate._attr_unique_id == "test_entry_climate_hc_a"
        assert climate._attr_translation_key == "heating_circuit"
        assert climate._attr_translation_placeholders == {"circuit": "A"}

    def test_hvac_modes_advertised(self):
        from homeassistant.components.climate import HVACMode

        climate, _ = self._make()
        assert set(climate._attr_hvac_modes) == {HVACMode.OFF, HVACMode.AUTO, HVACMode.HEAT, HVACMode.COOL}

    def test_hvac_mode_mapping(self):
        from homeassistant.components.climate import HVACMode

        for raw, expected in [
            (CircuitMode.OFF, HVACMode.OFF),
            (CircuitMode.TIMED, HVACMode.AUTO),
            (CircuitMode.NORMAL, HVACMode.HEAT),
            (CircuitMode.ECO, HVACMode.HEAT),
            (CircuitMode.MANUAL_HEAT, HVACMode.HEAT),
            (CircuitMode.MANUAL_COOL, HVACMode.COOL),
        ]:
            climate, _ = self._make(data={"hc_a_mode": raw})
            assert climate.hvac_mode == expected, f"raw={raw}"

    def test_hvac_mode_none_without_data(self):
        climate, _ = self._make(data=None)
        assert climate.hvac_mode is None

    def test_preset_mapping(self):
        from homeassistant.components.climate import PRESET_ECO, PRESET_NONE

        for raw, expected in [
            (CircuitMode.ECO, PRESET_ECO),
            (CircuitMode.NORMAL, PRESET_NONE),
            (CircuitMode.MANUAL_HEAT, PRESET_NONE),
        ]:
            climate, _ = self._make(data={"hc_a_mode": raw})
            assert climate.preset_mode == expected, f"raw={raw}"

    def test_preset_none_for_unknown_mode(self):
        climate, _ = self._make(data={"hc_a_mode": CircuitMode.TIMED})
        assert climate.preset_mode is None

    def test_hvac_action_off_when_circuit_off(self):
        from homeassistant.components.climate import HVACAction

        climate, _ = self._make(data={"hc_a_mode": CircuitMode.OFF})
        assert climate.hvac_action == HVACAction.OFF

    def test_hvac_action_reflects_heatpump_status(self):
        """The hvac_action follows the heatpump operating-mode register."""
        from homeassistant.components.climate import HVACAction

        # HEATING bit set
        climate, _ = self._make(
            data={"hc_a_mode": CircuitMode.NORMAL, "hp_operating_mode": int(HeatPumpStatus.HEATING)}
        )
        assert climate.hvac_action == HVACAction.HEATING

        # COOLING bit set
        climate, _ = self._make(
            data={"hc_a_mode": CircuitMode.NORMAL, "hp_operating_mode": int(HeatPumpStatus.COOLING)}
        )
        assert climate.hvac_action == HVACAction.COOLING

    def test_hvac_action_idle_when_no_status(self):
        from homeassistant.components.climate import HVACAction

        climate, _ = self._make(data={"hc_a_mode": CircuitMode.NORMAL})
        assert climate.hvac_action == HVACAction.IDLE

    async def test_async_set_hvac_mode_routes_through_coordinator(self):
        from homeassistant.components.climate import HVACMode

        climate, coord = self._make(data={"hc_a_mode": CircuitMode.NORMAL})
        await climate.async_set_hvac_mode(HVACMode.COOL)
        coord.async_write_register.assert_awaited_once_with(climate._mode_reg, CircuitMode.MANUAL_COOL)
        coord.client.write_register.assert_not_awaited()

    async def test_async_set_hvac_mode_heat_maps_to_normal(self):
        from homeassistant.components.climate import HVACMode

        climate, coord = self._make(data={"hc_a_mode": CircuitMode.OFF})
        await climate.async_set_hvac_mode(HVACMode.HEAT)
        coord.async_write_register.assert_awaited_once_with(climate._mode_reg, CircuitMode.NORMAL)

    async def test_async_set_preset_mode_routes_through_coordinator(self):
        from homeassistant.components.climate import PRESET_ECO, PRESET_NONE

        climate, coord = self._make(data={"hc_a_mode": CircuitMode.NORMAL})

        await climate.async_set_preset_mode(PRESET_ECO)
        coord.async_write_register.assert_awaited_with(climate._mode_reg, CircuitMode.ECO)

        await climate.async_set_preset_mode(PRESET_NONE)
        coord.async_write_register.assert_awaited_with(climate._mode_reg, CircuitMode.NORMAL)

    async def test_write_failure_propagates_from_coordinator(self):
        from homeassistant.components.climate import HVACMode
        from homeassistant.exceptions import HomeAssistantError

        climate, coord = self._make(data={"hc_a_mode": CircuitMode.NORMAL})
        coord.async_write_register = AsyncMock(side_effect=RuntimeError("link down"))
        # Climate wraps failures with translated HomeAssistantError (same as IdmEntity).
        with pytest.raises(HomeAssistantError):
            await climate.async_set_hvac_mode(HVACMode.AUTO)

    async def test_async_set_temperature_routes_through_coordinator(self):
        climate, coord = self._make(data={"hc_a_room_setpoint_heat_normal": 21.0})
        await climate.async_set_temperature(temperature=22.5)
        coord.async_write_register.assert_awaited_once_with(climate._target_reg, 22.5)
        coord.client.write_register.assert_not_awaited()

    async def test_async_set_temperature_noop_without_temp(self):
        climate, coord = self._make(data={"hc_a_room_setpoint_heat_normal": 21.0})
        await climate.async_set_temperature()
        coord.async_write_register.assert_not_awaited()


class TestIdmZoneRoomClimate:
    def _make(self, data=None):
        from custom_components.idm_heatpump.climate import IdmZoneRoomClimate

        coord = _make_coordinator(data=data)
        mode = _make_register("zm1_room2_mode", 3000, datatype=DataType.UCHAR, writable=True)
        target = _make_register("zm1_room2_setpoint", 3001)
        current = _make_register("zm1_room2_temp", 3002)
        return IdmZoneRoomClimate(coord, 1, 2, mode, target, current), coord

    def test_unique_id_and_translation(self):
        climate, _ = self._make()
        assert climate._attr_unique_id == "test_entry_climate_zm1_room2"
        assert climate._attr_translation_key == "zone_room"
        assert climate._attr_translation_placeholders == {"zone": "1", "room": "2"}

    def test_hvac_mode_mapping(self):
        from homeassistant.components.climate import HVACMode

        for raw, expected in [
            (RoomMode.OFF, HVACMode.OFF),
            (RoomMode.AUTOMATIC, HVACMode.AUTO),
            (RoomMode.NORMAL, HVACMode.HEAT),
            (RoomMode.ECO, HVACMode.HEAT),
            (RoomMode.COMFORT, HVACMode.HEAT),
        ]:
            climate, _ = self._make(data={"zm1_room2_mode": raw})
            assert climate.hvac_mode == expected, f"raw={raw}"

    def test_preset_mapping(self):
        from homeassistant.components.climate import PRESET_COMFORT, PRESET_ECO, PRESET_NONE

        for raw, expected in [
            (RoomMode.ECO, PRESET_ECO),
            (RoomMode.COMFORT, PRESET_COMFORT),
            (RoomMode.NORMAL, PRESET_NONE),
        ]:
            climate, _ = self._make(data={"zm1_room2_mode": raw})
            assert climate.preset_mode == expected, f"raw={raw}"

    def test_hvac_action_heating_when_target_above_current(self):
        from homeassistant.components.climate import HVACAction

        climate, _ = self._make(
            data={
                "zm1_room2_mode": RoomMode.NORMAL,
                "zm1_room2_setpoint": 22.0,
                "zm1_room2_temp": 19.0,
            }
        )
        assert climate.hvac_action == HVACAction.HEATING

    def test_hvac_action_idle_when_target_close_to_current(self):
        from homeassistant.components.climate import HVACAction

        climate, _ = self._make(
            data={
                "zm1_room2_mode": RoomMode.NORMAL,
                "zm1_room2_setpoint": 20.0,
                "zm1_room2_temp": 19.9,  # within 0.2 tolerance
            }
        )
        assert climate.hvac_action == HVACAction.IDLE

    def test_hvac_action_off_when_room_off(self):
        from homeassistant.components.climate import HVACAction

        climate, _ = self._make(data={"zm1_room2_mode": RoomMode.OFF})
        assert climate.hvac_action == HVACAction.OFF

    async def test_async_set_hvac_mode_routes_through_coordinator(self):
        from homeassistant.components.climate import HVACMode

        climate, coord = self._make(data={"zm1_room2_mode": RoomMode.NORMAL})
        await climate.async_set_hvac_mode(HVACMode.OFF)
        coord.async_write_register.assert_awaited_once_with(climate._mode_reg, RoomMode.OFF)
        coord.client.write_register.assert_not_awaited()

    async def test_async_set_preset_mode_routes_through_coordinator(self):
        from homeassistant.components.climate import PRESET_COMFORT, PRESET_ECO

        climate, coord = self._make(data={"zm1_room2_mode": RoomMode.NORMAL})
        await climate.async_set_preset_mode(PRESET_COMFORT)
        coord.async_write_register.assert_awaited_with(climate._mode_reg, RoomMode.COMFORT)
        await climate.async_set_preset_mode(PRESET_ECO)
        coord.async_write_register.assert_awaited_with(climate._mode_reg, RoomMode.ECO)
