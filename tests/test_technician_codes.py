"""Controller-family-specific installer code regression tests."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from custom_components.idm_heatpump.device_hierarchy import cleanup_disabled_feature_entities
from custom_components.idm_heatpump.sensor import IdmTechnicianCodeSensor, _technician_code_entities
from custom_components.idm_heatpump.technician_codes import calculate_codes, technician_code_levels


@pytest.mark.parametrize(
    "day,hour,expected", [(18, 16, "016"), (19, 16, "116"), (18, 0, "000"), (19, 9, "109"), (31, 23, "123")]
)
def test_navigator17_code_preserves_all_three_digits(day, hour, expected):
    assert calculate_codes(datetime(2026, 10, day, hour), model_name="Navigator 1.7") == {"level_1": expected}


@pytest.mark.parametrize("model", ["Navigator 1.7", "navigator_17", "Navigator 1_7", "Navigator  1.7"])
def test_navigator17_has_only_one_level(model):
    assert technician_code_levels(model) == ("level_1",)
    coordinator = SimpleNamespace(model_name=model, config_entry=SimpleNamespace(entry_id="entry"))
    entities = _technician_code_entities(coordinator)
    assert len(entities) == 1
    assert entities[0]._attr_unique_id == "entry_technician_level_1"


@pytest.mark.parametrize("model", [None, "Navigator 2.0", "Navigator 10", "Navigator Pro", "Navigator 170"])
def test_modern_controller_codes_are_unchanged(model):
    now = datetime(2026, 10, 18, 16)
    assert calculate_codes(now, model_name=model) == calculate_codes(now)
    assert technician_code_levels(model) == ("level_1", "level_2")


def test_sensor_cached_and_uncached_values_use_controller_family_and_ha_local_time():
    coordinator = SimpleNamespace(model_name="Navigator 1.7", config_entry=SimpleNamespace(entry_id="entry"))
    sensor = IdmTechnicianCodeSensor(coordinator, "level_1")
    with patch("custom_components.idm_heatpump.sensor.dt_util.now", return_value=datetime(2026, 10, 18, 16)):
        assert sensor.native_value == "016"
        sensor._refresh_codes()
        assert sensor.native_value == "016"
    with patch("custom_components.idm_heatpump.sensor.dt_util.now", return_value=datetime(2026, 10, 19, 0)):
        sensor._refresh_codes()
        assert sensor.native_value == "100"


def test_reload_removes_only_obsolete_level2_for_navigator17():
    coordinator = SimpleNamespace(
        model_name="Navigator 1.7", config_entry=SimpleNamespace(entry_id="entry", options={})
    )
    entries = [
        SimpleNamespace(unique_id="entry_technician_level_2", entity_id="sensor.old_level2"),
        SimpleNamespace(unique_id="entry_technician_level_1", entity_id="sensor.level1"),
        SimpleNamespace(unique_id="other_technician_level_2", entity_id="sensor.other"),
    ]
    registry = MagicMock()
    with (
        patch("custom_components.idm_heatpump.device_hierarchy.er.async_get", return_value=registry),
        patch(
            "custom_components.idm_heatpump.device_hierarchy.er.async_entries_for_config_entry", return_value=entries
        ),
    ):
        cleanup_disabled_feature_entities(MagicMock(), coordinator)
    registry.async_remove.assert_called_once_with("sensor.old_level2")
