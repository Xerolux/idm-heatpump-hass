# Optional IDM plant telemetry

Telemetry is **off by default**. Under **Reconfigure → Telemetry**, one explicit
switch consents to the complete plant-only schema. Enter the actual heat-pump
myIDM ID once; it is transmitted unchanged. The controller myIDM ID is used automatically when available. No anonymization is claimed.

Only the connected IDM plant, its controller and its connection through this
integration are in scope. No other HA devices, entity IDs, room names, people,
presence, household meters, unrelated integrations, files, credentials or PINs
are read for telemetry. Refusing creates no collector, timer, queue or network
contact, including no endpoint test. Normal local integration operation continues.

## Data and delivery

The fixed schema includes the myIDM ID, consent time/revision, report ID, integration
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
unchanged myIDM ID. They expire twelve calendar months after reception, with
hourly cleanup independent of diagnostic ZIP retention. Request erasure at
[IDM Tools telemetry/privacy](https://idmtools.xerolux.de/telemetry.html). The form
queues the myIDM ID and contact email privately; it does not automatically erase
records. The operator verifies entitlement through separate contact before
erasing matching reports. A myIDM ID alone is not proof. Disable telemetry as well
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


## Website and private operator access

The [public telemetry/privacy page](https://idmtools.xerolux.de/telemetry.html)
explains consent and accepts an erasure request using the myIDM ID and a contact
email. The request itself does not immediately erase data. Users disable
telemetry in HA to stop collection and sending.

The operator uses the existing **IDM Tools Authelia owner account and second
factor** at [private telemetry](https://auth.blueml.eu/idm-captures/telemetry).
No new login or password is created. The capture inbox also links to this page.
It shows private myIDM assignments, compatibility cohorts, observed counters and
pending erasure requests. Contact and verify the requester before using the
verified-erasure action. Public requests never grant private read access.


## Why sharing helps, and your firmware sensor

Consented plant observations reveal firmware compatibility, connection problems
and recurring faults, helping target integration improvements. In return, the
**Latest reported firmware** sensor appears only while telemetry is enabled.
It queries the matching server catalog on startup and at most every six hours.

The server groups observations by Navigator family, exact heat-pump model,
firmware prefix and numeric major line. `T_NAV10_20.*`, `NAV10_20.*` and `m_20.*`
are separate, as are different plant models. Version and build ordering is
numeric. If the interface does not report a heat-pump type, matching uses only other missing-type reports within the same detected controller and firmware series. Known plant models remain separate. An unknown controller/firmware series produces no recommendation.

This is **not an official latest IDM release** and does not establish availability
or suitability for a specific plant. Only IDM or the installer can assess and
install firmware. Matching firmware versions may be shown to other participants
without myIDM IDs or operating data. Attributes identify whether a higher version
was observed. Initially the sensor may be unknown until matching reports arrive;
existing diagnostic ZIPs are not repurposed for this catalog.

Disabling removes the sensor and its registry entry and cancels firmware queries.
No consent means no display and no query. This additional purpose uses notice
revision `idm-telemetry-v3` and requires explicit consent.
