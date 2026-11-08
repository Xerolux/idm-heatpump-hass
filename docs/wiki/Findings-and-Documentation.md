# Findings and documentation

This is the entry point for field discoveries and the documentation review
process. The wiki follows the source tree shown on [Home](Home); an installed
release uses its tagged manifest. Release history stays in [Changelog](Changelog).

## Findings register

| Finding | Evidence and scope | Practical consequence and open questions |
|---------|--------------------|-----------------------------------------|
| Issue #577 capture replay | Two issue-referenced private captures passed archive-ledger verification and were replayed with API 2.16.1. HTTP JSON yielded three circuit flow temperatures; the checked WebSocket status/home responses parsed and its HTTP data paths were 404s. | Capture notes do not prove controller identity or attribution to the original module. Missing quantities are not inferred. Compare current reporter diagnostics, API version and parsed keys with the exact module before claiming a parser fix. |
| External-power GLT entity recovery (#493) | Regression reproduces a read-only sensor omitted when startup reads an unset sentinel; supported inputs now retain their entity and recover on valid readback. See [Configuration](Configuration). | Writable Numbers already retain sentinel availability and polling dependencies. This correction does not establish a fix for controller-side battery display flicker; absent/unsupported registers remain filtered. |
| PV message 20300 at valid zero production | A Navigator 10 field test cleared the warning without acknowledgement after forwarding a small positive value. The tested firmware and procedure are recorded in [Configuration](Configuration#optional-workaround-for-pv-message-20300-at-zero-production). | Optional 10 W workaround; affects controller PV displays/statistics. Does not prove every 20300 warning has this cause or fix communication failures. |
| `NAV10_` and `T_NAV10_` firmware prefixes | Controller-family matching accepts both exact prefixes; lookalikes such as `NAV100_` are rejected. See [Configuration](Configuration). | HTTP transport alone does not identify a Navigator 2.0. Explicit model overrides retain precedence. |
| Shared Modbus connections | The active provider reports shared ownership when Home Assistant's unit API can be claimed; failures use the private transport. See [Troubleshooting](Troubleshooting#connection-drops). | Read actual `source`, `owns_socket` and `supports_shared_connection` diagnostics before investigating duplicate clients. A successful TCP connection alone does not prove correct register data. |
| Heat-sink flow is FLOAT32 | Field readings exposed an outdated UCHAR declaration in older register tables. See [Known limitations](Known-Limitations#heat-sink-sensors-without-plate-heat-exchanger). | Missing plate-heat-exchanger values may correctly be unavailable; avoid interpreting a decode artifact as zero physical flow. |
| Differential circuits have different semantics | Existing register readings represent storage/reference temperatures and signed reference-minus-storage difference. See [Configuration](Configuration#differential-temperature-controlled-circuits) and [Entities](Entities#differential-temperature-controlled-heating-circuits). | Keep the normal circuit selection as well as the differential selection. Threshold/hysteresis mapping and full hardware confirmation remain open; equal displayed values are not proof of register meaning. |
| Firmware observations are not update offers | The optional catalog matches community observations to controller/model/software metadata. See [Telemetry](Telemetry#firmware-orientation). | Independent opt-in, no installation, no guaranteed plant-specific availability. Only iDM or an authorized installer can assess an update. |
| Observed optimization needs comparable history | Reports, Predictive Advisor and Assist share bounded evidence. See [Predictive Advisor](Predictive-Advisor#shared-evidence-and-optimization-review). | Requires before/after history and suitable coverage. Weather and use can differ; an association does not establish causality or savings. |
| Web-only has model-specific controls | Navigator 10/Pro offers selected validated controls; Navigator 2.0 HTTP remains mainly a read-only supplement with a clock action. See [Protocol capabilities](Protocol-Capabilities). | GLT forwarding, one-shot DHW boost and calculated COP power inputs still need Modbus. A protocol feature is not automatically an implemented entity. |
| Installer access belongs to the installer | Installer-code entities were removed; see [Known limitations](Known-Limitations#firmware-version) and [Installer checklist](Installer-Checklist). | The integration does not calculate access codes or install firmware. |
| B10 high-pressure contact is closed when healthy | The web binary-sensor definition inverts B10 like B5/B15; the correction is recorded in [Changelog](Changelog). | Closed means no fault, open means fault. Incorrect polarity can mimic a permanent fault; check real faults on the controller. |
| Telemetry counters must match their observation window | Independent analysis stores can be newer than the telemetry checkpoint after reload. See [data and delivery](Telemetry#data-and-delivery). | Recovery uses a coherent time/counter pair. Older checkpoints omit operating durations once in a transitional report; HA operating and energy history is preserved. |
| Navigator 1.x supports more than reads | The official 1.x map includes a writable holding block and momentary coil actions. FHEM capture evidence and API contract tests are scoped in [Compatibility Matrix](Compatibility-Matrix). | Implemented support does not establish complete physical validation for every model/firmware combination. Respect EEPROM limits and never automate priority charging cyclically. |
| Unwired temperature inputs answer with memory garbage | A Navigator 2.0 heating circuit without an iDM room sensor reports about -327 °C on register 1364 (observed -327.33 and -327.22; issues #504, #668) instead of a declared sentinel. The value is finite and stable per boot. | The integration treats readings at or below -300 °C on temperature registers as "sensor not present": the health check ignores them, the sensor entity becomes unavailable (unless raw values are requested) and climate/water-heater cards publish no temperature. High-side garbage has no field evidence and remains flagged. |

## Recording the next discovery

Record the controller family, relevant firmware, integration/API versions,
connection mode and the exact observation. Remove credentials, PINs, addresses,
myIDM IDs and unrelated personal data before publishing. Link a redacted issue,
capture description or reproducible test where available.

State separately what was observed, what the implementation guarantees, what
is inferred and what still needs confirmation. A successful write or HTTP
acknowledgement does not establish physical behavior or long-term reliability.
Publish the explanation on the relevant feature page and its German mirror,
then add a concise entry here. Protocol details belong in
[Navigator Protocol Analysis](Navigator-Protocol-Analysis), cross-model evidence
in [Compatibility Matrix](Compatibility-Matrix), and unresolved restrictions
in [Known limitations](Known-Limitations).

## Keeping the wiki current

Every integration source module is assigned to user documentation in
`docs/wiki-coverage.json`. A source fingerprint records the tree that was
reviewed for each feature group. A changed module, new module, missing mirror,
unpublished page or undocumented service causes the documentation coverage
check to fail. The check also rejects obsolete release announcements on Home.

After reviewing the relevant English and German pages against a code change,
run `python scripts/check_wiki_coverage.py --update` to acknowledge the reviewed
source fingerprints. Inspect the resulting diff: this command updates the
review record, not the prose. Never use it as a substitute for documentation
review. New functionality needs setup, defaults, controls, privacy implications,
failure behavior and limitations on its feature page.

CI, dependency validation, release validation and Pages deployment enforce the
coverage check as well as version consistency. Automated checks make omissions
visible; they cannot prove that every sentence is correct. Recheck field
claims when new evidence contradicts them. Do not rewrite published release
history to match current behavior.
