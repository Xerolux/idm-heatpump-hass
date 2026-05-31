"""Standalone read-only test for IDM Heatpump integration.

Connects to the IDM heat pump and reads ALL registers.
No writes are performed. Reports all errors and data.
"""
from __future__ import annotations

import asyncio
import logging
import sys
import struct
import math

from idm_heatpump import (
    DataType,
    IdmModbusClient,
    RegisterDef,
    build_register_map,
    get_all_registers,
    get_detection_registers,
    get_heating_circuit_registers,
    get_zone_module_registers,
)
from idm_heatpump.client import RegisterType
from idm_heatpump.const import (
    HEATING_CIRCUIT_LETTERS,
    MAX_HEATING_CIRCUITS,
    MAX_ZONE_MODULES,
)

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)-8s %(name)s %(message)s",
)
_LOGGER = logging.getLogger("idm_test")

HOST = "192.168.178.103"
PORT = 502
SLAVE_ID = 1


async def test_basic_connection(client: IdmModbusClient) -> bool:
    """Test basic Modbus TCP connection."""
    _LOGGER.info("=" * 60)
    _LOGGER.info("PHASE 1: Basic Connection Test")
    _LOGGER.info("=" * 60)
    try:
        await client.connect()
        if client.is_connected:
            _LOGGER.info("SUCCESS: Connected to %s:%d", HOST, PORT)
            return True
        _LOGGER.error("FAILED: connect() returned but not connected")
        return False
    except Exception as e:
        _LOGGER.error("FAILED: Connection error: %s", e)
        return False


async def test_model_detection(client: IdmModbusClient) -> dict | None:
    """Detect model and capabilities."""
    _LOGGER.info("=" * 60)
    _LOGGER.info("PHASE 2: Model Detection")
    _LOGGER.info("=" * 60)
    try:
        info = await client.detect_model()
        _LOGGER.info("Model: %s", info.model_name)
        _LOGGER.info("Active circuits: %s", info.active_heating_circuits)
        _LOGGER.info("Zone modules: %d", info.zone_modules)
        _LOGGER.info("Solar: %s", info.has_solar)
        _LOGGER.info("ISC: %s", info.has_isc)
        _LOGGER.info("PV: %s", info.has_pv)
        _LOGGER.info("Cascade: %s", info.has_cascade)
        _LOGGER.info("Features: %s", info.features)
        return info
    except Exception as e:
        _LOGGER.error("Model detection failed: %s", e)
        return None


async def test_read_library_registers(client: IdmModbusClient, model_info: dict | None) -> dict[str, any]:
    """Read all registers from the idm_heatpump library."""
    _LOGGER.info("=" * 60)
    _LOGGER.info("PHASE 3: Reading Library Registers")
    _LOGGER.info("=" * 60)

    reg_map = build_register_map(model_info=model_info)
    _LOGGER.info("Total registers in library map: %d", len(reg_map))

    reg_list = list(reg_map.values())
    data = {}
    errors = []

    try:
        data = await client.read_batch(reg_list)
        _LOGGER.info("Successfully read %d/%d registers", len(data), len(reg_list))
    except Exception as e:
        _LOGGER.error("Batch read failed: %s", e)
        _LOGGER.info("Falling back to individual reads...")
        for reg in reg_list:
            try:
                val = await client.read_register(reg)
                data[reg.name] = val
            except Exception as re:
                errors.append((reg.name, reg.address, str(re)))

    if errors:
        _LOGGER.warning("Failed registers (%d):", len(errors))
        for name, addr, err in errors:
            _LOGGER.warning("  %s (addr %d): %s", name, addr, err)

    return data


async def test_individual_register_reads(client: IdmModbusClient) -> dict[str, any]:
    """Test reading key registers individually."""
    _LOGGER.info("=" * 60)
    _LOGGER.info("PHASE 4: Individual Register Reads (Key System Registers)")
    _LOGGER.info("=" * 60)

    key_registers = [
        RegisterDef(address=1000, datatype=DataType.FLOAT, name="outdoor_temp"),
        RegisterDef(address=1002, datatype=DataType.FLOAT, name="outdoor_temp_avg"),
        RegisterDef(address=1005, datatype=DataType.UCHAR, name="system_mode"),
        RegisterDef(address=1008, datatype=DataType.FLOAT, name="storage_temp"),
        RegisterDef(address=1010, datatype=DataType.FLOAT, name="cold_storage_temp"),
        RegisterDef(address=1012, datatype=DataType.FLOAT, name="dhw_temp_bottom"),
        RegisterDef(address=1014, datatype=DataType.FLOAT, name="dhw_temp_top"),
        RegisterDef(address=1030, datatype=DataType.FLOAT, name="dhw_draw_temp"),
        RegisterDef(address=1032, datatype=DataType.UCHAR, name="dhw_target_set"),
        RegisterDef(address=1050, datatype=DataType.FLOAT, name="hp_flow_temp"),
        RegisterDef(address=1052, datatype=DataType.FLOAT, name="hp_return_temp"),
        RegisterDef(address=1090, datatype=DataType.UCHAR, name="heatpump_status"),
        RegisterDef(address=1091, datatype=DataType.UCHAR, name="heating_request"),
        RegisterDef(address=1092, datatype=DataType.UCHAR, name="cooling_request"),
        RegisterDef(address=1093, datatype=DataType.UCHAR, name="dhw_request"),
        RegisterDef(address=1099, datatype=DataType.UCHAR, name="total_fault"),
        RegisterDef(address=1350, datatype=DataType.FLOAT, name="flow_temp_hk_a"),
        RegisterDef(address=1364, datatype=DataType.FLOAT, name="room_temp_hk_a"),
        RegisterDef(address=1378, datatype=DataType.FLOAT, name="target_flow_temp_hk_a"),
        RegisterDef(address=1748, datatype=DataType.FLOAT, name="energy_heat_heating"),
        RegisterDef(address=1750, datatype=DataType.FLOAT, name="energy_heat_total"),
        RegisterDef(address=1790, datatype=DataType.FLOAT, name="current_power_draw"),
        RegisterDef(address=4122, datatype=DataType.FLOAT, name="power_draw_total"),
        RegisterDef(address=4126, datatype=DataType.FLOAT, name="thermal_power"),
    ]

    results = {}
    for reg in key_registers:
        try:
            val = await client.read_register(reg)
            results[reg.name] = val
            _LOGGER.info("  %s (addr %d) = %s", reg.name, reg.address, val)
        except Exception as e:
            results[reg.name] = f"ERROR: {e}"
            _LOGGER.error("  %s (addr %d) FAILED: %s", reg.name, reg.address, e)

    return results


