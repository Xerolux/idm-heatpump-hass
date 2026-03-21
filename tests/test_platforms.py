"""Tests for sensor, binary_sensor, number, select, switch platforms."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.idm_heatpump.modbus_client import DataType, RegisterDef
from custom_components.idm_heatpump.const import DOMAIN, UNUSED_VALUE


def _make_register(name="temp", address=100, writable=False, enum_options=None, datatype=DataType.FLOAT):
    return RegisterDef(
        address=address,
        datatype=datatype,
        name=name,
        writable=writable,
        enum_options=enum_options,
    )


def _make_coordinator(data=None, hide_unused=False, last_update_success=True):
    coord = MagicMock()
    coord.hide_unused = hide_unused
    coord.data = data if data is not None else {}
    coord.last_update_success = last_update_success
    coord.client = MagicMock()
    coord.client.host = "192.168.1.100"
    coord.client.port = 502
    coord.config_entry = MagicMock()
    coord.config_entry.entry_id = "test_entry"
    coord.config_entry.title = "IDM"
    coord.async_write_register = AsyncMock()
    return coord


def _make_desc(key="temp"):
    desc = MagicMock()
    desc.key = key
    desc.name = key
    return desc


# ---------------------------------------------------------------------------
# Sensor platform
# ---------------------------------------------------------------------------

class TestIdmSensor:
    def test_native_value_plain(self):
        from custom_components.idm_heatpump.sensor import IdmSensor

        coord = _make_coordinator(data={"temp": 22.5})
        reg = _make_register("temp")
        sensor = IdmSensor(coord, reg, _make_desc("temp"))
        assert sensor.native_value == 22.5

    def test_native_value_none_when_missing(self):
        from custom_components.idm_heatpump.sensor import IdmSensor

        coord = _make_coordinator(data={})
        reg = _make_register("temp")
        sensor = IdmSensor(coord, reg, _make_desc("temp"))
        assert sensor.native_value is None

    def test_native_value_enum_lookup(self):
        from custom_components.idm_heatpump.sensor import IdmSensor

        enum_opts = {0: "Standby", 1: "Automatic"}
        coord = _make_coordinator(data={"mode": 1})
        reg = _make_register("mode", enum_options=enum_opts, datatype=DataType.UCHAR)
        sensor = IdmSensor(coord, reg, _make_desc("mode"))
        assert sensor.native_value == "Automatic"

    def test_native_value_enum_unknown(self):
        from custom_components.idm_heatpump.sensor import IdmSensor

        enum_opts = {0: "Standby"}
        coord = _make_coordinator(data={"mode": 99})
        reg = _make_register("mode", enum_options=enum_opts, datatype=DataType.UCHAR)
        sensor = IdmSensor(coord, reg, _make_desc("mode"))
        assert "Unknown" in sensor.native_value

    def test_native_value_none_with_enum_returns_none(self):
        from custom_components.idm_heatpump.sensor import IdmSensor

        enum_opts = {0: "Standby"}
        coord = _make_coordinator(data={})
        reg = _make_register("mode", enum_options=enum_opts)
        sensor = IdmSensor(coord, reg, _make_desc("mode"))
        assert sensor.native_value is None


class TestSensorAsyncSetupEntry:
    async def test_creates_sensors_from_coordinator(self):
        from custom_components.idm_heatpump.sensor import async_setup_entry

        coord = _make_coordinator()
        reg1 = _make_register("outdoor_temp", 100)
        reg2 = _make_register("flow_temp", 101)
        coord.sensor_descriptions = [
            {"register": reg1, "description": _make_desc("outdoor_temp")},
            {"register": reg2, "description": _make_desc("flow_temp")},
        ]

        entry = MagicMock()
        entry.runtime_data.coordinator = coord
        entry.options = {}

        added_entities = []
        async_add = MagicMock(side_effect=lambda entities: added_entities.extend(entities))

        await async_setup_entry(MagicMock(), entry, async_add)
        assert len(added_entities) == 2

    async def test_excludes_enum_uchar_sensors(self):
        from custom_components.idm_heatpump.sensor import async_setup_entry

        coord = _make_coordinator()
        reg_normal = _make_register("temp", 100)
        reg_enum_uchar = _make_register("mode", 200, datatype=DataType.UCHAR,
                                        enum_options={0: "off", 1: "on"})
        coord.sensor_descriptions = [
            {"register": reg_normal, "description": _make_desc("temp")},
            {"register": reg_enum_uchar, "description": _make_desc("mode")},
        ]

        entry = MagicMock()
        entry.runtime_data.coordinator = coord
        entry.options = {}

        added_entities = []
        async_add = MagicMock(side_effect=lambda entities: added_entities.extend(entities))

        await async_setup_entry(MagicMock(), entry, async_add)
        assert len(added_entities) == 1  # enum UCHAR excluded

    async def test_adds_technician_sensors_when_enabled(self):
        from custom_components.idm_heatpump.sensor import async_setup_entry

        coord = _make_coordinator()
        coord.sensor_descriptions = []

        entry = MagicMock()
        entry.runtime_data.coordinator = coord
        # Use spec-less MagicMock so .get() is a callable mock
        entry.options.get = MagicMock(side_effect=lambda k, d=None: True if k == "technician_codes" else d)

        added_entities = []
        async_add = MagicMock(side_effect=lambda entities: added_entities.extend(entities))

        await async_setup_entry(MagicMock(), entry, async_add)
        assert len(added_entities) == 2  # level_1 and level_2


class TestIdmTechnicianCodeSensor:
    def test_init(self):
        from custom_components.idm_heatpump.sensor import IdmTechnicianCodeSensor

        coord = _make_coordinator()
        sensor = IdmTechnicianCodeSensor(coord, "level_1")
        assert "level_1" in sensor._attr_unique_id
        assert sensor._attr_name == "Fachmann Ebene 1"

    def test_level_2_name(self):
        from custom_components.idm_heatpump.sensor import IdmTechnicianCodeSensor

        coord = _make_coordinator()
        sensor = IdmTechnicianCodeSensor(coord, "level_2")
        assert sensor._attr_name == "Fachmann Ebene 2"

    def test_available_always_true(self):
        from custom_components.idm_heatpump.sensor import IdmTechnicianCodeSensor

        coord = _make_coordinator(last_update_success=False)
        sensor = IdmTechnicianCodeSensor(coord, "level_1")
        assert sensor.available is True

    def test_native_value_returns_code(self):
        from custom_components.idm_heatpump.sensor import IdmTechnicianCodeSensor
        from custom_components.idm_heatpump.technician_codes import calculate_codes

        coord = _make_coordinator()
        sensor = IdmTechnicianCodeSensor(coord, "level_1")
        expected = calculate_codes()["level_1"]
        assert sensor.native_value == expected

    def test_entity_disabled_by_default(self):
        from custom_components.idm_heatpump.sensor import IdmTechnicianCodeSensor

        assert IdmTechnicianCodeSensor._attr_entity_registry_enabled_default is False

    async def test_async_will_remove_cancels_timer(self):
        from custom_components.idm_heatpump.sensor import IdmTechnicianCodeSensor

        coord = _make_coordinator()
        sensor = IdmTechnicianCodeSensor(coord, "level_1")
        mock_cancel = MagicMock()
        sensor._cancel_timer = mock_cancel
        await sensor.async_will_remove_from_hass()
        mock_cancel.assert_called_once()
        assert sensor._cancel_timer is None

    async def test_async_will_remove_no_timer(self):
        from custom_components.idm_heatpump.sensor import IdmTechnicianCodeSensor

        coord = _make_coordinator()
        sensor = IdmTechnicianCodeSensor(coord, "level_1")
        sensor._cancel_timer = None
        # Should not raise
        await sensor.async_will_remove_from_hass()

    def test_async_refresh_writes_ha_state(self):
        from custom_components.idm_heatpump.sensor import IdmTechnicianCodeSensor

        coord = _make_coordinator()
        sensor = IdmTechnicianCodeSensor(coord, "level_1")
        sensor.async_write_ha_state = MagicMock()
        sensor._async_refresh()
        sensor.async_write_ha_state.assert_called_once()

    async def test_async_added_to_hass_starts_timer(self):
        from custom_components.idm_heatpump.sensor import IdmTechnicianCodeSensor
        from unittest.mock import patch, MagicMock

        coord = _make_coordinator()
        sensor = IdmTechnicianCodeSensor(coord, "level_1")
        sensor.hass = MagicMock()
        cancel_mock = MagicMock()

        with patch(
            "custom_components.idm_heatpump.sensor.async_track_time_interval",
            return_value=cancel_mock,
        ) as mock_timer:
            await sensor.async_added_to_hass()
        mock_timer.assert_called_once()
        assert sensor._cancel_timer is cancel_mock


# ---------------------------------------------------------------------------
# Binary sensor platform
# ---------------------------------------------------------------------------

class TestIdmBinarySensor:
    def test_is_on_true(self):
        from custom_components.idm_heatpump.binary_sensor import IdmBinarySensor

        coord = _make_coordinator(data={"fault": 1})
        reg = _make_register("fault")
        sensor = IdmBinarySensor(coord, reg, _make_desc("fault"))
        assert sensor.is_on is True

    def test_is_on_false(self):
        from custom_components.idm_heatpump.binary_sensor import IdmBinarySensor

        coord = _make_coordinator(data={"fault": 0})
        reg = _make_register("fault")
        sensor = IdmBinarySensor(coord, reg, _make_desc("fault"))
        assert sensor.is_on is False

    def test_is_on_none_returns_false(self):
        from custom_components.idm_heatpump.binary_sensor import IdmBinarySensor

        coord = _make_coordinator(data={})
        reg = _make_register("fault")
        sensor = IdmBinarySensor(coord, reg, _make_desc("fault"))
        assert sensor.is_on is False


class TestBinarySensorAsyncSetupEntry:
    async def test_creates_entities(self):
        from custom_components.idm_heatpump.binary_sensor import async_setup_entry

        coord = _make_coordinator()
        coord.binary_sensor_descriptions = [
            {"register": _make_register("fault"), "description": _make_desc("fault")},
        ]

        entry = MagicMock()
        entry.runtime_data.coordinator = coord

        added = []
        async_add = MagicMock(side_effect=lambda e: added.extend(e))
        await async_setup_entry(MagicMock(), entry, async_add)
        assert len(added) == 1

    async def test_empty_descriptions(self):
        from custom_components.idm_heatpump.binary_sensor import async_setup_entry

        coord = _make_coordinator()
        coord.binary_sensor_descriptions = []

        entry = MagicMock()
        entry.runtime_data.coordinator = coord

        added = []
        async_add = MagicMock(side_effect=lambda e: added.extend(e))
        await async_setup_entry(MagicMock(), entry, async_add)
        assert len(added) == 0


# ---------------------------------------------------------------------------
# Number platform
# ---------------------------------------------------------------------------

class TestIdmNumber:
    def test_native_value(self):
        from custom_components.idm_heatpump.number import IdmNumber

        coord = _make_coordinator(data={"dhw_target": 48.0})
        reg = _make_register("dhw_target", writable=True)
        num = IdmNumber(coord, reg, _make_desc("dhw_target"))
        assert num.native_value == 48.0

    def test_native_value_none_when_missing(self):
        from custom_components.idm_heatpump.number import IdmNumber

        coord = _make_coordinator(data={})
        reg = _make_register("dhw_target", writable=True)
        num = IdmNumber(coord, reg, _make_desc("dhw_target"))
        assert num.native_value is None

    def test_native_value_converts_to_float(self):
        from custom_components.idm_heatpump.number import IdmNumber

        coord = _make_coordinator(data={"dhw_target": 48})
        reg = _make_register("dhw_target", writable=True)
        num = IdmNumber(coord, reg, _make_desc("dhw_target"))
        assert isinstance(num.native_value, float)
        assert num.native_value == 48.0

    async def test_async_set_native_value(self):
        from custom_components.idm_heatpump.number import IdmNumber

        coord = _make_coordinator(data={"dhw_target": 48.0})
        reg = _make_register("dhw_target", writable=True)
        num = IdmNumber(coord, reg, _make_desc("dhw_target"))
        await num.async_set_native_value(55.0)
        coord.async_write_register.assert_called_once_with(reg, 55.0)

    async def test_async_set_native_value_raises_on_error(self):
        from homeassistant.exceptions import HomeAssistantError
        from custom_components.idm_heatpump.number import IdmNumber

        coord = _make_coordinator()
        coord.async_write_register = AsyncMock(side_effect=Exception("write failed"))
        reg = _make_register("dhw_target", writable=True)
        num = IdmNumber(coord, reg, _make_desc("dhw_target"))
        with pytest.raises(HomeAssistantError):
            await num.async_set_native_value(55.0)


class TestNumberAsyncSetupEntry:
    async def test_creates_entities(self):
        from custom_components.idm_heatpump.number import async_setup_entry

        coord = _make_coordinator()
        coord.number_descriptions = [
            {"register": _make_register("dhw_target", writable=True),
             "description": _make_desc("dhw_target")},
        ]

        entry = MagicMock()
        entry.runtime_data.coordinator = coord

        added = []
        async_add = MagicMock(side_effect=lambda e: added.extend(e))
        await async_setup_entry(MagicMock(), entry, async_add)
        assert len(added) == 1


# ---------------------------------------------------------------------------
# Select platform
# ---------------------------------------------------------------------------

class TestIdmSelect:
    def test_init_sets_options(self):
        from custom_components.idm_heatpump.select import IdmSelect

        enum_opts = {0: "Standby", 1: "Automatic", 2: "Away"}
        coord = _make_coordinator()
        reg = _make_register("system_mode", writable=True, enum_options=enum_opts)
        sel = IdmSelect(coord, reg, _make_desc("system_mode"))
        assert set(sel._attr_options) == {"Standby", "Automatic", "Away"}

    def test_current_option_found(self):
        from custom_components.idm_heatpump.select import IdmSelect

        enum_opts = {0: "Standby", 1: "Automatic"}
        coord = _make_coordinator(data={"system_mode": 1})
        reg = _make_register("system_mode", enum_options=enum_opts)
        sel = IdmSelect(coord, reg, _make_desc("system_mode"))
        assert sel.current_option == "Automatic"

    def test_current_option_none_when_missing(self):
        from custom_components.idm_heatpump.select import IdmSelect

        enum_opts = {0: "Standby"}
        coord = _make_coordinator(data={})
        reg = _make_register("system_mode", enum_options=enum_opts)
        sel = IdmSelect(coord, reg, _make_desc("system_mode"))
        assert sel.current_option is None

    def test_current_option_none_when_raw_none(self):
        from custom_components.idm_heatpump.select import IdmSelect

        enum_opts = {0: "Standby"}
        coord = _make_coordinator(data={"system_mode": None})
        reg = _make_register("system_mode", enum_options=enum_opts)
        sel = IdmSelect(coord, reg, _make_desc("system_mode"))
        assert sel.current_option is None

    def test_option_to_value(self):
        from custom_components.idm_heatpump.select import IdmSelect

        enum_opts = {0: "Standby", 1: "Automatic"}
        coord = _make_coordinator()
        reg = _make_register("system_mode", enum_options=enum_opts)
        sel = IdmSelect(coord, reg, _make_desc("system_mode"))
        assert sel._option_to_value("Automatic") == 1

    def test_option_to_value_raises_on_unknown(self):
        from custom_components.idm_heatpump.select import IdmSelect

        enum_opts = {0: "Standby"}
        coord = _make_coordinator()
        reg = _make_register("system_mode", enum_options=enum_opts)
        sel = IdmSelect(coord, reg, _make_desc("system_mode"))
        with pytest.raises(ValueError):
            sel._option_to_value("NonExistent")

    async def test_async_select_option(self):
        from custom_components.idm_heatpump.select import IdmSelect

        enum_opts = {0: "Standby", 1: "Automatic"}
        coord = _make_coordinator(data={"system_mode": 0})
        reg = _make_register("system_mode", writable=True, enum_options=enum_opts)
        sel = IdmSelect(coord, reg, _make_desc("system_mode"))
        await sel.async_select_option("Automatic")
        coord.async_write_register.assert_called_once_with(reg, 1)

    async def test_async_select_option_raises_on_error(self):
        from homeassistant.exceptions import HomeAssistantError
        from custom_components.idm_heatpump.select import IdmSelect

        enum_opts = {0: "Standby", 1: "Automatic"}
        coord = _make_coordinator()
        coord.async_write_register = AsyncMock(side_effect=Exception("write error"))
        reg = _make_register("system_mode", writable=True, enum_options=enum_opts)
        sel = IdmSelect(coord, reg, _make_desc("system_mode"))
        with pytest.raises(HomeAssistantError):
            await sel.async_select_option("Automatic")


class TestSelectAsyncSetupEntry:
    async def test_creates_entities_with_enum(self):
        from custom_components.idm_heatpump.select import async_setup_entry

        coord = _make_coordinator()
        enum_opts = {0: "Standby", 1: "Auto"}
        coord.select_descriptions = [
            {"register": _make_register("mode", enum_options=enum_opts),
             "description": _make_desc("mode")},
        ]

        entry = MagicMock()
        entry.runtime_data.coordinator = coord

        added = []
        async_add = MagicMock(side_effect=lambda e: added.extend(e))
        await async_setup_entry(MagicMock(), entry, async_add)
        assert len(added) == 1

    async def test_excludes_entries_without_enum(self):
        from custom_components.idm_heatpump.select import async_setup_entry

        coord = _make_coordinator()
        coord.select_descriptions = [
            # No enum_options -> should be excluded
            {"register": _make_register("temp"), "description": _make_desc("temp")},
        ]

        entry = MagicMock()
        entry.runtime_data.coordinator = coord

        added = []
        async_add = MagicMock(side_effect=lambda e: added.extend(e))
        await async_setup_entry(MagicMock(), entry, async_add)
        assert len(added) == 0


# ---------------------------------------------------------------------------
# Switch platform
# ---------------------------------------------------------------------------

class TestIdmSwitch:
    def test_is_on_true(self):
        from custom_components.idm_heatpump.switch import IdmSwitch

        coord = _make_coordinator(data={"heating_request": 1})
        reg = _make_register("heating_request", writable=True)
        sw = IdmSwitch(coord, reg, _make_desc("heating_request"))
        assert sw.is_on is True

    def test_is_on_false(self):
        from custom_components.idm_heatpump.switch import IdmSwitch

        coord = _make_coordinator(data={"heating_request": 0})
        reg = _make_register("heating_request", writable=True)
        sw = IdmSwitch(coord, reg, _make_desc("heating_request"))
        assert sw.is_on is False

    def test_is_on_none_returns_false(self):
        from custom_components.idm_heatpump.switch import IdmSwitch

        coord = _make_coordinator(data={})
        reg = _make_register("heating_request", writable=True)
        sw = IdmSwitch(coord, reg, _make_desc("heating_request"))
        assert sw.is_on is False

    async def test_async_turn_on(self):
        from custom_components.idm_heatpump.switch import IdmSwitch

        coord = _make_coordinator(data={"heating_request": 0})
        reg = _make_register("heating_request", writable=True)
        sw = IdmSwitch(coord, reg, _make_desc("heating_request"))
        await sw.async_turn_on()
        coord.async_write_register.assert_called_once_with(reg, True)

    async def test_async_turn_off(self):
        from custom_components.idm_heatpump.switch import IdmSwitch

        coord = _make_coordinator(data={"heating_request": 1})
        reg = _make_register("heating_request", writable=True)
        sw = IdmSwitch(coord, reg, _make_desc("heating_request"))
        await sw.async_turn_off()
        coord.async_write_register.assert_called_once_with(reg, False)

    async def test_async_turn_on_raises_on_error(self):
        from homeassistant.exceptions import HomeAssistantError
        from custom_components.idm_heatpump.switch import IdmSwitch

        coord = _make_coordinator()
        coord.async_write_register = AsyncMock(side_effect=Exception("write error"))
        reg = _make_register("heating_request", writable=True)
        sw = IdmSwitch(coord, reg, _make_desc("heating_request"))
        with pytest.raises(HomeAssistantError):
            await sw.async_turn_on()

    async def test_async_turn_off_raises_on_error(self):
        from homeassistant.exceptions import HomeAssistantError
        from custom_components.idm_heatpump.switch import IdmSwitch

        coord = _make_coordinator()
        coord.async_write_register = AsyncMock(side_effect=Exception("write error"))
        reg = _make_register("heating_request", writable=True)
        sw = IdmSwitch(coord, reg, _make_desc("heating_request"))
        with pytest.raises(HomeAssistantError):
            await sw.async_turn_off()


class TestSwitchAsyncSetupEntry:
    async def test_creates_entities(self):
        from custom_components.idm_heatpump.switch import async_setup_entry

        coord = _make_coordinator()
        coord.switch_descriptions = [
            {"register": _make_register("glt_heating", writable=True),
             "description": _make_desc("glt_heating")},
        ]

        entry = MagicMock()
        entry.runtime_data.coordinator = coord

        added = []
        async_add = MagicMock(side_effect=lambda e: added.extend(e))
        await async_setup_entry(MagicMock(), entry, async_add)
        assert len(added) == 1


# ---------------------------------------------------------------------------
# Technician codes
# ---------------------------------------------------------------------------

class TestTechnicianCodes:
    def test_returns_dict_with_two_keys(self):
        from custom_components.idm_heatpump.technician_codes import calculate_codes

        result = calculate_codes()
        assert "level_1" in result
        assert "level_2" in result

    def test_level_1_format(self):
        from datetime import datetime
        from custom_components.idm_heatpump.technician_codes import calculate_codes

        dt = datetime(2025, 3, 15, 10, 30)
        result = calculate_codes(dt)
        assert result["level_1"] == "1503"

    def test_level_2_format(self):
        from datetime import datetime
        from custom_components.idm_heatpump.technician_codes import calculate_codes

        dt = datetime(2025, 3, 15, 10, 30)
        # hours=10 -> hh_last=0, hh_first=1; year_last=5; month_last=3; day_last=5
        result = calculate_codes(dt)
        assert result["level_2"] == "01535"

    def test_uses_current_time_when_none(self):
        from custom_components.idm_heatpump.technician_codes import calculate_codes
        from datetime import datetime

        result = calculate_codes()
        now = datetime.now()
        # level_1 should be DDMM of today
        expected_level_1 = f"{now.day:02d}{now.month:02d}"
        assert result["level_1"] == expected_level_1

    def test_single_digit_day_and_month(self):
        from datetime import datetime
        from custom_components.idm_heatpump.technician_codes import calculate_codes

        dt = datetime(2025, 1, 5, 8, 0)
        result = calculate_codes(dt)
        assert result["level_1"] == "0501"

    def test_midnight_hour(self):
        from datetime import datetime
        from custom_components.idm_heatpump.technician_codes import calculate_codes

        dt = datetime(2025, 3, 15, 0, 0)
        result = calculate_codes(dt)
        # hours=00 -> hh_last=0, hh_first=0
        assert result["level_2"][0] == "0"
        assert result["level_2"][1] == "0"
