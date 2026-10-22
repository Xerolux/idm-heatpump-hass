# Stability & Release Readiness

This page records what has been verified, what remains uncertain and what had
to be true before the beta label was removed. It is deliberately stricter than
a normal changelog.

## 0.23.1 release decision

**0.23.1** is a stable fix release straight off main, no prerelease line:
both fixes are small, locally bounded and carried by focused tests. The
full quality gate passed on both pull requests before the merge
(#579, #580): the four-leg CI matrix (Python 3.14 × HA
2026.8.1/2026.10.0 × manifest-pinned/api-main) with the coverage gates,
strict mypy against the real Home Assistant runtime, ruff, hassfest, the
real-Home-Assistant lifecycle smoke leg and the credential scan. The
register-map correction was reproduced locally against the pure resolver
before any code changed, and the counter guard was verified with the
reporter's exact readings (10036.0 → 10035.99). Field confirmation is
expected from both reporters on the release; #577 stays open until the
reporter confirms auto mode on his hybrid plant.

## 0.23.0 release decision

**0.23.0** is the stable cut of the line that ran through fourteen
prereleases (b1–b14, 2026-10-17 through 2026-10-20). For the cut, the
full quality gate passed on the release tree: the four-leg CI matrix
(Python 3.14 × HA 2026.8.1/2026.10.0 × manifest-pinned/api-main) with the
coverage gates, strict mypy against the real Home Assistant runtime,
ruff, hassfest, HACS, the real-Home-Assistant lifecycle smoke leg and the
release workflow's package-to-tag verification. The line was exercised in
the field continuously: every beta ran live on the maintainer's Navigator
10 plant as it shipped (the b10–b14 advisor work was verified there hour
by hour, ending in an observed hot-water charge inside the recommended PV
window on 2026-10-20), the FLOAT32 flow-register correction was confirmed
live on two plants (discussion #516), and the reporters behind #532,
#537–#539 and #546 validated their fixes directly. The unchanged b14
candidate soaked for about a day before this cut — short of the seven-day
gate, and the line's code changed almost daily. The maintainer decided to
cut anyway: the only write-path changes in the line confine themselves to
write-confirmation scheduling (#537 and its per-task tracking follow-up,
running live on the reference plant since 2026-10-17/18), the register-map
change is a read-typing correction, the advisor and storage changes are
local (additive storage fields, one-time building-model relearn, per-mode
counters starting at zero), and no EEPROM-sensitive register is touched by
any new path. Issue #493 is closed (controller-internal on the reporter's
firmware; the cyclic GLT refresh stays); `idm-heatpump-api` `2.14.4` is
the validated pair with this cut.

## 0.23.0-b10 release decision

**0.23.0-b10** bundles the advisor review pass (forecast time path,
recommendation lifecycle, model quality, write throttling) with the new
per-mode COP statistics. The riskiest items and how they are contained:
the building-model storage version bump forces a one-time relearn of the
heat-loss and flow-curve models (same mechanism as b7/#546, documented in
the changelog); the `refreshed_at` TTL anchor is an additive storage field
parsed defensively from older stores; and the per-mode energy counters
start at zero on adoption, never touching the existing all-mode totals.
The forecast fixes (local-time window rendering, quarter-hour grid
folding, price dedup) are read-path only. Live verification on the
reference plant follows this release: new `energy_cop_heating_*` /
`energy_cop_dhw_*` sensors, local window times on the DHW
recommendation, and the one-time model relearn; the evidence file
`docs/release-evidence/0.23.0-b10.md` records the outcome.

## 0.23.0-b5 release decision

