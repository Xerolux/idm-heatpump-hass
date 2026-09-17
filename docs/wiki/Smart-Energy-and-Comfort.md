# iDM Smart Energy & Comfort

The integration can run as a slim **Vanilla** integration or with the optional
**iDM Smart Energy & Comfort** feature profile.

## Vanilla

Vanilla exposes the core IDM Modbus and web entities. It keeps the integration
compact and does not create additional calculated analysis entities.

## iDM Smart Energy & Comfort

This profile adds local calculated sensors, compressor runtime and cycle
analysis, short-cycle diagnostics, persistent electrical and thermal energy
statistics, COP statistics, and safe domestic-hot-water boost controls. The
analysis is read-only. It does not stop the compressor or change the heating
curve.

## Activation

Open **Settings → Devices & services → iDM Heatpump → Configure**. Under
**Presentation and additional features**, select either:

- **iDM Smart Energy & Comfort** for the optional features
- **Vanilla** for the core IDM entities only

Saving reloads the integration. Core entity IDs remain unchanged; optional
entities are controlled by the selected profile.

## Persistent energy statistics

When the required IDM power registers are available, Smart adds total, daily
and monthly electrical and thermal energy sensors, plus total, daily and
monthly COP sensors. Values are integrated only from finite, non-negative power
readings and are stored across Home Assistant restarts. Long polling gaps and
invalid readings are excluded instead of being estimated.

The same statistics provide optional estimated electricity costs, CO₂
emissions and PV self-consumption by the heat pump. The electricity price and
emission factor are local Config Flow values; no tariff service or cloud data
is required. PV self-consumption is calculated only when a PV-production source
is selected in the external power mapping.

Analytics entities are placed in a separate **iDM Analytics** device group when
device hierarchy is enabled. This keeps the main heat-pump device focused on
controller values and does not change entity IDs.

## Optional PV surplus DHW automation

The **automatic PV surplus DHW charging** option is disabled by default. It
uses the selected external power sensors and only starts the existing
transactional DHW boost. Normal heating, the heating curve and the electric
heater are not changed.

Requirements:

- Smart profile is active.
- External power forwarding contains either a PV-surplus sensor or PV
  production and house-consumption sensors.
- A battery SOC sensor can optionally enforce a minimum battery level.
- The confirmation that Home Assistant is the only DHW controller is enabled.

Without the ownership confirmation the automation never starts. Do not enable
it while Smartfox, openWB or another system controls domestic hot water.
Invalid or unavailable source values fail closed. Minimum surplus, minimum SOC,
DHW target, maximum duration and cooldown are configurable.

The manager does not control the heating curve or the electric heater. Tariff
optimisation is not enabled because it would require an external tariff source.

## Comfort schedule and read-only advisers

The optional comfort schedule can write one selected room-temperature target on
one configured heating circuit during a daily time window. It is disabled by
default and requires the explicit confirmation that Home Assistant is the only
controller for that circuit. It restores the previous target after the window
and does not overwrite a manual change made while the schedule was active.

The heating-curve assistant and weather-preheat adviser are read-only. They
create recommendations only; they never write a setpoint. The heating-curve
adviser compares the current flow temperature with the circuit setpoint. The
weather adviser uses a selected Home Assistant weather entity and reports when
the configured outdoor-temperature threshold suggests preheating.

These entities are grouped separately under **iDM Comfort** when device
hierarchy is enabled.

## Optional iDM Health Monitor

The **iDM Health Monitor** is disabled by default and adds read-only diagnostic
entities. It checks communication failures, unusual compressor start
frequency, unusually low current COP, a clearly missed DHW target and
implausible temperature values. The health-report sensor exposes `ok` or
`problem` and lists active checks in its attributes. It does not change any
heat-pump setting and does not replace a technician diagnosis.

Health entities are placed under their own **iDM Health Monitor** device group
when device hierarchy is enabled. This is a diagnostic grouping only and does
not imply that the integration can replace an installer inspection.

The report summary can be copied from the entity attributes or supplemented by
Home Assistant's standard **Download diagnostics** action. It intentionally
contains no host, PIN, serial number or other connection secret. It is a
structured snapshot for an installer, not a replacement for a service report.
