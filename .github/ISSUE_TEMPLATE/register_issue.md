---
name: Register issue
about: Report a wrong, missing, unsafe, or unsupported Modbus register
title: "[REGISTER] "
labels: register, compatibility
assignees: ""
---

## Register

- Register key, if known:
- Address, if known:
- Read or write:
- Data type or unit, if known:

## Device

- Heat-pump model:
- Controller or Navigator version:
- Firmware version:
- Active heating circuits:
- Zone modules and rooms:
- Integration version:
- `idm-heatpump-api` version:

## Observed behavior

Describe what Home Assistant shows or what the register returns.

## Expected behavior

Describe what the device UI or documentation suggests should happen.

## Evidence

Attach diagnostics, debug logs, screenshots, or a redacted read-only Modbus capture.
Remove credentials, hostnames, IP addresses, and serial numbers before posting.

## Safety note

Do not test writes to EEPROM-sensitive, service, or unknown registers unless a maintainer explicitly asks for a controlled reproduction.
