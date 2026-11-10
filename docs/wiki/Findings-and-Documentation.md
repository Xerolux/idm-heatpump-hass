# Findings and documentation

This is the entry point for field discoveries and the documentation review
process. The wiki follows the source tree shown on [Home](Home); an installed
release uses its tagged manifest. Release history stays in [Changelog](Changelog).

## Findings register

| Finding | Evidence and scope | Practical consequence and open questions |
|---------|--------------------|-----------------------------------------|
| Issue #577 capture replay | Two issue-referenced private captures passed archive-ledger verification and were replayed with API 2.16.1. HTTP JSON yielded three circuit flow temperatures; the checked WebSocket status/home responses parsed and its HTTP data paths were 404s. | Capture notes do not prove controller identity or attribution to the original module. Missing quantities are not inferred. Compare current reporter diagnostics, API version and parsed keys with the exact module before claiming a parser fix. |
| External-power GLT entity recovery (#493) | Regression reproduces a read-only sensor omitted when startup reads an unset sentinel; supported inputs now retain their entity and recover on valid readback. See [Configuration](Configuration). | Writable Numbers already retain sentinel availability and polling dependencies. This correction does not itself fix controller-side battery display flicker; absent/unsupported registers remain filtered. |
| Battery use requires register 84 (#493) | IDM support confirmed to the #493 reporter that when a battery is used, register 84 (`battery_discharge`) must be written. After mapping battery charge/discharge together with SoC, the reporter saw no further flicker. See [external power setup](Installation-and-Setup#automatic-external-power-forwarding-from-home-assistant). | Map battery charge/discharge as well as SoC. For two batteries, forward the sum of their signed power (positive = discharge). This is a controller input requirement, not an integration defect. IDM did not confirm that every other external-power register must be written in every cycle. |
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

## Donation review: 9 November 2026

Three additional diagnostic ZIPs and six additional telemetry reports were reviewed.
The two Navigator 10 ZIPs contain usable web and statistic responses; numeric
setting parameters parse with the parameter reader and must not be routed to
the HTML-section parser. A note-only reply explicitly stating that a circuit
is unavailable is separate from malformed JSON. API 2.16.2 and integration
0.26.11 retain other successful circuits; diagnostics list absent circuit
letters without copying names or controller response text.

Open work, not forgotten or declared fixed:

- The donation declared as NAVIGATOR Pro has 499 readable FC03/FC04 words,
  including 48 function/address pairs absent from earlier readable references.
  Attribution, scaling and physical model remain unverified: do not create
  entities or change official register definitions from readability alone.
- Its HTTP login remains at an authentication form; the cause is not proven
  to be an incorrect PIN. Compare a fresh browser login and the capture tool's
  sanitized per-attempt trace before changing an authentication flow.
- Physical heat-pump models are absent in all eight reviewed telemetry reports.
  Capability flags are API model metadata, not proof of installed equipment.
- Five later telemetry reports have coherent complete duration counters; the
  transitional report intentionally omits them. Historical inconsistencies stay
  flagged. Do not mix stable `NAV10_` and test-channel `T_NAV10_` observations.
- #577's remaining parser and packed-register questions need exact issue-linked
  evidence. #649 has a healthy-state field confirmation; a forced fault was not
  tested. #493 is answered: IDM support requires register 84 to be written
  when a battery is used. #668 still awaits reporter confirmation. Existing
  public replies remain separate from a verified general controller
  requirement, except for this IDM confirmation of register 84.

The private originals stay under their existing retention policies. Synthetic
regression fixtures reproduce structures only; no donated readings or private
notes are published. A reviewed inbox status means the evidence was evaluated,
not that every open hypothesis is fixed or every address has a mapping.


## Donation review: 10 November 2026

Fresh Navigator 10 capture replays with API 2.16.2 confirm that explicitly unavailable heating circuits and freshwater components remain missing rather than becoming fabricated zeroes. Weather forecasts and numeric parameters parse successfully. Different menu counts reflect reported availability; identical firmware and Modbus address coverage do not establish one physical plant.

The server now exposes affected-report counts and web-outage coverage alongside paired Modbus failure ratios, both overall and by comparison cohort. A small overall ratio must not hide an affected report. These are reported communication observations, without a proven cause or outage duration; otherwise coherent runtime/energy observations are not discarded automatically. No extra client data, consent change or controller request is introduced. See [telemetry review quality](Telemetry#review-quality).

A menu type set narrowing from number-or-text to text-only is visible in the private structure diff but adds no new type fact for the selective notification. Synthetic regressions cover the distinction and preserve notification for a genuinely unseen type. No new API parser change is justified by this difference. Physical heat-pump model metadata, ambiguous Pro component attribution and explicit observation boundaries remain open; firmware matching continues to use source metadata rather than a hardcoded latest version.
