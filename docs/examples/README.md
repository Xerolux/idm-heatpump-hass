# IDM Heatpump dashboard examples

These examples are intentionally conservative. They only reference normal Home
Assistant entities and do not require custom cards. Entity IDs depend on the
configured integration name and on which registers are available on the heat
pump, so treat them as starting points and adjust them in the dashboard editor.

## Files

- `dashboard-idm-overview.yaml` – safe first dashboard with status, hot water,
  heating-circuit, operation-analysis and diagnostic sections.
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
