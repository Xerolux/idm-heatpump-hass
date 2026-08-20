# Field Diagnostics Guide

Last updated: 2026-07-21

This document describes which real-system data the still-open validations need.
Every step is **read-only**; direct Modbus write tests do not belong in field
diagnostics issues.

## Goals

- Only implement the flow deviation once the actually requested heat-pump flow
  setpoint has been verified unambiguously.
- Only classify binary registers as final once sentinel, active-low and
  firmware-dependent values from real Navigator 2.0 / 10 / Pro systems are known.
- Improve the COP documentation with additional data for domestic hot water,
  defrost cycles and further firmware levels.
- Back up Modbus transport questions for the later issue with real symptoms and
  diagnostic fields.

## Required attachments

- Home Assistant diagnostics export of the integration.
- Screenshot of the Navigator values from the same time window.
- Optional read-only raw value recording.
- Relevant log excerpt when the topic is transport or timeout behavior.

## Privacy

Please remove or redact before uploading:

- public and private IP addresses,
- host names,
- serial numbers,
- location data,
- personal notes or names.

## Safety rules

- No live write tests with `idm_heatpump.write_register`.
- No tests against EEPROM-sensitive registers.
- Do not test parallel energy managers on the same building-management/PV
  register.
- For transport topics, first collect logs and diagnostics exports instead of
  rebuilding the production connection.

## Matching issue template

Please use the **Field diagnostics / real-system data** template. It asks
specifically for the time window, operating state, HA values, Navigator values
and the safety confirmation.
