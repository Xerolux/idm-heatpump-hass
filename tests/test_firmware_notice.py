"""Firmware orientation is per-entry, explicit and never installs software."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from test_firmware_observations import make_firmware

from custom_components.idm_heatpump import _entry_reload_fingerprint
from custom_components.idm_heatpump.firmware_notice import ACK_KEY, clear_notices, ensure_notice, fingerprint
from custom_components.idm_heatpump.repairs import async_create_fix_flow
from custom_components.idm_heatpump.telemetry_entities import firmware_binary_sensor_entities


def test_binary_orientation_does_not_turn_unknown_into_no_update():
    firmware, entry, coordinator = make_firmware()
    entry.runtime_data = SimpleNamespace(firmware=firmware)
    coordinator.config_entry = entry
    sensor = firmware_binary_sensor_entities(MagicMock(), entry, coordinator)[0]
    assert not sensor.available and sensor.is_on is None
    for value in (True, False):
        firmware.firmware_result = {"newer_observed": value, "latest_firmware": "NAV10_20.24-12"}
        assert sensor.available and sensor.is_on is value
        assert "confirm availability" in sensor.extra_state_attributes["availability_note"]
    entry.options["firmware_check"] = False
    assert not sensor.available
    with patch("custom_components.idm_heatpump.telemetry_entities.er.async_get") as registry:
        registry.return_value.async_get_entity_id.return_value = "binary_sensor.example_firmware"
        assert firmware_binary_sensor_entities(MagicMock(), entry, coordinator) == []
        registry.return_value.async_remove.assert_called_once()


async def test_confirmation_survives_reload_and_only_new_version_notifies():
    hass = MagicMock()
    entry = SimpleNamespace(entry_id="example", data={"host": "example.invalid"})
    hass.config_entries.async_get_entry.return_value = entry
    hass.config_entries.async_update_entry.side_effect = lambda target, **kwargs: setattr(
        target, "data", kwargs["data"]
    )
    result = {"newer_observed": True, "installed_firmware": "NAV10_20.24-1", "latest_firmware": "NAV10_20.24-2"}
    with patch("custom_components.idm_heatpump.firmware_notice.ir.async_create_issue") as create:
        ensure_notice(hass, entry, result)
        issue = create.call_args.args[2]
        data = create.call_args.kwargs["data"]
        flow = await async_create_fix_flow(hass, issue, data)
        assert (await flow.async_step_init())["type"] == "form"
        assert (await flow.async_step_confirm({}))["type"] == "create_entry"
        assert entry.data[ACK_KEY] == [fingerprint(result["latest_firmware"])]
        create.reset_mock()
        ensure_notice(hass, entry, result)
        create.assert_not_called()
        ensure_notice(hass, entry, result | {"latest_firmware": "NAV10_20.24-3"})
        create.assert_called_once()
        create.reset_mock()
        ensure_notice(hass, entry, result | {"newer_observed": False})
        create.assert_not_called()
        assert "install" not in flow.__dict__


async def test_acknowledgement_refuses_missing_entry_or_mismatched_version():
    hass = MagicMock()
    hass.config_entries.async_get_entry.return_value = None
    data = {"entry_id": "example", "firmware": "NAV10_20.24-2", "fingerprint": fingerprint("NAV10_20.24-2")}
    issue = "firmware_observed_example_" + data["fingerprint"][:16]
    flow = await async_create_fix_flow(hass, issue, data)
    assert (await flow.async_step_init())["reason"] == "entry_not_found"
    hass.config_entries.async_get_entry.return_value = SimpleNamespace(entry_id="example", data={})
    for changed in (data | {"fingerprint": "wrong"}, data | {"firmware": None}):
        flow = await async_create_fix_flow(hass, issue, changed)
        assert (await flow.async_step_confirm({}))["reason"] == "entry_not_found"
    flow = await async_create_fix_flow(hass, issue + "wrong", data)
    assert (await flow.async_step_confirm({}))["reason"] == "entry_not_found"
    hass.config_entries.async_update_entry.assert_not_called()


def test_notice_cleanup_and_fingerprint_do_not_affect_other_entries():
    hass = MagicMock()
    with (
        patch("custom_components.idm_heatpump.firmware_notice.ir.async_get") as registry,
        patch("custom_components.idm_heatpump.firmware_notice.ir.async_delete_issue") as delete,
    ):
        registry.return_value.issues = {
            ("idm_heatpump", "firmware_observed_example_a"): None,
            ("idm_heatpump", "firmware_observed_other_a"): None,
            ("other", "firmware_observed_example_a"): None,
        }
        clear_notices(hass, "example", keep="firmware_observed_example_a")
        delete.assert_not_called()
        clear_notices(hass, "example")
        delete.assert_called_once_with(hass, "idm_heatpump", "firmware_observed_example_a")
    entry = SimpleNamespace(data={"host": "example.invalid"}, options={})
    before = _entry_reload_fingerprint(entry)
    entry.data[ACK_KEY] = ["a"]
    assert _entry_reload_fingerprint(entry) == before


@pytest.mark.parametrize("version", ["NAV10_20.99-test", "T_NAV10_20.99-test", " t_nav10_20.99-test "])
def test_controller_firmware_prefixes_are_not_confused_with_http_protocol(version):
    from custom_components.idm_heatpump.web_data import _firmware_indicates_nav10

    assert _firmware_indicates_nav10(version)


@pytest.mark.parametrize("version", [None, "", "NAV100_20.99", "T_NAV100_20.99", "T_NAV20_20.99", "prefix_NAV10_20.99"])
def test_unrelated_prefixes_do_not_identify_navigator10(version):
    from custom_components.idm_heatpump.web_data import _firmware_indicates_nav10

    assert not _firmware_indicates_nav10(version)


def test_firmware_comparison_entities_share_the_diagnostics_subdevice():
    from custom_components.idm_heatpump.device_hierarchy import resolve_device_scope
    from custom_components.idm_heatpump.telemetry_entities import IdmFirmwareObservedBinarySensor

    _firmware, entry, coordinator = make_firmware()
    coordinator.config_entry = entry
    sensor = IdmFirmwareObservedBinarySensor(coordinator)
    assert sensor.entity_description.key == "firmware_update_observed"
    for key in ("software_version", "telemetry_latest_firmware", "firmware_update_observed"):
        assert resolve_device_scope(key).kind == "diagnostics"
