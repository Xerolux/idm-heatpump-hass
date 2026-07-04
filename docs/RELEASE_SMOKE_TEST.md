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
       "pymodbus>=3.12.1,<4.0",
       "idm-heatpump-api[web]>=0.4.1,<0.6",
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
4. Upgrade from the previous stable release to this release through HACS.
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
