"""Generate reviewable HA template sensors and a GLT mapping for a hybrid PV site."""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Sources:
    """Explicitly selected W-valued sources; SOC is a percentage."""

    inverters: tuple[str, ...]
    hybrid: str
    battery: str
    soc: str
    grid: str
    battery_positive: str
    grid_positive: str

    def validate(self) -> None:
        for entity in (*self.inverters, self.hybrid, self.battery, self.soc, self.grid):
            if re.fullmatch(r"sensor\.[a-z0-9_]+", entity) is None:
                raise ValueError("Sources must be sensor entity IDs")
        if not self.inverters or len(set(self.inverters)) != len(self.inverters):
            raise ValueError("Select at least one inverter, without duplicates")
        if self.hybrid not in self.inverters:
            raise ValueError("The hybrid inverter must belong to the inverter list")
        if self.battery_positive not in ("charging", "discharging"):
            raise ValueError("Choose the observed battery sign explicitly")
        if self.grid_positive not in ("import", "export"):
            raise ValueError("Choose the observed grid sign explicitly")
        if len({self.battery, self.soc, self.grid, *self.inverters}) != len(self.inverters) + 3:
            raise ValueError("Power, SOC and inverter inputs must be distinct")


def _value(entity: str) -> str:
    return f"(states('{entity}') | float(0))"


def _valid(entity: str) -> str:
    return f"(is_number(states('{entity}')) and state_attr('{entity}', 'unit_of_measurement') == 'W')"


def generate(sources: Sources) -> tuple[list[dict[str, str]], dict[str, object]]:
    """Build templates only: no discovery, configuration changes or device I/O."""
    sources.validate()
    any_inverter = " or ".join(_valid(entity) for entity in sources.inverters)
    battery = _value(sources.battery)
    discharge = f"-({battery})" if sources.battery_positive == "charging" else battery
    grid = _value(sources.grid)
    export = f"-({grid})" if sources.grid_positive == "import" else grid
    loop = (
        "{% set ids = " + json.dumps(sources.inverters) + " %}"
        "{% set ns = namespace(total=0, count=0) %}"
        "{% for id in ids %}{% if is_number(states(id)) and state_attr(id, 'unit_of_measurement') == 'W' %}"
        "{% set ns.total = ns.total + (states(id) | float(0)) %}"
        "{% set ns.count = ns.count + 1 %}{% endif %}{% endfor %}"
    )
    others = tuple(entity for entity in sources.inverters if entity != sources.hybrid)
    pv = (
        "{% set ids = " + json.dumps(others) + " %}{% set ns = namespace(total=0) %}"
        "{% for id in ids %}{% if is_number(states(id)) and state_attr(id, 'unit_of_measurement') == 'W' %}"
        "{% set ns.total = ns.total + ([0, states(id) | float(0)] | max) %}"
        "{% endif %}{% endfor %}"
        f"{{% if {_valid(sources.hybrid)} and {_valid(sources.battery)} %}}"
        f"{{% set ns.total = ns.total + ([0, {_value(sources.hybrid)} - ({discharge})] | max) %}}"
        "{% endif %}{{ ns.total | round(1) }}"
    )
    pv_valid = " or ".join(
        [*(_valid(entity) for entity in others), f"({_valid(sources.hybrid)} and {_valid(sources.battery)})"]
    )
    safe_surplus = (
        f"{{% if ({any_inverter}) and {_valid(sources.grid)} and {_valid(sources.battery)} %}}"
        f"{{{{ [0, {export} - ([0, {discharge}] | max)] | max | round(1) }}}}"
        "{% else %}0{% endif %}"
    )
    definitions = [
        ("inverter_power", "Inverter Power", loop + "{{ ns.total | round(1) }}", any_inverter),
        ("pv_production", "PV Production", pv, pv_valid),
        (
            "house_consumption",
            "House Consumption",
            loop + f"{{{{ [0, ns.total - ({export})] | max | round(1) }}}}",
            f"({any_inverter}) and {_valid(sources.grid)}",
        ),
        ("pv_surplus", "PV Surplus", safe_surplus, "true"),
        ("battery_discharge", "Battery Discharge", "{{ " + discharge + " }}", _valid(sources.battery)),
        ("inverters_available", "Inverters Available", loop + "{{ ns.count }}", "true"),
    ]
    sensors = [
        {
            "name": "IDM GLT " + title,
            "unique_id": "idm_glt_" + key,
            "state": state,
            "availability": "{{ " + availability + " }}",
            "state_class": "measurement",
            **({"unit_of_measurement": "W", "device_class": "power"} if key != "inverters_available" else {}),
        }
        for key, title, state, availability in definitions
    ]
    mapping: dict[str, object] = {
        "external_power_forwarding": True,
        "external_power_forwarding_interval": 30,
        "external_power_battery_sign": "as_is",
        "energy_manager": False,
        "external_power_forwarding_entities": {
            **{
                key: "sensor.idm_glt_" + key
                for key in ("pv_surplus", "pv_production", "house_consumption", "battery_discharge")
            },
            "battery_soc": sources.soc,
        },
    }
    return sensors, mapping


def render_yaml(sensors: list[dict[str, str]]) -> str:
    """JSON-quote scalar values for a valid, dependency-free YAML document."""
    lines = [
        "# Review source units, signs, site membership and generated entity IDs before enabling GLT.",
        "template:",
        "  - sensor:",
    ]
    for sensor in sensors:
        for index, (key, value) in enumerate(sensor.items()):
            lines.append(("      - " if index == 0 else "        ") + key + ": " + json.dumps(value))
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inverter", action="append", required=True, help="Repeat for every AC power sensor (W)")
    for key in ("hybrid-inverter", "battery-power", "battery-soc", "grid-power"):
        parser.add_argument("--" + key, required=True)
    parser.add_argument("--battery-positive", choices=("charging", "discharging"), required=True)
    parser.add_argument("--grid-positive", choices=("import", "export"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mapping-output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.resolve() == args.mapping_output.resolve():
        parser.error("Template and mapping output paths must differ")
    if args.output.exists() or args.mapping_output.exists():
        parser.error("Output files already exist; choose new paths")
    try:
        sensors, mapping = generate(
            Sources(
                tuple(args.inverter),
                args.hybrid_inverter,
                args.battery_power,
                args.battery_soc,
                args.grid_power,
                args.battery_positive,
                args.grid_positive,
            )
        )
    except ValueError as error:
        parser.error(str(error))
    with args.output.open("x", encoding="utf-8") as handle:
        handle.write(render_yaml(sensors))
    with args.mapping_output.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(mapping, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
