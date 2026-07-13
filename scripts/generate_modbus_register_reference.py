#!/usr/bin/env python3
"""Generate the complete Modbus register catalog from the pinned API package."""

from __future__ import annotations

import argparse
import json
import re
import runpy
from importlib.metadata import version as distribution_version
from pathlib import Path

from idm_heatpump import (
    MODEL_NAVIGATOR_10,
    MODEL_NAVIGATOR_20,
    IdmModelInfo,
    RegisterDef,
    build_register_map,
)

ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = ROOT / "docs" / "wiki" / "Modbus-Register.md"
MANIFEST_PATH = ROOT / "custom_components" / "idm_heatpump" / "manifest.json"
NAMES_PATH = ROOT / "custom_components" / "idm_heatpump" / "adapter_names.py"

START_MARKER = "<!-- BEGIN GENERATED REGISTER REFERENCE -->"
END_MARKER = "<!-- END GENERATED REGISTER REFERENCE -->"

GROUPS = (
    (0, 999, "PV & Smart Grid", "74–999"),
    (1000, 1199, "System & heat pump", "1000–1199"),
    (1200, 1349, "Cascade & bivalence", "1200–1349"),
    (1350, 1699, "Heating circuits & demands", "1350–1699"),
    (1700, 1999, "Energy, solar, GLT & services", "1700–1999"),
    (2000, 2999, "Zone modules", "2000–2999"),
    (3000, 9999, "Navigator 10 extensions", "4000+"),
)


def _model_info(model_name: str) -> IdmModelInfo:
    return IdmModelInfo(
        model_name=model_name,
        active_heating_circuits=list("ABCDEFG"),
        zone_modules=10,
        has_solar=True,
        has_isc=True,
        has_pv=True,
        has_cascade=True,
    )


def _pinned_api_version() -> str:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    requirements = [item for item in manifest["requirements"] if item.startswith("idm-heatpump-api")]
    if len(requirements) != 1:
        raise RuntimeError("Expected exactly one idm-heatpump-api requirement")
    match = re.fullmatch(
        r"idm-heatpump-api(?:\[web\])?==([0-9]+\.[0-9]+\.[0-9]+)",
        requirements[0],
    )
    if match is None:
        raise RuntimeError("The idm-heatpump-api requirement must be pinned exactly")
    return match.group(1)


def _display_name_function():
    namespace = runpy.run_path(str(NAMES_PATH))
    base_function = namespace["_get_german_name"]
    direct_names = namespace["_GERMAN_NAMES"]

    def display_name(name: str) -> str:
        direct = direct_names.get(name)
        if direct is not None:
            return direct

        circuit_match = re.fullmatch(r"hc_([a-g])_(.+)", name)
        if circuit_match:
            circuit, suffix = circuit_match.groups()
            template = direct_names.get(f"hc_a_{suffix}")
            if template is not None:
                return template.replace("HK A", f"HK {circuit.upper()}")

        zone_match = re.fullmatch(r"zm(\d+)_(mode_heat_cool|dehumidification)", name)
        if zone_match:
            zone, kind = zone_match.groups()
            label = "Betriebsart Heizen/Kühlen" if kind == "mode_heat_cool" else "Entfeuchtung"
            return f"Zone {zone} {label}"

        return base_function(name)

    return display_name