async def test_heating_circuits(client: IdmModbusClient) -> dict[str, any]:
    """Test reading all heating circuit registers."""
    _LOGGER.info("=" * 60)
    _LOGGER.info("PHASE 5: Heating Circuit Registers (A-G)")
    _LOGGER.info("=" * 60)

    results = {}
    for letter in "abcdefg":
        _LOGGER.info("--- Circuit %s ---", letter.upper())
        try:
            regs = get_heating_circuit_registers(letter)
            data = await client.read_batch(list(regs.values()))
            for name, val in data.items():
                _LOGGER.info("  %s = %s", name, val)
                results[name] = val
            missing = set(regs.keys()) - set(data.keys())
            if missing:
                _LOGGER.warning("  Missing: %s", missing)
                for m in missing:
                    results[m] = "MISSING"
        except Exception as e:
            _LOGGER.error("  Circuit %s failed: %s", letter.upper(), e)
            results[f"circuit_{letter}"] = f"ERROR: {e}"

    return results


async def test_raw_register_scan(client: IdmModbusClient) -> None:
    """Scan raw register ranges to find which addresses respond."""
    _LOGGER.info("=" * 60)
    _LOGGER.info("PHASE 6: Raw Register Range Scan")
    _LOGGER.info("=" * 60)

    ranges = [
        (74, 16, "PV registers (74-89)"),
        (1000, 80, "System base (1000-1079)"),
        (1086, 10, "Groundwater (1086-1095)"),
        (1090, 30, "Status/Demand/Pumps (1090-1119)"),
        (1120, 15, "Bivalency/Cascade (1120-1134)"),
        (1147, 10, "Cascade stages (1147-1156)"),
        (1200, 35, "Cascade temps/limits (1200-1234)"),
        (1350, 160, "Heating circuits (1350-1509)"),
        (1650, 20, "External room temps (1650-1669)"),
        (1680, 20, "Faults (1680-1699)"),
        (1690, 30, "External/GLT (1690-1719)"),
        (1748, 20, "Energy (1748-1767)"),
        (1790, 10, "Power (1790-1799)"),
        (1850, 30, "Solar/ISC (1850-1879)"),
        (2000, 10, "Zone 1 (2000-2009)"),
        (2065, 10, "Zone 2 (2065-2074)"),
        (4001, 5, "Booster A (4001-4005)"),
        (4010, 15, "Booster A temps (4010-4024)"),
        (4040, 15, "Booster B temps (4040-4054)"),
        (4108, 25, "Power limit/Firmware (4108-4132)"),
    ]

    for start, count, label in ranges:
        try:
            raw = await client._read_registers(start, count, RegisterType.INPUT)
            _LOGGER.info("%s: OK (%d registers)", label, len(raw))
            _LOGGER.debug("  Raw values: %s", raw)
        except Exception as e:
            _LOGGER.warning("%s: FAILED - %s", label, e)

        try:
            raw_h = await client._read_registers(start, count, RegisterType.HOLDING)
            _LOGGER.info("%s (HOLDING): OK (%d registers)", label, len(raw_h))
        except Exception:
            pass


async def main() -> int:
    _LOGGER.info("IDM Heatpump Read-Only Integration Test")
    _LOGGER.info("Target: %s:%d (slave_id=%d)", HOST, PORT, SLAVE_ID)
    _LOGGER.info("")

    client = IdmModbusClient(host=HOST, port=PORT, slave_id=SLAVE_ID)
    exit_code = 0

    try:
        # Phase 1: Connection
        if not await test_basic_connection(client):
            _LOGGER.error("Cannot connect. Aborting.")
            return 1

        # Phase 2: Model Detection
        model_info = await test_model_detection(client)
        if model_info is None:
            _LOGGER.warning("Model detection failed, continuing with manual config")

        # Phase 3: Library registers
        lib_data = await test_read_library_registers(client, model_info)
        _LOGGER.info("Library data summary: %d values read", len(lib_data))
        for name, val in sorted(lib_data.items()):
            _LOGGER.debug("  %s = %s", name, val)

        # Phase 4: Individual key registers
        await test_individual_register_reads(client)

        # Phase 5: Heating circuits
        await test_heating_circuits(client)

        # Phase 6: Raw scan
        await test_raw_register_scan(client)

        _LOGGER.info("=" * 60)
        _LOGGER.info("TEST COMPLETE - All phases finished")
        _LOGGER.info("=" * 60)

    except KeyboardInterrupt:
        _LOGGER.info("Interrupted by user")
        exit_code = 130
    except Exception as e:
        _LOGGER.error("Unexpected error: %s", e, exc_info=True)
        exit_code = 1
    finally:
        await client.disconnect()
        _LOGGER.info("Disconnected.")

    return exit_code


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
