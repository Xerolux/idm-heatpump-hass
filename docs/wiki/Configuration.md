# Configuration

## Connection Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| **Host (IP)** | IP address of the IDM Navigator | - (required) |
| **Port** | Modbus TCP port | 502 |
| **Slave ID** | Modbus slave ID | 1 |
| **Name** | Integration name (to distinguish multiple instances) | IDM Navigator |
| **Local web PIN** | Optional PIN for local Navigator web supplement data | empty |

Leave the web PIN empty if you want Modbus-only operation. Modbus remains the
baseline path and works without a PIN. Providing a PIN also enables the setup
flow to offer a limited web-only fallback when Modbus is unavailable.

The direct Modbus socket is local to this integration and uses
`modbus-connection` with the tmodbus backend. Each config entry owns its own
connection; Home Assistant central cross-entry sharing is not currently
available.

## Options

The Home Assistant form groups settings into four areas so the common choices
stay easy to scan:

- Core settings: scan interval, unused entities, heating circuits, and zones
- Optional features: technician codes, cascade, and web supplement data
- External room temperatures: forwarding interval and tolerance
- Advanced Modbus settings: response timeout and retries (collapsed by default)

### Scan Interval

The scan interval determines how often registers are polled.

| Value | Recommendation |
|-------|---------------|
| 10 seconds | For active monitoring (default) |
| 30 seconds | Balanced |
| 60 seconds | For quieter systems |

### Web Supplement Data

The integration can optionally read additional local Navigator web data through
`idm-heatpump-api`. This is read-only and additive. It is used for values such
as Navigator generation, software version, heat pump model, selected Web UI
diagnostics, and Navigator 10 infosystem notifications.

| Option | Description | Default |
|--------|-------------|---------|
| Web supplement data | Enables the optional local web poll; it becomes active only with a valid PIN | on |
| Web supplement interval | Separate polling interval for web data | 30 seconds |
| Web host | Optional separate host for the Navigator web interface, useful when Modbus goes through a proxy | Modbus host |

Important behavior:

- If no PIN is configured, no web client is created and the integration stays in
  Modbus-only mode.
- During setup, reconfiguration and repair, the Modbus model is used only to
  choose which local web protocol to try first. If that attempt fails, the
  other supported protocol is also tested. The protocol that actually succeeds
  is stored with the config entry.
- During normal polling, the successful authenticated client is reused. If its
  session expires or the connection fails, the client is closed and the same
  known protocol is rebuilt immediately. The other Navigator generation is not
  probed during routine runtime recovery.
- After replacing the Navigator, changing the web endpoint or making a firmware
  change that alters the local interface, run **Reconfigure → Change connection
  settings** so protocol detection can run again.
- If the PIN is wrong during setup or reconfiguration, the form shows the PIN
  error immediately. After a Modbus failure, the PIN can be corrected directly
  in the recovery form without restarting setup.
- If the web interface is unreachable later, Modbus polling continues.
- Web polling runs separately and starts slightly after Modbus polling so both
  protocols do not hit the controller at the exact same moment.
- Modbus register values always have priority. Web sensors are only created for
  extra values or values without an existing Modbus entity. Web model/firmware
  metadata may complete an unknown Modbus result, but a definite family
  conflict is ignored.
- If a Modbus proxy is used, enter the proxy IP as **Host** and the original
  heat pump IP as **Web host** so the local Navigator web interface can still
  be reached.

Navigator 2.0 uses a local HTTP/CSRF login; Navigator 10 and Navigator Pro use
the Navigator-10 WebSocket login family. See [Local Navigator Web
Interface](Local-Web-Interface) for the complete detection and recovery state
machine.

### Room Temperature Forwarding

Room temperature forwarding is optional and disabled by default. When enabled,
the integration can forward selected Home Assistant temperature sensors to the
IDM external room temperature registers of the active heating circuits, for
example `hc_a_ext_room_temp`.

| Option | Description | Default |
|--------|-------------|---------|
| Room temperature forwarding | Enables forwarding for selected circuits | off |
| Forwarding interval | Periodic refresh interval for selected room temperatures | 300 seconds |
| Forwarding tolerance | Minimum change before a repeated value is written again | 0.2 °C |
| Sensor per heating circuit | Home Assistant temperature entity to forward | empty |

Important behavior:

- Values are written on sensor state changes and also refreshed periodically.
- Invalid, unavailable, non-numeric or out-of-range values are skipped.
- Leaving a circuit without a selected sensor keeps that circuit untouched.
- This feature writes Modbus values. Use sensors that represent the actual room
  temperature you want the heat pump to see.

