# Modbus Registers

## Overview

The IDM Navigator 2.0 heat pump provides **663 registers** via Modbus TCP:

| Type | Count |
|------|-------|
| Read-only (RO) | 215 |
| Read/Write (RW) | 266 |
| Write-only (W) | 16 |
| Context-dependent | 166 |

## Address Ranges

| Range | Addresses | Description |
|-------|-----------|-------------|
| PV/Battery | 74-86 | Photovoltaics and battery |
| System | 1000-1199 | System parameters, temperatures, pressures |
| Cascade/Bivalence | 1200-1349 | Multi-HP, heating element |
| Heating Circuits A-G | 1350-1699 | Individual heating circuits |
| BMS/Energy | 1700-1799 | Remote maintenance, energy measurement |
| Zones 1-10 | 2000-2999 | Zone modules with room control |

## Data Types

| Type | Description | Registers |
|------|-------------|-----------|
| **FLOAT** | IEEE 754 floating point (2 registers, Little Endian `<f` / `<HH`) | 2 |
| **UCHAR** | 8-bit unsigned (in 16-bit register, often with multiplier) | 1 |
| **INT8** | 8-bit signed (for negative values like parallel shift) | 1 |
| **UINT16** | 16-bit unsigned (e.g., for power limits) | 1 |
| **INT16** | 16-bit signed (e.g., for bivalence points down to -20°C) | 1 |
| **BOOL** | Boolean (0/1) | 1 |

> **Important:** When writing integer values (`UCHAR`, `INT8`, `INT16`, `UINT16`), the integration automatically applies the `multiplier` stored in the code and rounds the value accordingly.

## Modbus Parameters

| Parameter | Value |
|-----------|-------|
| Protocol | Modbus TCP |
| Default Port | 502 |
| Slave ID | 1 |
| FC Read | 03 (Read Input Registers) |
| FC Write | 16 (Write Multiple Registers) |

## Zone Base Addresses

| Zone | Base Address | Mode Address |
|------|-------------|--------------|
| Zone 1 | 2000 | 2059 |
| Zone 2 | 2067 | 2126 |
| Zone 3 | 2130 | 2189 |
| Zone 4 | 2193 | 2252 |
| Zone 5 | 2256 | 2315 |
| Zone 6 | 2319 | 2378 |
| Zone 7 | 2382 | 2441 |
| Zone 8 | 2445 | 2504 |
| Zone 9 | 2508 | 2567 |
| Zone 10 | 2571 | 2630 |

## Special Registers

| Address | Description | Special Note |
|---------|-------------|-------------|
| 1999 | Error acknowledgment | Must NOT be written permanently |
| 1696 | BMS heat request | Must be written cyclically every 10 min |
| 1698 | BMS cooling request | Must be written cyclically every 10 min |

## EEPROM-sensitive Registers

88 registers are EEPROM-sensitive and have a limited number of write cycles. The integration automatically warns about frequent writing of these registers.
