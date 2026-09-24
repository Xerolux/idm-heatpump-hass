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

After entering the connection details, choose a guided setup depth:

| Depth | What the wizard asks |
|-------|---------------------|
| Standard | Feature selection, required sensors and safe defaults |
| Advanced | The same features plus common intervals, thresholds and tuning |
| Expert | The same features plus every available transport and forwarding setting |

Each depth offers the same set of functions. Select only the functions you want
to change; each selected function opens a short page for its switch and any
needed sensor, circuit or group mapping. A final confirmation saves the
configuration and reloads the entry. Settings from a deeper mode remain saved
when you later choose a simpler mode. You can switch depth at any time through
Reconfigure > Features. Reconfigure > Connection changes the host, web access
and Modbus proxy. Existing options remain in place if their function was not
selected in the wizard.

When newly enabling beta features, an additional acknowledgement page appears
before saving. It is separate from the ownership confirmation required by the
automatic DHW manager and comfort schedule.

### Feature profile

The **Feature profile** controls optional IDM-specific entities:

| Profile | Enabled functionality |
|---------|-----------------------|
| `iDM Smart Energy & Comfort` | Calculated COP and deviation sensors, compressor cycle analysis, persistent energy/COP/cost statistics, short-cycle detection and DHW boost controls; optional health and comfort features |
| `Vanilla` | Core IDM register entities, climate controls, water heater, diagnostics and configured web data |

The Smart profile is enabled by default to preserve the complete existing
integration behavior. Vanilla is useful when only the original controller
values and controls should be exposed. Switching profiles reloads the entry;
optional entities may be removed or recreated, while core entity IDs remain
unchanged.

The profile does not automatically write energy values or modify the heating
curve. External PV, battery, room-temperature, humidity and storage forwarding
remain separate opt-in functions and are documented in their own sections.

Smart also exposes persistent energy, COP, cost, CO₂ and optional PV
self-consumption statistics when the required power registers are available.
The electricity price and CO₂ factor are configured locally in the options;
they are not fetched from an external service.

When **Device hierarchy** is enabled, optional entities are kept in their own
logical groups: **iDM Analytics**, **iDM Health Monitor**, and **iDM Comfort**.
Existing controller, heating-circuit, warm-water and web entities remain in
their existing groups and retain their entity IDs.

### External power source mapping and forwarding

The **External power forwarding** category maps existing Home Assistant sensors
to PV surplus, PV production, house consumption, battery charge/discharge,
battery SOC and electric-heater power. The forwarding switch is off by default.
When enabled, valid values are written to the corresponding IDM GLT registers
on source changes and periodically (default: 60 seconds).

Power sensors must report W, kW or MW; forwarding converts to kW. Battery SOC
must be a whole percentage from 0 to 100. The battery sign can be kept or
inverted to match the source convention. Invalid or out-of-range values are
skipped; an unavailable source does not write a fallback zero. Blank fields
leave their registers untouched. Do not have another energy manager write the
same register at the same time.

