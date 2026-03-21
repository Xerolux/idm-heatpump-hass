# Changelog

All notable changes to this project will be documented in this file.
## [0.2.0] - 2026-03-21

## v0.2.0 - IDM Navigator Heatpump

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
- feat: add IDM Navigator Heatpump integration with full CI/CD, docs, and wiki (450815e)

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
2. Search for "IDM Navigator Heatpump"
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

