"""Validate generated GLT signals with explicit signs and partial source failures."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest
import yaml
from jinja2 import Environment

from scripts.generate_solaredge_glt_templates import Sources, generate, main, render_yaml


def _sources(battery_positive: str = "charging", grid_positive: str = "export") -> Sources:
    return Sources(
        ("sensor.hybrid", "sensor.second", "sensor.third", "sensor.fourth"),
        "sensor.hybrid",
        "sensor.battery",
        "sensor.soc",
        "sensor.grid",
        battery_positive,
        grid_positive,
    )


def _number(value: str) -> bool:
    try:
        return math.isfinite(float(value))
    except ValueError:
        return False


def _render(
    values: dict[str, str], sources: Sources | None = None, units: dict[str, str] | None = None
) -> dict[str, float | None]:
    env = Environment()
    env.globals.update(
        states=lambda entity: values.get(entity, "unavailable"),
        state_attr=lambda entity, _attr: (units or {}).get(entity, "W"),
        is_number=_number,
    )
    result = {}
    for sensor in generate(sources or _sources())[0]:
        # Even an unavailable sensor's state expression must render safely.
        state = float(env.from_string(sensor["state"]).render())
        available = env.from_string(sensor["availability"]).render().strip().lower() == "true"
        result[sensor["unique_id"]] = state if available else None
    return result


BASE = {
    "sensor.hybrid": "1000",
    "sensor.second": "2000",
    "sensor.third": "3000",
    "sensor.fourth": "4000",
    "sensor.battery": "500",
    "sensor.grid": "500",
}


@pytest.mark.parametrize("battery_sign", ["charging", "discharging"])
@pytest.mark.parametrize("grid_sign", ["import", "export"])
def test_explicit_sign_conventions_produce_the_same_measurements(battery_sign: str, grid_sign: str) -> None:
    values = {
        **BASE,
        "sensor.battery": "500" if battery_sign == "charging" else "-500",
        "sensor.grid": "500" if grid_sign == "export" else "-500",
    }
    result = _render(values, _sources(battery_sign, grid_sign))
    assert result["idm_glt_pv_production"] == 10500
    assert result["idm_glt_house_consumption"] == 9500
    assert result["idm_glt_battery_discharge"] == -500
    assert result["idm_glt_pv_surplus"] == 500


@pytest.mark.parametrize("missing", ["sensor.hybrid", "sensor.second", "sensor.third", "sensor.fourth"])
def test_each_inverter_can_drop_out_and_rejoin(missing: str) -> None:
    result = _render({**BASE, missing: "unavailable"})
    assert result["idm_glt_inverters_available"] == 3
    assert result["idm_glt_inverter_power"] == 10000 - float(BASE[missing])
    assert result["idm_glt_pv_production"] == (9000 if missing == "sensor.hybrid" else 10500 - float(BASE[missing]))
    assert _render(BASE)["idm_glt_inverters_available"] == 4


@pytest.mark.parametrize("invalid", ["unavailable", "unknown", "nan", "inf"])
def test_missing_battery_keeps_other_pv_but_inhibits_surplus(invalid: str) -> None:
    result = _render({**BASE, "sensor.battery": invalid})
    assert result["idm_glt_pv_production"] == 9000
    assert result["idm_glt_battery_discharge"] is None
    assert result["idm_glt_pv_surplus"] == 0


def test_all_offline_and_grid_failure_inhibit_surplus() -> None:
    result = _render({"sensor.battery": "500", "sensor.grid": "500"})
    assert result["idm_glt_inverters_available"] == 0
    assert result["idm_glt_pv_production"] is None
    assert result["idm_glt_house_consumption"] is None
    assert result["idm_glt_pv_surplus"] == 0
    assert _render({**BASE, "sensor.grid": "unknown"})["idm_glt_pv_surplus"] == 0


def test_battery_export_is_not_pv_surplus_and_wrong_units_are_rejected() -> None:
    result = _render({**BASE, "sensor.battery": "-600"})
    assert result["idm_glt_pv_surplus"] == 0
    assert result["idm_glt_pv_production"] == 9400
    assert _render(BASE, units={"sensor.battery": "kW"})["idm_glt_pv_surplus"] == 0
    assert _render(BASE, units={"sensor.grid": "kWh"})["idm_glt_pv_surplus"] == 0
    assert _render(BASE, units={"sensor.second": "kW"})["idm_glt_inverters_available"] == 3


def test_cli_emits_valid_yaml_and_mapping_without_overwriting(tmp_path: Path) -> None:
    output, mapping = tmp_path / "templates.yaml", tmp_path / "mapping.json"
    args = [
        "--inverter",
        "sensor.hybrid",
        "--hybrid-inverter",
        "sensor.hybrid",
        "--battery-power",
        "sensor.battery",
        "--battery-soc",
        "sensor.soc",
        "--grid-power",
        "sensor.grid",
        "--battery-positive",
        "charging",
        "--grid-positive",
        "export",
        "--output",
        str(output),
        "--mapping-output",
        str(mapping),
    ]
    assert main(args) == 0
    assert len(yaml.safe_load(output.read_text())["template"][0]["sensor"]) == 6
    assert json.loads(mapping.read_text())["external_power_forwarding_entities"]["battery_soc"] == "sensor.soc"
    assert json.loads(mapping.read_text())["energy_manager"] is False
    with pytest.raises(SystemExit):
        main(args)
    assert yaml.safe_load(render_yaml(generate(_sources())[0]))["template"]


@pytest.mark.parametrize(
    "inverters,hybrid",
    [
        (("sensor.hybrid", "sensor.hybrid"), "sensor.hybrid"),
        (("sensor.second",), "sensor.hybrid"),
        (("not_a_sensor",), "not_a_sensor"),
    ],
)
def test_invalid_or_duplicate_sources_are_rejected(inverters: tuple[str, ...], hybrid: str) -> None:
    with pytest.raises(ValueError):
        generate(Sources(inverters, hybrid, "sensor.battery", "sensor.soc", "sensor.grid", "charging", "export"))
