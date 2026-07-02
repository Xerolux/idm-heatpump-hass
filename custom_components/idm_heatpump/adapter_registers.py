"""Register-map selection helpers for the HA adapter."""

from __future__ import annotations

from typing import Any

from idm_heatpump import IdmModelInfo, RegisterDef, build_register_map
from idm_heatpump.const import MODEL_NAVIGATOR_10, MODEL_NAVIGATOR_20


def model_info_from_flags(
    circuits: list[str],
    zone_modules: int,
    enable_cascade: bool,
) -> IdmModelInfo:
    """Construct model information from manual HA configuration flags."""
    return IdmModelInfo(
        model_name=MODEL_NAVIGATOR_10,
        active_heating_circuits=circuits,
        zone_modules=zone_modules,
        has_solar=True,
        has_isc=True,
        has_pv=True,
        has_cascade=enable_cascade,
    )


def build_filtered_register_map(
    model_info: Any = None,
    circuits: list[str] | None = None,
    zone_modules: int = 0,
) -> dict[str, RegisterDef]:
    """Build the library register map and apply local compatibility filters."""
    reg_map = build_register_map(
        model_info=model_info,
        circuits=circuits or [],
        zone_modules=zone_modules or 0,
    )

    if getattr(model_info, "model_name", None) == MODEL_NAVIGATOR_20:
        reg_map.pop("power_limit_hp", None)

    return reg_map
