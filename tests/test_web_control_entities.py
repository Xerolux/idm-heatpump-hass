"""Tests for the web-only control entities and the web write routing (Phase 4)."""

from __future__ import annotations

from dataclasses import replace as dc_replace
from unittest.mock import AsyncMock, MagicMock

import pytest
from idm_heatpump import (
    IdmWebHeatingCircuit,
    IdmWebHeatingCircuitChoice,
    IdmWebHeatingCircuitRef,
    IdmWebHeatingCircuitValue,
    IdmWebHomeOverview,
    IdmWebSettingParameter,
    IdmWebSystemMode,
)

from custom_components.idm_heatpump.const import CONNECTION_MODE_WEB_ONLY
from custom_components.idm_heatpump.web_control_entities import (
    web_control_button_entities,
    web_control_heatingcircuit_entities,
    web_control_number_entities,
    web_control_select_entities,
)
from custom_components.idm_heatpump.web_data import IdmWebSupplement


def _circuit(hc_id="A", mode_value=2, setpoint=21.5, minimum=15.0, maximum=30.0, param="HKA"):
    return IdmWebHeatingCircuit(
        hc_id=hc_id,
        display_name=f"{hc_id} OG",
        mode_value=mode_value,
        mode_parameter_id=f"{param}01",
        mode_options=(
            IdmWebHeatingCircuitChoice(0, "N2_OFF"),
            IdmWebHeatingCircuitChoice(1, "N2_TIMETABLE"),
            IdmWebHeatingCircuitChoice(2, "N2_NORMAL"),
        ),
        setpoint_normal=IdmWebHeatingCircuitValue(
            parameter_id=f"{param}04", value=setpoint, min_value=minimum, max_value=maximum, increment="0.1"
        ),
        room_temperature=21.4,
        pump_active=False,
        available_circuits=(IdmWebHeatingCircuitRef("A", "A OG", 1),),
    )


def _setpoint_parameter(value=48.0, minimum=30.0, maximum=60.0):
    return IdmWebSettingParameter(
        setting_id="13256",
        name="N2_HOT_WATER_DESIRED_TEMP",
        param="FW030",
        type="float",
        value=value,
        min_value=minimum,
        max_value=maximum,
        increment="0.5",
        unit="N2_GRAD",
    )


def _coordinator(*, connection_mode: str | None = CONNECTION_MODE_WEB_ONLY, variant: str = "nav10"):
    coordinator = MagicMock()
    coordinator.web_supplement = IdmWebSupplement(
        web_variant=variant,
        dhw_setpoint=_setpoint_parameter(),
        heating_circuits=(_circuit("A"), _circuit("D", mode_value=0, setpoint=22.0, param="HKD")),
        home_overview=IdmWebHomeOverview(
            system_mode=IdmWebSystemMode(
                value=1,
                options=(-1, 0, 1, 2, 3, 5, 4),
                cooling_configured=False,
            )
        ),
    )
    coordinator.async_web_set_system_mode = AsyncMock()
    coordinator.async_web_acknowledge_notifications = AsyncMock()
    coordinator.async_web_set_dhw_setpoint = AsyncMock()
    coordinator.async_web_set_heatingcircuit_parameter = AsyncMock()
    entry = coordinator.config_entry
    entry.entry_id = "web_entry"
    if connection_mode is None:
        entry.options = {}
        entry.data = {}
    else:
        entry.options = {"connection_mode": connection_mode}
        entry.data = {}
    return coordinator


class TestEntityCreation:
    def test_entities_exist_in_web_only_nav10(self):
        coordinator = _coordinator()
        assert len(web_control_select_entities(coordinator)) == 1
        assert len(web_control_button_entities(coordinator)) == 1
        assert len(web_control_number_entities(coordinator)) == 1

    def test_no_entities_in_modbus_modes(self):
        coordinator = _coordinator(connection_mode="auto")
        assert web_control_select_entities(coordinator) == []
        assert web_control_button_entities(coordinator) == []
        assert web_control_number_entities(coordinator) == []

    def test_no_entities_on_nav20(self):
        coordinator = _coordinator(variant="nav20")
        assert web_control_select_entities(coordinator) == []
        assert web_control_button_entities(coordinator) == []
        assert web_control_number_entities(coordinator) == []


