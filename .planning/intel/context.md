# Synthesized Context

The notes below preserve representative source wording verbatim and group it by topic. Each note retains its source path for downstream traceability.

## 1. Project identity and runtime baseline

source: docs/wiki/_Footer.md

> **IDM Heatpump** · GitHub · Issues · HACS · License: MIT · Requires HA 2026.5.0+

source: docs/wiki/_Sidebar.md

> **HA:** 2026.5.0+
> **Python:** 3.13+ · **pymodbus:** pymodbus>=3.12.1,<4.0 · **idm-heatpump-api[web]:** idm-heatpump-api[web]==0.7.6

source: docs/wiki/Home.md

> The **IDM Heatpump Home Assistant Integration** connects Home Assistant with the IDM Navigator 2.0 / 10 by IDM EnergieSysteme GmbH. It enables complete local control and monitoring of your heat pump via **Modbus TCP — no cloud, no subscription**.

## 2. Release status, history, and readiness

source: docs/CHANGELOG.md

> All notable changes to this project will be documented in this file.
>
> ## [0.8.1-beta.28] - 2026-07-11

source: docs/wiki/Changelog.md

> The authoritative, complete history is maintained in `docs/CHANGELOG.md` and the GitHub releases. This page only summarizes recent milestones.

source: docs/wiki/Stability-and-Release-Readiness.md

> Integration `0.8.1-beta.29` and `idm-heatpump-api` `0.7.6` form the tested, exactly pinned pair from this audit. The integration remains a beta while the hardware/community and soak gates below are still open.

## 3. Installation, setup, and configuration

source: docs/wiki/Installation-and-Setup.md

> **Required:** Full integration operation is only possible when Modbus TCP is enabled on the IDM Navigator/controller. Installing the Home Assistant integration cannot enable this controller setting remotely.

source: docs/wiki/Configuration.md

> Leave the web PIN empty if you want Modbus-only operation. Modbus remains the baseline path and works without a PIN. Providing a PIN also enables the setup flow to offer a limited web-only fallback when Modbus is unavailable.

## 4. Polling, availability, and recovery

source: docs/wiki/Data-Update.md

> The integration uses Modbus TCP to read register data directly from the IDM heat pump. All communication is **local** — there is no cloud connection.
>
> Exhausted timeout/no-response failures abort the poll and trigger the normal repair flow; they never count as permanent failures of individual registers.

## 5. Entity surface

source: docs/wiki/Entities.md

> The integration dynamically generates entities based on your heat pump configuration (heating circuits, zones, optional features).
>
> Adding more heating circuits, zones, cascade, optional technician codes, or optional web supplement data increases the counts.

## 6. Automation guidance

source: docs/wiki/Examples.md

> In Home Assistant, writable values of the heat pump are represented as **entities**. To change these values in automations, you don't use `idm_heatpump.write_register`, but the standard Home Assistant services.
>
> External requests should always have temperature, low-surplus and maximum-time stop paths. Verify the behavior with the Navigator GLT Monitor before leaving the automation unattended.

## 7. Hardware compatibility and limitations

source: docs/wiki/Compatibility-Matrix.md

> This matrix tracks tested IDM hardware without publishing private network data. It separates confirmed devices from expected compatibility so users can judge risk before installing.

source: docs/wiki/Supported-Devices.md

> The detailed model and firmware status is maintained in the Compatibility Matrix. The table below is a short installation-oriented summary.

source: docs/wiki/Known-Limitations.md

> Only **Modbus TCP** is supported (no serial Modbus RTU).
>
> Multiple IDM heat pumps are supported. Each connection must have a unique host, port, and slave-ID combination.

## 8. Navigator protocol evidence

source: docs/wiki/Navigator-Protocol-Analysis.md

> Diese Seite dokumentiert bestätigte Erkenntnisse aus der statischen Analyse des Navigator-Clients und der lesenden Validierung einer Navigator-10-Anlage. Sie ist keine vollständige Protokollspezifikation.
>
> Die Integration verwendet deshalb weiterhin Modbus als Basispfad und die lokale Webschnittstelle nur als optionale Ergänzung beziehungsweise Fallback. Es werden keine Cloud-Anmeldungen benötigt.

## 9. Maintenance and release operations

source: docs/MAINTENANCE.md

> This document defines the operating rules for the IDM Heatpump Home Assistant custom integration and its companion `idm-heatpump-api` package.
>
> Changes in these areas require maintainer review before merge: Modbus register definitions and model gates; write-enabled entities, services, and validation logic; EEPROM-sensitive or cyclic write handling; release workflows, dependency pins, and package metadata; diagnostics redaction and repair issue handling.

source: docs/RELEASE_PROCESS.md

> This process covers coordinated releases of `idm-heatpump-api` and the Home Assistant custom integration.
>
> Publish the API release. Open an integration PR that pins the exact API version in `custom_components/idm_heatpump/manifest.json`.

source: docs/RELEASE_SMOKE_TEST.md

> Run this checklist before publishing a stable HACS release. It verifies the same artifact and runtime dependency set that users install from GitHub.

## 10. Contribution and community conduct

source: docs/CONTRIBUTING.md

> We welcome contributions to this project! Whether it's reporting a bug, submitting a fix, or proposing new features, your contributions are highly appreciated.

source: docs/wiki/Contributing.md

> We welcome contributions to this project!
>
> By contributing, you agree that your code will be published under the MIT License.

source: docs/CODE_OF_CONDUCT.md

> We as members, contributors, and leaders pledge to make participation in our community a harassment-free experience for everyone.

## 11. Security policy

source: docs/SECURITY.md

> Always use the most recent release version. No security updates will be provided for outdated releases.
>
> If you identify a vulnerability, please email Xerolux before making it public, to allow time to address and fix the issue.

## 12. Troubleshooting and evidence collection

source: docs/wiki/Troubleshooting.md

> Open **Settings → Devices & Services → IDM Heatpump → Reconfigure → Test current connection**. This performs a read-only test using the saved settings.
>
> Do not include private IP addresses, hostnames, serial numbers, installer/customer data or unredacted network details.

## 13. Future Home Assistant Core documentation draft

source: docs/ha-core-integration-page.md

> Draft for a possible future Home Assistant Core documentation page. The current project is an unofficial HACS custom integration and is not yet part of Home Assistant Core.

The draft's write-enabled platforms, actions, and Gold metadata are not treated as the accepted scope of a first Core contribution; the higher-precedence decision in `decisions.md` governs that scope.
