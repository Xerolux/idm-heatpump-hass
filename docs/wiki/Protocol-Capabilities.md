# Protocol Capabilities

This page answers one question at a glance: **what can each connection path
read and write, on which Navigator family?** The integration supports three
paths — Modbus TCP, the local Navigator 2.0 web interface (HTTP/CSRF) and
the Navigator 10/Pro WebSocket — and they complement each other. Deep
background lives on [Navigator Protocol Analysis](Navigator-Protocol-Analysis),
registers on [Modbus Registers](Modbus-Register), hardware on
[Compatibility Matrix](Compatibility-Matrix).

## The three paths

| Path | Port | Authentication | Families | Role |
|---|---|---|---|---|
| **Modbus TCP** | 502 (unit 1) | none | 1.0/1.7 · 2.0 · 10/Pro | The spine: full register telemetry, *all* validated writes |
| **Web, old generation** (PHP, no CSRF) | 80 | local network code, plain login session | 2.0 (older firmware) | Read-only supplement |
| **Web, newer generation** (PHP + CSRF) | 80 | local network code + CSRF token | 2.0 (newer firmware) | Read-only supplement |
| **WebSocket** | 61220 | local PIN (`SYSLPIN`) | 10 / Pro | First-class second path: values Modbus lacks + validated writes |

The integration's Navigator 2.0 web client covers both web generations
transparently: it logs in with the CSRF token when the login form provides
one and falls back to the plain cookie session of older firmware otherwise,
then probes the PHP data pages (`/data/settings.php`, `/data/heatpump.php`,
`/data/info.php`, …). The endpoint set and the statistics pages were
cross-checked against the community integration
[AndyNew2/hacs-idm-hpweb](https://github.com/AndyNew2/hacs-idm-hpweb).

The connection mode option decides which paths an entry uses:
`auto` (recommended — Modbus + web supplement), `modbus_web` (both pinned on,
no web-only fallback), `web_only` (no Modbus at all), `modbus_only` (the web
interface is never contacted). See [Configuration](Configuration).

## Capability matrix

Legend: **R** readable · **W** writable · **R/W** both · **—** not available
on that path · *(note)* qualifications. Unmarked cells follow the legend of
their row; where a capability is firmware-dependent it says so.

| Capability | 1.0/1.7 Modbus | 2.0 Modbus | 2.0 Web (old / CSRF) | 10/Pro Modbus | 10/Pro WebSocket |
|---|---|---|---|---|---|
| Model & firmware detection | R | R | R (supplement hint) | R | R |
| Core telemetry (temperatures, statuses, pumps, valves) | R (1.x map) | R | R | R | R (64 values, setting pages) |
| Electrical / thermal power (COP inputs) | — | partly *(not confirmed)* | — | **R** | **—** *(firmware delivers neither)* |
| Energy counters (lifetime kWh) | — | R *(where present)* | — | R | R (heat quantities, total + today) |
| Statistics pages (runtime, heat, electrical) | — | — | R *(statistics.php; not read by this integration)* | — | R (statistic blocks) |
| Controller clock setting | — | — | W *(community-confirmed time-set)* | — | W *(setting 4537, capture-confirmed)* |
| Demand reason incl. PV (display wording) | — | — | — | — | **R** (`home/detail`) |
| Message texts (info system) | error codes only | error codes only | — | error codes only | **R** (`notification`, with texts) |
| Hot-gas, flow, board, pressures | — | partly | partly | partly | **R** |
| DHW circulation / statusInfo | — | — | — | — | **R** (`system.freshwater`) |
| Controller clock / jsonVersion / userlevel | — | — | — | — | **R** (`status/overview`) |
| Operating mode (system) | R/W (holding block) | R/W | — | R/W | **R/W** (`home/save`) |
| DHW setpoint | R/W (2152) | R/W | — | R/W | **R/W** (FW030, device-range-validated) |
| Heating-circuit mode | R/W (holding block) | R/W | — | R/W | **R/W** (HK\<x\>01) |
| Room setpoint (normal) | R/W (holding block) | R/W | — | R/W | **R/W** (HK\<x\>04, device-range-validated) |
| Heating curve / limits / shift | R/W (holding block) | R/W | — | R/W | W possible *(parameter ids known, not yet mapped)* |
| Error acknowledge | W (coil c3000, FC05) | W (register 1999) | — | W (register 1999) | **W** (`notification/save`) |
| DHW one-shot boost | W (demand coil c3003) | W (boost state machine) | — | W (boost state machine) | **—** *(weekly timetable only, no one-shot command)* |
| GLT inputs (ext. room temp, humidity, PV surplus) | W (PV supplement 74–88) | W | — | W | **—** *(level-0 GLT container answers empty)* |
| Zone-module rooms | — (separate family) | R/W *(registers)* | — | R/W | R/W *(room controller; not yet mapped)* |
| KNX bridge | serve *(shared names only)* | serve + commands | — | serve + commands | serve + commands *(everyday controls via WS)* |
| COP / energy statistics | — | partly | — | **yes** | **no** *(needs the power inputs)* |

## What this means in practice

- **Full operation (recommended `auto`):** Modbus delivers everything,
  including the power values behind COP and energy statistics; the web
  supplement adds the values Modbus never had (demand reason, message
  texts, hot-gas, circulation, device-side statistics).
- **`web_only` (Navigator 10/Pro):** a genuine operating mode — 10-second
  polls, climate/water-heater cards, KNX serving and the validated writes
  of the matrix above. What it cannot replace: COP/energy statistics
  (power values), GLT forwarding and the one-shot DHW boost — those need
  Modbus.
- **Navigator 2.0:** Modbus carries the load; the CSRF web interface is a
  read-only supplement (its write semantics were never captured and
  validated — deliberately not offered).
- **Navigator 1.0/1.7:** Modbus only, including the official RW holding
  block and the coil commands. No web module exists; the local web
  supplement should stay disabled. Holding-block writes are
  EEPROM-limited — the integration guards them with cooldowns and EEPROM
  intervals.

## Write safety on every path

| Guard | Modbus | WebSocket |
|---|---|---|
| Range/enum validation before sending | API register metadata | device's own declared min/max (read before write) |
| EEPROM protection | EEPROM-sensitive list + 60 s interval per register | *(EEPROM load not documented for web writes; pacing applies)* |
| Confirmation | read-back through the register poll | `<controller>Save` success note required; rejection raises |
| Transient-zero guard | lifetime counters | lifetime counters (same snapshot) |

Writes are never sent as free-form payloads on any path. Everything in the
matrix marked **W** went through this validation on real hardware before it
shipped; cells marked *(not yet mapped)* exist in the protocol but have not
earned the validation bar yet.
