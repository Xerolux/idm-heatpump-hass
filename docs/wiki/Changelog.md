# Changelog

The authoritative, complete history is maintained in
[`docs/CHANGELOG.md`](https://github.com/Xerolux/idm-heatpump-hass/blob/main/docs/CHANGELOG.md)
and the [GitHub releases](https://github.com/Xerolux/idm-heatpump-hass/releases).
This page only summarizes recent milestones.

## Unreleased stability audit — 2026-07-10

- Transport/no-response failures no longer count as permanent failures of individual registers.
- Zone-room mode validation isolates unsupported/invalid values and avoids repeated double reads after quarantine.
- Navigator 10 cascade capability recognizes the hardware-confirmed `255` unavailable sentinel.
- Advanced raw writes retain numeric/datatype validation and require explicit risk acknowledgement.
- Added measurable [stable-release gates](Stability-and-Release-Readiness).

## v0.8.1-beta.27 — 2026-07-10

- Pinned the hardware-verified API 0.7.5.
- Added register-specific unavailable-sentinel handling.
- Compared 170 definitions across 45 groups in 309 read-only batch/individual checks without a raw mismatch.

---

## Historical summary

## v0.4.6 — 2026-05-31

- 169+ entities (109 sensors, 8 binary, 44 numbers, 4 selects, 4 switches)
- Full `idm-heatpump` library integration (Option B complete)
- Binary sensors for compressors, fault alarms, heating/cooling/DHW demand
- Solar, ISC, PV, cascade registers all included
- German entity names throughout
- Write-only register protection (`error_acknowledge`)

## v0.4.4 — 2026-05-31

- Full migration to `idm-heatpump` library as core
- Navigator 10 support: heat sink sensors, flow rate, groundwater temps
- Booster A/B diagnostics (16 new sensors)

## v0.4.0 — 2026-05-30

- Major architectural change
- Navigator 10 support added
- First large library-backed dynamic register map

## v0.2.0 — 2026-03-22

- Initial release
- Basic Modbus TCP integration
- System sensors, heating circuits, DHW control
