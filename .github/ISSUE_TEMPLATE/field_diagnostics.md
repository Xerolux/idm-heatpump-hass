---
name: Field diagnostics / real-system data
about: Provide read-only diagnostics for flow-target, binary-register, firmware or Modbus transport validation
title: "[Field diagnostics]: "
labels: diagnostics, field-data
assignees: ''
---

## What should be validated?

Please select all that apply:

- [ ] Flow target / flow deviation (`hp_flow_temp` versus requested flow target)
- [ ] Binary register semantics (0/1, active-low, sentinel, firmware-specific values)
- [ ] COP validation data for DHW, defrost or another firmware version
- [ ] Modbus transport behavior / shared-connection preparation
- [ ] Other read-only validation

## Device and setup

- Heat pump model:
- Navigator generation: 2.0 / 10 / Pro / unknown
- Navigator firmware/software version:
- Active heating circuits:
- Zone modules / rooms:
- Optional modules: Solar / ISC / PV / Cascade / Booster / unknown
- Integration version:
- `idm-heatpump-api` version:
- Home Assistant version:

## Attachments

Please attach only data you are comfortable sharing publicly. Redact host names,
IP addresses, serial numbers, locations and personal information if needed.

- [ ] Home Assistant integration diagnostics export
- [ ] Screenshot(s) from the Navigator showing the same moment in time
- [ ] Optional read-only raw value capture
- [ ] Relevant Home Assistant log excerpt

## Time window

- Start time:
- End time:
- Approximate sampling interval:
- Operating state during capture: heating / DHW / cooling / defrost / standby / mixed

## Values visible in Home Assistant

Please list the relevant entity IDs and values, for example:

```text
sensor.idm_heatpump_hp_flow_temp =
sensor.idm_heatpump_thermal_power_flow_sensor =
sensor.idm_heatpump_power_consumption_hp =
binary_sensor.idm_heatpump_compressor_1 =
```

## Values visible on the Navigator

Please list the labels and values shown on the Navigator at the same time:

```text
Navigator label = value
Navigator label = value
```

## Safety confirmation

- [ ] I only collected read-only data.
- [ ] I did not run direct `write_register` tests against a real heat pump for this issue.
- [ ] I redacted private network and personal data where necessary.
