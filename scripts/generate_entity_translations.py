#!/usr/bin/env python3
"""Generate the entity name blocks in strings.json and the translation files.

Entity names must come from the translation files (Home Assistant quality scale
rule ``entity-translations``). The register space is generated, so the names are
generated too:

* the translation key and its placeholders come from
  ``custom_components/idm_heatpump/entity_names.py``;
* the English names come from ``ENGLISH_NAMES`` in the same module;
* the German names come from ``adapter_metadata.py`` (explicit overrides) and
  ``adapter_names.py`` (the register name table), i.e. exactly the names the
  integration showed before the entities were translated.

Like ``generate_entity_metadata_catalog.py`` the generator avoids importing Home
Assistant: ``adapter_metadata.py`` is parsed with ``ast`` and the remaining
integration modules are loaded by file path. ``idm-heatpump-api`` is imported
normally because it is a plain, HA-free library.

Usage::

    python scripts/generate_entity_translations.py            # rewrite the files
    python scripts/generate_entity_translations.py --check    # verify only
"""

from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "idm_heatpump"
METADATA_PATH = INTEGRATION / "adapter_metadata.py"

TARGET_FILES: dict[str, Path] = {
    "en": INTEGRATION / "strings.json",
    "en_translation": INTEGRATION / "translations" / "en.json",
    "de": INTEGRATION / "translations" / "de.json",
}

# Representative indexes used to derive the placeholder templates. They are
# deliberately different from each other and from 1 so a zone number can never
# be confused with a room number while the placeholders are substituted.
SAMPLE_CIRCUIT = "c"
SAMPLE_ZONE = 7
SAMPLE_ROOM = 3

CIRCUITS = ("a", "b", "c", "d", "e", "f", "g")
MAX_ZONE_MODULES = 10
MAX_ROOMS_PER_ZONE = 8


def _load_module(name: str, path: Path) -> ModuleType:
    """Import an HA-free integration module by file path."""
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        msg = f"Cannot load {path}"
        raise RuntimeError(msg)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


entity_names = _load_module("idm_entity_names", INTEGRATION / "entity_names.py")
adapter_names = _load_module("idm_adapter_names", INTEGRATION / "adapter_names.py")
adapter_glt = _load_module("idm_adapter_glt", INTEGRATION / "adapter_glt.py")


def _metadata_names() -> dict[str, str]:
    """Return the explicit German name overrides from adapter_metadata.py."""
    tree = ast.parse(METADATA_PATH.read_text(encoding="utf-8"), filename=str(METADATA_PATH))
    names: dict[str, str] = {}
    for node in tree.body:
        target = None
        if isinstance(node, ast.Assign) and node.targets and isinstance(node.targets[0], ast.Name):
            target = node.targets[0].id
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            target = node.target.id
        if target not in {"SENSOR_METADATA", "NUMBER_METADATA"}:
            continue
        table = node.value
        if not isinstance(table, ast.Dict):
            continue
        for register_node, meta_node in zip(table.keys, table.values, strict=True):
            if not isinstance(register_node, ast.Constant) or not isinstance(meta_node, ast.Dict):
                continue
            for key_node, value_node in zip(meta_node.keys, meta_node.values, strict=True):
                if (
                    isinstance(key_node, ast.Constant)
                    and key_node.value == "name"
                    and isinstance(value_node, ast.Constant)
                ):
                    names[str(register_node.value)] = str(value_node.value)
    return names


def _register_space() -> dict[str, Any]:
    """Return every register the integration can expose, in its largest layout."""
    import idm_heatpump as library

    registers: dict[str, Any] = dict(
        library.build_register_map(None, list(CIRCUITS), MAX_ZONE_MODULES, MAX_ROOMS_PER_ZONE)
    )
    for circuit in CIRCUITS:
        registers.update(library.get_heating_circuit_registers(circuit))
    for zone in range(1, MAX_ZONE_MODULES + 1):
        registers.update(library.get_zone_module_registers(zone, MAX_ROOMS_PER_ZONE))
    return registers


def _platforms_for(name: str, register: Any) -> tuple[str, ...]:
    """Return the platforms a register is exposed on.

    Mirrors the filters in ``library_adapter.py``. ``tests/test_entity_translations.py``
    checks the result against the entities the platform generators really build,
    so a drift between the two cannot go unnoticed.
    """
    datatype = register.datatype.value
    writable = bool(register.writable)
    write_only = bool(register.write_only)
    binary = bool(register.binary) or name.endswith("_relay")
    glt = adapter_glt.is_glt_measurement(name)

    platforms: list[str] = []
    if binary and not writable:
        platforms.append("binary_sensor")
    elif not write_only and (not writable or glt):
        platforms.append("sensor")
    if writable and not write_only:
        if register.enum_options and datatype != "BITFLAG":
            platforms.append("select")
        elif datatype == "BOOL":
            platforms.append("switch")
        else:
            platforms.append("number")
    return tuple(platforms)


