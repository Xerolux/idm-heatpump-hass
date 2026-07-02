# Troubleshooting

## Connection Problems

### "Connection failed"

- Check the **IP address** of the IDM Navigator
- Make sure **Modbus TCP** is enabled on the Navigator
- Check if **port 502** is reachable (firewall)
- Ping the IP address: `ping <ip-of-navigator>`

### Connection drops

- Check the network connection (LAN cable recommended)
- Increase the scan interval (e.g., to 30 seconds)
- Enable debug logging (see [Configuration](Configuration))
- The integration automatically optimizes Modbus connections to avoid constant reconnections (`self._client.connected` checks). If drops still occur, check the stability of your local network or WiFi.

### "No data received"

- Check the **Slave ID** (default: 1)
- Check if other Modbus clients are accessing the same port simultaneously
- Restarting the IDM Navigator may help

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
| Integration won't start | Restart HA, check logs |
| No connection | Check IP, port, firewall |
| Incorrect temperatures | Check register mapping, report bug |
| Write failed | Register writable? Note EEPROM warning |
| All entities "unavailable" | Navigator reachable? Modbus TCP enabled? |
