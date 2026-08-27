# KNX Bridge

> [!WARNING]
> **Experimental.** Automated behavior is covered by tests and static analysis.
> Setup, safe receive-only configuration and integration reload were also
> exercised on a live Home Assistant installation with an active KNX interface.
> No IDM group addresses had been imported into ETS, no physical group-address
> telegram was sent or decoded, and first-export bus load remains unmeasured.
> Treat it as something to try and report on, not as something to depend on.
> See [`docs/release-evidence/0.16.0-rc.6.md`](https://github.com/Xerolux/idm-heatpump-hass/blob/main/docs/release-evidence/0.16.0-rc.6.md)
> for exactly what is and is not verified.

Publish the heat pump on a KNX bus and take commands back from it — using
the KNX integration Home Assistant already has, and **without** the IDM
KNX gateway module.

---

## What this replaces

IDM sells KNX connectivity for the Navigator as a **Weinzierl KNX IP BAOS
774** module, configured in ETS with IDM's example project. That project
defines a fixed set of communication objects: object 1 is the outdoor
temperature, object 4 the system mode, object 222 the operating mode of
heating circuit A, and so on — each with a datapoint type and a direction.

The KNX bridge recreates that object list from the Modbus values this
integration already reads. A KNX installation sees the same object
numbers, the same datapoint types and the same read/write directions as it
would with the hardware module, so existing visualisations, room
controllers and logic blocks keep working — the gateway is just gone.

> **The bridge is not a KNX stack.** It calls the Home Assistant
> [KNX integration](https://www.home-assistant.io/integrations/knx/) for
> everything on the bus side. IP tunnelling, IP routing, the gateway
> connection and **KNX Secure** all come from there and are configured
> there. If the KNX integration is not set up, the bridge stays idle and
> raises a repair issue.

---

## Requirements

| | |
|---|---|
| **Home Assistant KNX integration** | Set up and connected to a gateway or tunnel |
| **IDM Heatpump integration** | Running over Modbus (a web-only entry has no register values to publish) |
| **Free KNX main group** | The catalogue needs 1000 consecutive group addresses |

---

## Where it lives in the UI

The bridge is part of the integration's **options**, so it appears in two
places and nowhere else:

| Flow | KNX bridge |
|---|---|
| Initial setup (adding the integration) | Yes — after the main options step |
| **Configure** on an existing entry | Yes — same step, prefilled with what is stored |
| **Reconfigure** menu | No. That menu edits connection settings (host, port, slave ID) and runs diagnostics; it does not touch options at all, the same way room temperature forwarding and the web supplement are not there either. |

Switching the bridge off keeps the configured base address, object groups and
overrides, so turning it back on does not cost you the ETS mapping.

In **web-only mode** the bridge stays off regardless of the setting: it serves
Modbus register values, which a web-only entry does not read. The log says so
at startup.

## Enabling it

1. **Settings → Devices & Services → IDM Heatpump → Configure**
2. Open the **KNX bridge** section and switch on **Enable KNX bridge**.
   The section also carries:
   - **Send values to KNX** — publish a telegram whenever a value changes
   - **Accept commands from KNX** — write incoming values into the heat pump
   - **Answer read requests** — reply to a `GroupValueRead` with the current value
   - **Full resend interval** — resend every value periodically (0 = only on change)
   - **Change tolerance** — how far a numeric value must move before it is sent again
3. Submit. A **KNX group addresses** step follows with:
   - **Base group address** — see below
   - **Object groups** — which parts of the catalogue take part
   - **Group address overrides** — for objects your ETS project already addresses differently

---

## How group addresses are assigned

IDM's example project ships with an **empty** group address table: every
installation assigns its own. The bridge therefore derives them from one
base address plus the IDM object number:

```
group address = base address + object number
```

With the default base `8/0/0`:

| IDM object | Value | Group address |
|---|---|---|
| 1 | Outdoor temperature | `8/0/1` |
| 4 | System mode | `8/0/4` |
| 21 | Hot water setpoint | `8/0/21` |
| 222 | Operating mode heating circuit A | `8/0/222` |
| 400 | Heat quantity heating | `8/1/144` |
| 999 | Total thermal energy | `8/3/231` |

The whole catalogue fits inside one main group (`8/0/1` … `8/3/231`), so a
single free main group is all the planning it needs.

### Overrides

If your ETS project already uses different addresses, list the exceptions —
one per line, `register = address`:

```
outdoor_temp = 1/2/3
system_mode = 1/2/4
# lines starting with a hash are ignored
```

An entry with an empty address excludes that object from the bridge
entirely. Everything not listed keeps its derived address.

---

## Object groups

Each catalogue entry belongs to one group, and only the selected groups are
published and registered:

| Group | Contents |
|---|---|
| `system` | Outdoor temperature, system mode, error number, buffer temperatures, error acknowledge |
| `heat_pump` | Flow/return, heat source, compressors, pumps, bivalence points, faults |
| `dhw` | Hot water temperatures and setpoint |
| `heating_circuits` | Circuits A–G: flow, room, setpoints, curve, limits, modes, external room temperature |
| `zones` | Zone modules 1–10 with up to 8 rooms each |
| `glt` | Building-management inputs: external temperatures, humidity, demand requests |
| `energy` | Heat quantities and current power |
| `solar` | Collector, return, charging temperatures and solar mode |
| `isc` | ISC cooling temperatures and mode |
| `cascade` | Available/running stages, requested temperatures, power and bivalence limits |
| `booster` | Booster 1 and 2 temperatures, pumps, compressors |
| `pv` | PV, battery, house consumption, total electric and thermal output |

Objects whose register the connected controller does not expose are skipped
automatically, so a Navigator without a zone module never puts zone objects
on the bus.

---

## Direction

Every object carries the direction IDM gave it in the example project:

- **Read-only objects** (temperatures, states, energy counters) are
  published only. A telegram arriving on one of them is ignored.
- **Writable objects** (modes, setpoints, external temperatures, demand
  requests) are published *and* registered for incoming telegrams. A group
  write on such an address is written into the corresponding Modbus
  register through the normal write path, including its safety checks,
  write cooldown and EEPROM protection.

KNX controls can emit intermediate values while a dial is turned or an arrow
is tapped. The bridge therefore keeps the newest value per register for a
one-second quiet period and writes only that final value. If the normal write
cooldown or the EEPROM interval is still active, the newest value stays queued
and is applied after the guard expires; a later telegram replaces it. Values
that already match the current coordinator state do not consume a write cycle.

This changes command handling, not write safety. The EEPROM-sensitive register
classification and the default 60-second EEPROM interval are unchanged. The
interval remains configurable in the integration settings for owners who
deliberately accept a different wear-versus-latency trade-off.

### Read requests

A KNX device that asks for a value — a push-button refreshing its display
after a restart, a visualisation coming back up — sends a `GroupValueRead`.
The bridge answers it with the value the heat pump currently reads, as a
`GroupValueResponse`, which is what the BAOS gateway does too.

The reply goes out immediately rather than through the paced send queue: a
read request is answered now or not usefully at all, and the number of them
is bounded by the devices asking. Write-only objects and values the
controller reports as unused are not answered, because there is nothing to
answer with.

Switching **Answer read requests** off leaves those addresses unregistered
and the bridge silent on reads. A `GroupValueResponse` from another device
is never written into the heat pump: it answers somebody else's question
rather than instructing us.

Incoming registration goes through the KNX integration's
`knx.event_register` service, so no change to the KNX integration's own
event filter is needed.

Two guards keep the bus and the controller from talking in circles: only
telegrams marked as *incoming* are acted upon, and a value that merely
echoes what the bridge published moments earlier is not written back.

---

## Ready-made ETS import files

The bridge sends on the group addresses, but ETS still needs them to exist in
the project so the real KNX devices — a push-button showing the flow
temperature, a visualisation, a logic module — can be linked to them. Two
generated files are in the repository so nobody types several hundred
addresses by hand:

| File | Contents |
|---|---|
| [`idm-waermepumpe-kompakt.xml`](https://github.com/Xerolux/idm-heatpump-hass/blob/main/docs/examples/knx/idm-waermepumpe-kompakt.xml) | 43 addresses: what a display or visualisation realistically shows, plus the values a KNX installation can feed back into the heat pump. Heating circuits A and B. |
| [`idm-waermepumpe-komplett.xml`](https://github.com/Xerolux/idm-heatpump-hass/blob/main/docs/examples/knx/idm-waermepumpe-komplett.xml) | all 654 objects |

Both assume the default base address `8/0/0`. The matching `.csv` files are a
readable reference — object number, register, direction — not import files.

**Import into ETS 6** (three-level group address style): back the project up,
right-click the top entry under *Group Addresses*, choose *Import Group
Addresses*, pick the `.xml`, then check the import report against addresses
that already exist.

### Generating your own

If `8/0/0` is taken in your project, or you want a different selection,
generate a file for your own base address:

```bash
# A curated subset on main group 11
python scripts/generate_knx_group_addresses.py --base 11/0/0 --profile compact --output ./out

# Only what a visualisation needs
python scripts/generate_knx_group_addresses.py --base 11/0/0 --groups system,dhw,energy --output ./out

# Named registers, whatever you like
python scripts/generate_knx_group_addresses.py --base 11/0/0 \
  --registers outdoor_temp,dhw_setpoint,hc_a_mode --output ./out
```

The names come from the integration's own German name table, so an address
reads in ETS the way the matching entity reads in Home Assistant.

## Exporting the object list for ETS

The `idm_heatpump.export_knx_group_addresses` action answers with the table
for **this** controller — object number, group address, datapoint type,
direction and unit — so a fresh ETS project can be built from it:

```yaml
action: idm_heatpump.export_knx_group_addresses
target:
  entity_id: sensor.idm_heatpump_outdoor_temperature
data:
  knx_base_address: "8/0/0"
response_variable: knx_objects
```

The response looks like this:

```yaml
base_address: "8/0/0"
count: 187
objects:
  - object: 1
    group_address: "8/0/1"
    register: outdoor_temp
    dpt: "9.001"
    group: system
    writable: false
    unit: "°C"
```

Both fields are optional: without them the action uses the addresses and
object groups configured for the bridge.

---

## Bus load

A first export sends one telegram per object, so the bridge paces them at
about 20 telegrams per second and only sends a value again once it has
actually moved further than the configured tolerance. On a plant with many
heating circuits and zone modules, restrict the object groups to what the
KNX side really consumes rather than publishing all of them.

---

## Datapoint types

The catalogue uses IDM's own datapoint types where the example project
states one, and derives the rest from the register:

| Kind of value | DPT |
|---|---|
| Temperatures | `9.001` |
| Humidity | `9.007` |
| Power (kW) | `9.024` |
| Heat quantities (kWh) | `14.031` |
| Percentages | `5.001` |
| Modes, states, counters | `7.001` (`5.010` for the system mode) |
| Bivalence points (signed °C) | `8.001` |
| Demand requests | 1-bit, sent as a raw `0`/`1` payload |

---

## Troubleshooting

**Repair issue "KNX bridge inactive"**
The KNX integration is not set up. Add it first, then reload the IDM
Heatpump entry.

**Nothing arrives on the bus**
Check that *Send values to KNX* is on, that the object's group is selected,
and that the controller actually reports the value — objects whose register
is missing or marked unused are skipped.

**A push-button stays blank after a restart**
Check that *Answer read requests* is on. If the device does not send a read
request at all, set a **Full resend interval** so every value is repeated
periodically.

**A command from KNX has no effect**
Only objects IDM marks as writable accept commands. Check that *Accept
commands from KNX* is on, and look for a write error in the log: the write
goes through the same safety checks as any other write. A value outside the
register range is rejected. An active general or EEPROM cooldown keeps the
newest valid command queued and applies it when the guard expires.

**Two objects share an address**
The override list refuses a duplicate address. If the derived addresses
collide with something else on the bus, move the base address to a free
main group.

---

## Not covered

Two objects from the example project are deliberately absent: the external
pump demand objects 384 (*brine / intermediate pump*) and 385
(*groundwater pump*). IDM's own labels do not map unambiguously onto the
two corresponding registers, and a wrong guess would command the wrong
pump. Use the `write_register` action for those until the mapping is
confirmed on hardware.

---

**See also:** [Configuration](Configuration) · [Services](Services) · [Modbus registers](Modbus-Register)