### External Humidity Forwarding

External humidity forwarding is optional and disabled by default. When
enabled, the integration forwards one selected Home Assistant humidity sensor
to the global IDM GLT humidity register (`ext_humidity`). Unlike room
temperature, humidity has no per-heating-circuit register, so only a single
sensor can be selected.

| Option | Description | Default |
|--------|-------------|---------|
| Humidity forwarding | Enables forwarding of the selected sensor | off |
| Forwarding interval | Periodic refresh interval | 300 seconds |
| Forwarding tolerance | Minimum change before a repeated value is written again | 2.0 % |
| Humidity sensor | Home Assistant humidity entity to forward | empty |

The same behavior notes as room temperature forwarding apply: values are
written on state changes and refreshed periodically, invalid or out-of-range
values are skipped, and leaving the sensor field empty disables forwarding.

### External Storage Temperature Forwarding

External storage temperature forwarding is optional and disabled by default.
When enabled, the integration forwards up to four selected Home Assistant
temperature sensors to the fixed IDM GLT storage registers: heat storage
(`glt_heat_storage_temp`), cold storage (`glt_cold_storage_temp`), and DHW
storage bottom/top (`glt_dhw_temp_bottom` / `glt_dhw_temp_top`).

| Option | Description | Default |
|--------|-------------|---------|
| Storage temperature forwarding | Enables forwarding for selected registers | off |
| Forwarding interval | Periodic refresh interval | 300 seconds |
| Forwarding tolerance | Minimum change before a repeated value is written again | 0.5 °C |
| Sensor per storage register | Home Assistant temperature entity to forward | empty |

The same behavior notes as room temperature forwarding apply: values are
written on state changes and refreshed periodically, invalid or out-of-range
values are skipped, and leaving a register's field empty keeps it untouched.

### Heating Circuits

Select the active heating circuits (A through G). Only enabled circuits create entities in Home Assistant.

### Zones

Specify the number of zone modules (0–10) and the active rooms per module. The integration supports up to 8 rooms per zone; 6 is the API default for current Navigator 10 hardware. Configure only physically present rooms to avoid unnecessary individual room-mode validation traffic.

### Technician Level Codes

Enable this optional feature to add two sensor entities that display the current
access codes for *Fachmann Ebene 1* and *Fachmann Ebene 2* on the IDM Navigator.
The feature is disabled by default.

| Sensor | Description |
|--------|-------------|
| `sensor.{name}_fachmann_ebene_1` | Current access code for technician level 1 |
| `sensor.{name}_fachmann_ebene_2` | Current access code for technician level 2 |

The sensors update every minute and can be used in a Home Assistant dashboard or
notification. They are integration-provided helper sensors rather than Modbus
register values, so they do not appear in the Modbus register catalog.

Treat both sensor states as sensitive access information. Enable them only when
needed, restrict dashboard visibility, and do not include their values in public
screenshots, support posts, notifications to shared devices or logs. The
calculation method is intentionally not part of the public documentation.

### Room Names

For each room in each zone, you can assign a custom name. These names are used as entity names in Home Assistant.

## Reconfiguration

1. Go to **Settings → Devices & Services**
2. Click **IDM Heatpump**
3. Click **Reconfigure**
4. Choose one of the two actions:
   - **Change connection settings** updates host, port, slave ID, local web PIN,
     and proxy settings after validating them.
   - **Test current connection** runs a read-only check against the saved
     settings. It does not save anything and never writes Modbus registers.

The test reads a known IDM Modbus register. If that fails, a short DNS/TCP
check identifies the network failure more precisely. If a local web PIN is
configured, it also verifies the Navigator web endpoint and authentication.
The result distinguishes hostname, refused connection,
timeout, unreachable endpoint, missing Modbus response, invalid PIN, and web
interface errors. Submit the result form again to repeat the test.

A wrong web PIN is rejected directly when changing the connection. Leaving it
empty keeps the entry in Modbus-only mode.

If Modbus fails while a valid web PIN is present, the flow offers web-only mode
and clearly lists its limitations. Choosing **Retry Modbus connection** returns
to the correct reconfiguration form; switching back from web-only mode clears
the fallback flag after a successful Modbus check. Existing heating-circuit,
zone and advanced Modbus options are preserved while web-only mode is active,
so they are available again after Modbus is restored.

Use **Configure** for scan interval, heating circuits, zones, technician codes,
optional web supplement settings, and optional room temperature forwarding.

### Advanced Modbus options

The collapsed **Advanced Modbus settings** section also provides power-user
controls in addition to timeout and retry settings:

