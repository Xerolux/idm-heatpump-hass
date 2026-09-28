# Navigator protocol analysis

This page documents confirmed findings from the static analysis of the Navigator
client and from the read-only validation of a Navigator 10 installation. It is
not a complete protocol specification.

## Confirmed local communication

- Modbus TCP: port `502`, unit/slave ID `1`.
- Local HTTP interface: port `80`.
- Navigator 10 WebSocket: port `61220`.
- WebSocket authentication through the local PIN as `auth_code`.
- Navigator 2.0 web access: local HTTP on port `80`, form login with a CSRF
  token and the local network code.
- For the implemented web access, Navigator Pro uses the Navigator 10 WebSocket
  variant.
- Web data is delivered as typed values with units or as a translated status.
- Concurrent WebSocket sessions work: on 2026-09-28 a live Home Assistant
  integration poll (one session) and several additional parallel sessions
  (probe, verification, capture proxy) authenticated and answered on the same
  Navigator 10 without interference. This is a one-time observation under
  normal load, not a stress test.

The integration therefore keeps Modbus as the base path and uses the local web
interface only as an optional supplement or fallback. No cloud logins are
required.

## Detection and reconnection

During setup, reconfiguration and repair, the variant Modbus makes most likely
is tried first, and on failure the other local variant is tried as well. Only
the client that actually succeeded is stored. In normal operation that session
is reused. After session or transport errors the same protocol client is rebuilt;
the other Navigator generation is deliberately not activated on a trial basis. A
renewed detection of both variants happens through reconfiguration, or for as
long as no reliable variant has been stored yet.

Details: [Local Navigator Web Interface](Local-Web-Interface).

## Installation validation

The validated installation was detected as **Navigator 10**. The corrected API
detector finds only heating circuit **A** there. The registers of the heating
circuits that are not configured do answer, but they return the sentinel value
`-1.0`.

On this installation the cascade probe at address `1147` answers with the raw
word `FFFF`, that is UCHAR `255`. That value means "not available" and must not
enable the optional cascade register group. As a result the detected map on this
installation dropped from 170 to 153 definitions.

Across 309 read-only batch/single comparisons over 170 definitions and 45 groups
there was no raw value deviation. The reported values `254`, `255` and `-1.0`
were register-specific not-available sentinels. Room operating modes are still
secured individually, because other Navigator 2.0 reports have shown plausible
but deviating batch values.

The local web client returned 60 normalized values, among them temperatures,
pressures, runtimes, energy amounts, status values and the software version. No
PINs, tokens, IP addresses, serial numbers, account IDs or raw responses are
stored in the repository.

## Findings from the EXE analysis

Identified were several Navigator generations, UDP discovery for older variants,
further TCP/TLS communication paths, live events such as `NC_CHANNELDATA`, typed
channel values, as well as dynamic channels, parameters, rooms, errors,
translations and virtual channels.

A capture session on 2026-09-27 additionally decoded the configuration database
of the Windows service tool ("IDM Smart Navigator" 2.3.118). Its files under
`%APPDATA%\NAVudpClient` are obfuscated with a 3-byte XOR key; the decoded
tables contain:

| Table | Entries | Content |
|---|---:|---|
| channels | 306 | measurement channels: alias, German description, unit, bitmask/state lists, firmware signal names |
| parameters | 2329 | controller parameters (`hparam`/`iparam`/`vparam`) with defaults, per-machine defaults and selection values |
| errors | 2005 | error codes with component and error-kind enums plus user/service descriptions (see next section) |
| topics | 46 | view grouping of the channels |
| translations | 16392 | enum texts; German is complete, English is not shipped for the device enums |

The UDP live protocol of the older modules (ports 20001, 20999 and 54551 named
in the binary) is not answered by a Navigator 10 web module; those ports belong
to the historical UDP live streaming of older NAV generations. Device discovery
in the current apps runs through the myIDM cloud, not through local UDP
broadcasts.

The concrete UDP wire format (scalings, byte orders, special types such as
`UDP_FUNCFLOAT`) remains undetermined; no integration code depends on it.

## Error-code database (service tool capture, 2026-09)

The decoded service tool configuration contains the complete vendor error-code
database. The numbering:

- `0` — "no error" placeholder;
- `20..999` — controller messages and errors. This is the range the Modbus
  `internal_message` register reports (020–999); 366 codes exist there, 343 of
  them with German component texts;
- `10000+` — device-side error blocks: 20000 display, 30000+ outdoor unit,
  inverter, fan, EVD, Carel peripherals and cascade devices (1637 codes).

Each entry carries the affected component (`text`, for example
`Wärmepumpenvorlauf`) and, where the vendor has one, the error kind (`info`,
for example `Maximaltemperatur`). `"{text} {info}"` reproduces the controller
display wording. 1160 entries carry German user descriptions and 1346 carry
German service remediation texts; English does not exist for these enums.

