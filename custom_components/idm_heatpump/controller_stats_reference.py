"""Cross-reference table between IDM-Controller ID spaces.

This module documents a non-obvious architectural fact about IDM Navigator
controllers that was confirmed by analysing a real Navigator 10 SD-card
backup (July 2026) and cross-checking against ``idm-heatpump-api`` register
definitions and a strictly read-only live Modbus probe.

A single physical quantity on the controller is addressed by up to three
independent ID spaces:

1. **Modbus register address** - what this integration reads via
   ``idm-heatpump-api``. Example: ``1748`` for heat-pump heating energy.
2. **Internal stats ID** - used by the controller's own statistics engine
   and persisted in ``stats/amount/<id>_v1.csv`` and
   ``stats/amount/last_values.json`` on the SD card. Example: ``477`` for
   the same heating energy. IDs in the 100000 range are cumulative totals
   of an underlying series (e.g. ``100495`` aggregates ``495``).
3. **KNX communication-object number** - assigned in the ETS example
   project for the Weinzierl BAOS gateway. Example: KNX object ``995`` is
   labelled "Photovotaik Surplus" and maps to ``pv_surplus``.

These three spaces overlap but are **not** 1:1, and the numbers are
deliberately different. Treat them as parallel names for the same
physical quantity, never as interchangeable addresses.

The mappings below were verified on a confirmed Navigator 10 plant
(firmware ``NAV10_20.24-880-g265e09c4a``). They are intentionally
incomplete: only registers that have been cross-confirmed across at
least two of the three spaces are listed. ``None`` means "no
cross-reference available in the verified set", not "the mapping does
not exist".

Use this module for:

- Diagnostic output that lets users correlate their Home Assistant
  readings with the on-device ``syscount.ini`` keys and the KNX object
  labels from the IDM example project.
- Regression tests that freeze the cross-reference so a silent library
  rename is caught at CI time.
- Documentation: the wiki section "IDM-Controller-ID-Räume" mirrors this
  table in human-readable form.

This module contains only constants. It performs no I/O, no Modbus, and
no Home Assistant calls.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class ControllerStatReference:
    """One row in the cross-reference table.

    ``library_register`` is the canonical name used by ``idm-heatpump-api``
    and this integration. ``syscount_key`` is the literal key used in the
    controller's ``syscount.ini``. ``internal_stats_id`` is the integer ID
    used in ``stats/amount/<id>_v1.csv`` and ``last_values.json``.
    ``knx_object`` is the communication-object number from the IDM ETS
    example project. ``semantic_label`` is the human-readable meaning.
    """

    library_register: str
    syscount_key: str | None
    internal_stats_id: int | None
    internal_stats_cumulative_id: int | None
    knx_object: int | None
    semantic_label: str
    unit: str
    note: str = ""


# Frozen, indexed by library register name. Order is stable for
# deterministic diagnostic output. Keep sorted by library_register.
SYSCOUNT_REGISTER_REFERENCE: Final[Mapping[str, ControllerStatReference]] = {
    "battery_discharge": ControllerStatReference(
        library_register="battery_discharge",
        syscount_key=None,
        internal_stats_id=None,
        internal_stats_cumulative_id=None,
        knx_object=993,
        semantic_label="Batterieentladung (Leistung)",
        unit="kW",
        note="GLT-Messwert-Register; in syscount.ini nicht einzeln geführt.",
    ),
    "battery_soc": ControllerStatReference(
        library_register="battery_soc",
        syscount_key=None,
        internal_stats_id=None,
        internal_stats_cumulative_id=None,
        knx_object=994,
        semantic_label="Batterieladezustand",
        unit="%",
        note="Signed INT16; -1 bedeutet 'nicht verfügbar'.",
    ),
    "energy_cooling": ControllerStatReference(
        library_register="energy_cooling",
        syscount_key="ZQHPC",
        internal_stats_id=None,
        internal_stats_cumulative_id=None,
        knx_object=401,
        semantic_label="Wärmemenge Kühlen (Wärmepumpe)",
        unit="kWh",
        note="Syscount-Schlüssel ZQHPC = 'Heat Pump Cooling'.",
    ),
    "energy_defrost": ControllerStatReference(
        library_register="energy_defrost",
        syscount_key="ZQHPD",
        internal_stats_id=472,
        internal_stats_cumulative_id=None,
        knx_object=403,
        semantic_label="Wärmemenge Abtauen (Wärmepumpe)",
        unit="kWh",
        note="Syscount-Schlüssel ZQHPD = 'Heat Pump Defrost'.",
    ),
    "energy_dhw": ControllerStatReference(
        library_register="energy_dhw",
        syscount_key="ZQHPP",
        internal_stats_id=471,
        internal_stats_cumulative_id=None,
        knx_object=402,
        semantic_label="Wärmemenge Warmwasser / Priority",
        unit="kWh",
        note="Controller-intern 'Priority'-Zähler; Bibliothek und Addon bezeichnen denselben Wert als DHW-Wärmemenge.",
    ),
    "energy_electric_heater": ControllerStatReference(
        library_register="energy_electric_heater",
        syscount_key="ZQELH",
        internal_stats_id=None,
        internal_stats_cumulative_id=None,
        knx_object=406,
        semantic_label="Wärmemenge Elektroheizstab",
        unit="kWh",
        note="Syscount-Schlüssel ZQELH = 'Electric Heater'.",
    ),
    "energy_heating": ControllerStatReference(
        library_register="energy_heating",
        syscount_key="ZQHPH",
        internal_stats_id=477,
        internal_stats_cumulative_id=None,
        knx_object=400,
        semantic_label="Wärmemenge Heizen (Wärmepumpe)",
        unit="kWh",
        note="Syscount-Schlüssel ZQHPH = 'Heat Pump Heating'.",
    ),
    "house_consumption": ControllerStatReference(
        library_register="house_consumption",
        syscount_key=None,
        internal_stats_id=None,
        internal_stats_cumulative_id=None,
        knx_object=992,
        semantic_label="Hausverbrauch (Leistung)",
        unit="kW",
        note="GLT-Messwert-Register; in syscount.ini nicht einzeln geführt.",
    ),
    "power_consumption_hp": ControllerStatReference(
        library_register="power_consumption_hp",
        syscount_key=None,
        internal_stats_id=None,
        internal_stats_cumulative_id=None,
        knx_object=997,
        semantic_label="Elektrische Gesamtleistungsaufnahme",
        unit="kW",
        note="KNX-Objekt 997 'Total electric output'.",
    ),
    "pv_production": ControllerStatReference(
        library_register="pv_production",
        syscount_key=None,
        internal_stats_id=496,
        internal_stats_cumulative_id=None,
        knx_object=996,
        semantic_label="Photovoltaik-Leistung",
        unit="kW",
        note="ETS-Beispielprojekt enthält den Tippfehler 'Photovotaik current'. "
        "Stats-ID 496 bestätigt über stats/amount/496_v1.csv; die Kumulation "
        "im 100000er-Raum ist nicht eindeutig zu codieren und daher nicht "
        "eingetragen.",
    ),
    "pv_surplus": ControllerStatReference(
        library_register="pv_surplus",
        syscount_key=None,
        internal_stats_id=495,
        internal_stats_cumulative_id=None,
        knx_object=995,
        semantic_label="Photovoltaik-Überschuss",
        unit="kW",
        note="ETS-Beispielprojekt enthält den Tippfehler 'Photovotaik Surplus'. "
        "Stats-ID 495 bestätigt über stats/amount/495_v1.csv; die Kumulation "
        "im 100000er-Raum ist nicht eindeutig zu codieren und daher nicht "
        "eingetragen.",
    ),
    "thermal_power_flow_sensor": ControllerStatReference(
        library_register="thermal_power_flow_sensor",
        syscount_key=None,
        internal_stats_id=None,
        internal_stats_cumulative_id=None,
        knx_object=998,
        semantic_label="Thermische Leistung (Durchflusssensor)",
        unit="kW",
        note="KNX-Objekt 998 'Current thermal output'.",
    ),
    "total_heat_energy": ControllerStatReference(
        library_register="total_heat_energy",
        syscount_key="ZQHPO",
        internal_stats_id=None,
        internal_stats_cumulative_id=None,
        knx_object=999,
        semantic_label="Wärmemenge gesamt (Durchflusssensor, Nav10)",
        unit="kWh",
        note="Syscount-Schlüssel ZQHPO = 'Heat Pump Overall'. "
        "KNX-Objekt 999 'Total thermal energy'. "
        "Zugehörige interne Stats-ID ist nicht quergesichert; die "
        "100000er-Kumulation wird ausschließlich der PV-Serie zugeordnet.",
    ),
}


def reference_for(library_register: str) -> ControllerStatReference | None:
    """Return the cross-reference row for ``library_register`` or ``None``.

    Lookup is by exact library register name (the same name
    ``idm-heatpump-api`` uses). Unknown registers return ``None`` so
    callers can iterate the full set without raising.
    """
    return SYSCOUNT_REGISTER_REFERENCE.get(library_register)


def syscount_label_for(library_register: str) -> str | None:
    """Return the human-readable syscount label for diagnostics, or ``None``.

    Convenience wrapper for ``diagnostics.py``: emits the controller's own
    ``syscount.ini`` key when one is known, so users can correlate their
    HA sensor value with the on-device counter directly.
    """
    row = SYSCOUNT_REGISTER_REFERENCE.get(library_register)
    if row is None or row.syscount_key is None:
        return None
    return f"{row.syscount_key} ({row.semantic_label})"


__all__ = [
    "SYSCOUNT_REGISTER_REFERENCE",
    "ControllerStatReference",
    "reference_for",
    "syscount_label_for",
]
