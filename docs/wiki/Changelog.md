# Changelog

The authoritative, complete history is maintained in
[`docs/CHANGELOG.md`](https://github.com/Xerolux/idm-heatpump-hass/blob/main/docs/CHANGELOG.md)
and the [GitHub releases](https://github.com/Xerolux/idm-heatpump-hass/releases).
This page only summarizes recent milestones.

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