**Validation against the integration:** every one of the 90 exact codes of the
hand-collected `internal_messages.py` table exists in the database with a
semantically identical text, and the composed wording matches (code 20
`Wärmepumpenvorlauf Maximaltemperatur`, code 100 `Außentemperatur` +
`Kurzschluss`). The numbering is therefore confirmed to be the same namespace
the Modbus register reports.

Since `idm-heatpump-api` 2.6.0 the database is packaged as read-only metadata
(`get_error_code_info()`), regenerable through the API repository's
`scripts/generate_error_codes.py`. The capture itself — which also contains
PINs, serial numbers and network data — is never committed. Six entries with
sub-error-bit breakdowns (`extras`) exist in the source and are dropped from
the packaged form.

## Deliberately not implemented

- myIDM cloud login, cloud polling and installation management
- firmware, configuration and SD card writes
- fixed UDP ports or guessed binary packets
- guessed channel meanings, units or scaling factors
- undocumented Modbus writes

Further protocol work needs anonymized local responses or recordings with the
channel ID, name, unit, scaling, data type, room assignment and live event.
Before committing, PINs, tokens, network data, serial numbers and owner data must
be removed.

## Note on the KNX example project file (.knxproj)

Occasionally an IDM-specific ETS project file is available (named something like
`KNX_NAVIGATOR_2_0_Beispielprojekt.knxproj`). That file describes the **KNX
gateway** (typically a Weinzierl `KNX IP BAOS 774`) and the communication objects
enabled on it. It is **not** a reliable source for IDM model or firmware
detection.

### What the `.knxproj` file does NOT provide

- no IDM heat pump model
- no IDM Navigator generation (Navigator 2.0 / 10 / Pro)
- no IDM firmware or software version
- no IDM serial number

The metadata it contains, such as `ApplicationVersion="16"`,
`VersionNumber="256"`, `MaskVersion="MV-07B0"`, `SerialNumber="KNX IP BAOS 774"`,
the project name (`"KNX Navigator 2.0"`) and device names
(`"IDM NAV2.0 KNX IP Gateway"`), identifies the KNX gateway and the ETS project
only. It must **never** be adopted as IDM firmware or an IDM model. Free-form
labels such as "Navigator 2.0" in the project name are no substitute for a Modbus
or web detection.

### What the `.knxproj` file does provide

The enabled communication objects are a valuable **completeness and naming
reference**. A corrected full evaluation of that example project file (as of
2026-07-27, 726 active objects) was cross-checked on the same day by a strictly
read-only live check on a Navigator 10 installation. All hypothetical assignments
were confirmed:

| KNX object | ETS name (partly with typos) | API register | Address | Type | Live value |
|---:|---|---|---:|---|---:|
| 995 | Photovotaik Surplus | `pv_surplus` | 74 | FLOAT kW | plausible |
| 996 | Photovotaik current | `pv_production` | 78 | FLOAT kW | plausible |
| 992 | Home Consumption | `house_consumption` | 82 | FLOAT kW | plausible |
| 993 | Battery Discharge | `battery_discharge` | 84 | FLOAT kW | plausible |
| 994 | Battery state of charge | `battery_soc` | 86 | **INT16 %** | `−1` = sentinel |
| 997 | Total electric output | `power_consumption_hp` | 4122 | FLOAT kW | plausible |
| 998 | Current thermal output | `thermal_power_flow_sensor` | 4126 | FLOAT kW | plausible |
| 999 | Total thermal energy | `total_heat_energy` | 4128 | FLOAT kWh | plausible |

Additionally confirmed: `electric_heater_power` (address 76) and
`pv_target_value` (address 88) are contained in the API, but are not active in
the example project.

### Important rules of interpretation

- **KNX object number ≠ Modbus address** (the numbers 992–999 are not addresses).
- **KNX DPT ≠ Modbus data type** (for example, `battery_soc` is a single signed
  INT16 register, not a two-register float).
- **KNX write flag ≠ Modbus write permission.** An enabled write flag only means
  that the object accepts telegrams from the bus; it is no evidence of a safe
  Modbus write.
- **`battery_soc` sentinel**: the raw value `65535` (unsigned 16-bit) has to be
  decoded as signed `−1` and means "not available". A UINT16 decoding would
  wrongly display `65535 %`.

### Consequence for this integration

Model and firmware detection stays exclusively with Modbus (`detect_model()`) and
the optional local web supplement. There is no code path that evaluates ETS or
BAOS metadata. The corresponding regression tests are in
`tests/test_knx_evidence.py`. Adding new registers or write services is not
justified from this file alone; see the section "Deliberately not implemented".

## IDM controller ID spaces

On an IDM Navigator controller, one physical quantity is addressed by up to
**three independent ID spaces**. These spaces overlap semantically, but they are
**not** 1:1, and the numbers are deliberately different. They must never be used
as interchangeable addresses.

