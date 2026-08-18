# IDM Heatpump dashboard examples

These examples are intentionally conservative. They only reference normal Home
Assistant entities and do not require custom cards. Entity IDs depend on the
configured integration name and on which registers are available on the heat
pump, so treat them as starting points and adjust them in the dashboard editor.

## Files

- `dashboard-idm-overview.yaml` – safe first dashboard with status, hot water,
  heating-circuit, operation-analysis and diagnostic sections.
- `dashboard-idm-heating-circuit.yaml` – one heating circuit per view, with
  comfort setpoints and heating-curve parameters kept apart.
- `dashboard-idm-hot-water.yaml` – domestic hot-water focused cards including
  boost status and conservative controls.
- `dashboard-idm-energy.yaml` – energy, PV/GLT and operating-quality cards.
- `dashboard-idm-diagnostics.yaml` – private support dashboard for versions,
  web supplement state, alarms and technician codes.

## Safety notes

- Prefer standard entity controls (`number`, `select`, `switch`, `water_heater`)
  over raw register writes.
- Do not expose technician-code, debug or manual-write helpers on public or
  shared dashboards.
- Keep PV/GLT control ownership clear: only one controller should write the same
  GLT/PV register.
- Heating-curve parameters (`heating_curve`, `parallel_shift`,
  `setpoint_flow_constant`, `setpoint_flow_cooling`) are disabled by default on
  new installations and must be enabled in the entity settings first. They write
  to EEPROM registers — set them by hand, do not automate them.
