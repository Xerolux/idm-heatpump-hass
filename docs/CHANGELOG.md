# Changelog

> **Dieses Projekt macht dir das Leben mit deiner IDM Wärmepumpe leichter – und das komplett kostenlos!**
> Falls es dir gefällt und du die Entwicklung unterstützen möchtest, freue ich mich riesig über eine kleine Aufmerksamkeit. Kein Muss – aber mega motivierend! 😊☕

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-Spendier%20mir%20einen%20Kaffee!-yellow?logo=buy-me-a-coffee&style=for-the-badge)](https://www.buymeacoffee.com/xerolux)
[![PayPal](https://img.shields.io/badge/PayPal-Danke%20f%C3%BCr%20deine%20Unterst%C3%BCtzung!-blue?logo=paypal&style=for-the-badge)](https://paypal.me/xerolux)
[![Tesla Referral](https://img.shields.io/badge/Tesla-Referral%20Link%20nutzen-red?logo=tesla&style=for-the-badge)](https://ts.la/sebastian564489)

---

All notable changes to this project will be documented in this file.
## [0.2.2] - 2026-03-21

## v0.2.2 - IDM Heatpump

**STABLE RELEASE**

### New Features

- docs: add Tesla referral and fix PayPal link (7df7ef6)
- feat: add Fachmann Ebene sensors via config flow option (9fe226b)
- docs: add disclaimer - no affiliation with IDM Energiesysteme GmbH (a3da3b2)

### Improvements

- docs: update GitHub Pages and README for v0.2.2 (a684381)
- Update custom funding links in FUNDING.yml (a76e93f)
- Release v0.2.1 - Update changelog and version files (887a67b)

### Bug Fixes

- docs: add Tesla referral and fix PayPal link (7df7ef6)

---

### Installation

**HACS (Recommended):**
1. Add custom repository: `Xerolux/idm-heatpump-hass`
2. Search for "IDM Heatpump"
3. Click Install

**Manual:**
1. Download `idm_heatpump_v2.zip`
2. Extract to `custom_components/idm_heatpump_v2`
3. Restart Home Assistant

---

[Full changelog: v0.2.1...v0.2.2](https://github.com/Xerolux/idm-heatpump-hass/compare/v0.2.1...v0.2.2)

---

### Support

- [Buy Me a Coffee](https://buymeacoffee.com/xerolux)
- [Ko-Fi](https://ko-fi.com/xerolux)
- [GitHub Sponsors](https://github.com/sponsors/xerolux)
- Star this repository

Every contribution is a huge motivation! Thank you!

---

### Feedback & Contributions

- [Report a bug](https://github.com/Xerolux/idm-heatpump-hass/issues/new?template=bug_report.md)
- [Request a feature](https://github.com/Xerolux/idm-heatpump-hass/issues/new?template=feature_request.md)
- [Contribute](https://github.com/Xerolux/idm-heatpump-hass/blob/main/docs/CONTRIBUTING.md)

---

**Developed by:** [Xerolux](https://github.com/Xerolux)
**Integration for:** IDM Navigator 2.0 by IDM EnergieSysteme GmbH
**License:** MIT

_Generated automatically by GitHub Actions on 2026-03-21 19:01:43 UTC_

---


## [0.2.2] - 2026-03-21

### New Features

- feat: Fachmann-Ebene Codes as HA sensor entities (optional, enabled via config flow)
  - Two sensors: Ebene 1 (`TTMM`) and Ebene 2 (time-based 5-digit code)
  - Auto-refresh every 60 seconds via `async_track_time_interval`
  - Activate under **Settings → Devices & Services → IDM Heatpump → Options → Fachmann-Ebene Codes anzeigen**

---

[Full changelog: v0.2.1...v0.2.2](https://github.com/Xerolux/idm-heatpump-hass/compare/v0.2.1...v0.2.2)

---

## [0.2.1] - 2026-03-21

## v0.2.1 - IDM Heatpump

**STABLE RELEASE**

### New Features

- test: move tests to root, add full mock test suite (116 tests) (fb7088f)
- fix: HACS validation compliance - remove ignored checks, add daily schedule (acb9a02)
- rename-integration-add-brand-logo (a7e24ea)
- feat: Rename integration to "IDM Heatpump" and add brand logo (118b574)

### Improvements

- Update Home Assistant version to 2025.12.0 (7260658)
- Release v0.2.0 - Update changelog and version files (9e12fd2)

### Bug Fixes

- fix: resolve all CodeQL alerts (eb2be3b)
- fix: HACS validation compliance - remove ignored checks, add daily schedule (acb9a02)

---

### Installation

**HACS (Recommended):**
1. Add custom repository: `Xerolux/idm-heatpump-hass`
2. Search for "IDM Heatpump"
3. Click Install

**Manual:**
1. Download `idm_heatpump_v2.zip`
2. Extract to `custom_components/idm_heatpump_v2`
3. Restart Home Assistant

---

[Full changelog: v0.2.0...v0.2.1](https://github.com/Xerolux/idm-heatpump-hass/compare/v0.2.0...v0.2.1)

---

### Support

- [Buy Me a Coffee](https://buymeacoffee.com/xerolux)
- [Ko-Fi](https://ko-fi.com/xerolux)
- [GitHub Sponsors](https://github.com/sponsors/xerolux)
- Star this repository

Every contribution is a huge motivation! Thank you!

---

### Feedback & Contributions

- [Report a bug](https://github.com/Xerolux/idm-heatpump-hass/issues/new?template=bug_report.md)
- [Request a feature](https://github.com/Xerolux/idm-heatpump-hass/issues/new?template=feature_request.md)
- [Contribute](https://github.com/Xerolux/idm-heatpump-hass/blob/main/docs/CONTRIBUTING.md)

---

**Developed by:** [Xerolux](https://github.com/Xerolux)
**Integration for:** IDM Navigator 2.0 by IDM EnergieSysteme GmbH
**License:** MIT

_Generated automatically by GitHub Actions on 2026-03-21 18:27:56 UTC_

---

## [0.2.1] - 2026-03-21

### Fixes

- fix: HACS validation compliance - remove ignored checks, add daily schedule

## [0.2.0] - 2026-03-21

## v0.2.0 - IDM Heatpump

**STABLE RELEASE**

### New Features

- fix: correct device_class, add state_class, service improvements (771b62b)
- feat: improve config flow UI and translations (284f2e6)
- add-missing-registers (2fc9fd9)
- Add missing registers from hacs-idm-heatpump (fa9468e)
- fix-modbus-client-and-add-tests (e7c5ada)
- Fix Hassfest target validation and add brand assets for HACS (6810943)
- Fix encode_value endianness bug, optimize connect(), and add mock tests (8850754)
- feat: add hide_unused option, fix pymodbus compat, dynamic HK sensors (481a4c2)
- feat: add IDM Heatpump integration with full CI/CD, docs, and wiki (450815e)

### Improvements

- optimize-ha-2026-3 (3ad8101)
- optimize-ha-2026-3 (86c0151)
- feat: improve config flow UI and translations (284f2e6)
- refactor: HA 2026.3 compatibility + bug fixes (df3c2e9)
- Enhance config flow with reconfigure support and UI descriptions (5fbf633)
- Update Wiki documentation for Modbus changes and troubleshooting (52a3086)
- Fix encode_value endianness bug, optimize connect(), and add mock tests (8850754)

### Bug Fixes

- fix: lowercase heating circuit identifiers to satisfy HA HACS validator (fab872c)
- fix: write operations now trigger coordinator refresh + use coordinator API (7416ede)
- fix: correct device_class, add state_class, service improvements (771b62b)
- refactor: HA 2026.3 compatibility + bug fixes (df3c2e9)
- Fix hacs-validation `ignore` format (3a0d72f)
- Fix CI by adding `ignore` to hacs-validation.yml (7cf9eac)
- fix-hacs-validation (ea89c76)
- fix-modbus-client-and-add-tests (e7c5ada)
- Fix Modbus datatypes, sizes, and integer multipliers (6f1364e)
- Fix HACS validation ignore parameter string formatting (8f49a43)
- Fix Hassfest target validation and add brand assets for HACS (6810943)
- Fix encode_value endianness bug, optimize connect(), and add mock tests (8850754)
- feat: add hide_unused option, fix pymodbus compat, dynamic HK sensors (481a4c2)
- fix: pymodbus API, FLOAT endianness, scan interval default 10s (768ff40)

---

### Installation

**HACS (Recommended):**
1. Add custom repository: `Xerolux/idm-heatpump-hass`
2. Search for "IDM Heatpump"
3. Click Install

**Manual:**
1. Download `idm_heatpump_v2.zip`
2. Extract to `custom_components/idm_heatpump_v2`
3. Restart Home Assistant

---

Full changelog: Initial release

---

### Support

- [Buy Me a Coffee](https://buymeacoffee.com/xerolux)
- [Ko-Fi](https://ko-fi.com/xerolux)
- [GitHub Sponsors](https://github.com/sponsors/xerolux)
- Star this repository

Every contribution is a huge motivation! Thank you!

---

### Feedback & Contributions

- [Report a bug](https://github.com/Xerolux/idm-heatpump-hass/issues/new?template=bug_report.md)
- [Request a feature](https://github.com/Xerolux/idm-heatpump-hass/issues/new?template=feature_request.md)
- [Contribute](https://github.com/Xerolux/idm-heatpump-hass/blob/main/docs/CONTRIBUTING.md)

---

**Developed by:** [Xerolux](https://github.com/Xerolux)
**Integration for:** IDM Navigator 2.0 by IDM EnergieSysteme GmbH
**License:** MIT

_Generated automatically by GitHub Actions on 2026-03-21 12:18:05 UTC_

---