| ID space | Used by | Heating example | PV surplus example |
|---|---|---:|---:|
| **Modbus register** | external protocol, through `idm-heatpump-api` | 1748 | 74 |
| **Internal stats ID** | statistics engine, SD card (`stats/amount/<id>_v1.csv`, `last_values.json`) | 477 | 495 (cumulative: 100495) |
| **KNX communication object** | ETS example project (Weinzierl BAOS 774) | 400 | 995 |

### What that means in practice

- **KNX object number ≠ Modbus address** (already stated in the KNX section).
- **Internal stats ID ≠ Modbus address.** Example: heating energy has the
  internal stats ID `477`, but the Modbus address `1748`. An error message of the
  form "Stat 477" on the controller display therefore corresponds to the Modbus
  value at address `1748`, and not to a gap in the Modbus address space.
- **Internal stats ID ≠ KNX object number.** Example: PV surplus has the internal
  ID `495`, but object number `995` in the KNX example project.
- **Cumulative stat IDs** in the 100000 range (for example `100495`) are the
  daily totals of the underlying series (`495`), not a physical quantity of their
  own.

### Syscount cross-reference (energy registers)

The file `syscount.ini` on the SD card contains the semantic names of the
cumulative counters. This integration keeps a cross-checked mapping table in
[`custom_components/idm_heatpump/controller_stats_reference.py`](https://github.com/Xerolux/idm-heatpump-hass/blob/main/custom_components/idm_heatpump/controller_stats_reference.py).
It is documented incompletely on purpose: only registers cross-checked through at
least two of the three ID spaces are included.

| Syscount key | Stats ID | Library register | Modbus | KNX object | Meaning |
|---|---:|---|---:|---:|---|
| `ZQHPH` | 477 | `energy_heating` | 1748 | 400 | Heat quantity, heating (heat pump) |
| `ZQHPP` | 471 | `energy_dhw` | 1754 | 402 | Heat quantity, domestic hot water / priority |
| `ZQHPD` | 472 | `energy_defrost` | 1756 | 403 | Heat quantity, defrost |
| `ZQHPC` | — | `energy_cooling` | 1752 | 401 | Heat quantity, cooling |
| `ZQELH` | — | `energy_electric_heater` | 1762 | 406 | Heat quantity, electric heating element |
| `ZQHPO` | — | `total_heat_energy` | 4128 | 999 | Heat quantity, total (Nav 10) |
| — | 495 | `pv_surplus` | 74 | 995 | Photovoltaic surplus |
| — | 496 | `pv_production` | 78 | 996 | Photovoltaic power |
| — | — | `house_consumption` | 82 | 992 | House consumption |
| — | — | `battery_discharge` | 84 | 993 | Battery discharge |
| — | — | `battery_soc` | 86 | 994 | Battery state of charge (INT16, `-1` = n/a) |
| — | — | `power_consumption_hp` | 4122 | 997 | Total electrical power |
| — | — | `thermal_power_flow_sensor` | 4126 | 998 | Thermal power |

### Use in the diagnostics export

The integration's diagnostics export (``Download diagnostics`` on the integration
page) contains the cross-referenced `syscount` key for every known energy
register. That allows a plausibility comparison between the Home Assistant
reading and the controller's own counter without removing the SD card.

### Limits of the finding

This table was collected on a confirmed Navigator 10 installation (firmware
`NAV10_20.24-880-g265e09c4a`). Navigator 2.0 and Pro may use different stats IDs;
the syscount key names, by contrast, should be generic. New entries always
require a cross-check through at least two of the three ID spaces (Modbus +
syscount, or Modbus + KNX).

## SD card structure (Navigator 10)

An SD card from a Navigator 10 typically contains the following usable
structures:

```
/
├── log/raw/<controller_id>/<YYMMDD>.mal   # binary daily logs, proprietary
├── recovery/
│   ├── Backup/config/<YYYY-MM-DD_HHMM>/   # daily 02:00 snapshots
│   └── autosaveconfig_<controller_id>--<id>/config/<YYYY-MM-DD_HHMM>/
└── update/backup/backup<YYYYMMDDHHMMSS>.iup   # firmware backup packages
```

The snapshot of a configuration backup contains, among other things:

| File | Content | Usable for |
|---|---|---|
| `syscount.ini` | cumulative counters (`ZQHPH`, `ZQHPP` etc.) | semantic cross-reference |
| `stats/amount/<id>_v1.csv` | daily time series per stats ID | plausibility comparison |
| `stats/amount/last_values.json` | last cumulative value per stats ID | plausibility comparison |
| `stats/amount/heating.csv`, `priority.csv` | named daily time series | plausibility comparison |
| `stats/energy/ba_energy_hp`, `ba_energy_eh` | binary energy and heating element blocks | structural reference |
| `stats/pv/ba_pv` | binary PV daily time series (9 columns) | structural reference |
| `stats/runtimes/ba_runtimes`, `bivalence_runtimes` | binary runtime statistics | structural reference |
| `zone.ini` | configured zones (`size=0` = none) | detection consistency |
| `heatpump.ini` | error buffer position (no serial!) | _low value_ |
| `frwaparam.ini` | firmware parameters (FRW*/FRWA*) | low value |
| `hparam.ini`, `iparam.ini` | heating/installation parameters | **do not commit** (installation specifics) |
| `errorLogBuffer.ini`, `paramLogBuffer.ini` | error and parameter logs | **do not commit** |

