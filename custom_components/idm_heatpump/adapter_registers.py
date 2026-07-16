"""Register-map selection helpers for the HA adapter."""

from __future__ import annotations

from typing import Any

from idm_heatpump import (
    MODEL_NAVIGATOR_10,
    MODEL_NAVIGATOR_20,
    IdmModelInfo,
    RegisterDef,
    build_register_map,
)

_NAVIGATOR_10_ONLY_REGISTERS: frozenset[str] = frozenset(
    {
        "power_limit_hp",
        "power_limit_cascade",
        "heat_sink_return_temp",
        "heat_sink_flow_temp",
        "heat_sink_flow_rate",
        "heat_sink_charging_pump_signal",
        "booster_fault",
        "booster_interlock",
        "booster_a_source_inlet_temp",
        "booster_a_source_outlet_temp",
        "booster_a_storage_temp",
        "booster_a_flow_temp",
        "booster_a_return_temp",
        "booster_a_source_pump",
        "booster_a_charging_pump",
        "booster_a_compressor",
        "booster_b_source_inlet_temp",
        "booster_b_source_outlet_temp",
        "booster_b_storage_temp",
        "booster_b_flow_temp",
        "booster_b_return_temp",
        "booster_b_source_pump",
        "booster_b_charging_pump",
        "booster_b_compressor",
    }
)


def model_info_from_flags(
    circuits: list[str],
    zone_modules: int,
    enable_cascade: bool,
    model_name: str = MODEL_NAVIGATOR_10,
) -> IdmModelInfo:
    """Construct model information from manual HA configuration flags.

    model_name defaults to Navigator 10 for backward compatibility but
    callers should supply the actually detected model name whenever
    possible to avoid polluting the register map with wrong entries.
    """
    return IdmModelInfo(
        model_name=model_name,
        active_heating_circuits=circuits,
        zone_modules=zone_modules,
        has_solar=True,
        has_isc=True,
        has_pv=True,
        has_cascade=enable_cascade,
    )


# During setup, each platform generator (sensor / binary_sensor / number /
# select / switch) calls build_filtered_register_map with the same arguments.
# Cache the most recent result so the library map is built only once per setup
# instead of five times. The cache holds a single entry keyed by the call
# signature; a different signature simply rebuilds.
_FILTERED_REGISTER_MAP_CACHE: tuple[Any, dict[str, RegisterDef]] | None = None


def build_filtered_register_map(
    model_info: Any = None,
    circuits: list[str] | None = None,
    zone_modules: int = 0,
) -> dict[str, RegisterDef]:
    """Build the library register map and apply local compatibility filters.

    Memoized: during setup, all five platform generators call this with the
    same model_info/circuits/zone_modules. The library map is expensive to
    rebuild, so the most recent result is cached and reused.
    """
    global _FILTERED_REGISTER_MAP_CACHE
    circuits_tuple = tuple(circuits or [])
    cache_key = (id(model_info), circuits_tuple, zone_modules)
    if _FILTERED_REGISTER_MAP_CACHE is not None:
        key, cached = _FILTERED_REGISTER_MAP_CACHE
        if key == cache_key:
            return cached

    reg_map = build_register_map(
        model_info=model_info,
        circuits=list(circuits_tuple),
        zone_modules=zone_modules or 0,
    )

    if getattr(model_info, "model_name", None) == MODEL_NAVIGATOR_20:
        for name in _NAVIGATOR_10_ONLY_REGISTERS:
            reg_map.pop(name, None)

    _FILTERED_REGISTER_MAP_CACHE = (cache_key, reg_map)
    return reg_map
