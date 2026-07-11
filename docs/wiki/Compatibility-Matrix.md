# Compatibility Matrix

This matrix tracks tested IDM hardware without publishing private network data. It separates confirmed devices from expected compatibility so users can judge risk before installing.

## Status Levels

| Status | Meaning |
|--------|---------|
| `confirmed` | Maintainer-tested or backed by a complete diagnostic report with model, firmware and active feature set. |
| `community-tested` | Reported by users with enough detail to reproduce the setup, but not maintainer-owned hardware. |
| `expected` | Register map should match, but no complete diagnostic report is available yet. |
| `unsupported` | Known not to use the Navigator Modbus TCP register model required by this integration. |

## Device Matrix

| Heat pump / controller | Status | Firmware | Active capabilities | Verified with | Notes |
|------------------------|--------|----------|---------------------|---------------|-------|
| IDM 6-15 with Navigator 10 | confirmed | reported by diagnostics | Heating circuit A, PV, Solar, ISC; cascade unavailable sentinel verified | HASS branch tests, API contract tests, repeated read-only Modbus probes | Maintainer test system. Private host, port and network data are intentionally omitted. |
| Navigator 10 / current hardware | community-tested | NAV10_20.23+ expected | Up to 7 heating circuits, up to 10 zone modules | API register model, diagnostics reports | Heat sink and booster registers are Navigator-10-gated. |
| Navigator 2.0 | expected | 2.x expected | Heating circuits, optional PV/Solar/ISC/Cascade | API register model, contract tests | A current Terra SWM report still needs a raw model-detection capture before broad compatibility can be confirmed. |
| Navigator Pro / zone modules | expected | unknown | Zone modules, room sensors and room modes | API register model, contract tests | Needs a complete public diagnostic report before being marked community-tested. |
| Terra SWM with Navigator controller | expected | unknown | Unknown | no complete report yet | Keep as expected until model, firmware and diagnostic export are available. |
| Unknown future Navigator model | expected | unknown | Unknown | no complete report yet | Must be treated as expected until auto-detection and diagnostics prove compatibility. |
| Pre-Navigator controllers | unsupported | any | none | architecture review | Older controllers use different communication/register models. |

## Report Requirements

Please include these fields when reporting compatibility:

- Heat pump model and Navigator/controller model.
- Firmware version from diagnostics.
- Integration version and `idm-heatpump-api` version.
- Active heating circuits, zone modules, PV, Solar, ISC and Cascade flags.
- Redacted Home Assistant diagnostics export.
- Whether the report is read-only or includes verified write actions.

Do not publish private IP addresses, hostnames, ports that identify your network, serial numbers or installer/customer data.