def _escape(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _access_label(register: RegisterDef) -> str:
    write_class = register.write_class.value
    if write_class == "forbidden":
        return "R"
    if write_class == "eeprom":
        return "RW · EEPROM"
    if write_class == "cyclic":
        ttl = int(register.cyclic_write_ttl or 0)
        return f"RW · zyklisch ≤ {ttl} s" if ttl else "RW · zyklisch"
    if write_class == "write_only":
        return "W · nur Schreiben"
    return "RW"


def _address_label(register: RegisterDef) -> str:
    if register.size == 1:
        return str(register.address)
    return f"{register.address}–{register.address + register.size - 1}"


def _notes(register: RegisterDef, navigator_10_only: set[str]) -> str:
    notes: list[str] = []
    if register.name in navigator_10_only:
        notes.append("Navigator 10")
    if register.enum_options:
        notes.append("Enum")
    if register.binary:
        notes.append("Binär")
    if not register.enabled_by_default:
        notes.append("standardmäßig deaktiviert")
    return ", ".join(notes) or "—"


def _build_reference() -> str:
    pinned_version = _pinned_api_version()
    installed_version = distribution_version("idm-heatpump-api")
    if installed_version != pinned_version:
        raise RuntimeError(f"Installed idm-heatpump-api {installed_version} does not match pinned {pinned_version}")

    registers = build_register_map(
        model_info=_model_info(MODEL_NAVIGATOR_10),
        rooms_per_zone=8,
    )
    navigator_20_registers = build_register_map(
        model_info=_model_info(MODEL_NAVIGATOR_20),
        rooms_per_zone=8,
    )
    navigator_10_only = set(registers) - set(navigator_20_registers)
    display_name = _display_name_function()

    ordered = sorted(registers.values(), key=lambda item: (item.address, item.name))
    writable_count = sum(item.writable for item in ordered)
    eeprom_count = sum(item.eeprom_sensitive for item in ordered)
    cyclic_count = sum(item.cyclic_required for item in ordered)

    lines = [
        START_MARKER,
        "## Complete register catalog",
        "",
        f"> Generated from `idm-heatpump-api[web]=={pinned_version}`. Do not edit this section manually.",
        "",
        f"This maximal catalog contains **{len(ordered)} logical register definitions**: all heating circuits A–G, "
        "ten zone modules with eight rooms each, and Solar, ISC, PV, cascade and Navigator 10 extensions. "
        "The integration selects only the subset supported and enabled on the detected installation.",
        "",
        f"Of these definitions, **{writable_count}** are writable, **{eeprom_count}** are EEPROM-sensitive "
        f"and **{cyclic_count}** require cyclic writes. `FLOAT` values occupy two Modbus words; the table "
        "therefore shows an address range for them. `R` means read-only, `RW` read/write and `W` write-only.",
        "",
        "The German description is intended for identification; the code-form register name is the "
        "authoritative key used by the integration. Availability can vary by Navigator model and firmware.",
        "",
    ]

    for start, end, title, address_range in GROUPS:
        group_registers = [item for item in ordered if start <= item.address <= end]
        if not group_registers:
            continue
        lines.extend(
            [
                f"### {address_range} · {title} ({len(group_registers)})",
                "",
                "| Adresse(n) | Beschreibung (DE) | Registername | Typ | Einheit | Zugriff | Hinweis |",
                "|------------|-------------------|--------------|-----|---------|---------|---------|",
            ]
        )
        for register in group_registers:
            unit = register.unit or "—"
            lines.append(
                "| "
                + " | ".join(
                    (
                        _address_label(register),
                        _escape(display_name(register.name)),
                        f"`{register.name}`",
                        register.datatype.value,
                        _escape(unit),
                        _access_label(register),
                        _notes(register, navigator_10_only),
                    )
                )
                + " |"
            )
        lines.append("")

    lines.append(END_MARKER)
    return "\n".join(lines)


def _updated_document() -> tuple[str, str]:
    current = DOC_PATH.read_text(encoding="utf-8")
    generated = _build_reference()
    pattern = re.compile(
        rf"{re.escape(START_MARKER)}.*?{re.escape(END_MARKER)}",
        flags=re.DOTALL,
    )
    updated, replacements = pattern.subn(generated, current)
    if replacements != 1:
        raise RuntimeError("Expected exactly one generated register-reference section")
    return current, updated


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail when the committed catalog differs from the generated output",
    )
    args = parser.parse_args()
    current, updated = _updated_document()
    if args.check:
        if current != updated:
            print(f"{DOC_PATH.relative_to(ROOT)} is not up to date")
            return 1
        print(f"{DOC_PATH.relative_to(ROOT)} is up to date")
        return 0
    DOC_PATH.write_text(updated, encoding="utf-8")
    print(f"Updated {DOC_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
