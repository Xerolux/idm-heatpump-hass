"""Contract tests for the entity name translations.

Home Assistant's ``entity-translations`` quality rule requires the visible name
of every entity to come from the translation files. These tests pin that for the
largest configuration the integration can build (7 heating circuits, 10 zone
modules with 8 rooms each, cascade, web supplement), so a register added by a
newer ``idm-heatpump-api`` release cannot ship without its name:

* every entity description carries a translation key that exists in
  ``strings.json`` with a ``name``;
* no description falls back to a hardcoded name;
* the placeholders in a name template are exactly the placeholders the entity
  supplies, so a template can never render with an unresolved ``{circuit}``;
* ``strings.json``, ``translations/en.json`` and ``translations/de.json`` stay
  in sync;
* the generated blocks are up to date with the generator.
"""

from __future__ import annotations

import json
import re
import string
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from custom_components.idm_heatpump.const import MAX_ROOM_COUNT, MAX_ZONE_COUNT
from custom_components.idm_heatpump.entity_names import (
    DERIVED_NAMES,
    ENGLISH_NAMES,
    translation_for_register,
    web_translation_for_value,
)
from custom_components.idm_heatpump.registers import (
    get_all_binary_sensor_descriptions,
    get_all_number_descriptions,
    get_all_select_descriptions,
    get_all_sensor_descriptions,
    get_all_switch_descriptions,
)

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION_DIR = ROOT / "custom_components" / "idm_heatpump"
GENERATOR = ROOT / "scripts" / "generate_entity_translations.py"

MAX_CIRCUITS = ["a", "b", "c", "d", "e", "f", "g"]
MAX_ZONE_ROOMS = {zone: MAX_ROOM_COUNT for zone in range(MAX_ZONE_COUNT)}


def _load(relative: str) -> dict:
    return json.loads((INTEGRATION_DIR / relative).read_text(encoding="utf-8"))


def _entity_block(relative: str) -> dict[str, dict[str, dict]]:
    return _load(relative)["entity"]


def _placeholders(template: str) -> set[str]:
    return {field for _, field, _, _ in string.Formatter().parse(template) if field}


def _register_descriptions() -> list[tuple[str, str, str]]:
    """Return (platform, register name, translation key) for the largest plant."""
    getters = (
        ("sensor", get_all_sensor_descriptions),
        ("binary_sensor", get_all_binary_sensor_descriptions),
        ("number", get_all_number_descriptions),
        ("select", get_all_select_descriptions),
        ("switch", get_all_switch_descriptions),
    )
    rows: list[tuple[str, str, str]] = []
    for platform, getter in getters:
        for entry in getter(MAX_CIRCUITS, MAX_ZONE_COUNT, MAX_ZONE_ROOMS):
            description = entry["description"]
            assert description.name in (None, ""), (
                f"{platform} entity {entry['register'].name} is named from a hardcoded "
                f"name ({description.name!r}) instead of a translation"
            )
            rows.append((platform, entry["register"].name, description.translation_key))
    return rows


class TestRegisterEntityNames:
    def test_every_register_entity_is_named_from_a_translation(self) -> None:
        strings = _entity_block("strings.json")

        for platform, register_name, translation_key in _register_descriptions():
            assert translation_key, f"{platform} entity {register_name} has no translation key"
            block = strings.get(platform, {}).get(translation_key)
            assert block is not None, f"{platform}.{translation_key} ({register_name}) is missing from strings.json"
            assert block.get("name"), f"{platform}.{translation_key} has no name"

    def test_name_placeholders_match_the_entity_placeholders(self) -> None:
        strings = _entity_block("strings.json")
        german = _entity_block("translations/de.json")

        for platform, register_name, translation_key in _register_descriptions():
            _, placeholders = translation_for_register(register_name)
            for language, block in (("en", strings), ("de", german)):
                template = block[platform][translation_key]["name"]
                assert _placeholders(template) == set(placeholders), (
                    f"{language} name of {platform}.{translation_key} expects "
                    f"{_placeholders(template)}, entity {register_name} supplies {set(placeholders)}"
                )

    def test_heating_circuits_and_zone_rooms_share_one_key(self) -> None:
        keys = {
            (platform, key)
            for platform, register_name, key in _register_descriptions()
            if register_name.startswith(("hc_", "zm"))
        }
        assert ("sensor", "hc_flow_temp") in keys
        assert ("sensor", "zone_room_temp") in keys
        assert not any(re.match(r"^hc_[a-g]_", key) for _, key in keys)
        assert not any(key.startswith("zm") for _, key in keys)