This integration does not read the SD card. The structure above is documented for
support purposes only; when users want to compare values, they can check the
corresponding CSV files manually against their HA sensors.

## Navigator 10 WebSocket – controller catalog

The Navigator 10 web interface speaks a WebSocket protocol on port `61220`. Every
frame has the form `{"controller": "<name>", "command": "<verb>", "data": {...}}`.
Authentication happens through the query parameter `?auth_code=<PIN>` when the
connection is established.

The following table is the result of a strictly read-only live exploration
(`overview`/`detail` only) on a confirmed Navigator 10 installation (firmware
`NAV10_20.24-880-g265e09c4a`, July 2026). It replaces the earlier, incomplete
picture from the static EXE analysis.

### Supported controllers

| Controller | Commands | Meaning |
|---|---|---|
| `status` | `overview` | authorization status (`{"authorized":true}`) |
| `home` | `overview`, `detail` | home screen status (frost protection info, auth active, demo mode, header) and detail data including energy flow (PV, house consumption, grid) |
| `system` | `overview` | system detail block (energy amounts today, type dictionary) |
| `system.freshwater` | `overview` | DHW detail (circulation, StatusInfo, SystemMode, temperatures) |
| `setting` | `detail`, `save`, `execute` | read settings (`detail`), write them (`save`), trigger actions (`execute`) |
| `statistic` | `overview`, `detail` | statistics blocks |
| `cascade` | `overview` | cascade information (empty response on a single-unit installation) |
| `notification` | `overview`, `save` | message overview, message change |
| `authentication` | `overview`, `save` | system information (buffer.systemMode, temperatures, energyflow); level login through `save` with `userlevel` and code |
| `showcase` | `overview` | demo and info sequences |
| `frostprotection` | `overview` | frost protection wizard (only active in a frost situation) |
| `relaytest` | `overview` | relay test wizard (only active in a service situation) |

### `statistic/detail` selectors (live-verified, September 2026)

A strictly read-only frame-by-frame sweep on a live Navigator 10
(jsonVersion 11, firmware `NAV10_20.24`) confirmed the request values:

| `statisticType` | Block | Value keys |
|---|---|---|
| `0` | heat-pump runtimes (`N2_RUNTIMEHEATPUMP`) | `heating`, `priority` (DHW), `defrost` |
| `2` | bivalence/second-stage runtime (`N2_RUNTIMEBIVALENCE`) | `bivalence1` |
| `3` | energy management heat pump (`N2_EMHP`) | — |
| `4` | energy management heating element (`N2_EMEH`) | — |
| `5` | energy flow (`RD_ENERGY_FLOW`) | PV origin/usage groups |
| `6` | heat quantities (`N2_HEATQUANTITIES`) | `heating`, `priority` (DHW) |
| `1` | — | answered `"specified statistic type [1] is not avaiable!"` |

`periodType` selects the aggregation: `0` daily history rows (`data.daily`
with `date`/`idx` per row), `1` today (`data.today` plus `data.typeDict`),
`7` lifetime totals (`data.total`). `statisticSubType` stays `null`. The
`statistic/overview` response enumerates the whole catalog with today's
values and weekly averages per block — including a `N2_WEATHER` category
with four forecast days.

### `status/overview` and `system.freshwater/overview` (live-verified)

`status/overview` answers with `jsonVersion`, `userlevel`, `language`,
`notificationCount`, the controller clock `timestamp` (epoch milliseconds),
`frostProtectionInfo {active, display}`, `network`, `authenticationEnabled`,
`demoModeActive` and `myidmInfo` (account data — never republished).
`system.freshwater/overview` answers with `circulation {active}`,
`statusInfo {status}` (numeric), `systemMode` and `temperatures {top,
bottom}` as decimal strings. Both shapes are parsed defensively by
`idm-heatpump-api` 2.7.0 (`IdmWebStatus` / `IdmWebFreshwater`).

**Sub-controller pattern**: the `system.*` sub-controllers (for example
`system.freshwater`) use `parameterId` instead of `settingId` in the `data`
block. The library currently uses only `setting/detail`, `home/detail`,
`statistic/detail` and `notification/overview`.

**Setting action types** (through `setting/execute`): the SPA code assigns
settings to certain UI components based on their `type` field. Known action types
are `restart`, `actioncode`, `execute`, `relaytest`, `tt1`, `ttw`, `ttboost`.
`execute` is the generic "trigger action" type, which starts the function stored
in the setting on the server side. The "restart display" button, for example, is
implemented as a setting of type `restart` and is triggered through
`setting/save` with the corresponding setting ID.

### Unsupported controllers

The following controller names were tried and were **explicitly rejected as
unsupported** by the Navigator 10 (`provided controller [...] is not
supported!`):