- **Pause between requests (0–0.5 seconds)** is the minimum gap the connection
  keeps between two Modbus requests, measured from the end of one request to
  the start of the next. `0 s` (the default) sends requests back-to-back, as
  every release before this option did. Raise it when the controller or a
  Modbus gateway answers "device busy", drops requests, or times out under a
  dense request stream. The pause applies to every request, so a full polling
  cycle takes correspondingly longer: with roughly 40 batches, `0.1 s` adds
  about 4 seconds per cycle. Start at `0.05 s`.
- **Pause after connect (0–5 seconds)** is awaited once after the link is
  established, before the first request is sent — on the first connect and on
  every reconnect, not per request. `0 s` (the default) sends immediately.
  Raise it for gateways that accept a connection before they are ready to
  answer.
- **Polling jitter (0–20%)** adds a random delay of up to the selected
  percentage of the scan interval to every poll. This spreads network and
  controller load when several heat pumps start polling at the same time.
  `0%` disables jitter.
- **Extended communication diagnostics** creates diagnostic entities for the
  last successful poll, poll duration, consecutive failures, and the active
  register count. Total polls and failures are included as attributes and in
  downloaded diagnostics.
- **Write cooldown (0–600 seconds)** applies per register. A second write to
  the same register during the configured interval is rejected without sending
  anything to the heat pump, and Home Assistant reports the remaining wait.
  `0` completely disables this protection; changing it is at the user's own
  risk. Different register addresses do not block one another.

The general write cooldown is independent of the API's EEPROM protection.
EEPROM-sensitive registers can therefore still be subject to the separately
configured EEPROM interval and its safety rules.

## Runtime and API versions

IDM Heatpump is a Home Assistant custom integration rather than an add-on.
The integration creates a diagnostic sensor named **IDM Heatpump API version**
(German: **IDM-Heatpump-API-Version**). Its state is the actually installed
`idm-heatpump-api` distribution version. The sensor attributes also show:

- `integration_version`: installed custom integration version
- `modbus_connection_version`: installed connection-library version
- `tmodbus_version`: installed direct socket-backend version

The same version set is included in downloaded diagnostics and written to the
Home Assistant log when the config entry starts. This is the authoritative way
to check the runtime; the version pinned in
`custom_components/idm_heatpump/manifest.json` describes what
should be installed, while the sensor shows what is actually loaded.

### Integration and API release pairing

This project has two independently versioned packages:

| Package | Current tested version | When it needs a new version |
|---------|------------------------|-----------------------------|
| Home Assistant custom integration | `0.15.0` (previous stable: `0.14.1`) | Integration code, config flow, diagnostics, entities or bundled user documentation changes |
| Connection library | `modbus-connection==4.10.0` | Transport contract, connection lifecycle or error semantics change |
| Direct socket backend | `tmodbus[async-serial]==0.6.1` | Wire/backend implementation changes |
| Compatibility library | `pymodbus>=3.12.1,<4.0` | Temporary compatibility with API imports and exception types |
| Python register/web library | `idm-heatpump-api[web]==2.0.0b1` | Register schema, encoding/decoding, batching, model detection, write safety or reusable web-client implementation changes |

The manifest lists the tested runtime in this order:
`modbus-connection==4.10.0`, `tmodbus[async-serial]==0.6.1`,
`pymodbus>=3.12.1,<4.0`, and `idm-heatpump-api[web]==2.0.0b1`.
The first two packages own the direct socket. `idm-heatpump-api` remains
responsible for IDM-specific device logic; pymodbus is temporarily retained
because that API still imports it. `4.8.1` is the version of
`modbus-connection`, not an IDM integration version. The transport was first
shipped by IDM integration beta `0.11.0-beta.1` and is now part of the stable
`0.11.x` line.

The adapter is implemented and covered by automated tests. Its redacted
diagnostics report `source: modbus_connection.tmodbus`, `owns_socket: true` and
`supports_shared_connection: false`. Read-only validation of this new transport
path on real Navigator hardware is still pending; real-hardware writes remain
out of scope unless explicitly authorized. IDM Heatpump is a custom
integration, not a Home Assistant add-on.

## Debug Logging

Enable extended logging for troubleshooting:

```yaml
logger:
  default: info
  logs:
    custom_components.idm_heatpump: debug
```

## EEPROM Notice

Certain registers are **EEPROM-sensitive** (88 total). These registers are stored in EEPROM when written and have a limited number of write cycles. The integration warns about excessive writing of these registers.

## BMS Cyclic Writing

Registers 1696 and 1698 (BMS temperature requests) must be written cyclically every 10 minutes to remain active. The switch entities for BMS requests handle this automatically.
