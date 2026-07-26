# IDM Heatpump — Local Read-Only Docker Test Bench

A reproducible, **strictly read-only** Docker environment that runs the **local**
IDM Heatpump integration and the **local** `idm-heatpump-api` in Home Assistant
against a real heat pump, and proves that **no write ever reaches the device**.

All traffic to the heat pump is forced through three read-only proxies:

| Proxy | Allows | Blocks |
|---|---|---|
| `modbus-proxy` (TCP 5020) | Modbus FC01–04 (reads) | every write FC (05/06/0F/10/16/17/…) |
| `web-proxy` HTTP (TCP 80) | `GET`, `HEAD`, and `POST` only on `/`, `/index.php`, `/login.php` (Navigator 2.0 login) | all other methods/paths |
| `web-proxy` Nav10 WS (TCP 61220) | Nav10 read commands `setting/detail`, `statistic/detail`, `notification/overview` | every other WS frame (potential write) |

Every request/frame is logged to `logs/<proxy>/`; blocked writes are additionally
logged to `*_blocked_writes.jsonl` and counted in the health endpoints. The
final report uses these logs to prove no write reached the heat pump.

## Layout

```
docker/live-readonly-test/
├── docker-compose.yml
├── .env(.example)            # IDM_HOST, IDM_WEB_PIN, HA creds (gitignored)
├── proxies/
│   ├── modbus-readonly/      # asyncio Modbus RO proxy (pure stdlib)
│   └── web-readonly/         # aiohttp HTTP RO proxy + Nav10 WS RO proxy (supervisor)
├── homeassistant/            # HA image with local API wheel pre-installed
│   ├── Dockerfile            # also force-installs pymodbus>=3.12.1,<4.0
│   ├── wheels/               # local idm-heatpump-api wheel (gitignored)
│   └── config/               # bind-mounted HA config; .storage/ preseeded by build.ps1
├── api-tester/               # isolated API + HA probes (local API wheel baked in)
│   ├── run_api_tests.py      # Modbus/Nav10-WS/single-vs-batch/sentinel/write-block
│   └── ha_probe.py           # onboarding, entity export, #171 reload, stability
├── scripts/                  # build.ps1, start/stop/clean.ps1, run_probe.ps1
├── logs/                     # proxy + HA logs (gitignored)
├── results/                  # JSON reports + tokens (gitignored)
└── release/                  # release ZIP + wheel + sha256 + evidence (gitignored)
```

## Quick start

```powershell
# 1) Configure secrets (never committed)
cd docker/live-readonly-test
copy .env.example .env
#   edit .env: IDM_HOST, IDM_WEB_PIN, HA_PASSWORD

# 2) Build wheels, seed HA config entry, build images
.\scripts\build.ps1

# 3) Start the proxies + Home Assistant
.\scripts\start.ps1
#   HA UI: http://localhost:8123  (onboarding is automated by the bootstrap probe)

# 4) Onboard HA, create a long-lived token, verify the integration loaded
.\scripts\run_probe.ps1 bootstrap

# 5) Isolated API tests (Modbus + Nav10 web + single/batch + sentinel + write-block)
.\scripts\run_probe.ps1 api-tests

# 6) Entity export + service snapshot
.\scripts\run_probe.ps1 entities
.\scripts\run_probe.ps1 services

# 7) #171 regression: services survive 3 config-entry reloads
.\scripts\run_probe.ps1 reload

# 8) 60-minute read-only stability test (background)
.\scripts\run_probe.ps1 stability

# Inspect the read-only proof
type .\logs\modbus-proxy\modbus_blocked_writes.jsonl
type .\logs\web-proxy\ws_blocked_writes.jsonl
```

## Container reference

| Container | Image | Purpose | Connects to |
|---|---|---|---|
| `idm-modbus-ro` | built (python:3.13-slim) | RO Modbus proxy | `192.168.178.103:502` |
| `idm-web-ro` | built (python:3.13-slim) | RO HTTP + Nav10 WS proxy | `192.168.178.103:80` + `:61220` |
| `idm-ha-test` | built (home-assistant:stable + local API + pymodbus) | HA + local integration | `modbus-proxy:5020`, `web-proxy:80/61220` |
| `idm-api-tester` | built (python:3.13-slim + local API) | on-demand probes | proxies + HA |

Healthchecks: modbus-proxy TCP 5021 JSON stats; web-proxy `GET /__health`;
Nav10 WS `GET /__wshealth`; HA `GET /api/`.

## Read-only guarantee

The proxies are the single enforcement point. Even if a test or the integration
issued a write, the proxy:

1. does **not** forward it to the LAN,
2. returns a Modbus exception (code 1) / HTTP 405 / WS drop so the client fails loudly,
3. appends a record to `*_blocked_writes.jsonl` and increments the blocked counter.

The synthetic write-block verifications in `run_api_tests.py` deliberately send a
single Modbus FC06 to the outdoor-temperature register (with the value just read,
so it is a no-op even hypothetically) and a Nav10 `setting/save` frame, purely to
prove the proxies block them. These are the only blocked writes in the logs.

## Reproducibility

`build.ps1` records `results/build_provenance.json` with the exact local API
wheel sha256 and the seeded config-entry id. The integration is mounted
read-only from `custom_components/idm_heatpump`, so container rebuilds are not
needed for integration-code changes; only `build.ps1` must re-run when the
`idm-heatpump-api` source changes (to rebuild the wheel).
