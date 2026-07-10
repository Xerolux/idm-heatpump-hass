# Troubleshooting

## Connection Problems

### Run the built-in connection test

Open **Settings → Devices & Services → IDM Heatpump → Reconfigure → Test
current connection**. This performs a read-only test using the saved settings:

1. Read a known IDM Modbus register with the configured slave ID.
2. If that fails, run a short DNS/TCP check to identify the network cause.
3. If a local web PIN exists, verify the Navigator web endpoint and PIN.

The test neither changes the config entry nor writes to the heat pump. Its
translated result identifies the failed stage, and submitting the result form
runs the test again. The same categorized reason is written to the log without
exposing the PIN.

### "Hostname could not be resolved"

- Check the spelling of the configured hostname
- Verify that Home Assistant can use the same local DNS/mDNS server as your browser
- Reconfigure with the fixed IP address of the heat pump to rule out DNS problems

### "Modbus TCP connection refused"

The target device actively rejected TCP. This is the strongest available
indication that **Modbus TCP is not enabled** or that the wrong port was used.

- On the Navigator/controller, open **Building management system
  (Gebäudeleittechnik) → Modbus TCP** and set it to **On / Ein**
- If this menu is missing or locked, sign in at installer/technician level or
  ask your heating installer/iDM service to enable it
- Use TCP port **502** unless the controller or proxy was configured differently
- Restart the Navigator/controller after enabling Modbus if the setting does not become active immediately
- If a proxy is used, confirm that it listens on the entered host and port

This setting must be enabled on the **heat pump/Navigator**, not on a PV
inverter. See [Enable Modbus TCP on the IDM heat pump](Installation-and-Setup#enable-modbus-tcp-on-the-idm-heat-pump)
for the complete checklist and official iDM references.

### "Modbus TCP connection timed out" or "endpoint is not reachable"

- Check the **IP address** of the IDM Navigator
- Verify that the controller is powered on
- Check whether a firewall, VLAN, subnet, or routing rule blocks port 502
- Ping the IP address: `ping <ip-of-navigator>`

Timeout means no answer arrived within five seconds. Unreachable means the
operating system reported a network/routing failure.

### Connection drops

- Check the network connection (LAN cable recommended)
- Increase the scan interval (e.g., to 30 seconds)
- Enable debug logging (see [Configuration](Configuration))
- The integration automatically optimizes Modbus connections to avoid constant reconnections (`self._client.connected` checks). If drops still occur, check the stability of your local network or WiFi.

### "No valid IDM register response"

- Check the **Slave ID** (default: 1)
- Confirm that Modbus access is enabled or released for external clients
- Check if other Modbus clients are accessing the same port simultaneously
- Restart the IDM Navigator after enabling Modbus

This message means the TCP endpoint was reached, but the setup probe did not
receive usable IDM register data. It is therefore different from a network or
firewall failure.

### Modbus is not available on the heat pump

Enter the local Navigator web PIN during setup. If the web interface can be
authenticated, the recovery step offers **web data only**. This mode exposes
read-only web sensors but no Modbus heating-circuit/zone registers, writable
entities, mode control, or error acknowledgement. Full functionality still
requires Modbus TCP to be enabled by the installer or iDM service if the local
controller does not expose the setting.

### "Navigator web PIN rejected"

- Open **Settings → Devices & Services → IDM Heatpump → Reconfigure → Change connection settings**
- Enter the current local Navigator web PIN again
- Do not use a cloud account password; the integration needs the local PIN
- Clear the PIN if you intentionally want Modbus-only operation

The runtime repair notification and log identify authentication failures
separately from network failures. The repair action can verify a replacement
PIN or disable optional web data. The PIN itself is never logged.

### "Navigator web interface could not be read"

- With direct Modbus access, the web host is normally the same heat pump IP
- With a Modbus proxy, enable the proxy option and enter the **original heat pump address** as web host
- Confirm that Home Assistant can reach the local Navigator web interface
- Clear the web PIN to continue with Modbus only

## Entity Problems

### Missing entities

- Make sure the corresponding **heating circuits** and **zones** are enabled in the configuration
- Reconfigure the integration
- Restart Home Assistant

### Incorrect or absurd values (e.g., -3276.8°C)

- Check if the register addresses are correct for your Navigator model.
- Extreme or incorrect numbers usually indicate incorrectly declared data types (Float, Word, sign). Please report such values via GitHub Issues so we can adjust the register in `registers.py` to `INT8`, `INT16`, or `FLOAT`.
- Enable debug logging and check the raw register values in the logs.
- Report incorrect register mappings as a [bug](https://github.com/Xerolux/idm-heatpump-hass/issues/new?template=bug_report.md).

### Values not updating

- Check the **scan interval** in the options
- Check the Home Assistant logs for error messages
- Reconfigure the integration

## EEPROM Warnings

If you receive a warning about EEPROM when writing values:

- These registers have a limited number of write cycles
- Changes to these values should be made **sparingly**
- The integration automatically warns about EEPROM sensitivity

## Debug Logging

Enable extended logging:

```yaml
logger:
  default: info
  logs:
    custom_components.idm_heatpump: debug
    pymodbus: debug
```

Look for in the logs:
- `idm_heatpump` - integration-specific messages
- `Modbus read error` - Modbus read errors
- `Modbus write error` - Modbus write errors
- `Decode failed` - Register decoding errors

## Export Diagnostics Data

1. Go to **Settings → Devices & Services**
2. Click **IDM Heatpump**
3. Click **Download diagnostics**
4. Attach the file to your [bug report](https://github.com/Xerolux/idm-heatpump-hass/issues/new?template=bug_report.md)

The export includes the installed integration, `idm-heatpump-api`, and
`pymodbus` versions. They are also visible on the **IDM Heatpump API version**
diagnostic sensor.

## Bug Report Checklist

Please include:

- Heat pump model and Navigator/controller model.
- Firmware version from the diagnostics export.
- Home Assistant version, integration version and `idm-heatpump-api` version.
- Active heating circuits, zone modules, PV, Solar, ISC and Cascade flags.
- The redacted diagnostics export.
- Relevant log lines around the first error.
- Whether the problem is read-only, a failed write, an unavailable register or an unexpected value.

Do not include private IP addresses, hostnames, serial numbers, installer/customer data or unredacted network details.

## 👩‍💻 For Developers (Mock Tests)

Please **never** run write operations on Modbus (`write_register`) live against a real heat pump when testing code changes to the base logic. Instead, use our mock tests in `custom_components/idm_heatpump/tests/test_modbus_client.py` via `pytest` to test decoding (`decode_value`) and encoding (`encode_value`) without risk.

## Common Errors and Solutions

| Problem | Solution |
|---------|----------|
| Hostname not found | Correct DNS/name or use the heat pump IP |
| Connection refused | Enable Modbus TCP and verify port 502 |
| Connection timeout | Check IP, power, firewall, VLAN and routing |
| No valid register response | Check slave ID, proxy target and Modbus permission |
| Web PIN rejected | Re-enter the local PIN in Reconfigure or clear it |
| Integration won't start | Read the categorized log message and download diagnostics |
| Incorrect temperatures | Check register mapping, report bug |
| Write failed | Register writable? Note EEPROM warning |
| All entities "unavailable" | Navigator reachable? Modbus TCP enabled? |
