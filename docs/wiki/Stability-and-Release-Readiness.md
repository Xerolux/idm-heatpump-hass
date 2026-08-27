# Stability & Release Readiness

This page records what has been verified, what remains uncertain and what had
to be true before the beta label was removed. It is deliberately stricter than
a normal changelog.

## Current Status

Integration `0.16.0-rc.2` and `idm-heatpump-api` `2.0.0` form the current
exactly pinned integration/API pair. The API version is written in PEP 440 form
because that is what pip resolves; the integration keeps SemVer tags for HACS.
Up to and including `0.14.1` the direct socket was pinned to
`modbus-connection==4.0.0a3` with `tmodbus==0.5.0`.

**`0.16.0`** drops pymodbus entirely — a breaking change, and the reason the
line opened with a beta. `idm-heatpump-api` `2.0.0` owns its own
exception hierarchy (`IdmModbusError` and subclasses) instead of inheriting
from pymodbus, and moves its built-in Modbus TCP transport behind an optional
extra. This integration injects a tmodbus-backed transport, so it now installs
no Modbus stack it does not speak. The transport pins are
`modbus-connection==4.10.0` and `tmodbus[async-serial]==0.6.1`.

**`0.15.1`** was the last line with pymodbus: it pinned `idm-heatpump-api`
`1.0.3`, moved the transport pair to `modbus-connection==4.10.0` /
`tmodbus[async-serial]==0.6.1`, and carried the write-diagnostics work from
[#237](https://github.com/Xerolux/idm-heatpump-hass/issues/237).

**`0.15.0`** moved that pair to `modbus-connection==4.8.1` and
`tmodbus[async-serial]==0.5.1`, adds room temperature sensors for all heating
circuits (A–G) via `idm-heatpump-api`, connection-pacing options, NC
contact inversion and orphaned sensor cleanup. It closes the `0.15.0-beta.1`
through `0.15.0-beta.3` cycle. Hardware smoke evidence for the cycle is recorded
in `docs/release-evidence/0.15.0-beta.2.md`; the stable cut is recorded in
`docs/release-evidence/0.15.0.md`.

**Maintainer decision on `0.15.0`:** the stable tag was cut on the same day
`0.15.0-beta.3` was published, so gate 6 (seven consecutive 24-hour periods of
soak on an unchanged candidate) was not satisfied, and no signed
clean-Home-Assistant smoke test exists for the stable candidate itself
(gate 2). Automated preflight, dependency-pin freshness and the beta-cycle
hardware verification did pass. This is a conscious maintainer call taken at
release time, not an oversight — recorded here and in
`docs/release-evidence/0.15.0.md` so it stays visible.

`idm-heatpump-api` `1.0.2` expanded the optional local web client to map heating-circuit
room temperatures `B61`–`B67` (`room_temperature_HK_A` through `G`), verified live on a
Navigator 10 ALM 6-15 (`B64 = 21.8 °C`). `1.0.3`, the version `0.15.0` pins, is a
maintenance release of that library: it carries CI and security-toolchain updates only
and its public behavior is identical to `1.0.2`.

**Maintainer decision on the stable-release gates below:** `0.11.0` was
published as stable without waiting out gate 6 (the seven-day soak, reset by
the `0.11.0-beta.7`/`beta.8` candidate changes shipped the same day) and
without closing gate 3's live follow-up,
[#192](https://github.com/Xerolux/idm-heatpump-hass/issues/192) (a
Navigator 2.0/Terra SWM model-detection display mismatch; the original
[#44](https://github.com/Xerolux/idm-heatpump-hass/issues/44) is closed, but
the underlying detection topic has an open recurrence). This is a conscious
maintainer call, not an oversight — recorded here so it stays visible.
Gates 1, 4, 5 and 7 are satisfied; gate 2 (clean-install smoke test) was not
independently re-run as part of this cut.

The previous beta cycle (`0.11.0-beta.1` through `0.11.0-beta.8`,
04.–14.08.2026) is preserved in `docs/CHANGELOG.md`, and the `0.8.5-beta.1`
through `0.8.5-beta.8` cycle before it remains preserved in its historical
evidence files.

The July 2026 stability audit verified:

- full lint, formatting, strict type checking and test suites in both repositories;
- grouped reads only across exactly adjacent, non-overlapping register ranges;
- transport/no-response errors cannot permanently disable otherwise valid registers;
- register-specific unavailable sentinels are treated as unused rather than corrupt;
- zone-room modes are individually checked and moved to the API's safe individual-read path after a mismatch;
- unsupported optional addresses are isolated without losing unrelated values;
- advanced raw writes require explicit risk acknowledgement and retain datatype/numeric validation.
- local web protocol discovery tests both supported Navigator families only
  while detection is needed, then persists and reconnects the successful
  protocol without runtime generation switching;
- diagnostics redact Modbus/web connection settings and the local web PIN, and
  reduce detailed web failures to a safe error category.

## Read-only Hardware Evidence

On the maintainer Navigator 10 system, repeated batch-versus-individual checks
covered 170 register definitions in 45 groups and 309 comparisons without a
raw mismatch. The initially reported values `254`, `255` and `-1.0` were
identical in both read modes and were therefore recorded as register-specific
unavailable sentinels.

The cascade capability probe at address 1147 returned raw `FFFF` (decoded
UCHAR `255`). Treating that as unavailable reduced the detected register map
from 170 to 153 definitions. Three complete read-only polls averaged about
2.38 seconds; 151 values were returned, no register was batch-quarantined and
only the firmware register unsupported by that firmware was isolated. These
numbers describe one system and are not universal performance guarantees.

On 2026-08-26 the maintainer Home Assistant instance ran integration
`0.16.0-beta.1` with API `2.0.0b1` through the production tmodbus adapter. The
redacted diagnostics reported 8,836 successful polls, zero failures, a 12.4 ms
last poll, no consecutive failures or model conflict, and a connected Navigator
10 web supplement. Home Assistant exposed 8 devices and 218 entities, showed no
IDM integration log errors, and the run performed no Modbus writes. The RC only
changes the exact API pin from the validated beta to the stable API artifact and
updates release documentation; the API stable release has no runtime changes
from its beta.

## Stable-release Gates

The following gates were satisfied for the `0.8.5` stable release and remain
the requirements any future stable cut must meet again:

1. Publish the audited API version, pin the integration to that exact version and rerun both complete suites against the published artifact.
2. Run the repository release smoke test on a clean Home Assistant installation, including setup, restart, reconfigure, diagnostics, unload/reload and safe entity writes.
3. Resolve or explicitly classify [the Navigator 2.0/Terra SWM model-detection report](https://github.com/Xerolux/idm-heatpump-hass/issues/44) with an exact read-only probe capture. Address 4108 presence alone must not be changed from assumptions.
4. Obtain community confirmation for [the Navigator 2.0 room-mode batch fix](https://github.com/Xerolux/idm-heatpump-hass/issues/69) and [eight-room zone configuration](https://github.com/Xerolux/idm-heatpump-hass/issues/68).
5. Obtain actionable diagnostics for [the unresolved generic server-error report](https://github.com/Xerolux/idm-heatpump-hass/issues/84) instead of guessing at a code change.
6. Complete a beta soak period without new confirmed data-corruption, reconnect-loop, unsafe-write or setup-regression reports.
7. Verify release notes, README, Wiki, dependency pin, manifest version and generated package contents agree.

## Beta Soak Policy

The soak gate means at least **seven consecutive 24-hour periods** on one
unchanged candidate. For `0.8.1-beta.31`, the clock started at publication on
`2026-07-11T18:59:52Z`; the earliest possible completion is
`2026-07-18T18:59:52Z`.

Record observations at publication, around the midpoint, and after the full
seven days. At each observation, review new and updated issues and hardware
feedback. A confirmed data-corruption problem, reconnect loop, unsafe write,
or setup regression fails the soak.

A change to candidate code, runtime dependencies, packaging, config-flow
behavior, polling, or write behavior starts a new candidate and restarts the
clock at its publication time. Documentation-only or evidence-only corrections
do not restart it. Elapsed time alone is insufficient: the candidate evidence
must also contain a passing clean-HA smoke test and a maintainer sign-off.

## Reporting Evidence

For a value or compatibility problem, include the redacted diagnostics export,
Navigator and heat-pump model, firmware, integration/API versions, active
circuits/zones/features, timestamp, register/entity name and the value shown by
the Navigator at the same time. Never publish private IP addresses, PINs,
serial numbers or customer/installer data.

For protocol investigation, maintainers should capture the exact function
code, start address, count and raw words for both the normal batch and an
individual read. Hardware investigation is read-only unless the owner has
explicitly authorized a specific write.

## Candidate Improvements

- Add an opt-in redacted protocol capture service for selected registers so users can gather batch/individual evidence without custom scripts.
- Persist anonymized compatibility reports by Navigator model and firmware, including capability sentinels.
- Add poll timing/request counts to diagnostics to expose slow controllers and over-configured zone setups.
- Consider adaptive scan guidance when a configured poll cannot reliably finish within its interval.
- Keep a climate entity deferred until IDM circuit/room/cooling semantics can be represented without hiding important controller state.