class TestDerivedEntityNames:
    def test_derived_names_are_shipped(self) -> None:
        strings = _entity_block("strings.json")

        for platform, names in DERIVED_NAMES.items():
            for key in names:
                assert strings.get(platform, {}).get(key, {}).get("name"), (
                    f"{platform}.{key} is missing from strings.json"
                )

    def test_web_values_resolve_to_a_shipped_key(self) -> None:
        from custom_components.idm_heatpump.sensor import _WEB_ONLY_EXTRA_VALUE_NAMES, _WEB_VALUE_NAMES
        from custom_components.idm_heatpump.web_binary_sensors import WEB_BINARY_VALUE_KEYS

        strings = _entity_block("strings.json")
        circuit_values = [
            f"{prefix}{letter}"
            for prefix in ("mixer_heating_circuit", "pump_heating_circuit", "flow_temp_HK_", "room_temperature_HK_")
            for letter in "ABCDEFG"
        ]
        for value_key in (*_WEB_VALUE_NAMES, *_WEB_ONLY_EXTRA_VALUE_NAMES, *WEB_BINARY_VALUE_KEYS, *circuit_values):
            key, placeholders = web_translation_for_value(value_key)
            platform = "binary_sensor" if value_key in WEB_BINARY_VALUE_KEYS else "sensor"
            block = strings.get(platform, {}).get(key)
            if block is None and platform == "sensor":
                # Heating-circuit pumps are binary sensors even though the value
                # key also appears in the sensor value list.
                block = strings.get("binary_sensor", {}).get(key)
            assert block is not None and block.get("name"), f"web value {value_key} has no name ({key})"
            assert _placeholders(block["name"]) == set(placeholders), (
                f"web value {value_key} supplies {set(placeholders)} for name {block['name']!r}"
            )


class TestTranslationFilesStayInSync:
    def test_english_translation_matches_strings(self) -> None:
        assert _entity_block("translations/en.json") == _entity_block("strings.json")

    def test_german_covers_every_english_key(self) -> None:
        english = _entity_block("strings.json")
        german = _entity_block("translations/de.json")

        for platform, keys in english.items():
            for key, payload in keys.items():
                assert key in german.get(platform, {}), f"de.json is missing {platform}.{key}"
                if "name" in payload:
                    assert german[platform][key].get("name"), f"de.json has no name for {platform}.{key}"
                for state_key in payload.get("state", {}):
                    assert state_key in german[platform][key].get("state", {}), (
                        f"de.json is missing state {platform}.{key}.{state_key}"
                    )

    def test_every_english_name_is_reachable(self) -> None:
        """No stale translation keys: the shipped names come from the tables."""
        strings = _entity_block("strings.json")
        known = set(ENGLISH_NAMES)
        for names in DERIVED_NAMES.values():
            known.update(names)
        # Entities that are not built from a register table: the config-flow
        # driven controls and the API version sensor keep hand-written keys.
        hand_written = {
            "heating_circuit",
            "zone_room",
            "water_heater",
            "idm_api_version",
            "modbus_active_registers",
            "modbus_consecutive_failures",
            "modbus_last_success",
            "modbus_poll_duration",
            "acknowledge_errors",
            "dhw_boost_start",
            "dhw_boost_cancel",
        }
        for platform, keys in strings.items():
            for key, payload in keys.items():
                if "name" not in payload:
                    continue
                assert key in known or key in hand_written, f"{platform}.{key} has no name source"


class TestGeneratorStaysAuthoritative:
    def test_generated_blocks_are_up_to_date(self) -> None:
        try:
            import idm_heatpump  # noqa: F401
        except ImportError:  # pragma: no cover - only in stubbed environments
            pytest.skip("idm-heatpump-api is stubbed; the generator needs the real library")
        if isinstance(getattr(sys.modules.get("idm_heatpump"), "build_register_map", None), MagicMock):
            pytest.skip("idm-heatpump-api is stubbed; the generator needs the real library")

        result = subprocess.run(
            [sys.executable, str(GENERATOR), "--check"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stdout or result.stderr