```
controller        firmware         update          upgrade
software          usb              upload          maintenance
system.update     system.firmware  system.software system.usb
does.not.exist    (negative control)
```

### Consequence: firmware update

The Navigator 10 WebSocket interface **offers no update endpoint**. The same is
true for the HTTP interface (port 80, a pure SPA with no server-side update
routes) and for Modbus TCP (port 502). The controller's three local interfaces
cover normal read/write operation, but no firmware operations.

Firmware updates on the Navigator 10 accordingly happen through:

1. **the myIDM cloud portal** (`app.myidm.at`) — the canonical web interface the
   framework calls the "IDM web interface". Push updates usually arrive
   automatically through this channel.
2. **a USB stick** through the controller display's service menu (installer
   level). The integration calculates the time-dependent *installer level* codes
   (L1/L2) and offers them as optional sensors. On the display itself one can
   then look for an "Update" / "Software" / "USB" menu item.

### Exploration notes for support

When users ask about firmware updates, the answer is clear:

- Locally through the web interface or the WebSocket: **not possible**, the
  device rejects all update controllers.
- Cloud (myIDM): the primary update channel.
- USB plus display: the secondary service channel.

Extending the integration with its own update functions is not planned and would
require deliberately including cloud functions (see the section "Deliberately
not implemented").

### Level-0 settingId catalog (read side, live-enumerated September 2026)

A strictly read-only enumeration — only `setting/detail` frames, the same
read the integration performs — probed 2016 candidate IDs across the ranges
700–15100 on a live Navigator 10 (jsonVersion 11, userlevel 0). Exactly eight
settingIds answer for an end user:

| settingId | Name | `type` | Redirect | Content |
|---|---|---|---|---|
| `4740` | `N2_SYSTEM_REBOOT` | **action** | 4488 | restart action (write side, Phase 4 material) |
| `4754` | `N2_SYSTEM_INFO` | info | 4747 | runtimes, switch cycles, software version, myIDM ID, controller online |
| `4768` | `N2_SENSORS` | info | 4761 | 26 sensor values (B-codes) |
| `4775` | `N2_DIGITAL_INPUTS` | info | 4761 | 8 digital inputs |
| `4782` | `N2_ANALOGUE_OUTPUTS` | info | 4761 | 4 analogue outputs |
| `4789` | `N2_DIGITAL_OUTPUTS` | info | 4761 | 14 digital outputs |
| `4824` | `N2_NETWORK_INFORMATIONS` | info | 4747 | network status + myIDM account (private data — never republished) |
| `13259` | `N2_HWS_INFO` | info | 4747 | hot-water-station heat quantities |

The controller distinguishes three error answers, which makes the catalog
trustworthy: `no setting item found for setting id [X]!` (the ID does not
exist), `setting item [X] is not a setting detail item!` (a container/menu
item — 4488, 4747 and 4761 are of this kind), and `setting item [X] is not
accessible!` (exists but is level-gated). The six read IDs the integration
uses today are exactly the six info pages with parseable tables; `4824`
carries only private network data and is deliberately not turned into
entities.

What this enumeration cannot deliver: the **write** half (`setting/save`
payload shapes for editable pages). That still needs the capture session
below — the level-0 read catalog suggests the writable end-user set is small,
since every accessible page on this firmware is of type `info` or a single
`action`.

## Write semantics (static analysis, capture-confirmed September 2026)

The controller serves its web UI (`lighttpd`, Angular SPA) over plain HTTP.
Reading the shipped JavaScript reconstructs the complete write surface the
official UI could send, and a maintainer capture session (2026-09-28, through
the `ws_capture` proxy, harmless reversible actions only) has since
**confirmed the payloads and the response frames live** for the system mode,
a freshwater setpoint, the date/time setting and both notification
acknowledgements.

| Facade method | Frame | Notes |
|---|---|---|
| `saveSetting` | `setting/save {settingId, value}` | sub-controller variant `setting.<x>/save`; the settings page adds `source:"Display"` |
| `executeSetting` | `setting/execute {settingId, value}` | action-type settings (e.g. the `N2_SYSTEM_REBOOT` page 4740) |
| `saveSystemMode` | `home/save {systemMode: {value: N}}` | **operating mode switch**; holiday adds `vacationDays`, `freshwaterActive` |
| `saveSystemFreshwater` | `system.freshwater/save {parameterId, value}` | e.g. tap-temperature dialog writes a °C number; `FW027`/`FW028` are re-sent by the SPA after 500 ms (firmware quirk) |
| `saveSystemHeatingcircuit` | `system.heatingcircuit/save {parameterId, value}` | per-circuit temperatures/timetables; a copy function sends the full object |
| `saveSystemVentilation` | `system.ventilation/save {parameterId, value}` / full object | |
| `saveChargePoint` | `system.chargePoint/save t` | controller not in the live catalog |
| `saveRoom` | `room/save {roomId, value}` | zone-module room settings |
| `saveIon` | `ion/save {parameterId, value}` | |
| `saveStatus` | `status/save {parameterId, value}` | the status page itself is writable |
| `saveAfw` | `frostprotection/save {itemId, value}` | frost wizard only |
| `saveRelayTestItem` | `relaytest/save {settingId or type, relayId, value}` | service situation only |
| `sendQuitAll` | `notification/save {quitAll: true}` | acknowledge all messages |
| `sendQuit` | `notification/save {code, remindMeLater}` | acknowledge one message |
| `saveAuthentication` | `authentication/save {userlevel: 4, code}` | **technician login, userlevel hardcoded to 4 — never automate** |
| `sendLocalPin` | `authorization/auth {pin}` | the local PIN handshake |
| graph saves | `graph/save {id?, name?, channels?, periodType?, remove?}` | user-side statistics charts |

**Operating mode values — live-confirmed.** The `home/overview` frame
carries the mode state and the controller's own option list: `options:
[-1, 0, 1, 2, 3, 5, 4]` — exactly the Modbus `system_mode` (register 1005)
numbering (0 standby, 1 automatic, 2 away, 3 holiday, 4 hot-water-only,
5 heating/cooling-only; −1 unknown). Switching the mode through the web
therefore sends `home/save {"systemMode":{"value":4}}` and so on. The SPA
uses **read-after-write** (it re-requests the overview after every save)
rather than optimistic state.

**Save responses — capture-confirmed (2026-09-28).** Every save answers
with one frame keyed `<controller>Save` carrying a `note` object;
`setting/save` additionally carries a `redirect` block the SPA follows:

| Request | Response frame (observed live) |
|---|---|
| `home/save {"systemMode":{"value":4}}` | `{"homeSave":{"note":{"text":"value has been saved successfully!","type":"success"}}}` |
| `system.freshwater/save {"parameterId":"FW030","value":49}` | `{"freshwaterSave":{"note":{"text":"value has been saved successfully!","type":"success"}}}` |
| `setting/save` (date/time, ISO-8601 `Z` value) | `{"settingSave":{"note":{"text":"value has been saved successfully!","type":"success"},"redirect":{"command":"overview","controller":"setting","data":{"settingId":"4488"},"reloadDelay":300}}}` |
| `setting/save` on an action-type setting | same envelope, note text `"action has been executed successfully!"` |
| `notification/save {"quitAll":true}` | `{"notificationSave":{"note":{"text":"cancellation has been executed successfully!","type":"success"}}}` |
| `notification/save {"code":"20005","remindMeLater":true}` | same `notificationSave` envelope |

Value formats observed: `systemMode` as a plain number, freshwater
setpoints as plain numbers (`FW030` is the tap temperature in °C), date/time
as ISO-8601 with `Z`, notification `code` as a string. The `note.type` mirrors
the read-side convention (`success`/`danger`), so a rejected write cannot be
mistaken for a confirmed one. Two session observations worth keeping: the
status frame reports `userlevel: 1` once an end-user session has logged in
(an `auth_code`-only connection reports `0`), and a single wrong entry on
the expert-code action (`12503`, `N2_CODE_ENTRY_EXPERT`) did **not** block
the input — it produced an informational `20005 N2_USERLEVELACTIVE`
notification — while repeated attempts block it (documented firmware
behaviour; do not automate).

Phase 4 consequences: `web_only` mode can be built against these confirmed
shapes — mode switch and DHW acknowledgement first — with each write feature
individually validated and authorized.

## Capturing frames yourself (ws_capture)

`idm-heatpump-api` ships a small logging WebSocket proxy for capture
sessions: `scripts/ws_capture.py` (pure standard library, no dependencies).

```
python scripts/ws_capture.py --host <navigator-ip> --pin <SYSLPIN> [--listen-port 61221] [--out ws-capture.jsonl]
```

The proxy listens locally and relays every frame between the browser and the
controller into a JSONL file (`dir` = `c2s`/`s2c`, parsed JSON payloads). The
PIN never appears in the log — it lives only in the handshake URL, which is
redacted. The proxy never fabricates frames: what is captured is exactly what
the official web UI sends.

**Procedure for a capture session (maintainer-operated):**

1. Start the proxy on the machine with browser access to the Navigator.
2. Open the Navigator web UI and point its WebSocket at the proxy instead of
   the controller (browser DevTools → local overrides, or a port-forward of
   61220 to the proxy port). Alternatively record with DevTools' Network tab
   (filter `WS`) — both routes produce equivalent material.
3. Click through every end-user settings page, change a harmless setpoint
   once, acknowledge a message. This is the legitimate way to capture
   `setting/save` / `notification/save` write semantics — the integration
   itself never writes.
4. Stop the proxy, then **sanitize before anything leaves the machine**:
   strip serial numbers, myIDM data, addresses and any remaining identifiers.
   Raw captures stay on the maintainer's machine; only sanitized knowledge
   enters this wiki or the repositories.

## User levels, codes and access parameters

Verified on 2026-09-27 against a second, independent Navigator 10 installation
(web module firmware of June 2026, `jsonVersion` 11), strictly read-only apart
from rejected login attempts:

- The WebSocket knows exactly two levels: **userlevel 0** (end user, unlocked
  by the local network PIN) and **userlevel 4** (technician/expert). The device
  explicitly rejects levels 1–3 ("specified userlevel [n] is not supported!").
- The level login is `authentication/save` with `{"userlevel": 4, "code": …}`;
  a wrong code answers `{"authorized": false}` without dropping the
  connection. Repeated wrong entries block the code input on the controller
  for a while (parameter `N2_USERLEVELINPUTBLOCKED`).
- The time-dependent installer codes L1/L2 that this integration computes are
  valid **only on the controller display's service menu**. Tested on the
  WebSocket: neither the end-user PIN nor correctly computed L1/L2 codes are
  accepted for userlevel 4. The WebSocket technician code is a separate,
  per-installation code (display menu `CODE_ENTRY_EXPERT`), which IDM
  distributes only through its service partners.

Access-relevant controller parameters (from the decoded parameter table):

| Parameter | Meaning |
|---|---|
| `SYSLPIN` | local network code (WebSocket/HTTP PIN); `0` blocks local access |
| `CODE_ENTRY_EXPERT` | technician code entry (display menu, per installation) |
| `SYSSSC` | simple service code (display/older modules) |
| `SYSDPTO` | display PIN timeout |
| `T13_CODE_VOREINST_1` / `T21_CODE_VOREINST_2` | factory presets of the technician code |

**Controller clock:** on the capture installation the controller clock ran
about two hours ahead of local time (most likely a doubly applied
daylight-saving offset). The L1/L2 codes are derived from the time **shown on
the controller display**, not from the querying computer's clock — always
verify the display time first.

Also confirmed in the same session: `setting/detail` without a `settingId`
answers `"data is empty!"`, the `frostprotection` and `relaytest` wizards
answer `"wizard is not available!"` outside their situations, and
`status/overview` reports `userlevel`, `myidmInfo`, the notification count,
`jsonVersion` and the controller clock (`timestamp`).

## myIDM cloud API (reference)

The myIDM cloud (`app.myidm.at`, `www.myidm.at`, `a.myidm.at`) is IDM's canonical
telemetry and control channel. The integration does **not** use it (see
"Deliberately not implemented"), but the following findings were verified in July
2026 through a strictly read-only live login (only `/api/user/login` +
`/api/installation/values`, no `/api/installation/command`) and are documented
here as a reference to make future research easier.

### ⚠️ Legacy API (verified for 2022–2026)

The API documented here is the **old v0 API**, which has been in use since at
least 2018 (Tom Beyer, [beyer.app](https://beyer.app/posts/2018-10-home-assistant-integration-heatpump-idm-terra-ml-complete/))
and was fully reverse-engineered in 2022 by the ioBroker adapter
[`lonestar2001/ioBroker.idm`](https://github.com/lonestar2001/ioBroker.idm). It
**still works as of July 2026**, but it must be assumed that IDM will shut it
down in the medium term in favor of the new OAuth2 API (see below).

### Endpoints (all under `https://www.myidm.at`)

| Endpoint | Method | Purpose | Body (form-urlencoded) |
|---|---|---|---|
| `/api/user/login` | POST | login, session token + installation list | `username=<email>&password=<sha1(password)>` |
| `/api/installation/values` | POST | read the current values of an installation | `token=<token>&installation=<id>` |
| `/api/installation/command` | POST | change the mode (system/circuit) | `token`, `installation`, `command`, `value`, optionally `circuit` |

**Important**:

- `User-Agent: IDM App (iOS)` (or `Android`) has to be set, otherwise the server
  sometimes does not respond.
- The password is sent as a **SHA1 hex hash** (an outdated scheme, no salt, no
  TLS pinning).
- The domain's SSL certificate has historically had chain problems; some clients
  (ioBroker, for example) therefore disable verification.

### `/api/user/login` – response structure

```json
{
  "token": "<64-character hex string>",
  "installations": [
    {
      "id": "64618",
      "name": "<installation name>",
      "config": { ... },
      "nav20": "<bool>",
      "nav20_online": 1,
      "navpro": "<bool>",
      "navpro_online": 0,
      "online": 0
    }
  ]
}
```

The fields `nav20_online` / `navpro_online` are cloud connectivity markers and
**not** a literal Navigator generation — on a confirmed Navigator 10 installation
`nav20_online: 1` is set, apparently because cloud connectivity runs generically
through that channel.

### `/api/installation/values` – response structure

Top-level keys of the JSON response:

| Key | Type | Meaning |
|---|---|---|
| `mode` | string | system mode (for example `icon_12`, `icon_auto`) |
| `state` | string | system status |
| `sum_heat` | string | total heat quantity, for example `"31549.6 kWh"` (with unit!) |
| `temp_outside` | string | outdoor temperature with unit |
| `temp_heat` | string | flow/return with unit |
| `temp_hygienic` | string | hygienic DHW temperature with unit |
| `temp_water` | string | DHW temperature with unit |
| `temp_water_params` | dict | `{default, max, min, value}` for the DHW setpoint |
| `error` | string/int | error count |
| `errors` | list[...] | error details |
| `circuits` | list[dict] | heating circuits (see below) |
| `system_mode_params` | list | available system modes |
| `circuit_mode_params` | list | available circuit modes |
| `solar_mode_params` | list | solar modes (where supported) |
| `online`, `nav20_online`, `navpro_online` | int | connectivity status |

Per circuit (`circuits[i]`):

```
info, mode, sensor_hum, state, temp_forerun, temp_forerun_actual,
temp_params_eco, temp_params_normal, temp_room, temp_room_actual,
temp_room_value
```

Values typically arrive as strings **with a unit suffix** (for example
`"52.7 °C"`), which the client has to strip.

### Mode and state icon mappings

IDM encodes modes and states as icon class names (HTML/CSS strings), not as
numeric values. The following table is the decoded assignment from ioBroker.idm
and Beyer 2018:

**System mode (`mode`)**

| Icon string | Meaning |
|---|---|
| `icon_12` | off |
| `icon_auto` | automatic |
| `icon_3` | domestic hot water / one-off DHW charge |

**System state (`state`)**

| Icon string | Meaning |
|---|---|
| `icon_12` | off |
| `icon_3` | heating for DHW |
| `icon_5` | heating |

**Circuit mode (`circuits[i].mode`)**

| Icon string | Meaning | numeric (for `/command`) |
|---|---|---|
| `icon_12` | off | 0 |
| `icon_24` | time program | 1 |
| `icon_21` | normal | 2 |
| `icon_11` | eco | 3 |
| `icon_10` | manual heating | 4 |
| `icon_1` | manual cooling | 5 |

**System mode values for `/api/installation/command` (`command=system_mode`)**

| Value | Meaning |
|---|---|
| 0 | off |
| 1 | automatic |
| 2 | domestic hot water |
| 3 | one-off domestic hot water (button character; jumps back to automatic) |

### Data freshness and consistency

The cloud data is **30–60 minutes old**, because the heat pump only uploads to
the cloud at that interval. A plausibility comparison against local Modbus reads
(July 2026, Navigator 10 installation) confirms semantic consistency:

| Cloud value | Modbus source | Difference |
|---|---|---|
| `sum_heat: 31549.6 kWh` | `total_heat_energy` (register 4128) | ~1 kWh (cloud is older) |
| `temp_outside: 21.6 °C` | `outdoor_temp` (register 1000) | typical daily curve |
| `temp_hygienic: 59 °C` | `dhw_temp_top` (register 1014) | ±1 K |

### What the legacy API does **not** offer

- ❌ **a firmware update endpoint** — neither a trigger nor a status query
- ❌ writing temperature setpoints (mode commands only)
- ❌ solar, ISC, booster, cascade or zone data (base heating circuit only)
- ❌ live data (30–60 min older than local)
- ❌ authentication at a modern level (SHA1 without salt, possibly TLS chain
  problems)

### New OAuth2 API (as of July 2026: **not documented**)

The current myIDM web frontend (`app.myidm.at`) uses a **modern OAuth2+PKCE API**
under `a.myidm.at/api/v1/`. The old SHA1 API and the new OAuth2 API exist side by
side, but the OAuth2 API has **not been reverse-engineered yet**.

Known paths of the v1 API (directory only, verified through a read-only GET on
`/api/v1/` after a Django session login):

```
/api/v1/heatpumps/
/api/v1/heatpumps/errors-log/
/api/v1/users/
/api/v1/translations/
/api/v1/texts/
/api/v1/errors/
/api/v1/bookmarks_new/
/api/v1/bookmarks/
/api/v1/channels/
/api/v1/data-act-channels/
/api/v1/virtual-channels/
... (list incomplete)
```

The endpoint list suggests a larger feature set than the legacy API
(`virtual-channels`, `data-act-channels`), but the API requires an OAuth2 bearer
token whose PKCE flow could not be fully reproduced in that session (the Django
session was accepted, but the `/api/v1/oauth2/authorize` endpoint refuses to be
reused for the SPA redirect).

**Open for future research**:

- the complete PKCE flow with correct `code_verifier` handling
- listing all `/api/v1/...` endpoints including write and update options
- reverse-engineering the SPA `app.myidm.at` for API call patterns

Should the OAuth2 API be decoded in a future session, the documentation here
should be extended.

### Relation to the integration

This integration is deliberately **100 % local** (Modbus + Nav 10 WS) and uses
neither of the two cloud APIs. See the section "Deliberately not implemented".
The cloud API documentation here serves completeness and support purposes only,
as well as possible future features (an optional cloud fallback when Modbus
detection fails, for example).
