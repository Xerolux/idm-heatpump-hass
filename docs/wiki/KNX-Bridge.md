# KNX Bridge

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

## Enabling it

1. **Settings → Devices & Services → IDM Heatpump → Configure**
2. Open the **KNX bridge** section and switch on **Enable KNX bridge**.
   The section also carries:
   - **Send values to KNX** — publish a telegram whenever a value changes
   - **Accept commands from KNX** — write incoming values into the heat pump
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

Incoming registration goes through the KNX integration's
`knx.event_register` service, so no change to the KNX integration's own
event filter is needed.

Two guards keep the bus and the controller from talking in circles: only
telegrams marked as *incoming* are acted upon, and a value that merely
echoes what the bridge published moments earlier is not written back.

---

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

**A command from KNX has no effect**
Only objects IDM marks as writable accept commands. Check that *Accept
commands from KNX* is on, and look for a write error in the log: the write
goes through the same safety checks as any other write, so a value outside
the register range or a write cooldown will reject it.

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