The saved mapping also supplies the optional PV estimate and automatic DHW
manager. They can read an existing mapping while forwarding is off. The
current guided wizard shows the mapping page only when forwarding is enabled;
it does not yet provide a separate source-selection page for read-only use.
See [external power setup](Installation-and-Setup#automatic-external-power-forwarding-from-home-assistant)
for controller preparation and field mappings.

### Optional PV energy manager

The **automatic PV surplus DHW charging** option is off by default. It only
starts the existing safe DHW boost when the selected PV surplus is available.
It requires the external power source mapping and the explicit confirmation
that Home Assistant is the only DHW controller. This is an ownership
declaration, not automatic detection of Smartfox, openWB or another controller.
Disable competing DHW control before confirming it.

Missing, unavailable or invalid source values fail closed. The manager does not
write GLT energy registers and does not alter normal heating, the heating curve
or the electric heater. Tariff, weather and heating preheat controls are not
enabled by this option. A selected tariff sensor changes cost accounting only;
automatic price-based heating control is not implemented. See
[Smart Energy & Comfort](Smart-Energy-and-Comfort#optional-pv-surplus-dhw-automation)
for source precedence, defaults and the behavior of an already running boost.

### Optional comfort schedule and advisers

The comfort schedule is disabled by default and requires the explicit
single-controller confirmation. It writes only the selected circuit's room
temperature target inside the configured daily window and restores the prior
target afterwards if the current value still matches the scheduled target.
A manual change made while the schedule is active is left untouched. Advanced
mode offers up to 16 daily windows across configured circuits, including
overnight windows, in Home Assistant's configured timezone. See
[schedule examples](Smart-Energy-and-Comfort#comfort-schedule-and-read-only-advisers).

The heating-curve assistant and weather-preheat adviser are read-only. They
publish recommendations without changing any IDM register. The weather adviser
requires a selected Home Assistant `weather` entity. All comfort entities are
shown under **iDM Comfort** when device hierarchy is enabled.

### Optional iDM Health Monitor

The **iDM Health Monitor** is disabled by default and adds read-only diagnostic
entities. It checks communication failures, compressor start frequency, low
current COP, DHW temperature deviation and implausible temperature values. The
`iDM health report` sensor exposes `ok` or `problem` and lists active checks in
its attributes. It does not change any heat-pump setting.

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

### KNX Bridge

The KNX bridge is optional and disabled by default. When enabled, the
integration publishes the IDM KNX communication objects on a KNX bus and
accepts commands from it — replacing the Weinzierl KNX IP BAOS gateway
module IDM sells for the Navigator. It drives the Home Assistant
[KNX integration](https://www.home-assistant.io/integrations/knx/), which
must be set up: gateway, tunnelling and KNX Secure come from there.

| Option | Description | Default |
|--------|-------------|---------|
| Enable KNX bridge | Turns the bridge on and shows the group address step | off |
| Send values to KNX | Publish a telegram whenever a value changes | on |
| Accept commands from KNX | Write incoming values on writable objects into the heat pump | on |
| Answer read requests | Reply to a KNX read request with the current value | on |
| Full resend interval | Resend every value periodically; 0 sends only on change | 0 seconds |
| Change tolerance | Minimum change before a numeric value is sent again | 0.1 |
| Base group address | Object numbers are added to this address | `8/0/0` |
| Object groups | Which parts of the catalogue take part | all |
| Group address overrides | `register = address` per line for objects addressed differently | empty |

Group addresses are derived as `base address + IDM object number`, so with
the default base object 1 (outdoor temperature) lands on `8/0/1` and object
222 (heating circuit A mode) on `8/0/222`. The whole catalogue fits inside
one main group. Use `idm_heatpump.export_knx_group_addresses` to get the
full table for your controller.

Full details, including the object groups and datapoint types, are in
[KNX Bridge](KNX-Bridge).

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
4. Choose the action you need:
   - **Features** opens Standard, Advanced or Expert setup to change selected
     feature settings without changing unselected categories.
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

Use **Configure** or **Reconfigure → Configure features** to edit the complete
options form, including scan interval, circuits, zones, Smart Energy & Comfort,
health monitoring, forwarding, and automatic controls. Saving reloads the
integration so optional entities follow the selected settings. Newly enabled
beta features require an explicit acknowledgement before saving.

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
- `home_assistant_version`: installed Home Assistant Core version
- `python_version`: Python runtime version

The same version set is included in downloaded diagnostics. The integration and
its direct dependency versions are also logged when the entry starts. This is the authoritative way
to check the runtime; the version pinned in
`custom_components/idm_heatpump/manifest.json` describes what
should be installed, while the sensor shows what is actually loaded.

### Integration and API release pairing

This project has two independently versioned packages:

| Package | Current tested version | When it needs a new version |
|---------|------------------------|-----------------------------|
| Home Assistant custom integration | `0.17.0-beta.2` (previous stable: `0.16.2`) | Integration code, config flow, diagnostics, entities or bundled user documentation changes |
| Connection library | `modbus-connection==4.12.1` | Transport contract, connection lifecycle or error semantics change |
| Direct socket backend | `tmodbus[async-serial]==0.6.2` | Wire/backend implementation changes |
| Python register/web library | `idm-heatpump-api[web]==2.4.0` | Register schema, encoding/decoding, batching, model detection, write safety or reusable web-client implementation changes |

The manifest lists the tested runtime in this order:
`modbus-connection==4.12.1`, `tmodbus[async-serial]==0.6.2`,
and `idm-heatpump-api[web]==2.4.0`. The first two packages own the direct
socket. `idm-heatpump-api` remains responsible for IDM-specific device logic
and owns its exception hierarchy; the integration no longer installs
pymodbus. `4.12.1` is the version of `modbus-connection`, not an IDM integration
version. The transport was first shipped by IDM integration beta
`0.11.0-beta.1`.

The adapter is implemented, covered by automated tests and live-verified on a
Navigator 10. Its redacted
diagnostics report `source: modbus_connection.tmodbus`, `owns_socket: true` and
`supports_shared_connection: false`. Navigator 2.0/Pro coverage and an
intentional connection-loss/reconnect test remain open; real-hardware writes
stay out of scope unless explicitly authorized. IDM Heatpump is a custom
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

## Experimental AI adviser (upcoming)

The experimental adviser provides daily/weekly reports and explanations of health and efficiency. It is off by default and has no plant control tools or voice exposure. Ollama is local; v0.17.2-b10 adds separately consented OpenAI and Z.ai reports with bounded requests. See [setup, report actions, data coverage and limitations](Experimental-AI-Adviser).
