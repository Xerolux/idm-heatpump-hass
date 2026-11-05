# Optional IDM plant telemetry

Telemetry is **off by default**. Under **Reconfigure → Telemetry**, one explicit
switch consents to the complete plant-only schema. Enter the actual heat-pump
myIDM ID once; it is transmitted unchanged. The controller myIDM ID is used automatically when available. No anonymization is claimed.

Only the connected IDM plant, its controller and its connection through this
integration are in scope. No other HA devices, entity IDs, room names, people,
presence, household meters, unrelated integrations, files, credentials or PINs
are read for telemetry. Refusing telemetry creates no telemetry collector, timer, queue or network
contact, including no telemetry endpoint test. Firmware queries are separate. Normal local integration operation continues.

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

The first attempt is randomly 24–48 hours after consent. Further attempts are
24–25 hours apart, including after errors. The exact next slot is persisted
before network I/O and checked once a minute without network traffic. After
downtime, overdue reports receive up to one hour of random recovery delay.
There are no immediate retries or backlog bursts. HTTPS uses only the fixed
IDM Tools endpoint, a 15-second timeout and no redirects. Failed reports remain
for the next daily slot; the server deduplicates the persisted report ID.

Disabling stops observations, cancels an in-flight task and deletes the local
collection. Bytes already received cannot be recalled. Re-enabling starts fresh;
a changed consent revision requires renewed explicit consent. Remote controls
and an expanded data schema are not authorized by the telemetry switch.

## Server retention and rights

Before the consent switch, the form links prominently to the complete privacy
notice, operator contact, data rights and erasure process. Opening that link is
not consent and does not enable collection. The summary and explicit switch
are available in both English and German. Version b5 changes presentation only;
the notice revision, purposes, data scope and existing daily slot remain unchanged.

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


## Independent firmware observations

Under **Reconfigure → Firmware query**, a separate explicit switch enables
**Latest reported firmware**. It is off by default and never inherits consent
from telemetry. Firmware-only operation works without a myIDM ID or telemetry.
Disabling telemetry does not disable separately authorized firmware queries.
Disabling firmware queries cancels the request and removes the sensor and its
registry entry immediately. Without firmware consent there is no catalog contact.

The query sends only Navigator family, controller/plant model and installed
firmware, after a random startup delay of up to 30 minutes, then every six hours
plus up to 30 minutes of random delay. It sends no myIDM ID, operating counters,
temperatures, credentials or other HA data. There is no persistent firmware queue;
the integration keeps only the current result. HA may retain sensor states
according to the local Recorder/backup configuration. The server uses metadata transiently and does not
save a plant report. The connection IP is technically visible; short-lived rate
identifiers expire within two hours at the next hourly cleanup. Both features
have a prominent link to the full privacy notice before their consent switch.

The catalog uses community telemetry observations only, never old diagnostic
ZIPs. Matching requires the same Navigator/controller and known plant model,
firmware prefix/channel and major line. Missing plant types match only other
missing-type reports in that same known controller/software series. Test and
stable channels remain separate. Ordering includes numeric build numbers.
Unknown metadata or absent observations produce no version recommendation.

This is not official IDM availability, installation permission or compatibility
approval. Only IDM/your installer can assess and install firmware. Sharing
telemetry helps build the catalog, but is not required to use firmware queries.
Telemetry notice v3 remains unchanged; independent firmware consent uses
`idm-firmware-v1`. The locally recorded consent time/revision is not sent in
firmware queries. Only telemetry uploads carry their own identity and consent.


On 5 November 2026 the operator confirmed that the server and backups are
hosted by netcup in Nuremberg, Germany. This resolves the location according to
the operator. Processing agreements and actual backup retention/erasure remain
separate checks.


The operator confirmed six-month retention of full netcup server snapshots.
The private data directory is on the root filesystem and thus included in a full
disk image. Twelve-month live expiry does not erase previous image copies.
Backup erasure and restoration handling remain unresolved before general
availability; this is not consent to an additional retention period.


## Independent erasure journal on Proxmox

The journal now resides on the Proxmox host outside netcup snapshots and guest
backups. It holds only random report/request IDs and erasure/expiry timestamps,
not myIDM IDs, contacts or measurements. A private outbound SSH tunnel protects
transfer without a new public port. Erasures are confirmed only after durable
external recording. Startup reconciles the current history; failure blocks access.
History expires after six calendar months plus one day. Old software snapshots
require the current service before access is enabled. The independent Proxmox
journal must not be rolled back together with netcup.