def _sample_register_name(key: str, placeholders: dict[str, str], names: list[str]) -> str:
    """Pick the register whose name carries the sample circuit/zone/room."""
    if not placeholders:
        return names[0]
    for name in names:
        _, sample = entity_names.translation_for_register(name)
        if placeholders.keys() != sample.keys():
            continue
        if "circuit" in sample and sample["circuit"] != SAMPLE_CIRCUIT.upper():
            continue
        if "zone" in sample and sample["zone"] != str(SAMPLE_ZONE):
            continue
        if "room" in sample and sample["room"] != str(SAMPLE_ROOM):
            continue
        return name
    msg = f"No sample register with the reference indexes for {key!r}"
    raise SystemExit(msg)


def _german_template(register_name: str, placeholders: dict[str, str], overrides: dict[str, str]) -> str:
    """Return the German name of a register with its indexes turned into placeholders."""
    name = overrides.get(register_name) or adapter_names._get_german_name(register_name)  # noqa: SLF001
    for placeholder, token in (
        ("circuit", f"HK {SAMPLE_CIRCUIT.upper()}"),
        ("zone", f"Zone {SAMPLE_ZONE}"),
        ("room", f"Raum {SAMPLE_ROOM}"),
    ):
        if placeholder not in placeholders:
            continue
        label, _, _index = token.partition(" ")
        replacement = f"{label} {{{placeholder}}}"
        if token not in name:
            msg = f"German name {name!r} of {register_name!r} does not carry the {placeholder} index"
            raise SystemExit(msg)
        name = name.replace(token, replacement)
    return name


def build_entity_blocks() -> tuple[dict[str, dict[str, dict[str, str]]], dict[str, dict[str, dict[str, str]]]]:
    """Return the generated ``entity`` blocks for English and German."""
    overrides = _metadata_names()
    registers = _register_space()

    by_platform_key: dict[tuple[str, str], list[str]] = {}
    for name, register in sorted(registers.items()):
        platforms = _platforms_for(name, register)
        if not platforms:
            # Write-only registers (error acknowledgement) are exposed as
            # buttons with their own hand-written translation key.
            continue
        key = entity_names.translation_key_for_register(name)
        if key not in entity_names.ENGLISH_NAMES:
            msg = f"Register {name!r} has no English name for translation key {key!r}"
            raise SystemExit(msg)
        for platform in platforms:
            by_platform_key.setdefault((platform, key), []).append(name)

    english: dict[str, dict[str, dict[str, str]]] = {}
    german: dict[str, dict[str, dict[str, str]]] = {}
    for (platform, key), names in sorted(by_platform_key.items()):
        _, placeholders = entity_names.translation_for_register(names[0])
        sample = _sample_register_name(key, placeholders, names)
        english_name = entity_names.ENGLISH_NAMES[key]
        german_name = _german_template(sample, placeholders, overrides)
        if platform == "number" and adapter_glt.is_glt_measurement(sample):
            # The register is a sensor as well; the number is the external
            # building-management setpoint and needs a distinguishable name.
            english_name += entity_names.BMS_SETPOINT_SUFFIX_EN
            german_name += entity_names.BMS_SETPOINT_SUFFIX_DE
        english.setdefault(platform, {})[key] = {"name": english_name}
        german.setdefault(platform, {})[key] = {"name": german_name}

    for platform, keys in entity_names.DERIVED_NAMES.items():
        for key, (english_name, german_name) in keys.items():
            english.setdefault(platform, {})[key] = {"name": english_name}
            german.setdefault(platform, {})[key] = {"name": german_name}
    return english, german


def _merge(existing: dict[str, Any], generated: dict[str, dict[str, dict[str, str]]]) -> dict[str, Any]:
    """Merge generated names into an entity block, keeping state translations."""
    merged: dict[str, Any] = json.loads(json.dumps(existing))
    entity_block: dict[str, Any] = merged.setdefault("entity", {})
    for platform, keys in generated.items():
        platform_block: dict[str, Any] = entity_block.setdefault(platform, {})
        for key, payload in keys.items():
            key_block: dict[str, Any] = platform_block.setdefault(key, {})
            key_block["name"] = payload["name"]
        entity_block[platform] = dict(sorted(platform_block.items()))
    merged["entity"] = dict(sorted(entity_block.items()))
    return merged


def _write(path: Path, payload: dict[str, Any], *, check: bool) -> bool:
    rendered = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    current = path.read_text(encoding="utf-8")
    if rendered == current:
        return True
    if check:
        print(f"{path.relative_to(ROOT)} is out of date; run scripts/generate_entity_translations.py")
        return False
    path.write_text(rendered, encoding="utf-8")
    print(f"Updated {path.relative_to(ROOT)}")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail instead of writing when a file is out of date")
    args = parser.parse_args(argv)

    english, german = build_entity_blocks()

    up_to_date = True
    for language, path in TARGET_FILES.items():
        generated = german if language == "de" else english
        payload = _merge(json.loads(path.read_text(encoding="utf-8")), generated)
        up_to_date &= _write(path, payload, check=args.check)
    return 0 if up_to_date else 1


if __name__ == "__main__":
    sys.exit(main())
