# Consent presentation review — 5 November 2026

Private build `0.26.0-b5` makes the telemetry summary readable, highlights the full
privacy notice immediately before the explicit consent switch and translates
both consistently. Opening the notice is not a consent action. Default refusal,
withdrawal, data scope, purposes, notice v3 and daily report timing are unchanged.
The notice and erasure form remain available without enabling telemetry.

## Unresolved production questions

This change is not a declaration of legal compliance. Public release remains
subject to checking hosting/processor agreements, provider backups and actual
rights-request handling, as recorded in the private deployment evidence.

The required product behavior gives access to the firmware comparison only when
all telemetry is enabled. The [EDPB consent guidance](https://www.edpb.europa.eu/sme/be-compliant/process-personal-data-lawfully_en)
requires free choice, easy withdrawal without negative consequences and consent
for each processing purpose. Firmware matching uses controller/model/software
metadata; operating counters and an unchanged myIDM ID are not technically
necessary to perform that query. Therefore, linking access to the query to the
complete telemetry dataset raises a conditionality/granularity question that
wording alone cannot resolve.

Retaining this requirement is not evidence that it is legally acceptable. Before
public release, obtain a qualified assessment of the concrete arrangement or
approve a design that separates the firmware service from unrelated analytics.
Do not silently broaden consent or describe the current arrangement as certified.

## Implemented resolution

The operator explicitly approved separating the firmware service from telemetry.
Private build `0.26.0-b6` implements independent consent, off by default, with no
inherited consent. The firmware query uses only controller/model/software metadata,
without a myIDM ID, counters or a local report store. Its consent time/revision is
local only. Telemetry is no longer a condition of the firmware service. The
conditionality concern described above records the superseded design. Hosting,
processor agreements and provider backups still require operator verification.

## Verification of the separated design

- Full unit run: 3,434 passed and two skipped; the sole failure was the module
  map not yet listing the new firmware module/test. After updating AGENTS.md,
  the release-contract check and all targeted privacy/firmware checks passed.
  Total coverage was 98.64%; the separate config-flow gate passed at 100%.
- Strict mypy (86 modules), Ruff and the sensitive-data/language checks passed.
- The twelve genuine HA smoke cases passed across the lifecycle suite and the
  corrected firmware-only case. Firmware-only setup has no telemetry store or
  identity requirement; telemetry-only setup has no firmware contact or sensor.
- Backend suite: 64 tests and 22 subtests passed; backend query schema remains
  unchanged and rejects additional identity/operating fields.
- Live HA b6 initially retained telemetry but removed the old firmware sensor
  because no independent firmware consent existed. Explicit firmware on/off/on
  created, removed and recreated the sensor while telemetry stayed enabled.
  Both German/English forms provide the full notice link. No daily report or
  actuator command was forced. Final private-test settings enable both purposes
  independently, as authorized by the operator.
- DE/EN public privacy pages explain independent firmware consent, minimal
  metadata, transient server queries and possible local Recorder/backup retention.
  Their legal-notice footer remains present. No public git push or release.


## Hosting clarification from the operator

The operator subsequently confirmed that both server and backups are at netcup
in Nuremberg, Germany. Location is no longer an unanswered operator question;
this statement has not been independently verified. Processor agreements and
actual backup retention/erasure are still separate operational checks.
