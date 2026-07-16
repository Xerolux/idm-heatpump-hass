# Release Smoke Test

Run this checklist against every stable-release candidate on a clean Home
Assistant installation connected to real IDM hardware. Automated tests and a
container that only imports the integration are useful preflight checks, but
they do not replace this end-to-end test.

Create one evidence record per candidate by copying
`docs/release-evidence/TEMPLATE.md` to
`docs/release-evidence/<version>.md`. Record `PASS`, `FAIL`, or `N/A` for every
check. `N/A` requires a reason. The stable-release gate passes only when all
required checks are `PASS`, every optional path is either `PASS` or justified
`N/A`, and a maintainer signs the final verdict.

## 0. Candidate and Test Environment

Record before testing:

- release version, tag, commit SHA, publication timestamp, and artifact URL;
- artifact SHA-256 and checksum-verification result;
- Home Assistant version and installation type;
- heat-pump model, Navigator generation, firmware, and connection path;
- whether local web data, zone modules, cascade, and room-temperature
  forwarding are in scope;
- tester, start time, and end time in UTC.

Use a new Home Assistant instance or remove the existing test instance and its
configuration volume. Reusing an already configured entry is not a fresh
installation test.

## 1. Artifact and Dependency Check

1. Download both release assets from the draft or tagged GitHub release. For
   example. Set `RELEASE_VERSION` to the exact candidate version without the
   leading `v` before running these commands:

   ```bash
   export RELEASE_VERSION="${RELEASE_VERSION:?set the candidate version first}"
   export RELEASE_TAG="v${RELEASE_VERSION}"
   export ARTIFACT_DIR="$(mktemp -d)"
   gh release download "$RELEASE_TAG" \
     --repo Xerolux/idm-heatpump-hass \
     --dir "$ARTIFACT_DIR"
   cd "$ARTIFACT_DIR"
   ```

2. Verify the published checksum:

   ```bash
   sha256sum -c idm_heatpump.zip.sha256
   ```

3. Unpack the artifact into a new temporary directory and confirm the manifest
   contains the candidate version and tested runtime pins:

   ```bash
   export UNPACK_DIR="$(mktemp -d)"
   unzip -q idm_heatpump.zip -d "$UNPACK_DIR"
   python - <<'PY'
   import json
   import os
   from pathlib import Path

   manifest = json.loads(
       (Path(os.environ["UNPACK_DIR"]) / "manifest.json").read_text(encoding="utf-8")
   )
   assert manifest["requirements"] == [
       "pymodbus>=3.12.1,<4.0",
       "idm-heatpump-api[web]==0.7.7",
   ]
   assert manifest["version"] == os.environ["RELEASE_VERSION"]
   print("artifact metadata ok")
   PY
   ```

4. Confirm the ZIP contains only the integration package contents and does not
   contain tests, bytecode, caches, repository metadata, or a second nested
   `idm_heatpump` directory.

## 2. Fresh Installation

1. Install the release through HACS, or copy the unpacked artifact to
   `custom_components/idm_heatpump`.
2. Restart Home Assistant.
3. Confirm Home Assistant starts without setup import errors for
   `idm_heatpump`, `idm_heatpump_api`, or `pymodbus`.
4. Record the installed integration and dependency versions from diagnostics;
   they must match the candidate and manifest.

## 3. Config Flow and First Poll

1. Add the integration from Settings -> Devices & services -> Add integration.
2. Enter host, port, slave ID, optional local web PIN, heating circuits, zones,
   cascade, optional technician-code settings, and optional web supplement
   settings.
3. Confirm setup completes and the first coordinator refresh succeeds.
4. Confirm detected model and capabilities match the connected device.
5. For Navigator 2.0 / Terra SWM, confirm no Navigator-10-only registers are
   polled during the first refresh.

## 4. Optional Web Supplement Path

Run this only on a system where the local Navigator web PIN is known.

1. Reconfigure the integration with an intentionally wrong web PIN.
2. Confirm the config flow rejects the PIN on the PIN field and the Home
   Assistant log contains the rejected web PIN message.
3. Clear the PIN and confirm setup/reconfigure still succeeds in Modbus-only
   mode.
4. Enter the correct PIN, enable web supplement data, and set the web interval.
5. Confirm the default web interval is 30 seconds unless deliberately changed.
6. Confirm the integration reports Navigator generation and software version
   after the web poll.
7. On Navigator 10, confirm infosystem notification count/summary sensors are
   created when the API returns notifications.
8. Temporarily block the web interface or use a bad web endpoint and confirm
   Modbus polling continues.
9. Confirm web values that duplicate Modbus entities are not created as
   duplicate entities.
10. Confirm the detected Navigator 2.0 or Navigator 10/Pro protocol is stored,
    then interrupt one web poll and verify runtime recovery reconnects only the
    same protocol.
11. Download diagnostics and confirm Modbus/web hosts, port, slave ID and web
    PIN are absent. A web failure may expose only its error category, never a
    URL, `auth_code` query or PIN.

## 5. Optional Room Temperature Forwarding

Run this only with a safe test sensor and a heating circuit where external room
temperature input is intended.

1. Confirm room temperature forwarding is disabled by default after setup.
2. Enable forwarding in the integration options and select one Home Assistant
   temperature sensor for one active heating circuit.
3. Confirm the options flow exposes interval and tolerance settings.
4. Change the source sensor value inside the valid range and confirm the
   matching `hc_<circuit>_ext_room_temp` register is written.
5. Confirm unavailable, non-numeric, or out-of-range source states are skipped.
6. Disable forwarding again unless the test system should keep using it.

## 6. Safe Write Path

Use only a reversible, documented register on a test system.

1. Change one safe writable entity, such as a temporary setpoint within its
   documented min/max range.
2. Confirm Home Assistant updates optimistically.
3. Confirm the next poll reads back the expected device value.
4. Restore the original value.

Do not use EEPROM-sensitive registers for this smoke test unless the release
specifically changes EEPROM protection.

## 7. Reload, Unload, and Upgrade

1. Reload the config entry and confirm entities return to `available`.
2. Unload the config entry and confirm the Modbus client disconnects cleanly.
3. Re-enable or reload the entry and confirm polling resumes.
4. In a separate instance or after restoring a snapshot, upgrade from the
   immediately preceding published release to this candidate through HACS.
5. Confirm entity unique IDs, device registry entries, and user customizations
   are preserved.

## 8. Evidence to Attach to the Release

- Home Assistant version.
- Integration version and artifact checksum.
- Detected heat pump model, firmware if available, and active capabilities.
- Web supplement enabled/disabled state, detected Navigator generation,
  software version, and PIN-validation result if tested.
- Room temperature forwarding enabled/disabled state and write result if
  tested.
- Confirmation of first poll, safe write, reload, unload, and upgrade.
- Any unsupported-register, timeout, or reconnect logs with IP addresses
  redacted.

Do not attach raw configuration storage, access tokens, PINs, IP addresses,
hostnames, serial numbers, or unredacted diagnostics.

## 9. Pass/Fail and Sign-Off

The result is:

- `PASS` only when Sections 1-3 and 6-7 pass, every applicable optional
  section passes, no privacy leak is found, and the original safe value is
  restored after the write test;
- `FAIL` when any required step fails or produces a new setup regression,
  reconnect loop, corrupted value, unsafe write, or leaked secret;
- `BLOCKED` when hardware, authorization for one reversible write, the
  preceding release, or another required test condition is unavailable.

A `BLOCKED` result is not a pass. Link the completed evidence record from
`docs/wiki/Stability-and-Release-Readiness.md` before approving a stable tag.
