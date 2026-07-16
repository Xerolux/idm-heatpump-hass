# Stability & Release Readiness

This page records what has been verified, what remains uncertain and what must
be true before removing the beta label. It is deliberately stricter than a
normal changelog.

## Current Status

Integration `0.8.1-beta.31` and `idm-heatpump-api` `0.7.7` form the current,
exactly pinned candidate pair. Automated CI, security, release-artifact, and
checksum checks passed. The candidate remains blocked for stable release until
the clean-Home-Assistant hardware smoke test, the minimum soak duration, and
the hardware/community gates below pass. See the
[candidate evidence](https://github.com/Xerolux/idm-heatpump-hass/blob/main/docs/release-evidence/0.8.1-beta.31.md).

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

## Stable-release Gates

All of the following should be satisfied before a non-beta release:

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
