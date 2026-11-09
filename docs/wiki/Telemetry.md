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
variant, API model solar/PV/cascade/ISC capability metadata (not verified installed equipment), snapshot register count,
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
IDM Tools endpoint, a 15-second timeout and no redirects. Network errors,
throttling and server-side faults keep the frozen report for the next daily
slot; a permanent client-error rejection (HTTP 4xx except 429) discards it so
the next slot composes a fresh one. The server deduplicates the persisted
report ID, which also survives a report recomposed after an integration
upgrade changed the schema.

## Delivery status, failures and repair

With telemetry consent active, the **Telemetry** device group (with the
optional device hierarchy enabled) shows the local
**Telemetry report status** sensor. It states `not_sent`, `accepted`,
`rejected` or `unavailable`, with attributes for the last and next attempt
time, the consecutive failed attempts, whether a report is pending and the
consent policy revision. The sensor is local-only: its information is never
part of the transmitted data, and it disappears with its registry entry when
consent is withdrawn.

Failed daily attempts accumulate into a persisted streak. After seven
consecutive undelivered daily reports, a repair notice under
**Settings → System → Repairs** points out that telemetry is not being
delivered; local heat-pump operation is unaffected. The notice clears itself
as soon as a report is accepted, and withdrawing consent removes it
immediately. One timer shared by telemetry and firmware observations drives
the per-minute checks, so enabling both consents wakes Home Assistant once
per minute instead of twice.

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

Under **Reconfigure → Share and compare firmware**, a separate explicit switch enables **Latest reported firmware**. It is off by default, independent of telemetry and works without a myIDM ID. Existing `idm-firmware-v1` consents remain valid; this release neither resets them nor enables a disabled feature. Disabling cancels future requests and removes the sensor immediately.

Only Navigator family, controller/plant model and installed firmware are sent, after up to 30 minutes of random startup delay and then every six hours plus up to 30 minutes of random delay. No myIDM ID, serial, operating values, credentials or other HA data are included. The server encrypts technical sightings aggregated per cohort, version and UTC day without a plant identifier. They expire automatically after twelve calendar months. There is no persistent client queue. Recorder/backups can retain sensor states according to your HA settings. The connection IP is technically visible; keyed rate counters expire within two hours at hourly cleanup. The privacy link remains before the switch. Disabling stops future contributions; existing aggregate sightings remain until expiry and cannot identify an individual contributor.

The catalog combines authorized telemetry, independent firmware sightings and explicit firmware metadata in private diagnostic ZIPs. Diagnostic-derived records stay tied to the original ZIP's 90-day expiry, deletion and test-exclusion state; telemetry remains subject to its own twelve-month retention and verified erasure. Original archives are not rewritten. The private telemetry overview lists firmware, comparison scope and sources. Counts are source observations, not distinct heat pumps; independent submissions aggregate per day.

Matching keeps Navigator/controller, known plant model, firmware prefix/channel and major line separate. Missing plant models match only other missing-type observations in the same controller series. `NAV10_` and `T_NAV10_` never cross-match. NAVIGATOR Pro is individual room control, not another name for Navigator 10. Generic legacy Pro metadata stays marked `unconfirmed_component`: its latest reported version remains visible within that declared group, but `newer_observed` stays unknown and no heat-pump update repair is created. Explicit room-control metadata has its own group. Contradictory family/prefix data does not establish compatibility.

A single matching observation is already the **latest reported firmware**. If it equals the installed version, there is no newer-version notice. This is the newest version observed in this catalog, not a claim about all manufacturer releases. Only iDM or an authorized installer can assess suitability and perform an update. No firmware image is uploaded or installed by this feature. The existing consent revision remains `idm-firmware-v1`; technical behavior and retention are explained in the updated notice.

## Independent erasure journal on Proxmox

The journal now runs only inside dedicated unprivileged LXC 117 on Proxmox,
independent of netcup snapshots. No application daemon, host bind mount or nesting
is used on the hypervisor. It holds only random report/request IDs and erasure/expiry timestamps,
not myIDM IDs, contacts or measurements. A private outbound SSH tunnel protects
transfer without a new public port. Erasures are confirmed only after durable
external recording. Startup reconciles the current history; failure blocks access.
History expires after six calendar months plus one day. Old software snapshots
require the current service before access is enabled. The independent Proxmox
journal must not be rolled back together with netcup.

The initial direct-host installation was removed, including its user, files and
private keys. New keys reside in the guest. Do not roll the journal container
itself back to an obsolete history together with netcup.

For a manual test, `idm_heatpump.send_telemetry` submits one report with existing consent, a one-minute cooldown and a newly reserved daily slot. `idm_heatpump.check_firmware` queries observations with its independent consent. Both actions take `entry_id` and never change plant settings.

## Automatic quality screening

The private IDM Tools summary separates report counts from distinct declared myIDM IDs. It shows per-counter availability, observation hours, matched poll/failure counters, paired energy increments and cohort quality flags. Windows shorter than one hour remain visible but are excluded from energy and operating-time comparisons. Operating durations exceeding the rounded observation window are flagged and excluded from operating shares, rather than normalized or overwritten. A zero event count does not prove complete source coverage.

After a reload, telemetry resumes saved counters and elapsed time together at current source baselines. Independent newer analysis checkpoints are not backfilled without matching time. An upgrade from older checkpoints omits operating durations until the pending window is acknowledged; frozen retry reports remain byte-for-byte unchanged. This does not reset Home Assistant operating history or change consent, reporting schedules or the transmitted schema.

## Firmware orientation

Under **Settings → Devices & services → IDM Heatpump → Reconfigure → Share and compare firmware**, enable the separate consent. The plant's **Telemetry** device group then shows **Latest reported firmware** (version number) and **Newer firmware observed (unconfirmed)** (on/off; unavailable without matching data). Attributes include installed/observed versions and the comparison time. Use **Developer tools → Actions → IDM Heatpump: Check firmware now** to request a manual comparison with existing consent.

A newer matching observation also raises a notice under **Settings → System → Repairs**. The notice card itself names both versions — the installed one and the newest matching community observation — and repeats that this is orientation, not availability. **Acknowledge seeing this notice** remembers that exact version for this device, including across restarts. Only a different newer version can trigger another notice. Acknowledging never performs an update.

Community reports do not establish availability or compatibility for a particular plant. iDM or an authorized installer must verify and perform updates. Voluntarily sharing reports improves the community comparison basis; firmware queries remain independently available without telemetry. Both consent settings remain optional and off by default.

With the optional device hierarchy enabled, the cloud-consent entities — **Latest reported firmware**, **Newer firmware observed (unconfirmed)** and **Telemetry report status** — share their own **Telemetry** subdevice beneath the plant. Moving them preserves their entity IDs; the installed software version stays in **Diagnostics**. Without the hierarchy, they remain diagnostic entities on the main device.