class TestSystemModeSelect:
    def test_options_follow_the_device_list_without_unknown(self):
        select = web_control_select_entities(_coordinator())[0]

        options = select.options
        assert "automatic" in options
        assert "hot_water_only" in options
        # -1 (unknown) appears in the device list but is not writable.
        assert len([o for o in options]) == 6

    def test_current_option_maps_the_device_value(self):
        select = web_control_select_entities(_coordinator())[0]

        assert select.current_option == "automatic"

    def test_current_option_none_without_overview(self):
        coordinator = _coordinator()
        coordinator.web_supplement = IdmWebSupplement(web_variant="nav10")
        select = web_control_select_entities(coordinator)[0]

        assert select.current_option is None

    async def test_select_option_routes_through_the_web_write(self):
        coordinator = _coordinator()
        select = web_control_select_entities(coordinator)[0]

        await select.async_select_option("hot_water_only")

        coordinator.async_web_set_system_mode.assert_awaited_once_with(4)

    async def test_unknown_option_is_rejected(self):
        coordinator = _coordinator()
        select = web_control_select_entities(coordinator)[0]

        try:
            await select.async_select_option("warp_drive")
        except ValueError:
            pass
        else:
            raise AssertionError("unknown option must raise")
        coordinator.async_web_set_system_mode.assert_not_awaited()


class TestAcknowledgeButton:
    async def test_press_routes_through_the_web_write(self):
        coordinator = _coordinator()
        button = web_control_button_entities(coordinator)[0]

        await button.async_press()

        coordinator.async_web_acknowledge_notifications.assert_awaited_once()


class TestDhwSetpointNumber:
    def test_bounds_and_value_come_from_the_device_declaration(self):
        number = web_control_number_entities(_coordinator())[0]

        assert number.native_value == 48.0
        assert number.native_min_value == 30.0
        assert number.native_max_value == 60.0
        assert number.native_step == 0.5

    def test_unavailable_without_a_parameter(self):
        coordinator = _coordinator()
        coordinator.web_supplement = IdmWebSupplement(web_variant="nav10")
        number = web_control_number_entities(coordinator)[0]

        assert number.available is False
        assert number.native_value is None

    def test_fallback_bounds_when_the_device_declares_none(self):
        parameter = _setpoint_parameter(minimum=None, maximum=None)
        parameter = IdmWebSettingParameter(setting_id="13256", param="FW030", value=48.0, increment=None)
        coordinator = _coordinator()
        coordinator.web_supplement = IdmWebSupplement(web_variant="nav10", dhw_setpoint=parameter)
        number = web_control_number_entities(coordinator)[0]

        assert number.native_min_value == 30.0
        assert number.native_max_value == 60.0
        assert number.native_step == 0.5

    async def test_write_routes_through_the_web_path(self):
        coordinator = _coordinator()
        number = web_control_number_entities(coordinator)[0]

        await number.async_set_native_value(49.0)

        coordinator.async_web_set_dhw_setpoint.assert_awaited_once_with(49.0)


