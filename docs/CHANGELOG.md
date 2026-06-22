# Changelog

> **Dieses Projekt macht dir das Leben mit deiner IDM Wärmepumpe leichter – und das komplett kostenlos!**
> Falls es dir gefällt und du die Entwicklung unterstützen möchtest, freue ich mich riesig über eine kleine Aufmerksamkeit. Kein Muss – aber mega motivierend! 😊☕

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-Spendier%20mir%20einen%20Kaffee!-yellow?logo=buy-me-a-coffee&style=for-the-badge)](https://www.buymeacoffee.com/xerolux)
[![PayPal](https://img.shields.io/badge/PayPal-Danke%20f%C3%BCr%20deine%20Unterst%C3%BCtzung!-blue?logo=paypal&style=for-the-badge)](https://paypal.me/xerolux)
[Tesla Referral](https://ts.la/sebastian564489)

---

All notable changes to this project will be documented in this file.
## [0.7.1] - 2026-06-22

### Bug Fixes
- Fix duplicate zone registers in number entities via description key deduplication
- Replace silent `except:pass` with `_LOGGER.warning(exc_info=True)` in all register description loaders

### Improvements
- Wire up `enable_cascade` config option to library `IdmModelInfo` — previously ignored, now properly excludes 18 writable cascade configuration registers when disabled

---

## [0.7.0] - 2026-06-18

## v0.7.0 - IDM Heatpump

**STABLE RELEASE**

[![GitHub Sponsor](https://img.shields.io/github/sponsors/xerolux?logo=github&style=for-the-badge&color=blue)](https://github.com/sponsors/xerolux)
[![Ko-Fi](https://img.shields.io/badge/Ko--fi-xerolux-blue?logo=ko-fi&style=for-the-badge)](https://ko-fi.com/xerolux)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-xerolux-yellow?logo=buy-me-a-coffee&style=for-the-badge)](https://www.buymeacoffee.com/xerolux)
[![PayPal](https://img.shields.io/badge/PayPal-xerolux-blue?logo=paypal&style=for-the-badge)](https://paypal.me/xerolux)
[![Tesla Referral](https://img.shields.io/badge/Tesla-Referral-red?logo=tesla&style=for-the-badge)](https://ts.la/sebastian564489)

### New Features

- Enhanced IDM Heatpump functionality

### Improvements

- P1-P3: Optimistic-update fix, CI consistency, test coverage (982cf37)
- Update manifest.json (d082969)
- Release v0.6.7 - Update changelog and version files (60649bb)

### Bug Fixes

- Fix duplicate zone room description keys (12eefea)
- Fix: CI HA version to 2026.2.3 (2026.5.0 not available on PyPI yet) (9239d79)
- P1-P3: Optimistic-update fix, CI consistency, test coverage (982cf37)
- Fix duplicate zone room description keys in number platform (7908176)
- fix: expose zone room numbers and repair test stubs (96c0763)

---

### Installation

**HACS (Recommended):**
1. Add custom repository: `Xerolux/idm-heatpump-hass`
2. Search for "IDM Heatpump"
3. Click Install

**Manual:**
1. Download `idm_heatpump.zip`
2. Extract to `custom_components/idm_heatpump`
3. Restart Home Assistant

---

[Full changelog: v0.6.7...v0.7.0](https://github.com/Xerolux/idm-heatpump-hass/compare/v0.6.7...v0.7.0)

---

### Support

Diese Integration wird in meiner Freizeit entwickelt – deine Unterstützung erhöht die Motivation für weitere Features und Updates! 🚀

[![GitHub Sponsor](https://img.shields.io/github/sponsors/xerolux?logo=github&style=for-the-badge&color=blue)](https://github.com/sponsors/xerolux)
[![Ko-Fi](https://img.shields.io/badge/Ko--fi-xerolux-blue?logo=ko-fi&style=for-the-badge)](https://ko-fi.com/xerolux)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-xerolux-yellow?logo=buy-me-a-coffee&style=for-the-badge)](https://www.buymeacoffee.com/xerolux)
[![PayPal](https://img.shields.io/badge/PayPal-xerolux-blue?logo=paypal&style=for-the-badge)](https://paypal.me/xerolux)
[![Tesla Referral](https://img.shields.io/badge/Tesla-Referral-red?logo=tesla&style=for-the-badge)](https://ts.la/sebastian564489)

_Jede Unterstützung ist eine große Motivation! Vielen Dank!_

---

### Feedback & Contributions

- [Report a bug](https://github.com/Xerolux/idm-heatpump-hass/issues/new?template=bug_report.md)
- [Request a feature](https://github.com/Xerolux/idm-heatpump-hass/issues/new?template=feature_request.md)
- [Contribute](https://github.com/Xerolux/idm-heatpump-hass/blob/main/docs/CONTRIBUTING.md)

---

**Developed by:** [Xerolux](https://github.com/Xerolux)
**Integration for:** IDM Navigator 2.0 by IDM EnergieSysteme GmbH
**License:** MIT

_Generated automatically by GitHub Actions on 2026-06-18 11:55:32 UTC_

---

## [0.7.0] - 2026-06-18

## v0.7.0 - IDM Heatpump

**BETA RELEASE - Testing phase, may contain bugs**

[![GitHub Sponsor](https://img.shields.io/github/sponsors/xerolux?logo=github&style=for-the-badge&color=blue)](https://github.com/sponsors/xerolux)
[![Ko-Fi](https://img.shields.io/badge/Ko--fi-xerolux-blue?logo=ko-fi&style=for-the-badge)](https://ko-fi.com/xerolux)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-xerolux-yellow?logo=buy-me-a-coffee&style=for-the-badge)](https://www.buymeacoffee.com/xerolux)
[![PayPal](https://img.shields.io/badge/PayPal-xerolux-blue?logo=paypal&style=for-the-badge)](https://paypal.me/xerolux)
[![Tesla Referral](https://img.shields.io/badge/Tesla-Referral-red?logo=tesla&style=for-the-badge)](https://ts.la/sebastian564489)

### New Features

- Enhanced IDM Heatpump functionality

### Improvements

- P1-P3: Optimistic-update fix, CI consistency, test coverage (982cf37)
- Update manifest.json (d082969)
- Release v0.6.7 - Update changelog and version files (60649bb)

### Bug Fixes

- Fix duplicate zone room description keys (12eefea)
- Fix: CI HA version to 2026.2.3 (2026.5.0 not available on PyPI yet) (9239d79)
- P1-P3: Optimistic-update fix, CI consistency, test coverage (982cf37)
- Fix duplicate zone room description keys in number platform (7908176)
- fix: expose zone room numbers and repair test stubs (96c0763)

---

### Installation

**HACS (Recommended):**
1. Add custom repository: `Xerolux/idm-heatpump-hass`
2. Search for "IDM Heatpump"
3. Click Install

**Manual:**
1. Download `idm_heatpump.zip`
2. Extract to `custom_components/idm_heatpump`
3. Restart Home Assistant

---

[Full changelog: v0.6.7...v0.7.0](https://github.com/Xerolux/idm-heatpump-hass/compare/v0.6.7...v0.7.0)

---

### Support

Diese Integration wird in meiner Freizeit entwickelt – deine Unterstützung erhöht die Motivation für weitere Features und Updates! 🚀

[![GitHub Sponsor](https://img.shields.io/github/sponsors/xerolux?logo=github&style=for-the-badge&color=blue)](https://github.com/sponsors/xerolux)
[![Ko-Fi](https://img.shields.io/badge/Ko--fi-xerolux-blue?logo=ko-fi&style=for-the-badge)](https://ko-fi.com/xerolux)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-xerolux-yellow?logo=buy-me-a-coffee&style=for-the-badge)](https://www.buymeacoffee.com/xerolux)
[![PayPal](https://img.shields.io/badge/PayPal-xerolux-blue?logo=paypal&style=for-the-badge)](https://paypal.me/xerolux)
[![Tesla Referral](https://img.shields.io/badge/Tesla-Referral-red?logo=tesla&style=for-the-badge)](https://ts.la/sebastian564489)

_Jede Unterstützung ist eine große Motivation! Vielen Dank!_

---

### Feedback & Contributions

- [Report a bug](https://github.com/Xerolux/idm-heatpump-hass/issues/new?template=bug_report.md)
- [Request a feature](https://github.com/Xerolux/idm-heatpump-hass/issues/new?template=feature_request.md)
- [Contribute](https://github.com/Xerolux/idm-heatpump-hass/blob/main/docs/CONTRIBUTING.md)

---

**Developed by:** [Xerolux](https://github.com/Xerolux)
**Integration for:** IDM Navigator 2.0 by IDM EnergieSysteme GmbH
**License:** MIT

_Generated automatically by GitHub Actions on 2026-06-18 11:52:04 UTC_

---

## [0.6.7] - 2026-06-13

## v0.6.7 - IDM Heatpump

**STABLE RELEASE**

[![GitHub Sponsor](https://img.shields.io/github/sponsors/xerolux?logo=github&style=for-the-badge&color=blue)](https://github.com/sponsors/xerolux)
[![Ko-Fi](https://img.shields.io/badge/Ko--fi-xerolux-blue?logo=ko-fi&style=for-the-badge)](https://ko-fi.com/xerolux)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-xerolux-yellow?logo=buy-me-a-coffee&style=for-the-badge)](https://www.buymeacoffee.com/xerolux)
[![PayPal](https://img.shields.io/badge/PayPal-xerolux-blue?logo=paypal&style=for-the-badge)](https://paypal.me/xerolux)
[![Tesla Referral](https://img.shields.io/badge/Tesla-Referral-red?logo=tesla&style=for-the-badge)](https://ts.la/sebastian564489)

### New Features

- feat: update to idm-heatpump-api 0.3.2 with dual-exposed GLT measurement registers (04a9b41)

### Improvements

- feat: update to idm-heatpump-api 0.3.2 with dual-exposed GLT measurement registers (04a9b41)
- Release v0.6.4 - Update changelog and version files (b5bc60b)

### Bug Fixes

- Merge pull request #38 from Xerolux/hotfix/duplicate-partial-import (c67ac20)
- fix: remove duplicate functools.partial import in services.py (8ccb568)
- Merge pull request #33 from ascha191/fix-service-handler-signatures (8c456e8)
- fix: bind hass via partial so service handlers receive ServiceCall correctly (517becc)
- fix: remove unused DataType import in library_adapter, bump version to 0.6.6 (56a536b)
- fix(#31): use slug keys for enum entity states with HA translation support (303f2c7)
- fix: simplify pump sentinel check and quote pip version specs in CI (5c2f482)
- fix: service handlers never received the ServiceCall (wrong registration signature) (6a4453f)
- Fix (a499027)
- fix: guard against missing coordinator data and connection leak in config flow (75ba7e1)
- chore: fix all ruff lint errors and remove committed log files (d6825cb)

---

### Installation

**HACS (Recommended):**
1. Add custom repository: `Xerolux/idm-heatpump-hass`
2. Search for "IDM Heatpump"
3. Click Install

**Manual:**
1. Download `idm_heatpump.zip`
2. Extract to `custom_components/idm_heatpump`
3. Restart Home Assistant

---

[Full changelog: v0.6.4...v0.6.7](https://github.com/Xerolux/idm-heatpump-hass/compare/v0.6.4...v0.6.7)

---

### Support

Diese Integration wird in meiner Freizeit entwickelt – deine Unterstützung erhöht die Motivation für weitere Features und Updates! 🚀

[![GitHub Sponsor](https://img.shields.io/github/sponsors/xerolux?logo=github&style=for-the-badge&color=blue)](https://github.com/sponsors/xerolux)
[![Ko-Fi](https://img.shields.io/badge/Ko--fi-xerolux-blue?logo=ko-fi&style=for-the-badge)](https://ko-fi.com/xerolux)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-xerolux-yellow?logo=buy-me-a-coffee&style=for-the-badge)](https://www.buymeacoffee.com/xerolux)
[![PayPal](https://img.shields.io/badge/PayPal-xerolux-blue?logo=paypal&style=for-the-badge)](https://paypal.me/xerolux)
[![Tesla Referral](https://img.shields.io/badge/Tesla-Referral-red?logo=tesla&style=for-the-badge)](https://ts.la/sebastian564489)

_Jede Unterstützung ist eine große Motivation! Vielen Dank!_

---

### Feedback & Contributions

- [Report a bug](https://github.com/Xerolux/idm-heatpump-hass/issues/new?template=bug_report.md)
- [Request a feature](https://github.com/Xerolux/idm-heatpump-hass/issues/new?template=feature_request.md)
- [Contribute](https://github.com/Xerolux/idm-heatpump-hass/blob/main/docs/CONTRIBUTING.md)

---

**Developed by:** [Xerolux](https://github.com/Xerolux)
**Integration for:** IDM Navigator 2.0 by IDM EnergieSysteme GmbH
**License:** MIT

_Generated automatically by GitHub Actions on 2026-06-13 23:06:16 UTC_

---

## [0.6.7] - 2026-06-13

### Fixed

- Service-Handler (`set_system_mode`, `acknowledge_errors`, `write_register`) funktionierten nie: Handler waren mit `(hass, call)` signiert, wurden aber ohne `hass` aufgerufen. Fix via `functools.partial` beim Registrieren. (Gemeldet & Patch von @ascha191, #33)

### Changed

- Abhängigkeit auf `idm-heatpump-api >= 0.3.2` (PV-Überschuss-Register 74/76/78/82/84/86 jetzt korrekt als beschreibbar markiert, passend zur iDM-Doku 812170 Rev. 10 Kap. 4.3.9)

## [0.6.5] - 2026-06-12

### Changed

- Update auf `idm-heatpump-api >= 0.3.2` (Registerstand laut aktueller iDM Navigator Doku)
- GLT-Messwert-Register (PV-Überschuss, PV-Produktion, Hausverbrauch, Batterie-Entladung, Batterie-SOC, E-Heizstab-Leistung sowie Zonenraum-Temperatur und -Feuchte) sind jetzt beschreibbar und werden doppelt angelegt: als Sensor (Anzeige/Historie, bestehende Entity-IDs bleiben erhalten) und als Number „… (Vorgabe)" für die externe GLT-Eingabe
- Neue Register: `pv_target_value` (PV Zielwert, 88), `variable_input` (Variabler Eingang, 1006), `ext_demand_groundwater_pump_m15_sw_max` (1715)
- Entfernt: `ext_demand_brine_pump_m16` (in aktueller Doku nicht mehr vorhanden)

### Fixed

- Pumpen-Statusregister (M73, M15, Sole-/Zwischenkreis, ISC, Booster): −1 bedeutet laut Doku „Aus" und wird nicht mehr fälschlich als „unbenutzt" (Entity unavailable) interpretiert
- `battery_soc` −1 („nicht verfügbar") wird weiterhin korrekt als unbenutzt erkannt

## [0.6.4] - 2026-06-02

## v0.6.4 - IDM Heatpump

**STABLE RELEASE**

[![GitHub Sponsor](https://img.shields.io/github/sponsors/xerolux?logo=github&style=for-the-badge&color=blue)](https://github.com/sponsors/xerolux)
[![Ko-Fi](https://img.shields.io/badge/Ko--fi-xerolux-blue?logo=ko-fi&style=for-the-badge)](https://ko-fi.com/xerolux)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-xerolux-yellow?logo=buy-me-a-coffee&style=for-the-badge)](https://www.buymeacoffee.com/xerolux)
[![PayPal](https://img.shields.io/badge/PayPal-xerolux-blue?logo=paypal&style=for-the-badge)](https://paypal.me/xerolux)
[![Tesla Referral](https://img.shields.io/badge/Tesla-Referral-red?logo=tesla&style=for-the-badge)](https://ts.la/sebastian564489)

### New Features

- Enhanced IDM Heatpump functionality

### Improvements

- Release v0.6.3 - Update changelog and version files (502b555)

### Bug Fixes

- fix: unify unused sensor detection with additional sentinel values (-32768, NaN, inf) (299021e)

---

### Installation

**HACS (Recommended):**
1. Add custom repository: `Xerolux/idm-heatpump-hass`
2. Search for "IDM Heatpump"
3. Click Install

**Manual:**
1. Download `idm_heatpump.zip`
2. Extract to `custom_components/idm_heatpump`
3. Restart Home Assistant

---

[Full changelog: v0.6.3...v0.6.4](https://github.com/Xerolux/idm-heatpump-hass/compare/v0.6.3...v0.6.4)

---

### Support

Diese Integration wird in meiner Freizeit entwickelt – deine Unterstützung erhöht die Motivation für weitere Features und Updates! 🚀

[![GitHub Sponsor](https://img.shields.io/github/sponsors/xerolux?logo=github&style=for-the-badge&color=blue)](https://github.com/sponsors/xerolux)
[![Ko-Fi](https://img.shields.io/badge/Ko--fi-xerolux-blue?logo=ko-fi&style=for-the-badge)](https://ko-fi.com/xerolux)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-xerolux-yellow?logo=buy-me-a-coffee&style=for-the-badge)](https://www.buymeacoffee.com/xerolux)
[![PayPal](https://img.shields.io/badge/PayPal-xerolux-blue?logo=paypal&style=for-the-badge)](https://paypal.me/xerolux)
[![Tesla Referral](https://img.shields.io/badge/Tesla-Referral-red?logo=tesla&style=for-the-badge)](https://ts.la/sebastian564489)

_Jede Unterstützung ist eine große Motivation! Vielen Dank!_

---

### Feedback & Contributions

- [Report a bug](https://github.com/Xerolux/idm-heatpump-hass/issues/new?template=bug_report.md)
- [Request a feature](https://github.com/Xerolux/idm-heatpump-hass/issues/new?template=feature_request.md)
- [Contribute](https://github.com/Xerolux/idm-heatpump-hass/blob/main/docs/CONTRIBUTING.md)

---

**Developed by:** [Xerolux](https://github.com/Xerolux)
**Integration for:** IDM Navigator 2.0 by IDM EnergieSysteme GmbH
**License:** MIT

_Generated automatically by GitHub Actions on 2026-06-02 10:26:05 UTC_

---

## [0.6.3] - 2026-06-02

## v0.6.3 - IDM Heatpump

**STABLE RELEASE**

[![GitHub Sponsor](https://img.shields.io/github/sponsors/xerolux?logo=github&style=for-the-badge&color=blue)](https://github.com/sponsors/xerolux)
[![Ko-Fi](https://img.shields.io/badge/Ko--fi-xerolux-blue?logo=ko-fi&style=for-the-badge)](https://ko-fi.com/xerolux)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-xerolux-yellow?logo=buy-me-a-coffee&style=for-the-badge)](https://www.buymeacoffee.com/xerolux)
[![PayPal](https://img.shields.io/badge/PayPal-xerolux-blue?logo=paypal&style=for-the-badge)](https://paypal.me/xerolux)
[![Tesla Referral](https://img.shields.io/badge/Tesla-Referral-red?logo=tesla&style=for-the-badge)](https://ts.la/sebastian564489)

### New Features

- style: apply ruff formatting, add ruff.toml with line-length=120 (fa88ccc)
- fix: add VOLUME_FLOW_RATE mapping for L/min (heat_sink_flow_rate) (855de22)

### Improvements

- chore: bump version to 0.6.3, update idm-heatpump-api to 0.3.1 (49e5f8c)
- Release v0.6.2 - Update changelog and version files (2598d20)

### Bug Fixes

- fix: remove UnitOfVolumeFlowRate import not available in HA 2026.2.0 (4077fea)
- fix: remove dead %rF fallback in get_icon_for_register (1ba4786)
- fix: add VOLUME_FLOW_RATE mapping for L/min (heat_sink_flow_rate) (855de22)
- fix: comprehensive state_class/device_class fix for all entity generators (a581bce)
- fix: restore state_class and device_class for energy and power sensors (30d2e99)

---

### Installation

**HACS (Recommended):**
1. Add custom repository: `Xerolux/idm-heatpump-hass`
2. Search for "IDM Heatpump"
3. Click Install

**Manual:**
1. Download `idm_heatpump.zip`
2. Extract to `custom_components/idm_heatpump`
3. Restart Home Assistant

---

[Full changelog: v0.6.2...v0.6.3](https://github.com/Xerolux/idm-heatpump-hass/compare/v0.6.2...v0.6.3)

---

### Support

Diese Integration wird in meiner Freizeit entwickelt – deine Unterstützung erhöht die Motivation für weitere Features und Updates! 🚀

[![GitHub Sponsor](https://img.shields.io/github/sponsors/xerolux?logo=github&style=for-the-badge&color=blue)](https://github.com/sponsors/xerolux)
[![Ko-Fi](https://img.shields.io/badge/Ko--fi-xerolux-blue?logo=ko-fi&style=for-the-badge)](https://ko-fi.com/xerolux)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-xerolux-yellow?logo=buy-me-a-coffee&style=for-the-badge)](https://www.buymeacoffee.com/xerolux)
[![PayPal](https://img.shields.io/badge/PayPal-xerolux-blue?logo=paypal&style=for-the-badge)](https://paypal.me/xerolux)
[![Tesla Referral](https://img.shields.io/badge/Tesla-Referral-red?logo=tesla&style=for-the-badge)](https://ts.la/sebastian564489)

_Jede Unterstützung ist eine große Motivation! Vielen Dank!_

---

### Feedback & Contributions

- [Report a bug](https://github.com/Xerolux/idm-heatpump-hass/issues/new?template=bug_report.md)
- [Request a feature](https://github.com/Xerolux/idm-heatpump-hass/issues/new?template=feature_request.md)
- [Contribute](https://github.com/Xerolux/idm-heatpump-hass/blob/main/docs/CONTRIBUTING.md)

---

**Developed by:** [Xerolux](https://github.com/Xerolux)
**Integration for:** IDM Navigator 2.0 by IDM EnergieSysteme GmbH
**License:** MIT

_Generated automatically by GitHub Actions on 2026-06-02 10:03:07 UTC_

---

## [0.6.2] - 2026-06-01

## v0.6.2 - IDM Heatpump

**STABLE RELEASE**

[![GitHub Sponsor](https://img.shields.io/github/sponsors/xerolux?logo=github&style=for-the-badge&color=blue)](https://github.com/sponsors/xerolux)
[![Ko-Fi](https://img.shields.io/badge/Ko--fi-xerolux-blue?logo=ko-fi&style=for-the-badge)](https://ko-fi.com/xerolux)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-xerolux-yellow?logo=buy-me-a-coffee&style=for-the-badge)](https://www.buymeacoffee.com/xerolux)
[![PayPal](https://img.shields.io/badge/PayPal-xerolux-blue?logo=paypal&style=for-the-badge)](https://paypal.me/xerolux)
[![Tesla Referral](https://img.shields.io/badge/Tesla-Referral-red?logo=tesla&style=for-the-badge)](https://ts.la/sebastian564489)

### New Features

- feat: revert domain from heatpump_idm back to idm_heatpump (v0.6.2) (cda3815)

### Improvements

- Release v0.6.1 - Update changelog and version files (df2a697)

### Bug Fixes

- fix: restore type: ignore comments for HA 2026.2.0 strict types, disable unused-ignore (2450d07)
- fix: resolve mypy attr-defined errors, remove unused type: ignore comments (4f66dee)
- brands-loading-check & fix error (2d06719)
- fix: use absolute URLs for images in README to fix HACS display (fccad00)
- fix: resize brand images to correct dimensions for hassfest validation (0be2283)

---

### Installation

**HACS (Recommended):**
1. Add custom repository: `Xerolux/idm-heatpump-hass`
2. Search for "IDM Heatpump"
3. Click Install

**Manual:**
1. Download `idm_heatpump.zip`
2. Extract to `custom_components/idm_heatpump`
3. Restart Home Assistant

---

[Full changelog: v0.6.1...v0.6.2](https://github.com/Xerolux/idm-heatpump-hass/compare/v0.6.1...v0.6.2)

---

### Support

Diese Integration wird in meiner Freizeit entwickelt – deine Unterstützung erhöht die Motivation für weitere Features und Updates! 🚀

[![GitHub Sponsor](https://img.shields.io/github/sponsors/xerolux?logo=github&style=for-the-badge&color=blue)](https://github.com/sponsors/xerolux)
[![Ko-Fi](https://img.shields.io/badge/Ko--fi-xerolux-blue?logo=ko-fi&style=for-the-badge)](https://ko-fi.com/xerolux)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-xerolux-yellow?logo=buy-me-a-coffee&style=for-the-badge)](https://www.buymeacoffee.com/xerolux)
[![PayPal](https://img.shields.io/badge/PayPal-xerolux-blue?logo=paypal&style=for-the-badge)](https://paypal.me/xerolux)
[![Tesla Referral](https://img.shields.io/badge/Tesla-Referral-red?logo=tesla&style=for-the-badge)](https://ts.la/sebastian564489)

_Jede Unterstützung ist eine große Motivation! Vielen Dank!_

---

### Feedback & Contributions

- [Report a bug](https://github.com/Xerolux/idm-heatpump-hass/issues/new?template=bug_report.md)
- [Request a feature](https://github.com/Xerolux/idm-heatpump-hass/issues/new?template=feature_request.md)
- [Contribute](https://github.com/Xerolux/idm-heatpump-hass/blob/main/docs/CONTRIBUTING.md)

---

**Developed by:** [Xerolux](https://github.com/Xerolux)
**Integration for:** IDM Navigator 2.0 by IDM EnergieSysteme GmbH
**License:** MIT

_Generated automatically by GitHub Actions on 2026-06-01 09:47:54 UTC_

---


## [0.6.2] - 2026-06-01

## v0.6.2 - Domain Revert: idm_heatpump

**STABLE RELEASE**

> ### ℹ️ Wichtige Änderung für v0.6.x-Nutzer
>
> **Die Integration-Domain wurde von `heatpump_idm` zurück auf `idm_heatpump` geändert.**
>
> Der Domain-Rename in v0.6.0 war unnötig — Python trennt `custom_components.idm_heatpump` (HA-Integration) und `idm_heatpump` (PyPI-Library) sauber voneinander. Es gab keinen echten Namenskonflikt.
>
> **Wenn du von v0.5.x aktualisierst:** Normales Update, keine manuelle Aktion erforderlich.
>
> **Wenn du bereits v0.6.x nutzt:** Integration einmal entfernen und neu hinzufügen (Einstellungen → Geräte & Dienste).

### Changes

- **Domain-Revert:** `heatpump_idm` → `idm_heatpump` (kein echter Namenskonflikt mit PyPI-Library vorhanden)
- **Brand-Images korrigiert:** `icon.png` 256×256, `logo.png` 512×512 (hassfest-Anforderung)

---

### Installation

**HACS (Recommended):**
1. Add custom repository: `Xerolux/idm-heatpump-hass`
2. Search for "IDM Heatpump"
3. Click Install

**Manual:**
1. Download `idm_heatpump.zip`
2. Extract to `custom_components/idm_heatpump`
3. Restart Home Assistant

---

[Full changelog: v0.6.1...v0.6.2](https://github.com/Xerolux/idm-heatpump-hass/compare/v0.6.1...v0.6.2)

---

## [0.6.1] - 2026-05-31

## v0.6.1 - IDM Heatpump

**STABLE RELEASE**

[![GitHub Sponsor](https://img.shields.io/github/sponsors/xerolux?logo=github&style=for-the-badge&color=blue)](https://github.com/sponsors/xerolux)
[![Ko-Fi](https://img.shields.io/badge/Ko--fi-xerolux-blue?logo=ko-fi&style=for-the-badge)](https://ko-fi.com/xerolux)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-xerolux-yellow?logo=buy-me-a-coffee&style=for-the-badge)](https://www.buymeacoffee.com/xerolux)
[![PayPal](https://img.shields.io/badge/PayPal-xerolux-blue?logo=paypal&style=for-the-badge)](https://paypal.me/xerolux)
[![Tesla Referral](https://img.shields.io/badge/Tesla-Referral-red?logo=tesla&style=for-the-badge)](https://ts.la/sebastian564489)

### New Features

- Enhanced IDM Heatpump functionality

### Improvements

- v0.6.1: CI fixes, mypy type safety, changelog update (240609f)
- Release v0.6.0 - Update changelog and version files (f116949)

### Bug Fixes

- fix: remove unused misc from type: ignore (80efca8)
- fix: mypy type: ignore comment for ConfigFlowResult fallback (8583c17)
- fix: resolve mypy strict type errors for CI (3bed518)
- style: fix Ruff formatting in library_adapter.py (0d90015)

---

### Installation

**HACS (Recommended):**
1. Add custom repository: `Xerolux/idm-heatpump-hass`
2. Search for "IDM Heatpump"
3. Click Install

**Manual:**
1. Download `idm_heatpump.zip`
2. Extract to `custom_components/idm_heatpump`
3. Restart Home Assistant

---

[Full changelog: v0.6.0...v0.6.1](https://github.com/Xerolux/idm-heatpump-hass/compare/v0.6.0...v0.6.1)

---

### Support

Diese Integration wird in meiner Freizeit entwickelt – deine Unterstützung erhöht die Motivation für weitere Features und Updates! 🚀

[![GitHub Sponsor](https://img.shields.io/github/sponsors/xerolux?logo=github&style=for-the-badge&color=blue)](https://github.com/sponsors/xerolux)
[![Ko-Fi](https://img.shields.io/badge/Ko--fi-xerolux-blue?logo=ko-fi&style=for-the-badge)](https://ko-fi.com/xerolux)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-xerolux-yellow?logo=buy-me-a-coffee&style=for-the-badge)](https://www.buymeacoffee.com/xerolux)
[![PayPal](https://img.shields.io/badge/PayPal-xerolux-blue?logo=paypal&style=for-the-badge)](https://paypal.me/xerolux)
[![Tesla Referral](https://img.shields.io/badge/Tesla-Referral-red?logo=tesla&style=for-the-badge)](https://ts.la/sebastian564489)

_Jede Unterstützung ist eine große Motivation! Vielen Dank!_

---

### Feedback & Contributions

- [Report a bug](https://github.com/Xerolux/idm-heatpump-hass/issues/new?template=bug_report.md)
- [Request a feature](https://github.com/Xerolux/idm-heatpump-hass/issues/new?template=feature_request.md)
- [Contribute](https://github.com/Xerolux/idm-heatpump-hass/blob/main/docs/CONTRIBUTING.md)

---

**Developed by:** [Xerolux](https://github.com/Xerolux)
**Integration for:** IDM Navigator 2.0 by IDM EnergieSysteme GmbH
**License:** MIT

_Generated automatically by GitHub Actions on 2026-05-31 22:06:08 UTC_

---


---

## v0.6.1 - CI Fixes & Type Safety

### Bug Fixes

- Fix CI: install `idm-heatpump-api` in GitHub Actions for tests and mypy
- Fix mypy strict type errors across 6 files (library_adapter, config_flow, registers, services, entity, sensor)
- Fix Ruff formatting in library_adapter.py
- Add proper type annotations to all library_adapter.py functions
- Use `ConfigFlowResult` in config_flow.py (with backward-compatible fallback)

---

## [0.6.0] - 2026-05-31

## v0.6.0 - IDM Heatpump

**STABLE RELEASE**

[![GitHub Sponsor](https://img.shields.io/github/sponsors/xerolux?logo=github&style=for-the-badge&color=blue)](https://github.com/sponsors/xerolux)
[![Ko-Fi](https://img.shields.io/badge/Ko--fi-xerolux-blue?logo=ko-fi&style=for-the-badge)](https://ko-fi.com/xerolux)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-xerolux-yellow?logo=buy-me-a-coffee&style=for-the-badge)](https://www.buymeacoffee.com/xerolux)
[![PayPal](https://img.shields.io/badge/PayPal-xerolux-blue?logo=paypal&style=for-the-badge)](https://paypal.me/xerolux)
[![Tesla Referral](https://img.shields.io/badge/Tesla-Referral-red?logo=tesla&style=for-the-badge)](https://ts.la/sebastian564489)

### New Features

- Enhanced IDM Heatpump functionality

### Improvements

- Release v0.5.0 - Update changelog and version files (f3bf45c)

### Bug Fixes

- Minor bug fixes and stability improvements

---

### Installation

**HACS (Recommended):**
1. Add custom repository: `Xerolux/idm-heatpump-hass`
2. Search for "IDM Heatpump"
3. Click Install

**Manual:**
1. Download `idm_heatpump.zip`
2. Extract to `custom_components/idm_heatpump`
3. Restart Home Assistant

---

[Full changelog: v0.5.0...v0.6.0](https://github.com/Xerolux/idm-heatpump-hass/compare/v0.5.0...v0.6.0)

---

### Support

Diese Integration wird in meiner Freizeit entwickelt – deine Unterstützung erhöht die Motivation für weitere Features und Updates! 🚀

[![GitHub Sponsor](https://img.shields.io/github/sponsors/xerolux?logo=github&style=for-the-badge&color=blue)](https://github.com/sponsors/xerolux)
[![Ko-Fi](https://img.shields.io/badge/Ko--fi-xerolux-blue?logo=ko-fi&style=for-the-badge)](https://ko-fi.com/xerolux)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-xerolux-yellow?logo=buy-me-a-coffee&style=for-the-badge)](https://www.buymeacoffee.com/xerolux)
[![PayPal](https://img.shields.io/badge/PayPal-xerolux-blue?logo=paypal&style=for-the-badge)](https://paypal.me/xerolux)
[![Tesla Referral](https://img.shields.io/badge/Tesla-Referral-red?logo=tesla&style=for-the-badge)](https://ts.la/sebastian564489)

_Jede Unterstützung ist eine große Motivation! Vielen Dank!_

---

### Feedback & Contributions

- [Report a bug](https://github.com/Xerolux/idm-heatpump-hass/issues/new?template=bug_report.md)
- [Request a feature](https://github.com/Xerolux/idm-heatpump-hass/issues/new?template=feature_request.md)
- [Contribute](https://github.com/Xerolux/idm-heatpump-hass/blob/main/docs/CONTRIBUTING.md)

---

**Developed by:** [Xerolux](https://github.com/Xerolux)
**Integration for:** IDM Navigator 2.0 by IDM EnergieSysteme GmbH
**License:** MIT

_Generated automatically by GitHub Actions on 2026-05-31 21:04:55 UTC_

---


---

## v0.6.0 - Domain Rename & Library Integration

---

> ~~### ⚠️ BREAKING CHANGE~~
>
> ~~**Die Integration-Domain wurde von `idm_heatpump` auf `heatpump_idm` geändert.**~~
>
> **Hinweis:** Dieser Domain-Rename wurde in v0.6.2 rückgängig gemacht. Die Domain lautet wieder `idm_heatpump`.
>
> ---

### Changes

- ~~**Domain-Rename:** `idm_heatpump` → `heatpump_idm`~~ (in v0.6.2 wieder rückgängig gemacht)
- **modbus_client.py entfernt:** Direkte Imports aus der PyPI-Library `idm-heatpump-api` statt lokalem Wrapper
- **PyPI-Library als Requirement:** `idm-heatpump-api>=0.3.0` wird automatisch von HA installiert
- **Duplikat `power_limit_hp` behoben:** War fälschlicherweise als Sensor UND Number registriert
- **Test-Datei umbenannt:** `test_modbus_client.py` → `test_library_client.py`
- **Dokumentation aktualisiert:** Alle Logger-Pfade auf `custom_components.idm_heatpump`
- **328 Tests bestanden**, Docker Live-Test gegen echte Wärmepumpe erfolgreich (168 Entities, 106 Register gelesen)

---

## [0.5.0] - 2026-05-31

## v0.5.0 - IDM Heatpump

**STABLE RELEASE**

[![GitHub Sponsor](https://img.shields.io/github/sponsors/xerolux?logo=github&style=for-the-badge&color=blue)](https://github.com/sponsors/xerolux)
[![Ko-Fi](https://img.shields.io/badge/Ko--fi-xerolux-blue?logo=ko-fi&style=for-the-badge)](https://ko-fi.com/xerolux)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-xerolux-yellow?logo=buy-me-a-coffee&style=for-the-badge)](https://www.buymeacoffee.com/xerolux)
[![PayPal](https://img.shields.io/badge/PayPal-xerolux-blue?logo=paypal&style=for-the-badge)](https://paypal.me/xerolux)
[![Tesla Referral](https://img.shields.io/badge/Tesla-Referral-red?logo=tesla&style=for-the-badge)](https://ts.la/sebastian564489)

### New Features

- Add 18 missing German names (cascade detail, solar, booster) (d81eeee)
- Add 53 German entity names, fix sensor name fallback to use German names, create API_ISSUES.md with library gaps (d253029)

### Improvements

- Update translations, README, wiki, GitHub Pages; remove duplicate workflow; sync entity counts to 169+ (ce19311)
- Release v0.4.4 - Update changelog and version files (7f72d6d)

### Bug Fixes

- Add 53 German entity names, fix sensor name fallback to use German names, create API_ISSUES.md with library gaps (d253029)
- v0.4.5: Fix error_acknowledge polling, implement selects/switches/numbers, resolve merge conflicts (c5c9a6d)

---

### Installation

**HACS (Recommended):**
1. Add custom repository: `Xerolux/idm-heatpump-hass`
2. Search for "IDM Heatpump"
3. Click Install

**Manual:**
1. Download `idm_heatpump.zip`
2. Extract to `custom_components/idm_heatpump`
3. Restart Home Assistant

---

[Full changelog: v0.4.4...v0.5.0](https://github.com/Xerolux/idm-heatpump-hass/compare/v0.4.4...v0.5.0)

---

### Support

Diese Integration wird in meiner Freizeit entwickelt – deine Unterstützung erhöht die Motivation für weitere Features und Updates! 🚀

[![GitHub Sponsor](https://img.shields.io/github/sponsors/xerolux?logo=github&style=for-the-badge&color=blue)](https://github.com/sponsors/xerolux)
[![Ko-Fi](https://img.shields.io/badge/Ko--fi-xerolux-blue?logo=ko-fi&style=for-the-badge)](https://ko-fi.com/xerolux)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-xerolux-yellow?logo=buy-me-a-coffee&style=for-the-badge)](https://www.buymeacoffee.com/xerolux)
[![PayPal](https://img.shields.io/badge/PayPal-xerolux-blue?logo=paypal&style=for-the-badge)](https://paypal.me/xerolux)
[![Tesla Referral](https://img.shields.io/badge/Tesla-Referral-red?logo=tesla&style=for-the-badge)](https://ts.la/sebastian564489)

_Jede Unterstützung ist eine große Motivation! Vielen Dank!_

---

### Feedback & Contributions

- [Report a bug](https://github.com/Xerolux/idm-heatpump-hass/issues/new?template=bug_report.md)
- [Request a feature](https://github.com/Xerolux/idm-heatpump-hass/issues/new?template=feature_request.md)
- [Contribute](https://github.com/Xerolux/idm-heatpump-hass/blob/main/docs/CONTRIBUTING.md)

---

**Developed by:** [Xerolux](https://github.com/Xerolux)
**Integration for:** IDM Navigator 2.0 by IDM EnergieSysteme GmbH
**License:** MIT

_Generated automatically by GitHub Actions on 2026-05-31 19:32:55 UTC_

---


## [0.4.5] - 2026-05-31

### Improvements
- Implemented `get_library_selects()`, `get_library_switches()`, `get_library_numbers()` from library registers
- Numbers now auto-generate from all writable library registers (was only 2 hardcoded before)
- Selects auto-generate from library registers with enum_options (system_mode, hc_X_mode)
- Switches auto-generate from library BOOL writable registers (demand_heating/cooling/dhw/onetime_dhw)
- Rewrote test_registers.py to use correct library naming (hc_ prefix, zm prefix for zones)
- Extended `is_register_unused()` to treat 65535 and 255 as unused sentinel values

### Bug Fixes
- Exclude write-only command registers (error_acknowledge) from polling - fixes "permanently failed" error
- Zone index fix: pass 1-based index to library's `get_zone_module_registers()`

## [0.4.4] - 2026-05-31

## v0.4.4 - IDM Heatpump

**STABLE RELEASE**

[![GitHub Sponsor](https://img.shields.io/github/sponsors/xerolux?logo=github&style=for-the-badge&color=blue)](https://github.com/sponsors/xerolux)
[![Ko-Fi](https://img.shields.io/badge/Ko--fi-xerolux-blue?logo=ko-fi&style=for-the-badge)](https://ko-fi.com/xerolux)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-xerolux-yellow?logo=buy-me-a-coffee&style=for-the-badge)](https://www.buymeacoffee.com/xerolux)
[![PayPal](https://img.shields.io/badge/PayPal-xerolux-blue?logo=paypal&style=for-the-badge)](https://paypal.me/xerolux)
[Tesla Referral](https://img.shields.io/badge/Tesla-Referral-red?logo=tesla&style=for-the-badge)](https://ts.la/sebastian564489)

### Improvements

- Major cleanup of legacy register code (removal of ~900 lines of old local definitions)
- Full migration to `idm_heatpump` library as core (100% Option B)
- Significantly expanded German register names and improved icon handling in the adapter
- All public entity description functions now delegate to the library adapter
- Ruff formatting fixes and lint cleanup

## [0.4.3] - 2026-05-31

## v0.4.3 - IDM Heatpump

**BETA RELEASE - Testing phase, may contain bugs**

[![GitHub Sponsor](https://img.shields.io/github/sponsors/xerolux?logo=github&style=for-the-badge&color=blue)](https://github.com/sponsors/xerolux)
[![Ko-Fi](https://img.shields.io/badge/Ko--fi-xerolux-blue?logo=ko-fi&style=for-the-badge)](https://ko-fi.com/xerolux)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-xerolux-yellow?logo=buy-me-a-coffee&style=for-the-badge)](https://www.buymeacoffee.com/xerolux)
[![PayPal](https://img.shields.io/badge/PayPal-xerolux-blue?logo=paypal&style=for-the-badge)](https://paypal.me/xerolux)
[![Tesla Referral](https://img.shields.io/badge/Tesla-Referral-red?logo=tesla&style=for-the-badge)](https://ts.la/sebastian564489)

### New Features

- Enhanced IDM Heatpump functionality

### Improvements

- Release v0.4.2 - Update changelog and version files (a5d92ba)

### Bug Fixes

- Implement selects, switches, numbers from library; fix 65535/255 unused detection; rewrite register tests (2f4e571)

---

### Installation

**HACS (Recommended):**
1. Add custom repository: `Xerolux/idm-heatpump-hass`
2. Search for "IDM Heatpump"
3. Click Install

**Manual:**
1. Download `idm_heatpump.zip`
2. Extract to `custom_components/idm_heatpump`
3. Restart Home Assistant

---

[Full changelog: v0.4.2...v0.4.3](https://github.com/Xerolux/idm-heatpump-hass/compare/v0.4.2...v0.4.3)

---

### Support

Diese Integration wird in meiner Freizeit entwickelt – deine Unterstützung erhöht die Motivation für weitere Features und Updates! 🚀

[![GitHub Sponsor](https://img.shields.io/github/sponsors/xerolux?logo=github&style=for-the-badge&color=blue)](https://github.com/sponsors/xerolux)
[![Ko-Fi](https://img.shields.io/badge/Ko--fi-xerolux-blue?logo=ko-fi&style=for-the-badge)](https://ko-fi.com/xerolux)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-xerolux-yellow?logo=buy-me-a-coffee&style=for-the-badge)](https://www.buymeacoffee.com/xerolux)
[![PayPal](https://img.shields.io/badge/PayPal-xerolux-blue?logo=paypal&style=for-the-badge)](https://paypal.me/xerolux)
[![Tesla Referral](https://img.shields.io/badge/Tesla-Referral-red?logo=tesla&style=for-the-badge)](https://ts.la/sebastian564489)

_Jede Unterstützung ist eine große Motivation! Vielen Dank!_

---

### Feedback & Contributions

- [Report a bug](https://github.com/Xerolux/idm-heatpump-hass/issues/new?template=bug_report.md)
- [Request a feature](https://github.com/Xerolux/idm-heatpump-hass/issues/new?template=feature_request.md)
- [Contribute](https://github.com/Xerolux/idm-heatpump-hass/blob/main/docs/CONTRIBUTING.md)

---

**Developed by:** [Xerolux](https://github.com/Xerolux)
**Integration for:** IDM Navigator 2.0 by IDM EnergieSysteme GmbH
**License:** MIT

_Generated automatically by GitHub Actions on 2026-05-31 16:17:12 UTC_

---

## [0.4.2] - 2026-05-31

## v0.4.2 - IDM Heatpump

**BETA RELEASE - Testing phase, may contain bugs**

[![GitHub Sponsor](https://img.shields.io/github/sponsors/xerolux?logo=github&style=for-the-badge&color=blue)](https://github.com/sponsors/xerolux)
[![Ko-Fi](https://img.shields.io/badge/Ko--fi-xerolux-blue?logo=ko-fi&style=for-the-badge)](https://ko-fi.com/xerolux)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-xerolux-yellow?logo=buy-me-a-coffee&style=for-the-badge)](https://www.buymeacoffee.com/xerolux)
[![PayPal](https://img.shields.io/badge/PayPal-xerolux-blue?logo=paypal&style=for-the-badge)](https://paypal.me/xerolux)
[![Tesla Referral](https://img.shields.io/badge/Tesla-Referral-red?logo=tesla&style=for-the-badge)](https://ts.la/sebastian564489)

### New Features

- Enhanced IDM Heatpump functionality

### Improvements

- Release v0.4.1 - Update changelog and version files (d7423e0)

### Bug Fixes

- fix: lower pymodbus requirement to >=3.7.0 to match HA bundled version (cd8e211)

---

### Installation

**HACS (Recommended):**
1. Add custom repository: `Xerolux/idm-heatpump-hass`
2. Search for "IDM Heatpump"
3. Click Install

**Manual:**
1. Download `idm_heatpump.zip`
2. Extract to `custom_components/idm_heatpump`
3. Restart Home Assistant

---

[Full changelog: v0.4.1...v0.4.2](https://github.com/Xerolux/idm-heatpump-hass/compare/v0.4.1...v0.4.2)

---

### Support

Diese Integration wird in meiner Freizeit entwickelt – deine Unterstützung erhöht die Motivation für weitere Features und Updates! 🚀

[![GitHub Sponsor](https://img.shields.io/github/sponsors/xerolux?logo=github&style=for-the-badge&color=blue)](https://github.com/sponsors/xerolux)
[![Ko-Fi](https://img.shields.io/badge/Ko--fi-xerolux-blue?logo=ko-fi&style=for-the-badge)](https://ko-fi.com/xerolux)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-xerolux-yellow?logo=buy-me-a-coffee&style=for-the-badge)](https://www.buymeacoffee.com/xerolux)
[![PayPal](https://img.shields.io/badge/PayPal-xerolux-blue?logo=paypal&style=for-the-badge)](https://paypal.me/xerolux)
[![Tesla Referral](https://img.shields.io/badge/Tesla-Referral-red?logo=tesla&style=for-the-badge)](https://ts.la/sebastian564489)

_Jede Unterstützung ist eine große Motivation! Vielen Dank!_

---

### Feedback & Contributions

- [Report a bug](https://github.com/Xerolux/idm-heatpump-hass/issues/new?template=bug_report.md)
- [Request a feature](https://github.com/Xerolux/idm-heatpump-hass/issues/new?template=feature_request.md)
- [Contribute](https://github.com/Xerolux/idm-heatpump-hass/blob/main/docs/CONTRIBUTING.md)

---

**Developed by:** [Xerolux](https://github.com/Xerolux)
**Integration for:** IDM Navigator 2.0 by IDM EnergieSysteme GmbH
**License:** MIT

_Generated automatically by GitHub Actions on 2026-05-31 15:11:25 UTC_

---

## [0.4.1] - 2026-05-31

## v0.4.2 - IDM Heatpump

### Bug Fixes
- Lowered `pymodbus` requirement to `>=3.7.0` to fix setup failure with HA's bundled pymodbus version

## v0.4.1 - IDM Heatpump

**BETA RELEASE - Testing phase, may contain bugs**

[![GitHub Sponsor](https://img.shields.io/github/sponsors/xerolux?logo=github&style=for-the-badge&color=blue)](https://github.com/sponsors/xerolux)
[![Ko-Fi](https://img.shields.io/badge/Ko--fi-xerolux-blue?logo=ko-fi&style=for-the-badge)](https://ko-fi.com/xerolux)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-xerolux-yellow?logo=buy-me-a-coffee&style=for-the-badge)](https://www.buymeacoffee.com/xerolux)
[![PayPal](https://img.shields.io/badge/PayPal-xerolux-blue?logo=paypal&style=for-the-badge)](https://paypal.me/xerolux)
[![Tesla Referral](https://img.shields.io/badge/Tesla-Referral-red?logo=tesla&style=for-the-badge)](https://ts.la/sebastian564489)

### New Features

- fix: Add 255 handling to German mode options in const.py for consistency during testing (50fb2de)
- fix: Add safe read-only test_connection() method to the HA client wrapper (9877e5d)
- feat: Navigator 10 support + start of migration to idm_heatpump library (9e92c8f)
- feat: HA 2026.5 compatibility, fix all lint/type errors, upgrade deps (bfb3006)
- feat: translate all docs to English, ensure HA 2026.5 compatibility (5943a9f)
- docs: update wiki and add wiki link to config flow (9b586c2)

### Improvements

- release: v0.4.1 - fix register alias mapping, update CI HA version (0ba2564)
- Refactor: optimize code, fix modbus datatypes and update service target definitions (75e1218)
- Release v0.2.9 - Update changelog and version files (4194b26)
- Release v0.2.9 - Update changelog and version files (3047597)
- update-wiki-writing-values (717ba28)
- docs: update wiki and add wiki link to config flow (9b586c2)
- Release v0.2.9 - Update changelog and version files (ad3b675)

### Bug Fixes

- release: v0.4.1 - fix register alias mapping, update CI HA version (0ba2564)
- fix: Add 255 handling to German mode options in const.py for consistency during testing (50fb2de)
- fix: Add safe read-only test_connection() method to the HA client wrapper (9877e5d)
- feat: HA 2026.5 compatibility, fix all lint/type errors, upgrade deps (bfb3006)
- Refactor: optimize code, fix modbus datatypes and update service target definitions (75e1218)
- fix modbus batching and harden service targeting (d808ca6)
- fix-pymodbus-slave-param-issue (660f02e)
- Fix ModbusClientMixin slave/device_id parameter issue (a682ccc)
- fix-pymodbus-version-requirement (e7df2dc)
- Fix: Lower pymodbus requirement to 3.11.2 and support both device_id and slave (12b5177)

---

### Installation

**HACS (Recommended):**
1. Add custom repository: `Xerolux/idm-heatpump-hass`
2. Search for "IDM Heatpump"
3. Click Install

**Manual:**
1. Download `idm_heatpump.zip`
2. Extract to `custom_components/idm_heatpump`
3. Restart Home Assistant

---

[Full changelog: v0.2.9...v0.4.1](https://github.com/Xerolux/idm-heatpump-hass/compare/v0.2.9...v0.4.1)

---

### Support

Diese Integration wird in meiner Freizeit entwickelt – deine Unterstützung erhöht die Motivation für weitere Features und Updates! 🚀

[![GitHub Sponsor](https://img.shields.io/github/sponsors/xerolux?logo=github&style=for-the-badge&color=blue)](https://github.com/sponsors/xerolux)
[![Ko-Fi](https://img.shields.io/badge/Ko--fi-xerolux-blue?logo=ko-fi&style=for-the-badge)](https://ko-fi.com/xerolux)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-xerolux-yellow?logo=buy-me-a-coffee&style=for-the-badge)](https://www.buymeacoffee.com/xerolux)
[![PayPal](https://img.shields.io/badge/PayPal-xerolux-blue?logo=paypal&style=for-the-badge)](https://paypal.me/xerolux)
[![Tesla Referral](https://img.shields.io/badge/Tesla-Referral-red?logo=tesla&style=for-the-badge)](https://ts.la/sebastian564489)

_Jede Unterstützung ist eine große Motivation! Vielen Dank!_

---

### Feedback & Contributions

- [Report a bug](https://github.com/Xerolux/idm-heatpump-hass/issues/new?template=bug_report.md)
- [Request a feature](https://github.com/Xerolux/idm-heatpump-hass/issues/new?template=feature_request.md)
- [Contribute](https://github.com/Xerolux/idm-heatpump-hass/blob/main/docs/CONTRIBUTING.md)

---

**Developed by:** [Xerolux](https://github.com/Xerolux)
**Integration for:** IDM Navigator 2.0 by IDM EnergieSysteme GmbH
**License:** MIT

_Generated automatically by GitHub Actions on 2026-05-31 15:04:29 UTC_

---


## [0.4.1] - 2026-05-31

### Bug Fixes
- Fixed register alias mapping: sensor and number entities sharing the same Modbus address now both receive data (was causing number entities for HK A to show unavailable)
- Updated library dependency to `idm-heatpump>=0.2.1` (adds 255 "Not configured" handling for mode options, firmware_version fix)

### Improvements
- Added `collect_alias_map()` for proper multi-name register resolution in coordinator
- Docker test setup added (`docker/`, `run_docker_test.ps1`, `run_docker_test.sh`)
- Live-tested on Navigator 10 with 7 heating circuits, solar, ISC, PV, cascade

## [0.4.0] - 2026-05-31

### Major Features
- **Major architectural change (Option B)**: The integration now uses the official `idm-heatpump` Python library (published on PyPI) as its core for Modbus communication and register definitions. The addon is a thin HA-specific layer on top (via `library_adapter.py`).
- Full support for the official iDM "MODBUS TCP NAVIGATOR 10" register set (June 2025 documentation)
- Added heat sink / plate heat exchanger sensors (addresses 1068–1074), including **Durchfluss Wärmesenke (B2) at 1072** — excellent for strainer/filter monitoring on ALM units
- Added power limitation registers (4108 / 4112) as writable numbers — ideal for demand response and peak shaving
- Added Booster A/B monitoring (4001–4052)
- `modbus_client.py` is now a minimal compatibility wrapper around the library's `IdmModbusClient` (massive code deduplication)
- Added additional fault registers and groundwater temperatures
- Zone modules now correctly default to 6 rooms per module (Navigator 10 / current hardware). Legacy 8-room configurations remain supported via manual setting.
- Improved model detection to recognize Navigator 10 controllers
- All new descriptions and documentation updated to English + German

This work was driven by user feedback (especially from owners of ALM 2-8 with Navigator 10).

## [0.2.9] - 2026-03-23

## v0.2.9 - IDM Heatpump

**STABLE RELEASE**

[![GitHub Sponsor](https://img.shields.io/github/sponsors/xerolux?logo=github&style=for-the-badge&color=blue)](https://github.com/sponsors/xerolux)
[![Ko-Fi](https://img.shields.io/badge/Ko--fi-xerolux-blue?logo=ko-fi&style=for-the-badge)](https://ko-fi.com/xerolux)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-xerolux-yellow?logo=buy-me-a-coffee&style=for-the-badge)](https://www.buymeacoffee.com/xerolux)
[![PayPal](https://img.shields.io/badge/PayPal-xerolux-blue?logo=paypal&style=for-the-badge)](https://paypal.me/xerolux)
[![Tesla Referral](https://img.shields.io/badge/Tesla-Referral-red?logo=tesla&style=for-the-badge)](https://ts.la/sebastian564489)

### New Features

- docs: update wiki and add wiki link to config flow (9b586c2)
- Merge pull request #19 from Xerolux/claude/add-code-headers-pzKZI (1fb6526)
- Add Xerolux 2026 copyright header to all Python source files (fa2e121)
- Merge pull request #17 from Xerolux/claude/add-claude-documentation-G9lZu (aa69106)
- docs: add CLAUDE.md with comprehensive codebase guide for AI assistants (6e9eeff)
- Add Tesla referral badge to README (cb6aff5)
- add-ai-heatpump-image (a347d6a)
- feat: add option to toggle cascade registers in config flow (d5176aa)
- docs: add AI-generated heatpump image to README and Wiki Home (57eb301)

### Improvements

- Release v0.2.9 - Update changelog and version files (3047597)
- update-wiki-writing-values (717ba28)
- docs: update wiki and add wiki link to config flow (9b586c2)
- Release v0.2.9 - Update changelog and version files (ad3b675)
- fix-bugs-improve-quality (7312982)
- update-dependencies-2026 (232cffb)
- chore: update dependencies and bump HA min version to 2026.3 (a0ad9a7)
- Update image caption in README.md (f10ef98)
- Release v0.2.8 - Update changelog and version files (7ddf02a)

### Bug Fixes

- fix-pymodbus-slave-param-issue (660f02e)
- Fix ModbusClientMixin slave/device_id parameter issue (a682ccc)
- fix-pymodbus-version-requirement (e7df2dc)
- Fix: Lower pymodbus requirement to 3.11.2 and support both device_id and slave (12b5177)
- fix-bugs-improve-quality (7312982)
- fix: 8 bugs and quality improvements (89fe6d0)
- fix-wiki-links (bce1871)
- fix-wiki-links (29a89e2)
- fix: remove .md extension from wiki internal link in Services.md (297eabd)
- fix: Wiki-Links von raw/blob GitHub-URLs auf korrekte Wiki-Links korrigiert (17e2253)
- fix(config_flow): use description_placeholders for URLs in translations to satisfy hassfest (886d18b)

---

### Installation

**HACS (Recommended):**
1. Add custom repository: `Xerolux/idm-heatpump-hass`
2. Search for "IDM Heatpump"
3. Click Install

**Manual:**
1. Download `idm_heatpump.zip`
2. Extract to `custom_components/idm_heatpump`
3. Restart Home Assistant

---

[Full changelog: v0.2.8...v0.2.9](https://github.com/Xerolux/idm-heatpump-hass/compare/v0.2.8...v0.2.9)

---

### Support

Diese Integration wird in meiner Freizeit entwickelt – deine Unterstützung erhöht die Motivation für weitere Features und Updates! 🚀

[![GitHub Sponsor](https://img.shields.io/github/sponsors/xerolux?logo=github&style=for-the-badge&color=blue)](https://github.com/sponsors/xerolux)
[![Ko-Fi](https://img.shields.io/badge/Ko--fi-xerolux-blue?logo=ko-fi&style=for-the-badge)](https://ko-fi.com/xerolux)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-xerolux-yellow?logo=buy-me-a-coffee&style=for-the-badge)](https://www.buymeacoffee.com/xerolux)
[![PayPal](https://img.shields.io/badge/PayPal-xerolux-blue?logo=paypal&style=for-the-badge)](https://paypal.me/xerolux)
[![Tesla Referral](https://img.shields.io/badge/Tesla-Referral-red?logo=tesla&style=for-the-badge)](https://ts.la/sebastian564489)

_Jede Unterstützung ist eine große Motivation! Vielen Dank!_

---

### Feedback & Contributions

- [Report a bug](https://github.com/Xerolux/idm-heatpump-hass/issues/new?template=bug_report.md)
- [Request a feature](https://github.com/Xerolux/idm-heatpump-hass/issues/new?template=feature_request.md)
- [Contribute](https://github.com/Xerolux/idm-heatpump-hass/blob/main/docs/CONTRIBUTING.md)

---

**Developed by:** [Xerolux](https://github.com/Xerolux)
**Integration for:** IDM Navigator 2.0 by IDM EnergieSysteme GmbH
**License:** MIT

_Generated automatically by GitHub Actions on 2026-03-23 18:12:22 UTC_

---

## [0.2.9] - 2026-03-23

## v0.2.9 - IDM Heatpump

**STABLE RELEASE**

[![GitHub Sponsor](https://img.shields.io/github/sponsors/xerolux?logo=github&style=for-the-badge&color=blue)](https://github.com/sponsors/xerolux)
[![Ko-Fi](https://img.shields.io/badge/Ko--fi-xerolux-blue?logo=ko-fi&style=for-the-badge)](https://ko-fi.com/xerolux)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-xerolux-yellow?logo=buy-me-a-coffee&style=for-the-badge)](https://www.buymeacoffee.com/xerolux)
[![PayPal](https://img.shields.io/badge/PayPal-xerolux-blue?logo=paypal&style=for-the-badge)](https://paypal.me/xerolux)
[![Tesla Referral](https://img.shields.io/badge/Tesla-Referral-red?logo=tesla&style=for-the-badge)](https://ts.la/sebastian564489)

### New Features

- docs: update wiki and add wiki link to config flow (9b586c2)
- Merge pull request #19 from Xerolux/claude/add-code-headers-pzKZI (1fb6526)
- Add Xerolux 2026 copyright header to all Python source files (fa2e121)
- Merge pull request #17 from Xerolux/claude/add-claude-documentation-G9lZu (aa69106)
- docs: add CLAUDE.md with comprehensive codebase guide for AI assistants (6e9eeff)
- Add Tesla referral badge to README (cb6aff5)
- add-ai-heatpump-image (a347d6a)
- feat: add option to toggle cascade registers in config flow (d5176aa)
- docs: add AI-generated heatpump image to README and Wiki Home (57eb301)

### Improvements

- update-wiki-writing-values (717ba28)
- docs: update wiki and add wiki link to config flow (9b586c2)
- Release v0.2.9 - Update changelog and version files (ad3b675)
- fix-bugs-improve-quality (7312982)
- update-dependencies-2026 (232cffb)
- chore: update dependencies and bump HA min version to 2026.3 (a0ad9a7)
- Update image caption in README.md (f10ef98)
- Release v0.2.8 - Update changelog and version files (7ddf02a)

### Bug Fixes

- fix-pymodbus-version-requirement (e7df2dc)
- Fix: Lower pymodbus requirement to 3.11.2 and support both device_id and slave (12b5177)
- fix-bugs-improve-quality (7312982)
- fix: 8 bugs and quality improvements (89fe6d0)
- fix-wiki-links (bce1871)
- fix-wiki-links (29a89e2)
- fix: remove .md extension from wiki internal link in Services.md (297eabd)
- fix: Wiki-Links von raw/blob GitHub-URLs auf korrekte Wiki-Links korrigiert (17e2253)
- fix(config_flow): use description_placeholders for URLs in translations to satisfy hassfest (886d18b)

---

### Installation

**HACS (Recommended):**
1. Add custom repository: `Xerolux/idm-heatpump-hass`
2. Search for "IDM Heatpump"
3. Click Install

**Manual:**
1. Download `idm_heatpump.zip`
2. Extract to `custom_components/idm_heatpump`
3. Restart Home Assistant

---

[Full changelog: v0.2.8...v0.2.9](https://github.com/Xerolux/idm-heatpump-hass/compare/v0.2.8...v0.2.9)

---

### Support

Diese Integration wird in meiner Freizeit entwickelt – deine Unterstützung erhöht die Motivation für weitere Features und Updates! 🚀

[![GitHub Sponsor](https://img.shields.io/github/sponsors/xerolux?logo=github&style=for-the-badge&color=blue)](https://github.com/sponsors/xerolux)
[![Ko-Fi](https://img.shields.io/badge/Ko--fi-xerolux-blue?logo=ko-fi&style=for-the-badge)](https://ko-fi.com/xerolux)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-xerolux-yellow?logo=buy-me-a-coffee&style=for-the-badge)](https://www.buymeacoffee.com/xerolux)
[![PayPal](https://img.shields.io/badge/PayPal-xerolux-blue?logo=paypal&style=for-the-badge)](https://paypal.me/xerolux)
[![Tesla Referral](https://img.shields.io/badge/Tesla-Referral-red?logo=tesla&style=for-the-badge)](https://ts.la/sebastian564489)

_Jede Unterstützung ist eine große Motivation! Vielen Dank!_

---

### Feedback & Contributions

- [Report a bug](https://github.com/Xerolux/idm-heatpump-hass/issues/new?template=bug_report.md)
- [Request a feature](https://github.com/Xerolux/idm-heatpump-hass/issues/new?template=feature_request.md)
- [Contribute](https://github.com/Xerolux/idm-heatpump-hass/blob/main/docs/CONTRIBUTING.md)

---

**Developed by:** [Xerolux](https://github.com/Xerolux)
**Integration for:** IDM Navigator 2.0 by IDM EnergieSysteme GmbH
**License:** MIT

_Generated automatically by GitHub Actions on 2026-03-23 16:45:49 UTC_

---

## [0.2.9] - 2026-03-23

## v0.2.9 - IDM Heatpump

**STABLE RELEASE**

[![GitHub Sponsor](https://img.shields.io/github/sponsors/xerolux?logo=github&style=for-the-badge&color=blue)](https://github.com/sponsors/xerolux)
[![Ko-Fi](https://img.shields.io/badge/Ko--fi-xerolux-blue?logo=ko-fi&style=for-the-badge)](https://ko-fi.com/xerolux)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-xerolux-yellow?logo=buy-me-a-coffee&style=for-the-badge)](https://www.buymeacoffee.com/xerolux)
[![PayPal](https://img.shields.io/badge/PayPal-xerolux-blue?logo=paypal&style=for-the-badge)](https://paypal.me/xerolux)
[![Tesla Referral](https://img.shields.io/badge/Tesla-Referral-red?logo=tesla&style=for-the-badge)](https://ts.la/sebastian564489)

### New Features

- Merge pull request #19 from Xerolux/claude/add-code-headers-pzKZI (1fb6526)
- Add Xerolux 2026 copyright header to all Python source files (fa2e121)
- Merge pull request #17 from Xerolux/claude/add-claude-documentation-G9lZu (aa69106)
- docs: add CLAUDE.md with comprehensive codebase guide for AI assistants (6e9eeff)
- Add Tesla referral badge to README (cb6aff5)
- add-ai-heatpump-image (a347d6a)
- feat: add option to toggle cascade registers in config flow (d5176aa)
- docs: add AI-generated heatpump image to README and Wiki Home (57eb301)

### Improvements

- fix-bugs-improve-quality (7312982)
- update-dependencies-2026 (232cffb)
- chore: update dependencies and bump HA min version to 2026.3 (a0ad9a7)
- Update image caption in README.md (f10ef98)
- Release v0.2.8 - Update changelog and version files (7ddf02a)

### Bug Fixes

- fix-bugs-improve-quality (7312982)
- fix: 8 bugs and quality improvements (89fe6d0)
- fix-wiki-links (bce1871)
- fix-wiki-links (29a89e2)
- fix: remove .md extension from wiki internal link in Services.md (297eabd)
- fix: Wiki-Links von raw/blob GitHub-URLs auf korrekte Wiki-Links korrigiert (17e2253)
- fix(config_flow): use description_placeholders for URLs in translations to satisfy hassfest (886d18b)

---

### Installation

**HACS (Recommended):**
1. Add custom repository: `Xerolux/idm-heatpump-hass`
2. Search for "IDM Heatpump"
3. Click Install

**Manual:**
1. Download `idm_heatpump.zip`
2. Extract to `custom_components/idm_heatpump`
3. Restart Home Assistant

---

[Full changelog: v0.2.8...v0.2.9](https://github.com/Xerolux/idm-heatpump-hass/compare/v0.2.8...v0.2.9)

---

### Support

Diese Integration wird in meiner Freizeit entwickelt – deine Unterstützung erhöht die Motivation für weitere Features und Updates! 🚀

[![GitHub Sponsor](https://img.shields.io/github/sponsors/xerolux?logo=github&style=for-the-badge&color=blue)](https://github.com/sponsors/xerolux)
[![Ko-Fi](https://img.shields.io/badge/Ko--fi-xerolux-blue?logo=ko-fi&style=for-the-badge)](https://ko-fi.com/xerolux)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-xerolux-yellow?logo=buy-me-a-coffee&style=for-the-badge)](https://www.buymeacoffee.com/xerolux)
[![PayPal](https://img.shields.io/badge/PayPal-xerolux-blue?logo=paypal&style=for-the-badge)](https://paypal.me/xerolux)
[![Tesla Referral](https://img.shields.io/badge/Tesla-Referral-red?logo=tesla&style=for-the-badge)](https://ts.la/sebastian564489)

_Jede Unterstützung ist eine große Motivation! Vielen Dank!_

---

### Feedback & Contributions

- [Report a bug](https://github.com/Xerolux/idm-heatpump-hass/issues/new?template=bug_report.md)
- [Request a feature](https://github.com/Xerolux/idm-heatpump-hass/issues/new?template=feature_request.md)
- [Contribute](https://github.com/Xerolux/idm-heatpump-hass/blob/main/docs/CONTRIBUTING.md)

---

**Developed by:** [Xerolux](https://github.com/Xerolux)
**Integration for:** IDM Navigator 2.0 by IDM EnergieSysteme GmbH
**License:** MIT

_Generated automatically by GitHub Actions on 2026-03-23 16:05:39 UTC_

---

## [0.2.8] - 2026-03-22

## v0.2.8 - IDM Heatpump

**STABLE RELEASE**

[![GitHub Sponsor](https://img.shields.io/github/sponsors/xerolux?logo=github&style=for-the-badge&color=blue)](https://github.com/sponsors/xerolux)
[![Ko-Fi](https://img.shields.io/badge/Ko--fi-xerolux-blue?logo=ko-fi&style=for-the-badge)](https://ko-fi.com/xerolux)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-xerolux-yellow?logo=buy-me-a-coffee&style=for-the-badge)](https://www.buymeacoffee.com/xerolux)
[![PayPal](https://img.shields.io/badge/PayPal-xerolux-blue?logo=paypal&style=for-the-badge)](https://paypal.me/xerolux)
[![Tesla Referral](https://img.shields.io/badge/Tesla-Referral-red?logo=tesla&style=for-the-badge)](https://ts.la/sebastian564489)

### New Features

- feat: add BITFLAG datatype for human-readable WP status, fix zone mode to RO sensor (43c21f3)
- fix: remove invalid addresses, add missing cascade/zone sensors per IDM YAML (d97347b)

### Improvements

- Release v0.2.7 - Update changelog and version files (8864a8e)

### Bug Fixes

- fix-modbus-read-errors- (50524af)
- feat: add BITFLAG datatype for human-readable WP status, fix zone mode to RO sensor (43c21f3)
- fix-modbus-read-errors (9d76d58)
- fix: remove invalid addresses, add missing cascade/zone sensors per IDM YAML (d97347b)
- fix: comprehensive register address corrections based on official IDM Modbus YAML (5ae8ea4)

---

### Installation

**HACS (Recommended):**
1. Add custom repository: `Xerolux/idm-heatpump-hass`
2. Search for "IDM Heatpump"
3. Click Install

**Manual:**
1. Download `idm_heatpump.zip`
2. Extract to `custom_components/idm_heatpump`
3. Restart Home Assistant

---

[Full changelog: v0.2.7...v0.2.8](https://github.com/Xerolux/idm-heatpump-hass/compare/v0.2.7...v0.2.8)

---

### Support

Diese Integration wird in meiner Freizeit entwickelt – deine Unterstützung erhöht die Motivation für weitere Features und Updates! 🚀

[![GitHub Sponsor](https://img.shields.io/github/sponsors/xerolux?logo=github&style=for-the-badge&color=blue)](https://github.com/sponsors/xerolux)
[![Ko-Fi](https://img.shields.io/badge/Ko--fi-xerolux-blue?logo=ko-fi&style=for-the-badge)](https://ko-fi.com/xerolux)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-xerolux-yellow?logo=buy-me-a-coffee&style=for-the-badge)](https://www.buymeacoffee.com/xerolux)
[![PayPal](https://img.shields.io/badge/PayPal-xerolux-blue?logo=paypal&style=for-the-badge)](https://paypal.me/xerolux)
[![Tesla Referral](https://img.shields.io/badge/Tesla-Referral-red?logo=tesla&style=for-the-badge)](https://ts.la/sebastian564489)

_Jede Unterstützung ist eine große Motivation! Vielen Dank!_

---

### Feedback & Contributions

- [Report a bug](https://github.com/Xerolux/idm-heatpump-hass/issues/new?template=bug_report.md)
- [Request a feature](https://github.com/Xerolux/idm-heatpump-hass/issues/new?template=feature_request.md)
- [Contribute](https://github.com/Xerolux/idm-heatpump-hass/wiki/Contributing)

---

**Developed by:** [Xerolux](https://github.com/Xerolux)
**Integration for:** IDM Navigator 2.0 by IDM EnergieSysteme GmbH
**License:** MIT

_Generated automatically by GitHub Actions on 2026-03-22 16:59:16 UTC_

---

## [0.2.7] - 2026-03-22

## v0.2.7 - IDM Heatpump

**STABLE RELEASE**

[![GitHub Sponsor](https://img.shields.io/github/sponsors/xerolux?logo=github&style=for-the-badge&color=blue)](https://github.com/sponsors/xerolux)
[![Ko-Fi](https://img.shields.io/badge/Ko--fi-xerolux-blue?logo=ko-fi&style=for-the-badge)](https://ko-fi.com/xerolux)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-xerolux-yellow?logo=buy-me-a-coffee&style=for-the-badge)](https://www.buymeacoffee.com/xerolux)
[![PayPal](https://img.shields.io/badge/PayPal-xerolux-blue?logo=paypal&style=for-the-badge)](https://paypal.me/xerolux)
[![Tesla Referral](https://img.shields.io/badge/Tesla-Referral-red?logo=tesla&style=for-the-badge)](https://ts.la/sebastian564489)

### New Features

- Enhanced IDM Heatpump functionality

### Improvements

- Release v0.2.6 - Update changelog and version files (45d37fb)

### Bug Fixes

- fix-modbus-read-errors (ce477e3)
- fix: correct unit conversions, datatypes, and enum labels for sensor registers (2f3e537)
- fix: multiple correctness and robustness improvements (5424c28)
- fix: show Fachmanncode sensors by default and suppress repeated Modbus errors (6702799)

---

### Installation

**HACS (Recommended):**
1. Add custom repository: `Xerolux/idm-heatpump-hass`
2. Search for "IDM Heatpump"
3. Click Install

**Manual:**
1. Download `idm_heatpump.zip`
2. Extract to `custom_components/idm_heatpump`
3. Restart Home Assistant

---

[Full changelog: v0.2.6...v0.2.7](https://github.com/Xerolux/idm-heatpump-hass/compare/v0.2.6...v0.2.7)

---

### Support

Diese Integration wird in meiner Freizeit entwickelt – deine Unterstützung erhöht die Motivation für weitere Features und Updates! 🚀

[![GitHub Sponsor](https://img.shields.io/github/sponsors/xerolux?logo=github&style=for-the-badge&color=blue)](https://github.com/sponsors/xerolux)
[![Ko-Fi](https://img.shields.io/badge/Ko--fi-xerolux-blue?logo=ko-fi&style=for-the-badge)](https://ko-fi.com/xerolux)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-xerolux-yellow?logo=buy-me-a-coffee&style=for-the-badge)](https://www.buymeacoffee.com/xerolux)
[![PayPal](https://img.shields.io/badge/PayPal-xerolux-blue?logo=paypal&style=for-the-badge)](https://paypal.me/xerolux)
[![Tesla Referral](https://img.shields.io/badge/Tesla-Referral-red?logo=tesla&style=for-the-badge)](https://ts.la/sebastian564489)

_Jede Unterstützung ist eine große Motivation! Vielen Dank!_

---

### Feedback & Contributions

- [Report a bug](https://github.com/Xerolux/idm-heatpump-hass/issues/new?template=bug_report.md)
- [Request a feature](https://github.com/Xerolux/idm-heatpump-hass/issues/new?template=feature_request.md)
- [Contribute](https://github.com/Xerolux/idm-heatpump-hass/wiki/Contributing)

---

**Developed by:** [Xerolux](https://github.com/Xerolux)
**Integration for:** IDM Navigator 2.0 by IDM EnergieSysteme GmbH
**License:** MIT

_Generated automatically by GitHub Actions on 2026-03-22 14:11:50 UTC_

---

## [0.2.6] - 2026-03-22

## v0.2.6 - IDM Heatpump

**STABLE RELEASE**

[![GitHub Sponsor](https://img.shields.io/github/sponsors/xerolux?logo=github&style=for-the-badge&color=blue)](https://github.com/sponsors/xerolux)
[![Ko-Fi](https://img.shields.io/badge/Ko--fi-xerolux-blue?logo=ko-fi&style=for-the-badge)](https://ko-fi.com/xerolux)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-xerolux-yellow?logo=buy-me-a-coffee&style=for-the-badge)](https://www.buymeacoffee.com/xerolux)
[![PayPal](https://img.shields.io/badge/PayPal-xerolux-blue?logo=paypal&style=for-the-badge)](https://paypal.me/xerolux)
[![Tesla Referral](https://img.shields.io/badge/Tesla-Referral-red?logo=tesla&style=for-the-badge)](https://ts.la/sebastian564489)

### New Features

- chore: Add test_ha and .claude to .gitignore (e532685)

### Improvements

- Release v0.2.5 - Update changelog and version files (6256846)
- Release v0.2.5 - Update changelog and version files (c969fcb)

### Bug Fixes

- Minor bug fixes and stability improvements

---

### Installation

**HACS (Recommended):**
1. Add custom repository: `Xerolux/idm-heatpump-hass`
2. Search for "IDM Heatpump"
3. Click Install

**Manual:**
1. Download `idm_heatpump.zip`
2. Extract to `custom_components/idm_heatpump`
3. Restart Home Assistant

---

[Full changelog: v0.2.5...v0.2.6](https://github.com/Xerolux/idm-heatpump-hass/compare/v0.2.5...v0.2.6)

---

### Support

Diese Integration wird in meiner Freizeit entwickelt – deine Unterstützung erhöht die Motivation für weitere Features und Updates! 🚀

[![GitHub Sponsor](https://img.shields.io/github/sponsors/xerolux?logo=github&style=for-the-badge&color=blue)](https://github.com/sponsors/xerolux)
[![Ko-Fi](https://img.shields.io/badge/Ko--fi-xerolux-blue?logo=ko-fi&style=for-the-badge)](https://ko-fi.com/xerolux)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-xerolux-yellow?logo=buy-me-a-coffee&style=for-the-badge)](https://www.buymeacoffee.com/xerolux)
[![PayPal](https://img.shields.io/badge/PayPal-xerolux-blue?logo=paypal&style=for-the-badge)](https://paypal.me/xerolux)
[![Tesla Referral](https://img.shields.io/badge/Tesla-Referral-red?logo=tesla&style=for-the-badge)](https://ts.la/sebastian564489)

_Jede Unterstützung ist eine große Motivation! Vielen Dank!_

---

### Feedback & Contributions

- [Report a bug](https://github.com/Xerolux/idm-heatpump-hass/issues/new?template=bug_report.md)
- [Request a feature](https://github.com/Xerolux/idm-heatpump-hass/issues/new?template=feature_request.md)
- [Contribute](https://github.com/Xerolux/idm-heatpump-hass/wiki/Contributing)

---

**Developed by:** [Xerolux](https://github.com/Xerolux)
**Integration for:** IDM Navigator 2.0 by IDM EnergieSysteme GmbH
**License:** MIT

_Generated automatically by GitHub Actions on 2026-03-22 12:04:21 UTC_

---

## [0.2.5] - 2026-03-22

## v0.2.5 - IDM Heatpump

**STABLE RELEASE**

[![GitHub Sponsor](https://img.shields.io/github/sponsors/xerolux?logo=github&style=for-the-badge&color=blue)](https://github.com/sponsors/xerolux)
[![Ko-Fi](https://img.shields.io/badge/Ko--fi-xerolux-blue?logo=ko-fi&style=for-the-badge)](https://ko-fi.com/xerolux)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-xerolux-yellow?logo=buy-me-a-coffee&style=for-the-badge)](https://www.buymeacoffee.com/xerolux)
[![PayPal](https://img.shields.io/badge/PayPal-xerolux-blue?logo=paypal&style=for-the-badge)](https://paypal.me/xerolux)
[![Tesla Referral](https://img.shields.io/badge/Tesla-Referral-red?logo=tesla&style=for-the-badge)](https://ts.la/sebastian564489)

### New Features

- chore: Add test_ha and .claude to .gitignore (e532685)
- fix: Add CONFIG_SCHEMA to resolve Home Assistant validation error (6a558c8)
- feat: Add badges to top of release notes (5fc5e53)

### Improvements

- Release v0.2.5 - Update changelog and version files (c969fcb)
- Release v0.2.5 - Update version and changelog (2643176)
- Release v0.2.4 - Update changelog and version files (2cb52a7)
- Release v0.2.4 - Update changelog and version files (8f6c3cd)
- Release v0.2.4 - Update changelog and version files (9b1714b)

### Bug Fixes

- fix: Add CONFIG_SCHEMA to resolve Home Assistant validation error (6a558c8)

---

### Installation

**HACS (Recommended):**
1. Add custom repository: `Xerolux/idm-heatpump-hass`
2. Search for "IDM Heatpump"
3. Click Install

**Manual:**
1. Download `idm_heatpump.zip`
2. Extract to `custom_components/idm_heatpump`
3. Restart Home Assistant

---

[Full changelog: v0.2.4...v0.2.5](https://github.com/Xerolux/idm-heatpump-hass/compare/v0.2.4...v0.2.5)

---

### Support

Diese Integration wird in meiner Freizeit entwickelt – deine Unterstützung erhöht die Motivation für weitere Features und Updates! 🚀

[![GitHub Sponsor](https://img.shields.io/github/sponsors/xerolux?logo=github&style=for-the-badge&color=blue)](https://github.com/sponsors/xerolux)
[![Ko-Fi](https://img.shields.io/badge/Ko--fi-xerolux-blue?logo=ko-fi&style=for-the-badge)](https://ko-fi.com/xerolux)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-xerolux-yellow?logo=buy-me-a-coffee&style=for-the-badge)](https://www.buymeacoffee.com/xerolux)
[![PayPal](https://img.shields.io/badge/PayPal-xerolux-blue?logo=paypal&style=for-the-badge)](https://paypal.me/xerolux)
[![Tesla Referral](https://img.shields.io/badge/Tesla-Referral-red?logo=tesla&style=for-the-badge)](https://ts.la/sebastian564489)

_Jede Unterstützung ist eine große Motivation! Vielen Dank!_

---

### Feedback & Contributions

- [Report a bug](https://github.com/Xerolux/idm-heatpump-hass/issues/new?template=bug_report.md)
- [Request a feature](https://github.com/Xerolux/idm-heatpump-hass/issues/new?template=feature_request.md)
- [Contribute](https://github.com/Xerolux/idm-heatpump-hass/wiki/Contributing)

---

**Developed by:** [Xerolux](https://github.com/Xerolux)
**Integration for:** IDM Navigator 2.0 by IDM EnergieSysteme GmbH
**License:** MIT

_Generated automatically by GitHub Actions on 2026-03-22 12:01:52 UTC_

---

## [0.2.5] - 2026-03-22

## v0.2.5 - IDM Heatpump

**STABLE RELEASE**

[![GitHub Sponsor](https://img.shields.io/github/sponsors/xerolux?logo=github&style=for-the-badge&color=blue)](https://github.com/sponsors/xerolux)
[![Ko-Fi](https://img.shields.io/badge/Ko--fi-xerolux-blue?logo=ko-fi&style=for-the-badge)](https://ko-fi.com/xerolux)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-xerolux-yellow?logo=buy-me-a-coffee&style=for-the-badge)](https://www.buymeacoffee.com/xerolux)
[![PayPal](https://img.shields.io/badge/PayPal-xerolux-blue?logo=paypal&style=for-the-badge)](https://paypal.me/xerolux)
[![Tesla Referral](https://img.shields.io/badge/Tesla-Referral-red?logo=tesla&style=for-the-badge)](https://ts.la/sebastian564489)

### New Features

- fix: Add CONFIG_SCHEMA to resolve Home Assistant validation error (6a558c8)
- feat: Add badges to top of release notes (5fc5e53)

### Improvements

- Release v0.2.5 - Update version and changelog (2643176)
- Release v0.2.4 - Update changelog and version files (2cb52a7)
- Release v0.2.4 - Update changelog and version files (8f6c3cd)
- Release v0.2.4 - Update changelog and version files (9b1714b)

### Bug Fixes

- fix: Add CONFIG_SCHEMA to resolve Home Assistant validation error (6a558c8)

---

### Installation

**HACS (Recommended):**
1. Add custom repository: `Xerolux/idm-heatpump-hass`
2. Search for "IDM Heatpump"
3. Click Install

**Manual:**
1. Download `idm_heatpump.zip`
2. Extract to `custom_components/idm_heatpump`
3. Restart Home Assistant

---

[Full changelog: v0.2.4...v0.2.5](https://github.com/Xerolux/idm-heatpump-hass/compare/v0.2.4...v0.2.5)

---

### Support

Diese Integration wird in meiner Freizeit entwickelt – deine Unterstützung erhöht die Motivation für weitere Features und Updates! 🚀

[![GitHub Sponsor](https://img.shields.io/github/sponsors/xerolux?logo=github&style=for-the-badge&color=blue)](https://github.com/sponsors/xerolux)
[![Ko-Fi](https://img.shields.io/badge/Ko--fi-xerolux-blue?logo=ko-fi&style=for-the-badge)](https://ko-fi.com/xerolux)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-xerolux-yellow?logo=buy-me-a-coffee&style=for-the-badge)](https://www.buymeacoffee.com/xerolux)
[![PayPal](https://img.shields.io/badge/PayPal-xerolux-blue?logo=paypal&style=for-the-badge)](https://paypal.me/xerolux)
[![Tesla Referral](https://img.shields.io/badge/Tesla-Referral-red?logo=tesla&style=for-the-badge)](https://ts.la/sebastian564489)

_Jede Unterstützung ist eine große Motivation! Vielen Dank!_

---

### Feedback & Contributions

- [Report a bug](https://github.com/Xerolux/idm-heatpump-hass/issues/new?template=bug_report.md)
- [Request a feature](https://github.com/Xerolux/idm-heatpump-hass/issues/new?template=feature_request.md)
- [Contribute](https://github.com/Xerolux/idm-heatpump-hass/wiki/Contributing)

---

**Developed by:** [Xerolux](https://github.com/Xerolux)
**Integration for:** IDM Navigator 2.0 by IDM EnergieSysteme GmbH
**License:** MIT

_Generated automatically by GitHub Actions on 2026-03-22 11:57:43 UTC_

---

## [0.2.5] - 2026-03-22

## v0.2.5 - IDM Heatpump

**STABLE RELEASE**

### Bug Fixes

- fix: Add CONFIG_SCHEMA to resolve Home Assistant validation error (6a558c8)

---

### Installation

**HACS (Recommended):**
1. Add custom repository: `Xerolux/idm-heatpump-hass`
2. Search for "IDM Heatpump"
3. Click Install

**Manual:**
1. Download `idm_heatpump.zip`
2. Extract to `custom_components/idm_heatpump`
3. Restart Home Assistant

---

[Full changelog: v0.2.4...v0.2.5](https://github.com/Xerolux/idm-heatpump-hass/compare/v0.2.4...v0.2.5)

---

### Support

Diese Integration wird in meiner Freizeit entwickelt – deine Unterstützung erhöht die Motivation für weitere Features und Updates! 🚀

[![GitHub Sponsor](https://img.shields.io/github/sponsors/xerolux?logo=github&style=for-the-badge&color=blue)](https://github.com/sponsors/xerolux)
[![Ko-Fi](https://img.shields.io/badge/Ko--fi-xerolux-blue?logo=ko-fi&style=for-the-badge)](https://ko-fi.com/xerolux)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-xerolux-yellow?logo=buy-me-a-coffee&style=for-the-badge)](https://www.buymeacoffee.com/xerolux)
[![PayPal](https://img.shields.io/badge/PayPal-xerolux-blue?logo=paypal&style=for-the-badge)](https://paypal.me/xerolux)
[![Tesla Referral](https://img.shields.io/badge/Tesla-Referral-red?logo=tesla&style=for-the-badge)](https://ts.la/sebastian564489)

_Jede Unterstützung ist eine große Motivation! Vielen Dank!_

---

### Feedback & Contributions

- [Report a bug](https://github.com/Xerolux/idm-heatpump-hass/issues/new?template=bug_report.md)
- [Request a feature](https://github.com/Xerolux/idm-heatpump-hass/issues/new?template=feature_request.md)
- [Contribute](https://github.com/Xerolux/idm-heatpump-hass/wiki/Contributing)

---

**Developed by:** [Xerolux](https://github.com/Xerolux)
**Integration for:** IDM Navigator 2.0 by IDM EnergieSysteme GmbH
**License:** MIT

---

## [0.2.4] - 2026-03-22

## v0.2.4 - IDM Heatpump

**STABLE RELEASE**

### New Features

- feat: Add badges and motivation text to release notes (0ab0a04)
- Add files via upload (2710ed2)

### Improvements

- Release v0.2.4 - Update version in manifest (057da6c)
- Release v0.2.3 - Update changelog and version files (98c2d67)

### Bug Fixes

- fix brand Icon (a32c390)

---

### Installation

**HACS (Recommended):**
1. Add custom repository: `Xerolux/idm-heatpump-hass`
2. Search for "IDM Heatpump"
3. Click Install

**Manual:**
1. Download `idm_heatpump.zip`
2. Extract to `custom_components/idm_heatpump`
3. Restart Home Assistant

---

[Full changelog: v0.2.3...v0.2.4](https://github.com/Xerolux/idm-heatpump-hass/compare/v0.2.3...v0.2.4)

---

### Support

Diese Integration wird in meiner Freizeit entwickelt – deine Unterstützung erhöht die Motivation für weitere Features und Updates! 🚀

[![GitHub Sponsor](https://img.shields.io/github/sponsors/xerolux?logo=github&style=for-the-badge&color=blue)](https://github.com/sponsors/xerolux)
[![Ko-Fi](https://img.shields.io/badge/Ko--fi-xerolux-blue?logo=ko-fi&style=for-the-badge)](https://ko-fi.com/xerolux)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-xerolux-yellow?logo=buy-me-a-coffee&style=for-the-badge)](https://www.buymeacoffee.com/xerolux)
[![PayPal](https://img.shields.io/badge/PayPal-xerolux-blue?logo=paypal&style=for-the-badge)](https://paypal.me/xerolux)
[![Tesla Referral](https://img.shields.io/badge/Tesla-Referral-red?logo=tesla&style=for-the-badge)](https://ts.la/sebastian564489)

_Jede Unterstützung ist eine große Motivation! Vielen Dank!_

---

### Feedback & Contributions

- [Report a bug](https://github.com/Xerolux/idm-heatpump-hass/issues/new?template=bug_report.md)
- [Request a feature](https://github.com/Xerolux/idm-heatpump-hass/issues/new?template=feature_request.md)
- [Contribute](https://github.com/Xerolux/idm-heatpump-hass/wiki/Contributing)

---

**Developed by:** [Xerolux](https://github.com/Xerolux)
**Integration for:** IDM Navigator 2.0 by IDM EnergieSysteme GmbH
**License:** MIT

_Generated automatically by GitHub Actions on 2026-03-22 11:51:16 UTC_

---

## [0.2.4] - 2026-03-22

## v0.2.4 - IDM Heatpump

**STABLE RELEASE**

[![GitHub Sponsor](https://img.shields.io/github/sponsors/xerolux?logo=github&style=for-the-badge&color=blue)](https://github.com/sponsors/xerolux)
[![Ko-Fi](https://img.shields.io/badge/Ko--fi-xerolux-blue?logo=ko-fi&style=for-the-badge)](https://ko-fi.com/xerolux)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-xerolux-yellow?logo=buy-me-a-coffee&style=for-the-badge)](https://www.buymeacoffee.com/xerolux)
[![PayPal](https://img.shields.io/badge/PayPal-xerolux-blue?logo=paypal&style=for-the-badge)](https://paypal.me/xerolux)
[![Tesla Referral](https://img.shields.io/badge/Tesla-Referral-red?logo=tesla&style=for-the-badge)](https://ts.la/sebastian564489)

### New Features

- feat: Add badges to top of release notes (5fc5e53)
- feat: Add badges and motivation text to release notes (0ab0a04)
- Add files via upload (2710ed2)

### Improvements

- Release v0.2.4 - Update changelog and version files (9b1714b)
- Release v0.2.4 - Update version in manifest (057da6c)
- Release v0.2.3 - Update changelog and version files (98c2d67)

### Bug Fixes

- fix brand Icon (a32c390)

---

### Installation

**HACS (Recommended):**
1. Add custom repository: `Xerolux/idm-heatpump-hass`
2. Search for "IDM Heatpump"
3. Click Install

**Manual:**
1. Download `idm_heatpump.zip`
2. Extract to `custom_components/idm_heatpump`
3. Restart Home Assistant

---

[Full changelog: v0.2.3...v0.2.4](https://github.com/Xerolux/idm-heatpump-hass/compare/v0.2.3...v0.2.4)

---

### Support

Diese Integration wird in meiner Freizeit entwickelt – deine Unterstützung erhöht die Motivation für weitere Features und Updates! 🚀

[![GitHub Sponsor](https://img.shields.io/github/sponsors/xerolux?logo=github&style=for-the-badge&color=blue)](https://github.com/sponsors/xerolux)
[![Ko-Fi](https://img.shields.io/badge/Ko--fi-xerolux-blue?logo=ko-fi&style=for-the-badge)](https://ko-fi.com/xerolux)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-xerolux-yellow?logo=buy-me-a-coffee&style=for-the-badge)](https://www.buymeacoffee.com/xerolux)
[![PayPal](https://img.shields.io/badge/PayPal-xerolux-blue?logo=paypal&style=for-the-badge)](https://paypal.me/xerolux)
[![Tesla Referral](https://img.shields.io/badge/Tesla-Referral-red?logo=tesla&style=for-the-badge)](https://ts.la/sebastian564489)

_Jede Unterstützung ist eine große Motivation! Vielen Dank!_

---

### Feedback & Contributions

- [Report a bug](https://github.com/Xerolux/idm-heatpump-hass/issues/new?template=bug_report.md)
- [Request a feature](https://github.com/Xerolux/idm-heatpump-hass/issues/new?template=feature_request.md)
- [Contribute](https://github.com/Xerolux/idm-heatpump-hass/wiki/Contributing)

---

**Developed by:** [Xerolux](https://github.com/Xerolux)
**Integration for:** IDM Navigator 2.0 by IDM EnergieSysteme GmbH
**License:** MIT

_Generated automatically by GitHub Actions on 2026-03-22 11:49:36 UTC_

---

## [0.2.4] - 2026-03-22

## v0.2.4 - IDM Heatpump

**STABLE RELEASE**

### New Features

- feat: Add badges and motivation text to release notes (0ab0a04)
- Add files via upload (2710ed2)

### Improvements

- Release v0.2.4 - Update version in manifest (057da6c)
- Release v0.2.3 - Update changelog and version files (98c2d67)

### Bug Fixes

- fix brand Icon (a32c390)

---

### Installation

**HACS (Recommended):**
1. Add custom repository: `Xerolux/idm-heatpump-hass`
2. Search for "IDM Heatpump"
3. Click Install

**Manual:**
1. Download `idm_heatpump.zip`
2. Extract to `custom_components/idm_heatpump`
3. Restart Home Assistant

---

[Full changelog: v0.2.3...v0.2.4](https://github.com/Xerolux/idm-heatpump-hass/compare/v0.2.3...v0.2.4)

---

### Support

Diese Integration wird in meiner Freizeit entwickelt – deine Unterstützung erhöht die Motivation für weitere Features und Updates! 🚀

[![GitHub Sponsor](https://img.shields.io/github/sponsors/xerolux?logo=github&style=for-the-badge&color=blue)](https://github.com/sponsors/xerolux)
[![Ko-Fi](https://img.shields.io/badge/Ko--fi-xerolux-blue?logo=ko-fi&style=for-the-badge)](https://ko-fi.com/xerolux)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-xerolux-yellow?logo=buy-me-a-coffee&style=for-the-badge)](https://www.buymeacoffee.com/xerolux)
[![PayPal](https://img.shields.io/badge/PayPal-xerolux-blue?logo=paypal&style=for-the-badge)](https://paypal.me/xerolux)
[![Tesla Referral](https://img.shields.io/badge/Tesla-Referral-red?logo=tesla&style=for-the-badge)](https://ts.la/sebastian564489)

_Jede Unterstützung ist eine große Motivation! Vielen Dank!_

---

### Feedback & Contributions

- [Report a bug](https://github.com/Xerolux/idm-heatpump-hass/issues/new?template=bug_report.md)
- [Request a feature](https://github.com/Xerolux/idm-heatpump-hass/issues/new?template=feature_request.md)
- [Contribute](https://github.com/Xerolux/idm-heatpump-hass/wiki/Contributing)

---

**Developed by:** [Xerolux](https://github.com/Xerolux)
**Integration for:** IDM Navigator 2.0 by IDM EnergieSysteme GmbH
**License:** MIT

_Generated automatically by GitHub Actions on 2026-03-22 11:47:48 UTC_

---

## [0.2.3] - 2026-03-22

## v0.2.3 - IDM Heatpump

**STABLE RELEASE**

### New Features

- docs: add HA Core integration documentation page (4746602)
- feat: add strict typing and mark all quality scale rules as done (0753c67)
- chore: add coverage and pytest artifacts to .gitignore (f265e03)
- test: add comprehensive test suite with 97% coverage (247 tests) (eaf9422)
- feat: HA quality scale prep – Bronze/Silver/Gold compliance (d2c5463)
- add-donation-badges (072962b)
- docs: add donation badges (Buy Me a Coffee, PayPal, Tesla) to top of changelog (513ae11)

### Improvements

- docs: update version references to HA 2026.3, Python 3.14.2, pymodbus 3.11.2 (9526226)
- fix(quality_scale): update domain-rename status to done (767dc27)
- Release v0.2.2 - Update changelog and version files (824a486)

### Bug Fixes

- fix(quality_scale): mark config-flow and test-coverage as done (429ffae)
- fix(quality_scale): update domain-rename status to done (767dc27)

---

### Installation

**HACS (Recommended):**
1. Add custom repository: `Xerolux/idm-heatpump-hass`
2. Search for "IDM Heatpump"
3. Click Install

**Manual:**
1. Download `idm_heatpump.zip`
2. Extract to `custom_components/idm_heatpump`
3. Restart Home Assistant

---

[Full changelog: v0.2.2...v0.2.3](https://github.com/Xerolux/idm-heatpump-hass/compare/v0.2.2...v0.2.3)

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
- [Contribute](https://github.com/Xerolux/idm-heatpump-hass/wiki/Contributing)

---

**Developed by:** [Xerolux](https://github.com/Xerolux)
**Integration for:** IDM Navigator 2.0 by IDM EnergieSysteme GmbH
**License:** MIT

_Generated automatically by GitHub Actions on 2026-03-22 08:03:14 UTC_

---

## [0.2.3] - 2026-03-21

## v0.2.3 - IDM Heatpump

**STABLE RELEASE**

### Breaking Changes

- **Domain umbenannt:** `idm_heatpump_v2` → `idm_heatpump`
  Bestehende Installationen müssen nach dem Update neu eingerichtet werden (Entities bekommen neue IDs).

### Improvements

- rename: Integration-Domain von `idm_heatpump_v2` auf `idm_heatpump` umbenannt (HA Core Anforderung)
- docs: HA Core Integration Dokumentationsseite hinzugefügt (`docs/ha-core-integration-page.md`)
- fix(quality_scale): Domain-Rename, Config-Flow-Coverage und Test-Coverage als done markiert

---

[Full changelog: v0.2.2...v0.2.3](https://github.com/Xerolux/idm-heatpump-hass/compare/v0.2.2...v0.2.3)

---

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
1. Download `idm_heatpump.zip`
2. Extract to `custom_components/idm_heatpump`
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
- [Contribute](https://github.com/Xerolux/idm-heatpump-hass/wiki/Contributing)

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
1. Download `idm_heatpump.zip`
2. Extract to `custom_components/idm_heatpump`
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
- [Contribute](https://github.com/Xerolux/idm-heatpump-hass/wiki/Contributing)

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
1. Download `idm_heatpump.zip`
2. Extract to `custom_components/idm_heatpump`
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
- [Contribute](https://github.com/Xerolux/idm-heatpump-hass/wiki/Contributing)

---

**Developed by:** [Xerolux](https://github.com/Xerolux)
**Integration for:** IDM Navigator 2.0 by IDM EnergieSysteme GmbH
**License:** MIT

_Generated automatically by GitHub Actions on 2026-03-21 12:18:05 UTC_

---

