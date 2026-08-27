# Changelog

The authoritative, complete history is maintained in
[`docs/CHANGELOG.md`](https://github.com/Xerolux/idm-heatpump-hass/blob/main/docs/CHANGELOG.md)
and the [GitHub releases](https://github.com/Xerolux/idm-heatpump-hass/releases).
This page only summarizes recent milestones.

## v0.16.0-rc.4 — 2026-08-27

**Entity names are translated.** Until now only a handful of control entities
had translations; every other entity — the Modbus registers, the calculated and
operating-analysis sensors, the technician codes and the local web supplement
values — carried a hardcoded German name in every language. All of them now
resolve through a Home Assistant translation key, so an English installation
shows English names and a German one shows the names it always had. Entity IDs
and unique IDs are unchanged.

The rest of the candidate is quality-scale work with no user-visible effect:
the config flow reached 100 % test coverage and the suite 95 %, both enforced in
CI; the optional web clients use Home Assistant's own aiohttp session; and
strict typing lost its seven disabled error codes.

See [Entities](Entities#entity-names-and-languages).

## v0.16.0-rc.3 — 2026-08-27

Optional, **experimental** **KNX bridge**: the integration can serve the IDM KNX communication
objects — same object numbers, datapoint types and read/write directions as
IDM's ETS example project — through the Home Assistant `knx` integration, so
the Weinzierl `KNX IP BAOS 774` gateway module is no longer needed. KNX Secure,
tunnelling and routing come from the `knx` integration. One base group address
configures all 654 objects, and `idm_heatpump.export_knx_group_addresses`
returns the table for ETS.

Experimental: unit-tested, but never yet exercised against a real KNX bus.

See [KNX Bridge](KNX-Bridge).

## v0.15.0 — 2026-08-22

Stable release closing the `0.15.0-beta.1`..`beta.3` cycle. No breaking changes:
unique IDs, entity IDs, register addresses and write paths are unchanged, and an
existing config entry keeps polling exactly as before.

### Changed

- **Transport off the alpha pin**: `modbus-connection==4.8.1` and
  `tmodbus[async-serial]==0.5.1` (previously `4.0.0a3` / `0.5.0`), with a typed
  error hierarchy and `ModbusDesyncError` for gateways serving several clients.

### Added

- **Web room temperature sensors for all heating circuits A–G**: `B61`–`B67`
  (`room_temperature_HK_A`..`G`), verified live on Navigator 10 ALM 6-15.
- **Connection pacing options** under "Advanced Modbus settings": pause between
  requests (0–0.5 s) and pause after connect (0–5 s), both `0` by default.
- **Automated dependency pin freshness checking** and an English documentation
  contract, both enforced in CI.

### Fixed

- **Inverted NC digital inputs in the web supplement**: `ew_evu_lock_contact`,
  `dewpoint_humidity_alarm` and `failure_eheating` now report `off` in normal
  operation and `on` on alarm, lock or fault.
- **Orphaned deprecated sensor entities**: stale `sensor.*_web` entries left
  over from the `binary_sensor` migration are cleaned from the entity registry
  at startup.

> **Release gate note**: this stable tag was cut without the seven-day soak and
> without a signed stable-candidate smoke test — a deliberate maintainer
> decision, recorded in `docs/release-evidence/0.15.0.md` and on
> [Stability and Release Readiness](Stability-and-Release-Readiness).

## v0.15.0-beta.3 — 2026-08-22

Beta candidate 3: adds room temperature sensors for all heating circuits (A–G)
in the optional Navigator web supplement, bumps `idm-heatpump-api` to 1.0.2.

### Added

- **Web room temperature sensors for all heating circuits A–G**: Support for `B61`–`B67`
  (`room_temperature_HK_A`..`G`), verified live on Navigator 10 ALM 6-15 (`B64 = 21.8 °C`).
- **`idm-heatpump-api[web]`**: Bumped to `1.0.2`.

## v0.15.0-beta.2 — 2026-08-22

Beta candidate 2: fixes inverted state on normally closed (NC) digital inputs in
the Navigator web supplement, automatically cleans up orphaned legacy sensor
entities in Home Assistant's entity registry, and adds automated dependency
pin freshness checking.

### Fixed

- **Inverted NC digital inputs in Web supplement**: `ew_evu_lock_contact`,
  `dewpoint_humidity_alarm`, and `failure_eheating` are Normally Closed contacts
  and now correctly report `off` in normal operation and `on` on alarm/lock.
- **Orphaned deprecated sensor entities cleanup**: Stale `sensor.*_web` entities
  migrated to `binary_sensor` are automatically cleaned from Home Assistant's
  entity registry at startup.
- **Dependency pin updater platform support**: Normalized paths to POSIX format.

### Added

- **English documentation contract**: Enforced by tests.
- **Automated dependency freshness checking**: Daily PyPI pin verification.

## v0.15.0-beta.1 — 2026-08-19

Beta candidate: the transport pin moves off the `modbus-connection==4.0.0a3`
alpha onto `4.8.1`, plus two new pacing options that are off by default. Because
this changes the runtime dependency of the direct Modbus socket, it ships
through the pre-release channel — the soak clock for a stable tag restarts with
this candidate. No breaking changes; unique IDs, entity IDs, register addresses
and write paths are unchanged, and an existing config entry polls exactly as
before without any action.

### Changed

- **Transport pinned to `modbus-connection==4.8.1` and
  `tmodbus[async-serial]==0.5.1`** (previously `4.0.0a3` / `0.5.0`). The newer
  library adds a typed error hierarchy, connection-wide pacing, and — since
  4.8.0 — `ModbusDesyncError`: when a peer answers a different request than the
  one sent (typical for a gateway serving several Modbus clients at once), the
  backend drops the link instead of decoding the foreign reply. The
  `async-serial` extra is not optional even though this integration is TCP-only:
  since `modbus-connection` 4.7.0 the backend module imports `serialx` at module
  level.
- **Transport error translation now uses the typed exceptions** instead of
  comparing `exception_code` numbers. The contract is unchanged: code 2 stays
  `IllegalAddressError` (coordinator bisect), codes 5/6/10/11 stay on the
  retry-in-place path, and the `exception_code=<N>` marker the coordinator
  matches on is still rendered as a number.

### Added

- **Two options under "Advanced Modbus settings"**, both `0` by default:
  **pause between requests** (0–0.5 s, minimum gap from the end of one request
  to the start of the next) and **pause after connect** (0–5 s, once per
  connect and reconnect). Raise them for controllers or gateways that answer
  "device busy", drop requests, or time out under a dense request stream. The
  guided setup profiles set the request pause along: "unreliable network"
  0.05 s, "multiple clients" 0.1 s.

## v0.14.1 — 2026-08-18

Patch release: three bugs around the lifecycle of optional heating circuits. No
breaking changes; unique IDs, register addresses and write paths are unchanged.

### Fixed

- **Sensors of a circuit enabled later never appeared.** Entities are only built
  while the config entry loads. If the controller still reported the `-1.0`
  sentinel in that one poll, the "hide unused sensors" filter dropped the
  circuit's read-only registers — so the circuit got its controls but neither
  flow, room nor setpoint temperature, until some later reload happened to catch
  better values. A configured circuit is now exempt from that filter, the same
  way writable controls already were. Availability still follows the live value.
- **Flow deviation showed the flow temperature while idle.** A circuit that asks
  for nothing reports setpoint `0.0`. That is a normal operating state, not a
  declared sentinel, so the sensor computed `flow - 0` and published the
  measured flow temperature as a 26 K deviation. It is now suppressed (state
  `unknown`) while the circuit requests nothing, like the COP sensor at
  standstill.
- **"Unnamed device" in the device list.** Sub-devices are created before the
  platforms so `via_device` links resolve regardless of platform order; their
  name only arrives with the first entity. A sub-device that never received one
  stayed in the list as an unnamed, empty entry. Those are now detached when the
  config entry loads. A sub-device whose entities the user merely disabled is
  kept.
- **Orphaned entities of deselected circuits.** Unchecking a circuit left its
  entities in the registry as permanently unavailable. They are now removed when
  the config entry loads, narrowly scoped to register-backed entities of this
  entry whose register points at an unconfigured circuit. Re-enabling the
  circuit recreates them under unchanged unique IDs.

## v0.14.0 — 2026-08-18

Minor release: one usability fix on the heating curve, the circuit design
parameters become expert entities, plus a per-circuit dashboard example and a
contract test that catches the root cause of the 0.13.0 bug in CI. Config
entries, entity IDs, unique IDs, register addresses and write paths are
unchanged, and the tested dependency pairing is identical to 0.13.0.

### Fixed

- **Heating curve step size.** `hc_{a..g}_heating_curve` is a FLOAT register and
  therefore inherited the default step of 0.5, even though its range is
  0.1–3.5. Common settings such as 0.3 or 0.4 fell between two steps and could
  not be entered. The step is now 0.1; the range still comes from
  `idm-heatpump-api`.

### Changed

- **Heating-curve parameters are expert entities.** `hc_{x}_heating_curve`,
  `hc_{x}_parallel_shift`, `hc_{x}_setpoint_flow_constant` and
  `hc_{x}_setpoint_flow_cooling` are created disabled on **new** installations,
  like `power_limit_hp` already was. They define the design of the whole
  heating system and write to EEPROM registers. Existing installations are
  unaffected — `entity_registry_enabled_default` only applies when an entity is
  first created.

### Added

- **Per-circuit dashboard example**
  (`docs/examples/dashboard-idm-heating-circuit.yaml`). Home Assistant sorts a
  device page alphabetically and mixes comfort setpoints with design
  parameters; the example keeps them in separate sections and adds a history
  graph of measured flow, requested flow, room and outdoor temperature.
- **Contract test for the web value keys** (`tests/test_cross_repo_contract.py`).
  It compares the value names `idm-heatpump-api` can deliver against the keys
  the integration turns into entities and fails as soon as the API provides a
  value the integration would silently discard — the root cause of the
  circuit B–G bug in 0.13.0.

## v0.13.0 — 2026-08-18

Minor release with one fix that makes new entities appear on systems with more
than one heating circuit, plus German names for the optional circuits. Fully
backward compatible: config entries, entity IDs, unique IDs, register addresses
and write paths are unchanged, and the tested dependency pairing is identical
to 0.12.0.

### Fixed

- **Web entities for every heating circuit, not just circuit A.** The Navigator
  web values for the circuit pump (`M31`–`M37`), mixer (`M41`–`M47`) and flow
  temperature (`B51`–`B57`) are provided by `idm-heatpump-api` for circuits
  A–G, but the integration only picked up the circuit-A keys from a static
  allowlist. A circuit enabled later through the options flow therefore never
  received its `(Web)` entities — the values arrived and were discarded. Web
  entities are now created per configured heating circuit, so they appear on
  the reload that follows a later activation.
- **German names for heating circuits B–G.** The name table only contained
  `hc_a_*` entries, so every optional circuit fell back to the English default
  (`Hc D Cooling Limit` instead of `Kühlgrenze HK D`). Names for B–G are now
  derived from the circuit-A table. Entity IDs and unique IDs are unchanged;
  only the displayed name differs.

## v0.12.0 — 2026-08-17

Minor release with two new features and one polling fix. Fully backward
compatible: config entries, entity IDs, unique IDs, register addresses and
write paths are unchanged, and the tested dependency pairing is identical to
0.11.1.

### Added

- **Flow deviation per heating circuit** (`calculated_hc_{a..g}_flow_deviation`):
  the measured flow temperature of a circuit minus the flow setpoint the
  controller requests for that same circuit. Positive means overshoot, negative
  means the circuit does not reach its setpoint — the key figure when tuning a
  heating curve. Nothing is estimated; both operands are decoded registers of
  one circuit. Idle (`0.0`) and unconfigured (`-1.0`) circuits report
  `unavailable` instead of a meaningless deviation. With device hierarchy
  enabled the sensor sits on its heating-circuit device.
- **Self-diagnosis for a scan interval that is too short**: when polling takes
  at least 80% of its own interval for several cycles in a row, a repair issue
  explains the situation and names the three effective remedies. This
  saturation is what turns into timeouts, especially when a second Modbus
  client shares the controller.

### Fixed

- Calculated sensors could lose their source registers under entity-aware
  polling — `calculated_cop` was missing from the hand-maintained dependency
  list, so disabling the two power sensors made the COP sensor permanently
  unavailable. Dependencies are now derived from the sensor definitions.

See [`docs/CHANGELOG.md`](https://github.com/Xerolux/idm-heatpump-hass/blob/main/docs/CHANGELOG.md#0120---2026-08-17)
for the full entry including test and CI changes.

## v0.11.1 — 2026-08-15

Patch release fixing [#192](https://github.com/Xerolux/idm-heatpump-hass/issues/192):
a runtime model correction from the web supplement (e.g. Navigator 2.0 →
Navigator 10 based on a NAV10 firmware-string match) updated the
coordinator's live state, but Home Assistant's Device Registry — populated
once at entity-setup time — never received the correction, since that
detection key is deliberately excluded from the reload fingerprint to avoid
tearing down active connections. The device page kept showing the original
model while diagnostics already showed the corrected one. The coordinator
now pushes a changed model/firmware/serial number directly into the Device
Registry whenever a correction actually changes one of them.

## v0.11.0 — 2026-08-15

First stable release of the 0.11.x line, after eight betas
(`0.11.0-beta.1` – `0.11.0-beta.8`). Fully backward compatible: existing
config entries, entity IDs, register addresses and write paths are
unchanged. See [`docs/CHANGELOG.md`](https://github.com/Xerolux/idm-heatpump-hass/blob/main/docs/CHANGELOG.md#0110---2026-08-15)
for the full consolidated changelog.

### Added

- Direct Modbus TCP socket now runs through `modbus-connection==4.0.0a3`
  with the `tmodbus==0.5.0` backend, replacing the previous direct-Pymodbus
  path.
- External humidity forwarding and external storage-temperature forwarding
  (GLT), alongside the existing per-heating-circuit room-temperature
  forwarding.
- Transport diagnostics (`modbus-connection`/`tmodbus` versions, socket
  ownership, connection status).

### Changed

- `idm-heatpump-api[web]` pinned `0.9.1` → `1.0.1` (the stable API 1.x line
  introduces the public transport-injection contract this integration's
  tmodbus path relies on).
- Minimum Home Assistant version raised to `2026.8.1`;
  `via_device` → `via_device_id` device-registry migration.

### Fixed

- Eight confirmed bugs found in a full codebase audit (climate preset-mode
  safety, a `write_register` `KeyError`, a diagnostics IP-leak, a register-
  cache collision, a write-filter gap, reconfigure input loss, a stale
  device-info cache, and a zone-room validation counter reset), plus
  repair-issue IDs now scoped per config entry and narrower exception
  handling in the polling coordinator.

### Known limitation

- A Navigator 2.0/Terra SWM model-detection follow-up
  ([#192](https://github.com/Xerolux/idm-heatpump-hass/issues/192)) remains
  open and is being investigated post-release.

## v0.11.0-beta.3 - 2026-08-05

- Continues the direct `modbus-connection==4.0.0a3` / `tmodbus==0.5.0` socket
  with the stable `idm-heatpump-api[web]==1.0.0`.
- Transient Modbus exception codes 5 (Acknowledge), 6 (Server Device Busy), 10
  (Gateway Path Unavailable) and 11 (Gateway Target Failed to Respond) are now
  translated to `ModbusException`, so the API retry loop repeats them in place
  on the same connection instead of forcing a hard reconnect — matching the
  API 1.0 transport contract (retry-in-place path). Code 2 remains
  `IllegalAddressError` for the coordinator bisect logic.
- Removed the dead `_NON_RETRYABLE_DEVICE_EXCEPTION_CODES` set and corrected
  comments that misdescribed the API retry behavior.

## v0.11.0-beta.1 — 2026-08-04

- This is the first IDM integration beta whose direct Modbus TCP socket runs
  through
  `modbus-connection==4.0.0a3` with the separately pinned
  `tmodbus==0.5.0` backend. `4.0.0a3` is the transport library version; the IDM
  integration version is `0.11.0-beta.1` (latest stable: `0.10.1`).
- `idm-heatpump-api[web]==0.9.1` continues to own the register model, batching,
  encoding/decoding, model detection and write safety. Its
  `pymodbus>=3.12.1,<4.0` dependency remains temporarily pinned because API
  0.9.1 still imports it, but pymodbus no longer owns the direct socket.
- Diagnostics and the API-version sensor now include `modbus-connection` and
  `tmodbus` versions plus redacted transport capabilities.
- The adapter is implemented and covered by automated tests. Each config entry
  still owns its socket and reports `supports_shared_connection: false` because
  Home Assistant central cross-entry sharing is not available; read-only
  validation of the new path on real Navigator hardware remains pending.
- Transient Modbus responses 5 (Acknowledge), 6 (Server Device Busy), 10
  (Gateway Path Unavailable), and 11 (Gateway Target Failed to Respond) escape
  the batch layer without individual-read fallback or permanent register
  quarantine. Backend-owned busy retries are not duplicated by the adapter.
- This beta does not satisfy the stable hardware-smoke and soak gates yet.

## v0.8.5 — 2026-07-23

First stable release of the 0.8.5 line. Consolidates the eight beta candidates
plus the final i18n and stability fixes from the stable code review.

### Added

- **Manual Navigator model override** (Auto / Navigator 10 / Navigator 2.0 /
  Navigator Pro), wenn die automatische Erkennung mehrdeutig ist.
- **Restart-sicherer Warmwasser-Boost** mit den Services
  `idm_heatpump.start_dhw_boost` und `idm_heatpump.cancel_dhw_boost` sowie
  Start-/Cancel-Buttons. Der Boost-Zustand überlebt HA-Neustarts.
- **Optionale Gerät-Hierarchie** (Wärmepumpe, DHW-Controller, Zonenmodule als
  separate Sub-Geräte).
- **Entity-bewusstes Modbus-Polling**, **Momentan-COP-Sensor** und
  **Betriebszyklus-Analyse** (Verdichter-/Abtau-Zähler).
- **Navigator-Web-Binary-Sensoren** für Online-/Regler-Online-Status.

### Changed

- **API-Pin aktualisiert:** `idm-heatpump-api[web]==0.8.4` (war 0.8.1).
  Bringt sentinel-aware Heizkreis-Modus-Probes, robusteren Navigator-10-vs-2.0-Differenzierer
  für Terra SWM, automatische Kaskadenerkennung und Navigator-10-Heizkreisdaten
  für die Kreise B–G.
- **Klima- und Warmwasser-Entitäten melden ihre unterstützte Schrittweite**
  (0,5 °C bzw. 1 °C für integer-backed Register).
- **Modbus-Register-Wiki** gegen API 0.8.4 regeneriert.
- **Repository aufgeräumt** (`.planning/`, alte `ROADMAP.md`, verwaiste Skripte
  und AI-Handoff-Doku entfernt).
- **README und HA-Core-Entwurf** listen jetzt alle 8 Plattformen und das
  vollständige Service-Set inkl. DHW-Boost.

### Fixed

- **Integer-Modbus-Numbers bieten keine invaliden Nachkommastellen mehr an**
  ([#158](https://github.com/Xerolux/idm-heatpump-hass/issues/158)).
- **Terra SWM / Navigator 2.0 wurde fälschlich als Navigator 10 erkannt**
  (Issue #44); die Erkennung verlangt jetzt plausible Power-Limit-Werte.
- **Water-Heater-Entität ignoriert jetzt den Unused-Sentinel** und zeigt nicht
  mehr `-1 °C` als Live-Temperatur an.
- **DHW-Boost nutzt Übersetzungsschlüssel** statt harter deutscher Strings;
  die Multi-Device-Service-ValidationError verwendet den bestehenden Schlüssel
  `multiple_entries_select_entry`.
- **DHW-Boost:`DhwBoostError` wird im Timeout-/Target-Restore-Pfad sauber
  abgefangen** statt als unhandled Task-Exception durchzuschlagen.

### Known limitation

- **Home Assistants experimentelle `modbus_connection` wird noch nicht
  verwendet.** Der vorbereitete Transport-Vertrag bleibt bewusst inaktiv, bis
  die offizielle HA-Schnittstelle final ist.

## v0.8.5-beta.8 — 2026-07-23

### Changed

- **Neue Beta-Kandidatenversion `0.8.5-beta.8`:** Aktualisiert Manifest,
  Release-Evidence, Changelog und Wiki-Verweise auf den aktuellen Beta-Stand.
  Laufzeitcode, Entitäten, Register, Schreibpfade und der getestete
  `idm-heatpump-api[web]==0.8.4`-Pin bleiben unverändert.

## v0.8.5-beta.7 — 2026-07-22

### Fixed

- **Endgültiges Navigator-Modell wird mit der API synchronisiert:** Manuelle
  Modell-Overrides und eindeutige spätere Web-Korrekturen gelten nun auch für
  die modellabhängigen Register- und Schreibprüfungen der API.
- **Zukünftiger Modbus-Transportvertrag korrigiert:** Der weiterhin inaktive
  Vertrag unterscheidet FC04/Input Register und FC03/Holding Register und
  begrenzt Slave-IDs auf 1–247. Der produktive Transport bleibt unverändert.

## v0.8.5-beta.6 — 2026-07-22

### Fixed

- **Ganzzahlige Modbus-Werte verwenden jetzt Schrittweite 1:** Heiz- und
  Kühlgrenzen der Heizkreise A–G sowie alle weiteren schreibbaren Integer-
  Register bieten keine ungültigen 0,5-Schritte mehr an.
- **Climate und Warmwasser melden die unterstützte Zielwert-Schrittweite:**
  Heizkreis- und Raum-Sollwerte verwenden 0,5 °C, der ganzzahlige Warmwasser-
  Sollwert 1 °C.

## v0.8.5-beta.5 — 2026-07-22

### Changed

- **Pin auf `idm-heatpump-api[web]==0.8.4`:** Aktualisiert die API-Bibliothek
  auf v0.8.4 für verbesserte Modbus-Modellerkennung (Erkennung aktiver Heizkreise
  über Betriebsmodus-Register, verlässliche Abfrage für Navigator 10 vs. 2.0
  bei Terra SWM Firmware und Kaskaden-Erkennung).

## v0.8.4 — 2026-07-19

### Changed

- **Zonenmodul-Raumrelais ist jetzt ein `binary_sensor`:** Der Relaisstatus
  pro Raum (`zm{z}_room{r}_relay`) wurde bisher als numerischer Sensor mit
  `0`/`1` angezeigt. Er läuft jetzt auf der `binary_sensor`-Plattform und
  zeigt `on`/`off` (Device Class `Running`, Toggle-Icon). Erfordert das
  mitgelieferte `idm-heatpump-api[web]==0.8.1`, in dem das Relay-Register
  als `binary=True` markiert ist. Schließt #128.
- Pin auf `idm-heatpump-api[web]==0.8.1`.

## v0.8.3 — 2026-07-16

### Changed

- **Pin auf `idm-heatpump-api[web]==0.8.0`:** Wirkt zwei Verbesserungen der
  Bibliothek automatisch aus (keine Code-Änderung an der Integration):
  - `detect_model` erkennt **nicht-kontinuierliche Heizkreise** (z. B. nur HK A
    und HK D installiert) zusätzlich über die Active-Mode-Register 1498–1504.
  - Der Navigator-10-Web-Client liefert **Vorlauf, Pumpe und Mischer der
    Heizkreise B–G** (vorher nur HK A und HK C).
  - Enthält den IPv4/IPv6-Web-Anmeldungsfix für den Navigator 2.0 aus API 0.7.7.

## v0.8.2 — 2026-07-12

### ⚠️ Wichtige Hinweise zum Update (Breaking Changes)

Das direkte Update von v0.8.1 auf v0.8.2 enthält keine zusätzlichen Breaking
Changes. Bei einem Update von v0.7.4 oder älter gelten weiterhin die
v0.8-Änderungen: lokaler Webzugriff mit PIN, die fest gepinnte API 0.7.6, neue
`climate`- und `water_heater`-Plattformen, die entfernte Entität
`ext_demand_brine_pump_m16`, fehlertolerantes Polling und IP-unabhängige Unique
IDs. Die vollständigen Hinweise stehen im [Changelog](../CHANGELOG.md).

### Korrekturen

- Benennt native Regler eindeutig als **Heizkreis A**, **Zone 1 Raum 1** und
  **Warmwasser**, statt den Gerätenamen für mehrere Entitäten anzuzeigen.
- Zeigt für Warmwasser den passenden Modus **Wärmepumpe** statt des
  irreführenden Status **Hochleistung**.
- Vervollständigt die kanonischen Entity-Texte und sichert das Naming mit Tests
  ab.

## v0.8.1-beta.29 — 2026-07-11

- Remembers the successful Navigator 2.0 or Navigator 10/Pro local web
  protocol and retries only that protocol during normal runtime recovery.
- Tries both supported web protocols during setup, reconfiguration and repair,
  and treats local network code `0` as disabled.
- Redacts web host, web PIN and detailed web connection strings from downloaded
  diagnostics.
- Adds GLT Monitor diagnosis, writable-control guidance, exact PV/battery
  datatypes and guarded examples for PV surplus and external DHW requests.
- Keeps `idm-heatpump-api[web]==0.7.6`; this release needs a new integration
  version, not a new API package.
- Consolidates verified constraints and remaining verification work in the
  project knowledge base and Wiki.

## v0.8.1-beta.28 — 2026-07-11

- Pins the published `idm-heatpump-api` 0.7.6 stability release.
- Propagates transport failures without disabling valid registers.
- Quarantines proven room-mode batch mismatches and avoids later double reads.
- Recognizes the verified cascade-unavailable sentinel.
- Restores explicitly acknowledged custom-register writes with numeric validation.

## Unreleased stability audit — 2026-07-10

- Transport/no-response failures no longer count as permanent failures of individual registers.
- Zone-room mode validation isolates unsupported/invalid values and avoids repeated double reads after quarantine.
- Navigator 10 cascade capability recognizes the hardware-confirmed `255` unavailable sentinel.
- Advanced raw writes retain numeric/datatype validation and require explicit risk acknowledgement.
- Added measurable [stable-release gates](Stability-and-Release-Readiness).

## v0.8.1-beta.27 — 2026-07-10

- Pinned the hardware-verified API 0.7.5.
- Added register-specific unavailable-sentinel handling.
- Compared 170 definitions across 45 groups in 309 read-only batch/individual checks without a raw mismatch.

---

## Historical summary

## v0.4.6 — 2026-05-31

- 169+ entities (109 sensors, 8 binary, 44 numbers, 4 selects, 4 switches)
- Full `idm-heatpump` library integration (Option B complete)
- Binary sensors for compressors, fault alarms, heating/cooling/DHW demand
- Solar, ISC, PV, cascade registers all included
- German entity names throughout
- Write-only register protection (`error_acknowledge`)

## v0.4.4 — 2026-05-31

- Full migration to `idm-heatpump` library as core
- Navigator 10 support: heat sink sensors, flow rate, groundwater temps
- Booster A/B diagnostics (16 new sensors)

## v0.4.0 — 2026-05-30

- Major architectural change
- Navigator 10 support added
- First large library-backed dynamic register map

## v0.2.0 — 2026-03-22

- Initial release
- Basic Modbus TCP integration
- System sensors, heating circuits, DHW control