class TestHeatingCircuitEntities:
    def test_two_entities_per_circuit_are_created(self):
        entities = web_control_heatingcircuit_entities(_coordinator())
        assert len(entities) == 4  # setpoint + mode for A and D

    def test_no_entities_without_circuits(self):
        coordinator = _coordinator()
        coordinator.web_supplement = IdmWebSupplement(web_variant="nav10")
        assert web_control_heatingcircuit_entities(coordinator) == []

    def test_setpoint_uses_device_declared_bounds(self):
        entities = web_control_heatingcircuit_entities(_coordinator())
        numbers = [e for e in entities if isinstance(e, type(entities[0])) and "setpoint" in e._attr_unique_id]
        number_a = next(e for e in numbers if "_a_" in e._attr_unique_id)
        assert number_a.native_value == 21.5
        assert number_a.native_min_value == 15.0
        assert number_a.native_max_value == 30.0
        assert number_a.native_step == 0.1

    async def test_setpoint_write_routes_through_the_web_path(self):
        coordinator = _coordinator()
        entities = web_control_heatingcircuit_entities(coordinator)
        number_a = next(e for e in entities if "setpoint" in e._attr_unique_id and "_a_" in e._attr_unique_id)
        await number_a.async_set_native_value(22.0)
        coordinator.async_web_set_heatingcircuit_parameter.assert_awaited_once_with(
            "HKA04", 22.0, min_value=15.0, max_value=30.0
        )

    def test_mode_options_follow_the_device_chooselist(self):
        entities = web_control_heatingcircuit_entities(_coordinator())
        select_a = next(e for e in entities if "_mode" in e._attr_unique_id and "_a_" in e._attr_unique_id)
        assert select_a.options == ["off", "timed_program", "normal"]
        assert select_a.current_option == "normal"

    async def test_mode_write_routes_through_the_web_path(self):
        coordinator = _coordinator()
        entities = web_control_heatingcircuit_entities(coordinator)
        select_a = next(e for e in entities if "_mode" in e._attr_unique_id and "_a_" in e._attr_unique_id)
        await select_a.async_select_option("eco")
        coordinator.async_web_set_heatingcircuit_parameter.assert_awaited_once_with("HKA01", 3.0)


def _circuit_a_with(**changes):
    """Return heating circuit A with individual fields replaced."""
    return dc_replace(_circuit("A"), **changes)


def _replace_circuits(coordinator, *circuits):
    """Point the coordinator's supplement at a new circuit tuple."""
    coordinator.web_supplement = dc_replace(coordinator.web_supplement, heating_circuits=tuple(circuits))


class TestWebControlGate:
    def test_no_entities_without_a_config_entry(self):
        coordinator = _coordinator()
        coordinator.config_entry = None

        assert web_control_select_entities(coordinator) == []
        assert web_control_number_entities(coordinator) == []
        assert web_control_button_entities(coordinator) == []
        assert web_control_heatingcircuit_entities(coordinator) == []

    def test_no_heating_circuit_entities_outside_web_only(self):
        coordinator = _coordinator(connection_mode="auto")

        assert web_control_heatingcircuit_entities(coordinator) == []

    def test_circuits_without_an_id_are_skipped(self):
        coordinator = _coordinator()
        _replace_circuits(coordinator, IdmWebHeatingCircuit(hc_id=""), _circuit("A"))

        unique_ids = {e._attr_unique_id for e in web_control_heatingcircuit_entities(coordinator)}

        assert len(unique_ids) == 2  # setpoint + mode of circuit A only
        assert all("_a_" in uid for uid in unique_ids)

    def test_differential_circuits_get_no_web_controls(self):
        coordinator = _coordinator()
        coordinator.config_entry.options = {
            "connection_mode": CONNECTION_MODE_WEB_ONLY,
            "heating_circuits": ["a", "d"],
            "differential_circuits": ["a"],
        }

        entities = web_control_heatingcircuit_entities(coordinator)

        assert len(entities) == 2  # circuit D keeps both, differential A is excluded
        assert all("_d_" in e._attr_unique_id for e in entities)


class TestWebControlDeviceInfo:
    def test_every_control_reports_the_main_device(self):
        coordinator = _coordinator()
        main_info = {"identifiers": {("idm_heatpump", "web_entry")}}
        coordinator.device_info = MagicMock(return_value=main_info)

        assert web_control_select_entities(coordinator)[0].device_info is main_info
        assert web_control_number_entities(coordinator)[0].device_info is main_info
        assert web_control_button_entities(coordinator)[0].device_info is main_info
        for entity in web_control_heatingcircuit_entities(coordinator):
            assert entity.device_info is main_info


class TestSystemModeSelectGuards:
    def test_current_option_none_once_the_supplement_is_gone(self):
        coordinator = _coordinator()
        select = web_control_select_entities(coordinator)[0]
        coordinator.web_supplement = None

        assert select.current_option is None
        assert select.available is False


