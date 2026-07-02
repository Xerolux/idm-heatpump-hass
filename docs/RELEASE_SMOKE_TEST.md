# Release Smoke Test

Run this checklist before publishing a stable HACS release. It verifies the
same artifact and runtime dependency set that users install from GitHub.

## 1. Artifact and Dependency Check

1. Download the release artifact `idm_heatpump.zip` from the draft or tagged
   GitHub release.
2. Verify the checksum:

   ```bash
   sha256sum -c idm_heatpump.zip.sha256
   ```

3. Unpack the artifact into a temporary directory:

   ```bash
   rm -rf /tmp/idm_heatpump_release
   mkdir -p /tmp/idm_heatpump_release
   unzip idm_heatpump.zip -d /tmp/idm_heatpump_release
   ```

4. Confirm the manifest contains the tested runtime pins:

   ```bash
   python - <<'PY'
   import json
   from pathlib import Path

   manifest = json.loads(Path("/tmp/idm_heatpump_release/manifest.json").read_text())
   assert manifest["requirements"] == [
       "pymodbus==3.12.1",
       "idm-heatpump-api==0.3.7",
   ]
   print("runtime requirements ok")
   PY
   ```

## 2. Fresh Installation

1. Install the release through HACS, or copy the unpacked artifact to
   `custom_components/idm_heatpump`.
2. Restart Home Assistant.
3. Confirm Home Assistant starts without setup import errors for
   `idm_heatpump`, `idm_heatpump_api`, or `pymodbus`.

## 3. Config Flow and First Poll

1. Add the integration from Settings -> Devices & services -> Add integration.
2. Enter host, port, slave ID, heating circuits, zones, cascade, and optional
   technician-code settings.
3. Confirm setup completes and the first coordinator refresh succeeds.
4. Confirm detected model and capabilities match the connected device.
5. For Navigator 2.0 / Terra SWM, confirm no Navigator-10-only registers are
   polled during the first refresh.

## 4. Safe Write Path

Use only a reversible, documented register on a test system.

1. Change one safe writable entity, such as a temporary setpoint within its
   documented min/max range.
2. Confirm Home Assistant updates optimistically.
3. Confirm the next poll reads back the expected device value.
4. Restore the original value.

Do not use EEPROM-sensitive registers for this smoke test unless the release
specifically changes EEPROM protection.

## 5. Reload, Unload, and Upgrade

1. Reload the config entry and confirm entities return to `available`.
2. Unload the config entry and confirm the Modbus client disconnects cleanly.
3. Re-enable or reload the entry and confirm polling resumes.
4. Upgrade from the previous stable release to this release through HACS.
5. Confirm entity unique IDs, device registry entries, and user customizations
   are preserved.

## 6. Evidence to Attach to the Release

- Home Assistant version.
- Integration version and artifact checksum.
- Detected heat pump model, firmware if available, and active capabilities.
- Confirmation of first poll, safe write, reload, unload, and upgrade.
- Any unsupported-register, timeout, or reconnect logs with IP addresses
  redacted.
