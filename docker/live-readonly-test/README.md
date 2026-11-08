# IDM Heatpump — Local Read-Only Docker Test Bench

A reproducible, **strictly read-only** Docker environment that runs the **local**
IDM Heatpump integration and the **local** `idm-heatpump-api` in Home Assistant
against a real heat pump, and proves that **no write ever reaches the device**.

All traffic to the heat pump is forced through three read-only proxies:

| Proxy | Allows | Blocks |
|---|---|---|
| `modbus-proxy` (TCP 5020) | Modbus FC01–04 (reads) | every write FC (05/06/0F/10/16/17/…) |
| `web-proxy` HTTP (TCP 80) | `GET`, `HEAD`, and `POST` only on `/`, `/index.php`, `/login.php` (Navigator 2.0 login) | all other methods/paths |
| `web-proxy` Nav10 WS (TCP 61220) | the pinned API's read frames (`setting/detail`, `statistic/detail`, `notification/overview`, `home/detail`, `home/overview`, `status/overview`, `system`, `system.freshwater`, `system.heatpump.performance`, `system.heatingcircuit/detail` per circuit, `weather`, `ion`, `energyflow`) | every other WS frame — in particular any `save` command, the protocol's only write verb |

The WS allowlist mirrors the read requests of the **pinned** API client
(`idm_heatpump/web.py`); when the API adds read frames, extend the allowlist
in the same change or the proxy will silently drop them (that is how the
2026-11-08 session found `home/detail` and `system.heatingcircuit/detail`
missing). Unknown commands stay blocked by default; proxy logging falls back
to stdout when the log directory is unwritable, so enforcement never depends
on file logging.

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
├── homeassistant/            # HA image (pinned to the manifest minimum) with local API wheel pre-installed
│   ├── Dockerfile            # also pre-installs the validated transport pair (modbus-connection/tmodbus)
│   ├── wheels/               # local idm-heatpump-api wheel (gitignored)
│   └── config/               # bind-mounted HA config; .storage/ preseeded by build.ps1/build.sh
├── api-tester/               # isolated API + HA probes (local API wheel baked in)
│   ├── run_api_tests.py      # Modbus/Nav10-WS/single-vs-batch/sentinel/write-block
│   └── ha_probe.py           # onboarding, entity export, #171 reload, stability
├── scripts/                  # build/start/stop/clean + run_probe, each as .ps1 (Windows) and .sh (Linux/macOS)
├── logs/                     # proxy + HA logs (gitignored)
├── results/                  # JSON reports + tokens (gitignored)
└── release/                  # release ZIP + wheel + sha256 + evidence (gitignored)
```

## Quick start

Windows (PowerShell) — or the same commands as `./scripts/*.sh` on Linux/macOS
(the `.sh` scripts are counterparts with identical behaviour; `build.sh` finds
the API repository next to this repository or through `IDM_API_REPO=...`):

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
| `idm-modbus-ro` | built (python:3.14-slim) | RO Modbus proxy | `192.0.2.10:502` |
| `idm-web-ro` | built (python:3.14-slim) | RO HTTP + Nav10 WS proxy | `192.0.2.10:80` + `:61220` |
| `idm-ha-test` | built (home-assistant:2026.11.0 + local API + transport pair) | HA + local integration | `modbus-proxy:5020`, `web-proxy:80/61220` |
| `idm-api-tester` | built (python:3.14-slim + local API) | on-demand probes | proxies + HA |

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

## Shared-connection validation setup

`homeassistant/config/configuration.yaml` optionally configures the **core
`modbus` integration as a second holder** on the same read-only endpoint (one
holding-register sensor). With the IDM integration's shared claim
(`modbus.async_get_unit`) that exercises reference counting and link sharing
across holders; restart `modbus-proxy` mid-poll to observe both holders recover
without an availability window. This is the bench used for the 2026-11-08
shared-connection field validation (see `docs/release-evidence/`).

## Reproducibility

`build.ps1`/`build.sh` records `results/build_provenance.json` with the exact
local API wheel sha256 and the seeded config-entry id. The integration is
mounted read-only from `custom_components/idm_heatpump`, so container rebuilds
are not needed for integration-code changes; only the build script must re-run
when the `idm-heatpump-api` source changes (to rebuild the wheel). The Home
Assistant image is pinned to the integration's minimum supported version — move
the pin in the same change that raises the manifest minimum.

The weekly **Docker Bench Build** workflow rebuilds all four images from the
manifest-pinned API source without any hardware attached, so the bench cannot
silently rot between field validations.

## Version notes

The integration's Modbus runtime is the `modbus-connection`/`tmodbus` pair
installed into the HA image so its manifest requirements resolve without a
PyPI fetch; pymodbus is gone from the integration since API 2.0. The isolated
api-tester additionally installs the API's optional built-in pymodbus
transport (`[pymodbus]` extra) for its standalone probes — that path never
runs inside Home Assistant.