class TestDhwSetpointNumberGuards:
    def test_unavailable_once_the_supplement_is_gone(self):
        coordinator = _coordinator()
        number = web_control_number_entities(coordinator)[0]
        coordinator.web_supplement = None

        assert number.available is False
        assert number.native_value is None
        assert number.native_min_value == 30.0
        assert number.native_max_value == 60.0
        assert number.native_step == 0.5


class TestHeatingCircuitSetpointGuards:
    def _number_a(self, coordinator):
        entities = web_control_heatingcircuit_entities(coordinator)
        return next(e for e in entities if "setpoint" in e._attr_unique_id and "_a_" in e._attr_unique_id)

    def test_available_while_the_circuit_and_setpoint_exist(self):
        assert self._number_a(_coordinator()).available is True

    def test_unavailable_once_the_supplement_is_gone(self):
        coordinator = _coordinator()
        number = self._number_a(coordinator)
        coordinator.web_supplement = None

        assert number.available is False
        assert number.native_value is None

    def test_unavailable_when_the_circuit_disappears(self):
        coordinator = _coordinator()
        number = self._number_a(coordinator)
        _replace_circuits(coordinator, _circuit("D", mode_value=0, setpoint=22.0, param="HKD"))

        assert number.available is False
        assert number.native_value is None

    def test_native_value_none_when_the_device_value_is_missing(self):
        coordinator = _coordinator()
        number = self._number_a(coordinator)
        _replace_circuits(
            coordinator,
            _circuit_a_with(setpoint_normal=IdmWebHeatingCircuitValue(parameter_id="HKA04")),
        )

        assert number.native_value is None

    def test_step_falls_back_without_a_numeric_increment(self):
        coordinator = _coordinator()
        number = self._number_a(coordinator)
        _replace_circuits(
            coordinator,
            _circuit_a_with(
                setpoint_normal=IdmWebHeatingCircuitValue(parameter_id="HKA04", value=21.5, increment="auto")
            ),
        )

        assert number.native_step == 0.1

    async def test_write_is_skipped_without_a_setpoint_parameter(self):
        coordinator = _coordinator()
        number = self._number_a(coordinator)
        _replace_circuits(coordinator, _circuit_a_with(setpoint_normal=None))

        await number.async_set_native_value(22.0)

        coordinator.async_web_set_heatingcircuit_parameter.assert_not_awaited()


class TestHeatingCircuitModeGuards:
    def _select_a(self, coordinator):
        entities = web_control_heatingcircuit_entities(coordinator)
        return next(e for e in entities if "_mode" in e._attr_unique_id and "_a_" in e._attr_unique_id)

    def test_available_while_the_mode_parameter_exists(self):
        assert self._select_a(_coordinator()).available is True

    def test_unavailable_once_the_supplement_is_gone(self):
        coordinator = _coordinator()
        select = self._select_a(coordinator)
        coordinator.web_supplement = None

        assert select.available is False
        assert select.current_option is None

    def test_unavailable_when_the_circuit_disappears(self):
        coordinator = _coordinator()
        select = self._select_a(coordinator)
        _replace_circuits(coordinator, _circuit("D", mode_value=0, setpoint=22.0, param="HKD"))

        assert select.available is False

    def test_current_option_none_without_a_mode_value(self):
        coordinator = _coordinator()
        select = self._select_a(coordinator)
        _replace_circuits(coordinator, _circuit("A", mode_value=None))

        assert select.current_option is None

    async def test_unknown_option_is_rejected(self):
        coordinator = _coordinator()
        select = self._select_a(coordinator)

        with pytest.raises(ValueError, match="Unknown heating-circuit mode"):
            await select.async_select_option("warp_drive")

        coordinator.async_web_set_heatingcircuit_parameter.assert_not_awaited()

    async def test_write_is_skipped_without_a_mode_parameter(self):
        coordinator = _coordinator()
        select = self._select_a(coordinator)
        _replace_circuits(coordinator, _circuit_a_with(mode_parameter_id=None))

        await select.async_select_option("normal")

        coordinator.async_web_set_heatingcircuit_parameter.assert_not_awaited()
