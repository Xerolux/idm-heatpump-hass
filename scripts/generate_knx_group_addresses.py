#!/usr/bin/env python3
"""Generate ETS group address files for the IDM KNX bridge.

The bridge derives every group address as ``base address + IDM object
number``. ETS still needs those addresses to exist in the project so the
real KNX devices — a glass push-button showing the flow temperature, a
visualisation, a logic module — can be linked to them. This script writes
that list in the two formats ETS 6 accepts for a group address import, so
nobody has to type several hundred addresses by hand.

Names come from the integration's own German name table, so an address
reads the same in ETS as the matching entity does in Home Assistant.

Examples::

    # Everything, from the bridge's default base address
    python scripts/generate_knx_group_addresses.py --output docs/examples/knx

    # A curated subset for a plant with two heating circuits, main group 11
    python scripts/generate_knx_group_addresses.py --base 11/0/0 --profile compact

    # Only what a visualisation needs, straight to stdout
    python scripts/generate_knx_group_addresses.py --groups system,dhw --format csv --stdout
"""

from __future__ import annotations

import argparse
import importlib.util
import pathlib
import sys
from collections.abc import Iterable, Sequence
from typing import Any
from xml.sax.saxutils import quoteattr

ROOT = pathlib.Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "idm_heatpump"


def _load(module_name: str, filename: str) -> Any:
    """Import a component module without pulling in Home Assistant.

    ``custom_components.idm_heatpump.__init__`` imports Home Assistant, which
    is not installed when this script runs, so the two pure-data modules are
    loaded directly by path instead.
    """
    spec = importlib.util.spec_from_file_location(module_name, COMPONENT / filename)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise RuntimeError(f"cannot load {filename}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_names = _load("_idm_knx_names", "adapter_names.py")
_catalog = _load("_idm_knx_catalog", "knx_catalog.py")

KNX_OBJECTS = _catalog.KNX_OBJECTS
OBJECT_GROUPS = _catalog.OBJECT_GROUPS
InvalidGroupAddressError = _catalog.InvalidGroupAddressError

# German labels for the catalogue groups, used to name the middle groups.
GROUP_LABELS: dict[str, str] = {
    "system": "System",
    "heat_pump": "Wärmepumpe",
    "dhw": "Warmwasser",
    "heating_circuits": "Heizkreise",
    "zones": "Zonenmodule",
    "glt": "Gebäudeleittechnik",
    "energy": "Wärmemengen",
    "solar": "Solar",
    "isc": "ISC",
    "cascade": "Kaskade",
    "booster": "Booster",
    "pv": "PV und Batterie",
}

# The handful of registers the integration's name table does not cover.
EXTRA_NAMES: dict[str, str] = {
    "smart_grid_status": "Smart Grid Status",
    **{f"zm{zone}_mode_heat_cool": f"Zone {zone} Heizen/Kühlen" for zone in range(1, 11)},
    **{f"zm{zone}_dehumidification": f"Zone {zone} Entfeuchtung" for zone in range(1, 11)},
}

# A curated subset: what a push-button, a display or a visualisation
# realistically shows, plus the inputs a KNX installation can usefully feed
# back into the heat pump. Heating circuits A and B only -- extend with
# --groups heating_circuits for all of A..G.
COMPACT_REGISTERS: tuple[str, ...] = (
    # System
    "outdoor_temp",
    "outdoor_temp_avg",
    "internal_message",
    "system_mode",
    "error_acknowledge",
    # Buffers and hot water
    "storage_temp",
    "dhw_temp_bottom",
    "dhw_temp_top",
    "dhw_tapping_temp",
    "dhw_setpoint",
    # Heat pump
    "hp_flow_temp",
    "hp_return_temp",
    "heat_source_inlet_temp",
    "heat_source_outlet_temp",
    "hp_operating_mode",
    "heating_demand",
    "cooling_demand",
    "dhw_demand",
    "compressor_status_1",
    # Heating circuits A and B
    "hc_a_flow_temp",
    "hc_a_room_temp",
    "hc_a_setpoint_flow_temp",
    "hc_a_mode",
    "hc_a_room_setpoint_heat_normal",
    "hc_a_active_mode",
    "hc_a_ext_room_temp",
    "hc_b_flow_temp",
    "hc_b_room_temp",
    "hc_b_setpoint_flow_temp",
    "hc_b_mode",
    "hc_b_room_setpoint_heat_normal",
    "hc_b_active_mode",
    "hc_b_ext_room_temp",
    # Values a KNX installation can feed back in
    "ext_outdoor_temp",
    "ext_humidity",
    "demand_heating",
    "demand_cooling",
    "demand_dhw_charging",
    # Energy
    "energy_heating",
    "energy_cooling",
    "energy_dhw",
    "current_power",
    "power_consumption_hp",
)


def object_name(register: str) -> str:
    """Return the display name for a register."""
    if register in EXTRA_NAMES:
        return EXTRA_NAMES[register]
    return str(_names._get_german_name(register))


def dpt_attribute(dpt: str | None) -> str:
    """Convert a catalogue datapoint type into the ETS ``DPTs`` spelling.

    ``9.001`` becomes ``DPST-9-1``; a bare main type becomes ``DPT-9``. A
    1-bit object without a sub-type is exported as ``DPST-1-1`` (switch),
    which is what a push-button or actuator expects on such an address.
    """
    if dpt is None:
        return "DPST-1-1"
    main, _, sub = dpt.partition(".")
    if not sub:
        return f"DPT-{int(main)}"
    return f"DPST-{int(main)}-{int(sub)}"


def selected_objects(
    *,
    profile: str,
    groups: Sequence[str] | None,
    registers: Sequence[str] | None,
) -> list[Any]:
    """Return the catalogue objects a run should export."""
    if registers:
        wanted = list(registers)
    elif groups:
        unknown = sorted(set(groups) - set(OBJECT_GROUPS))
        if unknown:
            raise SystemExit(f"unknown object group(s): {', '.join(unknown)}")
        allowed = set(groups)
        return [obj for obj in KNX_OBJECTS if obj.group in allowed]
    elif profile == "compact":
        wanted = list(COMPACT_REGISTERS)
    else:
        return list(KNX_OBJECTS)

    by_register = {obj.register: obj for obj in KNX_OBJECTS}
    unknown_registers = [name for name in wanted if name not in by_register]
    if unknown_registers:
        raise SystemExit(f"unknown register(s): {', '.join(unknown_registers)}")
    chosen = {name for name in wanted}
    return [obj for obj in KNX_OBJECTS if obj.register in chosen]


def rows(base_address: str, objects: Iterable[Any], *, prefix: str) -> list[dict[str, Any]]:
    """Resolve objects into address rows sorted by group address."""
    base_raw = _catalog.validate_base_address(base_address)
    result = []
    for obj in objects:
        raw = base_raw + obj.number
        name = object_name(obj.register)
        result.append(
            {
                "raw": raw,
                "address": _catalog.format_group_address(raw),
                "main": (raw >> 11) & 0x1F,
                "middle": (raw >> 8) & 0x07,
                "name": f"{prefix} {name}".strip(),
                "dpt": dpt_attribute(obj.dpt),
                "dpt_plain": obj.dpt or "1.001",
                "object": obj.number,
                "register": obj.register,
                "group": obj.group,
                "writable": obj.writable,
            }
        )
    result.sort(key=lambda row: row["raw"])
    return result


def _middle_group_label(entries: list[dict[str, Any]]) -> str:
    """Name a middle group after the catalogue groups it actually holds.

    A middle group that mixes more than three areas gets its object range
    instead: four or more names joined by separators is not a label anyone
    can read in the ETS tree.
    """
    seen: list[str] = []
    for entry in entries:
        label = GROUP_LABELS.get(entry["group"], entry["group"])
        if label not in seen:
            seen.append(label)
    if len(seen) <= 3:
        return " · ".join(seen)
    numbers = [entry["object"] for entry in entries]
    return f"Objekte {min(numbers)}–{max(numbers)}"


def render_xml(address_rows: list[dict[str, Any]], *, project_name: str) -> str:
    """Render an ETS 6 group address import file (three-level style)."""
    if not address_rows:
        raise SystemExit("nothing selected — no group addresses to write")

    main_groups = sorted({row["main"] for row in address_rows})
    lines = [
        '<?xml version="1.0" encoding="utf-8" standalone="yes"?>',
        '<GroupAddress-Export xmlns="http://knx.org/xml/ga-export/01">',
    ]
    for main in main_groups:
        main_rows = [row for row in address_rows if row["main"] == main]
        start = max(main * 2048, 1)
        lines.append(
            f'  <GroupRange Name={quoteattr(project_name)} RangeStart="{start}" RangeEnd="{main * 2048 + 2047}">'
        )
        for middle in sorted({row["middle"] for row in main_rows}):
            middle_rows = [row for row in main_rows if row["middle"] == middle]
            middle_start = max(main * 2048 + middle * 256, 1)
            label = _middle_group_label(middle_rows)
            lines.append(
                f"    <GroupRange Name={quoteattr(label)} "
                f'RangeStart="{middle_start}" RangeEnd="{main * 2048 + middle * 256 + 255}">'
            )
            for row in middle_rows:
                lines.append(
                    f"      <GroupAddress Name={quoteattr(row['name'])} "
                    f'Address="{row["address"]}" DPTs="{row["dpt"]}" />'
                )
            lines.append("    </GroupRange>")
        lines.append("  </GroupRange>")
    lines.append("</GroupAddress-Export>")
    return "\n".join(lines) + "\n"


def render_csv(address_rows: list[dict[str, Any]], *, project_name: str) -> str:
    """Render the technical reference table (semicolon separated)."""
    lines = ["Hauptgruppe;Mittelgruppe;Gruppenadresse;Name;DPT;IDM-Objekt;Register;Richtung"]
    for row in address_rows:
        middle = _middle_group_label([row])
        direction = "lesen/schreiben" if row["writable"] else "lesen"
        lines.append(
            f"{project_name};{middle};{row['address']};{row['name']};"
            f"{row['dpt_plain']};{row['object']};{row['register']};{direction}"
        )
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base", default="8/0/0", help="base group address (default: %(default)s)")
    parser.add_argument(
        "--profile",
        choices=("compact", "full"),
        default="full",
        help="compact = a curated subset for displays and visualisations; full = the whole catalogue",
    )
    parser.add_argument(
        "--groups", help=f"comma separated object groups instead of a profile: {', '.join(OBJECT_GROUPS)}"
    )
    parser.add_argument("--registers", help="comma separated register names instead of a profile")
    parser.add_argument("--format", choices=("xml", "csv", "both"), default="both")
    parser.add_argument("--prefix", default="WP", help="name prefix for every address (default: %(default)s)")
    parser.add_argument("--project-name", default="Wärmepumpe", help="name of the top level group range")
    parser.add_argument("--output", type=pathlib.Path, help="directory to write into")
    parser.add_argument("--basename", default="idm-waermepumpe-gruppenadressen", help="output file stem")
    parser.add_argument("--stdout", action="store_true", help="write to stdout instead of files")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.stdout and args.format == "both":
        raise SystemExit("--stdout needs a single --format (xml or csv)")
    if not args.stdout and args.output is None:
        raise SystemExit("pass --output DIR or --stdout")

    groups = [g.strip() for g in args.groups.split(",") if g.strip()] if args.groups else None
    registers = [r.strip() for r in args.registers.split(",") if r.strip()] if args.registers else None

    try:
        objects = selected_objects(profile=args.profile, groups=groups, registers=registers)
        address_rows = rows(args.base, objects, prefix=args.prefix)
    except InvalidGroupAddressError as err:
        raise SystemExit(f"unusable base address {args.base!r}: {err}") from err

    rendered = {
        "xml": render_xml(address_rows, project_name=args.project_name),
        "csv": render_csv(address_rows, project_name=args.project_name),
    }

    if args.stdout:
        sys.stdout.write(rendered[args.format])
        return 0

    args.output.mkdir(parents=True, exist_ok=True)
    written = []
    for suffix in ("xml", "csv"):
        if args.format in (suffix, "both"):
            path = args.output / f"{args.basename}.{suffix}"
            path.write_text(rendered[suffix], encoding="utf-8")
            written.append(path)
    print(f"{len(address_rows)} group addresses from {args.base}")
    for path in written:
        print(f"  wrote {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
