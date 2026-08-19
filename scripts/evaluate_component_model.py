#!/usr/bin/env python3
"""Measure whether the IDM register map fits ``modbus-connection``'s component model.

Background: solaredge-modbus-multi v4.0.0-pre.11 moved all of its reads and
writes onto a ``modbus-connection`` ``Component``.  The equivalent step for this
project would happen inside ``idm-heatpump-api``, which owns the register map,
batching and decoding.  This script produces the evidence for that decision:

1. it mirrors every register of the maximal Navigator 10 map as a library field
   on a ``ManualComponent`` (the runtime-built variant, since the IDM map is
   generated per model, heating circuit and zone room);
2. it reads the component against the library's in-memory mock and compares every
   decoded value with the decoding ``idm-heatpump-api`` performs today;
3. it reports the request plan the library builds for several ``max_gap``
   settings, next to the number of requests the API's own batching produces;
4. it checks the three documented logical overlaps of the official IDM map
   (``docs/Register-Map-Invariants.md`` in ``idm-heatpump-api``), which must stay
   separate exact requests.

The findings are written up in ``docs/dev/component-model-evaluation.md``.  Rerun
this script when ``modbus-connection`` changes its read planning, since that is
the part that decides the outcome.

Usage: ``python scripts/evaluate_component_model.py``
"""

from __future__ import annotations

import asyncio
import math
from typing import Any

from idm_heatpump import IdmModelInfo, build_register_map
from idm_heatpump.client import DataType, IdmModbusClient, ModbusCodec, RegisterDef, RegisterType
from modbus_connection.mock import MockModbusConnection
from modbus_connection.model.fields import float32, gauge, integer
from modbus_connection.model.manual import ManualComponent

# The largest system the integration supports: every heating circuit, every zone
# module, and all optional sub-systems.
MAXIMAL_MODEL = IdmModelInfo(
    model_name="Navigator 10",
    active_heating_circuits=list("ABCDEFG"),
    zone_modules=10,
    has_solar=True,
    has_isc=True,
    has_pv=True,
    has_cascade=True,
)

# Documented logical overlaps: a UCHAR data point sharing an address with the
# high word of a neighbouring FLOAT.  The device answers these request-sensitive:
# the exact documented request decides which value comes back.
DOCUMENTED_OVERLAPS = (
    ("humidity_sensor", "hc_a_mode"),
    ("hc_g_heating_curve", "hc_a_heating_limit"),
    ("hc_g_room_setpoint_cool_eco", "hc_a_cooling_limit"),
)


def _word_for(address: int) -> int:
    """Return deterministic pseudo-data, so both decoders see identical words."""
    return (address * 7919) % 65536


def _field_for(register: RegisterDef) -> Any:
    """Mirror one ``RegisterDef`` as a ``modbus-connection`` field."""
    if register.datatype is DataType.FLOAT:
        # IDM FLOAT: IEEE-754 over two registers, low word first.
        return float32(register.address, word_order="little", scale=register.multiplier)
    if register.datatype in (DataType.INT16, DataType.INT8):
        return gauge(register.address, register.multiplier, signed=True)
    if register.multiplier == 1.0:
        return integer(register.address, signed=False)
    return gauge(register.address, register.multiplier, signed=False)


def _api_decode(register: RegisterDef, words: list[int]) -> Any:
    """Decode the same words the way ``idm-heatpump-api`` does today."""
    if register.datatype is DataType.FLOAT:
        return ModbusCodec.decode_float32(words) * register.multiplier
    raw = words[0]
    if register.datatype is DataType.INT16:
        return ModbusCodec.decode_int16(raw) * register.multiplier
    if register.datatype is DataType.INT8:
        return ModbusCodec.decode_int8(raw) * register.multiplier
    return raw * register.multiplier


def _space_of(register: RegisterDef) -> str:
    return "input" if register.register_type is RegisterType.INPUT else "holding"


def _build_component(unit: Any, registers: list[RegisterDef], *, max_gap: int) -> ManualComponent:
    component = ManualComponent(unit, max_gap=max_gap)
    for register in registers:
        component.add(register.name, _field_for(register), space=_space_of(register))
    return component


def _values_match(expected: Any, actual: Any) -> bool:
    if isinstance(expected, float) and isinstance(actual, float):
        if math.isnan(expected) and math.isnan(actual):
            return True
        return abs(expected - actual) <= max(1e-6, abs(expected) * 1e-6)
    return expected == actual


async def main() -> None:
    registers = [reg for reg in build_register_map(MAXIMAL_MODEL).values() if not reg.write_only]
    connection = MockModbusConnection()
    unit = connection.for_unit(1)

    # Seed by absolute address rather than per register: the documented overlaps
    # would otherwise have one data point overwrite what the other is compared
    # against.
    seeded: dict[tuple[str, int], int] = {}
    for register in registers:
        store = unit.input if register.register_type is RegisterType.INPUT else unit.holding
        for offset in range(register.size):
            address = register.address + offset
            value = seeded.setdefault((_space_of(register), address), _word_for(address))
            store[address] = value

    component = _build_component(unit, registers, max_gap=1)
    await component.async_update()

    mismatches = []
    for register in registers:
        words = [seeded[(_space_of(register), register.address + offset)] for offset in range(register.size)]
        expected = _api_decode(register, words)
        actual = component.get(register.name)
        if not _values_match(expected, actual):
            mismatches.append((register.name, register.datatype.value, expected, actual))

    print(f"registers in the maximal map: {len(registers)}")
    print(f"decoding mismatches vs idm-heatpump-api: {len(mismatches)}")
    for row in mismatches[:20]:
        print("   ", row)

    api_requests = len(IdmModbusClient("192.0.2.1")._group_registers(registers))
    documented_words = sum(register.size for register in registers)
    print(f"\nrequests per poll, API batching (strict adjacency, max 40 words): {api_requests}")
    for max_gap in (0, 1, 2, 4, 8, 16):
        blocks = _build_component(unit, registers, max_gap=max_gap)._build_plan().blocks
        planned = sum(len(space_blocks) for space_blocks in blocks.values())
        words = sum(width for space_blocks in blocks.values() for _, width in space_blocks)
        print(
            f"requests per poll, library planning max_gap={max_gap:>2}: {planned:>3}"
            f"  ({words - documented_words:+} words no data point claims)"
        )

    print("\ndocumented logical overlaps (must stay separate exact requests):")
    by_name = {register.name: register for register in registers}
    for float_name, uchar_name in DOCUMENTED_OVERLAPS:
        pair = _build_component(unit, [by_name[float_name], by_name[uchar_name]], max_gap=1)
        blocks = pair._build_plan().blocks
        planned = [block for space_blocks in blocks.values() for block in space_blocks]
        verdict = "ONE merged request" if len(planned) == 1 else "separate requests"
        print(f"   {float_name} + {uchar_name}: {planned} -> {verdict}")


if __name__ == "__main__":
    asyncio.run(main())
