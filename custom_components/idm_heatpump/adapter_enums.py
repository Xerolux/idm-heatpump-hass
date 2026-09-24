"""Enum translation helpers for IDM register values."""

from __future__ import annotations

import re

from .entity_names import translation_key_for_register

_SYSTEM_MODE_SLUGS: dict[int, str] = {
    0: "standby",
    1: "automatic",
    2: "absent",
    3: "holiday",
    4: "hot_water_only",
    5: "heating_cooling_only",
}

_CIRCUIT_MODE_SLUGS: dict[int, str] = {
    0: "off",
    1: "timed_program",
    2: "normal",
    3: "eco",
    4: "manual_heating",
    5: "manual_cooling",
    255: "not_configured",
}

_ROOM_MODE_SLUGS: dict[int, str] = {
    0: "off",
    1: "automatic",
    2: "eco",
    3: "normal",
    4: "comfort",
}

_SOLAR_MODE_SLUGS: dict[int, str] = {
    0: "automatic",
    1: "hot_water",
    2: "heating",
    3: "hot_water_and_heating",
    4: "heat_source_pool",
}

# Navigator 1.0/1.7 official RW holding block (ma_de_812049 Rev.1). The value
# sets deliberately differ from the shared family's enums, so they carry their
# own slug tables under their own translation keys.
_SYSTEM_MODE_17_SLUGS: dict[int, str] = {
    0: "standby",
    1: "automatic",
    2: "hot_water",
    3: "hot_water_once",
}

_HC_OPERATING_MODE_17_SLUGS: dict[int, str] = {
    0: "off",
    1: "time_program",
    2: "normal",
    3: "eco",
    4: "heating_only",
}

_SOLAR_OPERATING_MODE_17_SLUGS: dict[int, str] = {
    0: "automatic",
    1: "domestic_water",
    2: "heat_storage",
    3: "domestic_water_and_heat_storage",
    4: "heat_source_pool",
}

_HP_OPERATING_MODE_DE: dict[int, str] = {
    0: "Aus",
    1: "Heizbetrieb",
    2: "Kühlbetrieb",
    4: "Warmwasser",
    8: "Abtauen",
}

_BITFLAG_DE_LABELS: dict[str, dict[int, str]] = {
    "hp_operating_mode": _HP_OPERATING_MODE_DE,
}

_CIRCUIT_MODE_RE = re.compile(r"^hc_[a-g]_mode$")
_CIRCUIT_ACTIVE_MODE_RE = re.compile(r"^hc_[a-g]_active_mode$")
_CIRCUIT_OPERATING_MODE_17_RE = re.compile(r"^hc_[a-g]_operating_mode$")
_ROOM_MODE_RE = re.compile(r"^zm\d+_room\d+_mode$")


def _slug_map(name: str) -> dict[int, str] | None:
    """Return the int-to-slug map of a known enum register."""
    if name == "system_mode":
        return _SYSTEM_MODE_SLUGS
    if name == "system_mode_17":
        return _SYSTEM_MODE_17_SLUGS
    if _CIRCUIT_MODE_RE.match(name) or _CIRCUIT_ACTIVE_MODE_RE.match(name):
        return _CIRCUIT_MODE_SLUGS
    if _CIRCUIT_OPERATING_MODE_17_RE.match(name):
        return _HC_OPERATING_MODE_17_SLUGS
    if _ROOM_MODE_RE.match(name):
        return _ROOM_MODE_SLUGS
    if name == "solar_mode":
        return _SOLAR_MODE_SLUGS
    if name == "solar_operating_mode_17":
        return _SOLAR_OPERATING_MODE_17_SLUGS
    return None


def get_slug_map_and_key(name: str) -> tuple[dict[int, str] | None, str | None]:
    """Return (int-to-slug map, translation_key) for a known enum register.

    The translation key is the entity translation key of the register, so the
    option labels and the entity name live under the same key: one heating
    circuit mode key with a ``{circuit}`` placeholder instead of one key per
    circuit.
    """
    slug_map = _slug_map(name)
    if slug_map is None:
        return None, None
    return slug_map, translation_key_for_register(name)


def get_bitflag_de_labels(name: str) -> dict[int, str] | None:
    """Return German label overrides for BITFLAG registers."""
    return _BITFLAG_DE_LABELS.get(name)
