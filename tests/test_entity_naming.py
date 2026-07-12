"""Entity naming contracts for control platforms."""

from __future__ import annotations

import json
from pathlib import Path


INTEGRATION_DIR = Path(__file__).resolve().parents[1] / "custom_components" / "idm_heatpump"


def _load_json(relative_path: str) -> dict[str, object]:
    return json.loads((INTEGRATION_DIR / relative_path).read_text(encoding="utf-8"))


def test_control_entity_names_are_declared_in_canonical_strings() -> None:
    """Canonical strings must contain every translated control entity name."""
    entity_strings = _load_json("strings.json")["entity"]

    assert entity_strings["climate"]["heating_circuit"]["name"] == "Heating Circuit {circuit}"
    assert entity_strings["climate"]["zone_room"]["name"] == "Zone {zone} Room {room}"
    assert entity_strings["water_heater"]["water_heater"]["name"] == "Domestic Hot Water"
    assert entity_strings["button"]["acknowledge_errors"]["name"] == "Acknowledge Errors"


def test_german_control_entity_names_are_user_facing() -> None:
    """German names must describe the control instead of falling back to the device name."""
    entity_strings = _load_json("translations/de.json")["entity"]

    assert entity_strings["climate"]["heating_circuit"]["name"] == "Heizkreis {circuit}"
    assert entity_strings["climate"]["zone_room"]["name"] == "Zone {zone} Raum {room}"
    assert entity_strings["water_heater"]["water_heater"]["name"] == "Warmwasser"


def test_control_entities_do_not_override_their_translated_names() -> None:
    """Control entities must opt into translation without masking the result."""
    climate_source = (INTEGRATION_DIR / "climate.py").read_text(encoding="utf-8")
    water_heater_source = (INTEGRATION_DIR / "water_heater.py").read_text(encoding="utf-8")

    assert "_attr_name = None" not in climate_source
    assert '_attr_translation_key = "water_heater"' in water_heater_source
    assert "_attr_name = None" not in water_heater_source
    assert "STATE_HEAT_PUMP" in water_heater_source
    assert "STATE_PERFORMANCE" not in water_heater_source
