# Optional IDM plant telemetry

Telemetry is **off by default**. Under **Reconfigure → Telemetry**, one explicit
switch consents to the complete plant-only schema. Enter the actual heat-pump
serial number once; it is transmitted unchanged. A myIDM ID is not assumed to be
the serial number. No anonymization is claimed.

Only the connected IDM plant, its controller and its connection through this
integration are in scope. No other HA devices, entity IDs, room names, people,
presence, household meters, unrelated integrations, files, credentials or PINs
are read for telemetry. Refusing creates no collector, timer, queue or network
contact, including no endpoint test. Normal local integration operation continues.

## Data and delivery

The fixed schema includes the serial, consent time/revision, report ID, integration
version, Navigator family/model, heat-pump model, firmware, connection mode/web
variant, detected solar/PV/cascade/ISC capabilities, snapshot register count,
observed hours, Modbus polls/failures, observed web outages and alarm-code
transitions. Existing plant analysis may add compressor starts, operating-mode
seconds and electrical/thermal energy aggregates. Missing sources are omitted;
telemetry never requests additional plant polls or performs a write.

Plant aggregates and one frozen pending report are persisted in HA's local
storage, with delayed saves after updates and a flush on clean unload. Abrupt
power loss can lose unsaved changes. Restart downtime does not count as observed
runtime. Error transitions count what was observed, not a complete alarm log.

The first attempt is at least 24 hours after consent, checked hourly, and further
attempts are at least 24 hours apart across restarts. HTTPS uses only the fixed
IDM Tools endpoint, a 15-second timeout and no redirects. Failed reports remain
for the next daily slot; the server deduplicates the persisted report ID.

Disabling stops observations, cancels an in-flight task and deletes the local
collection. Bytes already received cannot be recalled. Re-enabling starts fresh;
a changed consent revision requires renewed explicit consent. Remote controls
and an expanded data schema are not authorized by the telemetry switch.

## Server retention and rights

Reports are private, AES-GCM encrypted outside the web root and linked to the
unchanged serial. They expire twelve calendar months after reception, with
hourly cleanup independent of diagnostic ZIP retention. Request erasure at
[IDM Tools telemetry/privacy](https://idmtools.xerolux.de/telemetry.html). The form
queues the serial and contact email privately; it does not automatically erase
records. The operator verifies entitlement through separate contact before
erasing matching reports. A serial alone is not proof. Disable telemetry as well
to prevent new submissions.

The notice identifies the controller, purpose, consent basis, recipients,
retention, withdrawal, rights and contact. Actual hosting, processor agreements,
access logs, backups, operator request handling and deletion still require
operational verification before deployment. This implementation is not a legal
certification. HACS distribution does not constitute privacy approval.

## Telemetry versus IDM Web Capture

Daily observations help assess firmware compatibility and stability. They do not
replace protocol captures, unknown-register discovery or investigating a setup
that cannot start in HA. IDM Web Capture remains the targeted diagnostic tool.
Neither telemetry consent nor a server response permits remote capture commands.