**0.23.0-b5** carries the advisor presentation polish and the web-value
fallback from the same field pass: the recommendation topic superseding
(one active entry per topic, user status inherited across daily
re-issues) and the #516 fallback (web values fill registers whose Modbus
reading is the not-present pattern; real Modbus values always win). Both
are read-path changes with focused tests (topic superseding, fallback
selection matrix). The three b4 fixes were verified live on the reference
plant after the HACS update and restart: the periodic coordinator-wide
unavailability windows are gone (#537, verified across two forwarding
intervals), the operation reason reports English labels only (#538) and
the advisor shows `flow_sensor: false` with flow samples counting as
unavailable on the no-TWT plant (#539) — which this beta's fallback can
now lift again wherever the web supplement serves a real flowmeter
value. Issues #537/#538/#539 closed as completed.

## 0.23.0-b4 release decision

**0.23.0-b4** ships the three findings from the advisor field-feedback
pass (reference plant, 0.23.0-b3, evidence in issues #537/#538/#539). The
availability flap (#537) is the significant one: its root cause is a
silently-swallowed `CancelledError` in Home Assistant's coordinator
pinned by a real-HA probe, fixed by a scheduling guard — verified by
three new real-Home-Assistant regression tests alongside the lifecycle
smoke leg. #538 and #539 are read-path classifications (label vocabulary
mapping, no-TWT flow gating). All three stay open until confirmed on the
reference plant after the HACS update. The advisor's core question was
answered by the same pass: the heating-curve recommendations match the
controller's own display and the room temperatures, with rising daily
confidence — the advisor itself needed no change.

## 0.23.0-b1 release decision

**0.23.0-b1** opens the 0.23 line with two fixes carved from issue #532's
evidence (Navigator 2.0 reporter, diagnostics and log attached): the
register-side "not present" sentinels ship in the freshly released
device-logic patch (exactly pinned in the manifest; compatibility matrix
updated), and
the integration-side `---` web placeholder handling. Both are read-path
classification changes — no write path, no register map addresses, no
configuration surface moved. The prerelease was cut to give the reporter
and the field a testable build quickly; the issue stays open until the
reporter confirms the warnings and the listener-error flood are gone on
his plant. Deliberate non-changes: `ext_humidity` above 100 % stays
rejected (upstream KNX data), the corrupt-batch re-read recovery of
issue #69 is untouched (sentinels are per-register, not validator-wide),
and the Navigator 1.7 map is not modified (separate protocol family, no
hardware capture).

## 0.22.0 release decision

**0.22.0** is the stable cut of the resilience line that ran through seven
prereleases (b1–b7, 2026-10-13 through 2026-10-15) and absorbed the
never-promoted 0.21.3 line. For the cut, the full quality gate passed on the
tagged tree: the four-leg matrix (Python 3.14 × HA 2026.8.1/2026.10.0 ×
manifest-pinned/api-main) with coverage 95 % and `config_flow` 100 %, strict
mypy against the real Home Assistant runtime, ruff, hassfest, HACS, the
real-Home-Assistant lifecycle smoke including the no-leaked-tasks assertion,
packaging, checksum and package-to-tag verification. The line was exercised
in the field continuously: the outage dampening and the five-minute quiet
window ran on the maintainer's own plant through recurring Modbus proxy
outages (verified clean from b1 on — dampening works, repairs self-clear),
and external reporters validated the bidirectional grid meter (#519,
confirmed on b5 with its rounding follow-up on b6) and drove the #493 and
#504 investigations whose fixes shipped through the absorbed 0.21.3 line and
the 0.22 betas. The unchanged b7 candidate soaked for under a day — short
of the seven-day gate 6, and the line's code changed almost daily; the
maintainer decided to cut anyway because the write-surface changes are
confined to GLT RAM inputs (no EEPROM-sensitive register is touched by any
new path, and the RAM refresh cadence is mandatory on the affected
firmwares) while the register map, the model-detection core and the web
supplement are unchanged from the 0.21.x stable. Issue #493 remains open
for a reporter's firmware-specific battery display flicker: the
integration-side handling (cyclic RAM refresh) is validated on the
reference plant, the residual flicker is controller-internal and under
investigation with IDM support, and it affects neither control nor data
integrity. No configuration migration is needed; rolling back to 0.21.2
keeps working.

## 0.21.2 release decision

This maintenance candidate addresses the newly reported #489: optional external
power selections are suggested instead of enforced as defaults, and fractional
SOC readings are validated and rounded to the integer GLT input. Tests exercise
clearing all six roles, preserving remaining mappings, null/blank handling and
fractional conversion, including a genuine HA selector-validation smoke test.
The full coverage, runtime typing, lint, lifecycle and GitHub gates are required
before publication. Dependency pins and transport remain unchanged. Clearing
stops forwarding and the optional HA battery condition; it does not reset a
controller register or prove that the Navigator has forgotten its last sample.

## 0.21.1 release decision

This maintenance candidate addresses confirmed integration defects in automatic
PV DHW boost pacing and system-mode ownership (#487), and adds the controller-
family-specific Navigator 1.7 technician code (#486). Runtime dependencies,
transport and register maps are unchanged. Publication requires both full-suite
coverage gates, strict runtime typing, lint, the real-HA lifecycle suite and the
GitHub quality/security gates to pass on the candidate.

The tests cover mode-preserving start, enforcement, rollback and recovery,
restart-safe cooldown, invalid readings and family-specific code selection.
No physical controller writes or extended field soak were performed. Automated
validation does not prove the sole cause of the reporter's buffer cycles or
on-device acceptance of the Navigator 1.7 code. Navigator PV buffer control is
independent of the HA DHW cooldown. The optional parameters from #429 remain
unavailable because their register mapping is unverified; no mapping is guessed.

## Current Status

See the [published stable release](https://github.com/Xerolux/idm-heatpump-hass/releases/latest)
for the installed stable channel. Current source-tree versions are documented
below and checked automatically; an older release keeps the pins in its own
tagged manifest. The release decisions below describe their original candidates.

## 0.21.0 release decision

**0.21.0** is the stable cut of the Predictive Advisor line that ran through
four prereleases (b1–b4, 2026-10-07 through 2026-10-11). The advisor is
strictly read-only by construction — its module owns no write path, and the
accepting of a recommendation records only an acknowledgment — and it is fully
local and deterministic. For the cut, the full quality gate passed on the
tagged tree: the four-leg matrix (Python 3.14 × HA 2026.8.1/2026.10.0 ×
manifest-pinned/api-main) with coverage 95 % and `config_flow` 100 %, strict
mypy against the real Home Assistant runtime, ruff 0.17, hassfest, HACS, the
real-Home-Assistant lifecycle smoke including the no-leaked-tasks assertion,
packaging, checksum and package-to-tag verification. The line was exercised in
the field by external reporters within days (issues #460 and #471 were filed,
diagnosed and fixed inside the line, and their fixes shipped through b2–b4 and
the parallel 0.20.x cuts). The unchanged b4 candidate soaked from 2026-10-11
to the cut — one day, short of the seven-day gate 6; the maintainer decided to
cut anyway because the advisor carries no write risk and the same tree's
transport and polling core is byte-identical to the 0.20.x line that has been
the stable channel since 2026-10-09. The advisor's learning phases (7-day
baselines before heating-curve recommendations, staged observation) mean its
full behavior unfolds over the first days of operation rather than in a soak.
No configuration migration is needed; rolling back to 0.20.x keeps working.

## 0.20.4 release decision

**0.20.4** is a maintenance cut on top of 0.20.3, branched from the `v0.20.3`
tag: it cherry-picks the issue
[#471](https://github.com/Xerolux/idm-heatpump-hass/issues/471) fix (the
external power forwarding interval becomes a real options field — the guided
advanced page crashed on the missing key — plus quiet write-cooldown skips
and a regression test over every guided feature and level) and raises the
`modbus-connection` floor to `>=4.12.4`, following Home Assistant 2026.10.1's
own core modbus pin; the HA-pin ceiling rule built for 0.20.3 now permits the
rise. The release run validated the tagged tree with the full quality matrix
including the real-Home-Assistant lifecycle suite; packaging, checksum and
package-to-tag verification passed. The dependency moves formally restart the
soak clock (gate 6); the maintainer shipped for the same reasons as 0.20.2
and 0.20.3 — the functional delta is a configuration-flow fix with
regression tests, and the transport bump tracks the exact pair Home Assistant
itself installs at its newest stable release. The 0.21.0 line has carried the
guided fix since 0.21.0-b4.

## 0.20.3 release decision

**0.20.3** is a pin-and-documentation-only maintenance cut on top of 0.20.2,
branched from the `v0.20.2` tag: the device logic moves to
`idm-heatpump-api[web]==2.14.4`, whose only change widens the
`dhw_charge_off_temp` validation range from the documented 46..53 °C to
46..67 °C — the reporter's plant in issue
[#460](https://github.com/Xerolux/idm-heatpump-hass/issues/460) measures
63 °C there and the controller's own web interface offers 50..67 °C. The
tree additionally cherry-picks two maintenance fixes needed to build and
release against that day's tooling: the ruff 0.17 lint findings and the
Home-Assistant-pin ceiling that keeps the `modbus-connection` floor at the
4.12.3 Home Assistant itself pins (upstream 4.12.4 is uninstallable next to
HA; without the ceiling rule every release — including this one — was
blocked). The release run validated the tagged tree with the full quality
matrix; packaging, checksum and package-to-tag verification passed. The
dependency move formally restarts the soak clock (gate 6); the maintainer
decided to ship for the same reasons as 0.20.2 — the delta is a register-
data patch in the library plus tree-identical transport pins — and the
0.21.0 line has carried the same pin since 0.21.0-b3.

## 0.20.2 release decision

**0.20.2** is a pin-and-documentation-only maintenance cut on top of 0.20.1,
branched from the `v0.20.1` tag: the device logic moves to
`idm-heatpump-api[web]==2.14.4`, whose only change calms the per-poll WARNING
for a persistently invalid register value (issue
[#460](https://github.com/Xerolux/idm-heatpump-hass/issues/460)) — one
warning per register and episode instead of one per poll. No integration code
changed against 0.20.1. The release run validated the tagged tree with the
full quality matrix; packaging, checksum and package-to-tag verification
passed. The dependency move formally restarts the soak clock (gate 6); the
maintainer decided to ship anyway because the delta is a logging-only library
patch already exercised by the full gate, and the 0.21.0 beta line has
carried the identical pin since 0.21.0-b2. The 0.21.0 line continues
independently of this cut.

## 0.20.1 release decision

**0.20.1** is the stable cut of the self-healing line that ran through five
prereleases (b1–b5, 2026-09-30 through 2026-10-02); the stable tag changed
no code against b5. For the cut, automated CI — including the
real-Home-Assistant lifecycle suite on both the minimum 2026.8.1 and the
2026.10.0 beta — plus HACS, Hassfest, security checks, release packaging,
published checksum verification and package-to-tag comparison passed. The
line ran on the maintainer's Navigator 10 plant from 2026-09-30; the
unchanged b5 candidate soaked from 2026-10-02 to the cut — four days, short
of the seven-day gate 6, with no confirmed data corruption, reconnect loop,
unsafe write or setup regression reported in the tracker. Issues
[#429](https://github.com/Xerolux/idm-heatpump-hass/issues/429)
(differential-temperature circuits, live-validated on the reporter's
hardware) and
[#319](https://github.com/Xerolux/idm-heatpump-hass/issues/319) (Navigator
1.x priority charge) closed completed inside the line. The transport pins
became Home-Assistant-owned minimum versions — hassfest rejects exact pins
for them — and the device logic is pinned to `idm-heatpump-api[web]==2.14.4`.
The gate-6 shortfall is recorded here so it stays visible.

## Earlier release decisions

**`0.20.0`** was the web-first stable cut: every write slice of the
controllable web-only mode — operating mode, error acknowledgement, the
hot-water setpoint, per-circuit setpoints and modes — was capture-confirmed
(2026-09-28) and live-validated on the maintainer's plant with reversible
round trips, and the Navigator 1.0/1.7 family was completed on the official
coil block (c3000–c3003) with tester-confirmed behaviour
([#319](https://github.com/Xerolux/idm-heatpump-hass/issues/319)). The
automated gates passed. No separate evidence file exists for this cut — its
validation is recorded in the 0.20.1 line evidence — and the release was
superseded by 0.20.1 after six days, when the self-healing line was ready.

**`0.19.0`** is the stable cut of the line that ran through sixteen betas.
It makes the Navigator 1.0/1.7 family a full citizen — the complete official
holding block, a firmware-honest range guard, the capture-verified FW030
float setpoint and a water heater card — and adds PV visibility (issue
#353), the solar thermal opt-out, the per-register diagnostics report, a
more honest AI adviser and the German wiki mirror. Automated CI (including
the real-Home-Assistant smoke leg), HACS, Hassfest, security checks, release
packaging, published checksum verification and package-to-tag comparison
passed; `0.19.0-b15` ran on the maintainer's production plant with a clean
log, and the Navigator 1.0/1.7 register corrections were confirmed by a
tester's post-update diagnostics on the released version (issue #364). The
`0.17.x`/`0.16.x` decisions below remain as published.

**`0.17.2-b6`/`0.18.0`:** automated CI, HACS, Hassfest, security checks,
release packaging, published checksum verification and package-to-tag
comparison passed for the candidate. The read-only running-plant
observation in the
[September 18 audit](https://github.com/Xerolux/idm-heatpump-hass/blob/main/docs/dev/post-release-audit-2026-09-18.md)
used beta 5; it was not hardware validation or a seven-day soak of beta 6.
The [candidate record](https://github.com/Xerolux/idm-heatpump-hass/blob/main/docs/release-evidence/0.17.2-b6.md)
captured the pre-publication state.

**`0.17.0`** is the stable cut of the line that opened with `0.17.0-beta.1`
on 2026-09-09. It carries the full code-audit result, the model-reconciliation
corrections of `beta.3` and the Navigator 1.0/1.7 protocol family of
`beta.4`, on `idm-heatpump-api` `2.1.1` and `modbus-connection` `4.11.1`.

**Maintainer decision on `0.17.0`:** the stable tag was cut on 2026-09-13,
the day `0.17.0-beta.4` was published, so gate 6 (seven consecutive 24-hour
periods of soak on an unchanged candidate) was not satisfied for `beta.4` —
although `beta.1` through `beta.3` had been in the field since 2026-09-09 with
no regression report. Gate 3's live hardware follow-up remains open twice
over: no Navigator 1.0/1.7 device is maintainer-owned (the call for testers is
[#319](https://github.com/Xerolux/idm-heatpump-hass/issues/319)), and the KNX
bridge's physical-bus verification is unchanged from `0.16.0`. Automated
preflight, dependency-pin freshness and the full CI matrix did pass, and a
read-only model-detection probe against the maintainer's Navigator 10 on
2026-09-13 confirmed the new detection does not misclassify a shared-family
controller. This is a conscious maintainer call taken at release time, not an
oversight — recorded here and in `docs/release-evidence/0.17.0.md` so it stays
visible.

Source-tree integration `0.23.1` and `idm-heatpump-api` `2.14.4` form the current
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
`modbus-connection>=4.12.4` and `tmodbus[async-serial]>=0.6.2`.

**`0.17.0-beta.2`** removes one thing `0.17.0-beta.1` introduced: the repair
issue for a register the heat pump does not implement. A controller that answers
`Illegal Data Address` for, say, `firmware_version` is behaving normally — that
model, firmware or hardware option simply lacks the function — but a warning
card in **Settings → Repairs** reads like a defect, and it asked for an action
that does not exist. The explanation stays, as a log line and in the diagnostics
download. Everything else is identical to `0.17.0-beta.1`; the soak clock
restarts because the code changed.

**`0.17.0-beta.1`** is the first candidate of the `0.17.0` line and carries the
result of the code audit in `docs/dev/code-audit-2026-09.md`. Eight bugs are
fixed, among them a poll that outlived its config entry, a failed setup that
left live entities behind, a second heat pump behind one Modbus gateway that
could no longer be added, forwarded temperatures that were not converted to
degrees Celsius, and sentinel readings that reached a temperature state. Six
robustness items and three performance items came with them, plus the
extractions that made the affected code testable: `model_resolution.py` for the
model reconciliation and a public coordinator surface for the seven modules that
used to reach into its private attributes. Both runtime pins moved forward
(`modbus-connection` `4.11.1`, `idm-heatpump-api` `2.0.1`); no register map or
entity identifier changed. It is a beta because the audit touched model
detection, setup and teardown, write-enabled entities and services, and because
the dependency change restarts the soak clock.

**`0.16.2`** is a patch on `0.16.1`: `validate_overrides` accepted a KNX
group-address override that claimed the derived address (`base + object
number`) of another served object, and the bridge then routed that address to
only one of the two registers. Address resolution and the KNX options step now
refuse any address claimed twice. `tmodbus[async-serial]` moved from `0.6.1` to
`0.6.2`; no register or entity changed.

**`0.16.1`** is a patch on `0.16.0`: with the local web supplement pointed
at an IP address, the integration closed a Home Assistant aiohttp session
instead of detaching it, which Home Assistant reports in the log and which
reaches into a connector shared with every other integration. The per-IP
session is now released with `detach()` and created with `auto_cleanup=False`
so a rebuilt web client does not leave the old one pinned until Home Assistant
stops. Nothing else changed — registers, entities, the KNX bridge, the write
guards and the runtime pins are identical to `0.16.0`.

**`0.16.0`** is the stable cut of that line, identical in code to
`0.16.0-rc.6`. Its headline feature is the **experimental KNX bridge**: the
integration serves the 654 IDM KNX communication objects itself, through the
Home Assistant `knx` integration, so the Weinzierl `KNX IP BAOS 774` gateway
module is no longer needed. The bridge is opt-in and off by default, and its
physical-bus behaviour remains unverified — see the open gates below.

**Maintainer decision on `0.16.0`:** the stable tag was cut on 2026-08-28,
one day after `0.16.0-rc.6` was published, so gate 6 (seven consecutive
24-hour periods of soak on an unchanged candidate) was not satisfied — its
earliest eligible completion was 2026-09-03. Gate 3's live KNX follow-up
(physical group-address telegram interoperability and first-export bus load)
and Navigator 2.0/Pro hardware coverage also remain open. Automated preflight,
dependency-pin freshness and the RC5/RC6 live smoke evidence on the maintainer
Navigator 10 did pass. This is a conscious maintainer call taken at release
time, not an oversight — recorded here and in
`docs/release-evidence/0.16.0.md` so it stays visible.

**`0.16.0-rc.6`** retains RC5's latest-value KNX queue and adds startup
recovery for the event filter. Home Assistant can expose the KNX services
before its KNX runtime is ready; the bridge now retries only the missing
group-address batches instead of requiring a manual IDM reload. The write
guards and configurable 60-second EEPROM default are unchanged. Physical
group-address telegram interoperability and bus load remain open.

**`0.15.1`** was the last line with pymodbus: it pinned `idm-heatpump-api`
`1.0.3`, moved the transport pair to `modbus-connection>=4.12.4` /
`tmodbus[async-serial]>=0.6.2`, and carried the write-diagnostics work from
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
