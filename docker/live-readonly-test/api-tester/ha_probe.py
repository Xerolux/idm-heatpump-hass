"""HA-side probes for the read-only test bench (runs in the api-tester container).

Subcommands (MODE / argv[1]):
  bootstrap   onboard HA, create a long-lived access token, verify the IDM
              integration loaded. Writes /results/.ha_token (gitignored).
  entities    export entity registry + devices + states + service list to
              /results/entity_export.json. Validates counts per platform.
  services    snapshot the idm_heatpump domain services.
  reload      #171 regression: snapshot services, reload the entry via WS,
              snapshot again, repeat a few times, compare.
  stability   poll states/logs for STABILITY_MINUTES, record entity-count,
              unavailable count, model stability.

All access uses the long-lived token from bootstrap. No writes are issued to
the heat pump (reload only re-loads the config entry; it does not write).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime
from typing import Any

import aiohttp

RESULTS_DIR = os.environ.get("RESULTS_DIR", "/results")
HA_URL = os.environ.get("HA_URL", "http://homeassistant:8123")
HA_USER = os.environ.get("HA_USERNAME", "idmadmin")
HA_PASS = os.environ.get("HA_PASSWORD", "ChangeMeTestOnly_2026!")
CLIENT_ID = "http://homeassistant:8123/"


def log(m: str) -> None:
    print(f"[ha-probe] {m}", flush=True)


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _save(path: str, obj: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, ensure_ascii=False)


def _save_raw(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


async def _wait_ha(session: aiohttp.ClientSession, timeout: float = 180) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            async with session.get(f"{HA_URL}/api/", timeout=aiohttp.ClientTimeout(total=5)) as r:
                if r.status in (200, 401):
                    return True
        except Exception:
            await asyncio.sleep(3)
    return False


async def _onboard(session: aiohttp.ClientSession) -> str:
    """Complete user onboarding and exchange auth_code for tokens. Returns access_token."""
    async with session.post(
        f"{HA_URL}/api/onboarding/users",
        json={
            "name": "IDM Test Admin",
            "username": HA_USER,
            "password": HA_PASS,
            "client_id": CLIENT_ID,
            "language": "en",
        },
        timeout=aiohttp.ClientTimeout(total=15),
    ) as r:
        body = await r.text()
        if r.status == 403 and "already done" in body.lower():
            log("onboarding already done; will authenticate with existing credentials")
            return await _login_existing(session)
        if r.status != 200:
            raise RuntimeError(f"onboarding/users failed {r.status}: {body}")
        auth_code = (json.loads(body)).get("auth_code")
        if not auth_code:
            raise RuntimeError(f"no auth_code in onboarding response: {body}")
    # Exchange for tokens.
    async with session.post(
        f"{HA_URL}/auth/token",
        data={"grant_type": "authorization_code", "code": auth_code, "client_id": CLIENT_ID},
        timeout=aiohttp.ClientTimeout(total=15),
    ) as r:
        body = await r.text()
        if r.status != 200:
            raise RuntimeError(f"token exchange failed {r.status}: {body}")
        tok = json.loads(body)
    access = tok["access_token"]
    # Persist refresh token so later runs can refresh without re-onboarding.
    if tok.get("refresh_token"):
        _save_raw(os.path.join(RESULTS_DIR, ".ha_refresh"), tok["refresh_token"])
    # Finish onboarding steps (best-effort).
    headers = {"Authorization": f"Bearer {access}"}
    for path, payload in [
        ("/api/onboarding/core_config", {}),
        ("/api/onboarding/analytics", {}),
        ("/api/onboarding/integration", {"client_id": CLIENT_ID, "redirect_uri": CLIENT_ID}),
    ]:
        try:
            async with session.post(f"{HA_URL}{path}", json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as rr:
                await rr.read()
        except Exception as e:
            log(f"onboarding step {path} best-effort failed: {e}")
    return access


async def _login_existing(session: aiohttp.ClientSession) -> str:
    """When onboarding was already completed, get a fresh token via password grant."""
    async with session.post(
        f"{HA_URL}/auth/token",
        data={
            "grant_type": "password",
            "username": HA_USER,
            "password": HA_PASS,
            "client_id": CLIENT_ID,
        },
        timeout=aiohttp.ClientTimeout(total=15),
    ) as r:
        body = await r.text()
        if r.status != 200:
            raise RuntimeError(f"password login failed {r.status}: {body}")
        return json.loads(body)["access_token"]


class WS:
    def __init__(self, session: aiohttp.ClientSession, token: str) -> None:
        self.session = session
        self.token = token
        self._id = 0
        self.ws: aiohttp.client_ws.ClientWebSocketResponse | None = None

    async def __aenter__(self) -> "WS":
        self.ws = await self.session.ws_connect(f"{HA_URL}/api/websocket", heartbeat=30)
        # first message: auth_required
        msg = await self.ws.receive(timeout=15)
        await self.ws.send_json({"type": "auth", "access_token": self.token})
        msg = await self.ws.receive(timeout=15)
        data = msg.json()
        if data.get("type") != "auth_ok":
            raise RuntimeError(f"WS auth failed: {data}")
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self.ws is not None:
            await self.ws.close()

    async def cmd(self, command: str, **extra: Any) -> Any:
        assert self.ws is not None
        self._id += 1
        msg = {"id": self._id, "type": command, **extra}
        await self.ws.send_json(msg)
        while True:
            m = await self.ws.receive(timeout=30)
            d = m.json()
            if d.get("id") == self._id and d.get("type") == "result":
                if not d.get("success"):
                    raise RuntimeError(f"WS command {command} failed: {d.get('error')}")
                return d.get("result")
            # ignore event/other messages


async def _create_llat(session: aiohttp.ClientSession, access_token: str) -> str:
    async with WS(session, access_token) as ws:
        token = await ws.cmd(
            "auth/long_lived_access_token",
            client_name="api-tester",
            lifespan=365,
        )
    if not isinstance(token, str):
        raise RuntimeError(f"unexpected LLAT result: {token!r}")
    return token


async def _load_token() -> str:
    path = os.path.join(RESULTS_DIR, ".ha_token")
    if not os.path.exists(path):
        raise RuntimeError("no token found; run 'bootstrap' first")
    with open(path, encoding="utf-8") as fh:
        return fh.read().strip()


async def cmd_bootstrap(args: argparse.Namespace) -> int:
    report: dict[str, Any] = {"started_at": now_iso(), "ha_url": HA_URL}
    timeout = aiohttp.ClientTimeout(total=20)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        if not await _wait_ha(session):
            log("HA did not become ready"); return 2
        try:
            access = await _onboard(session)
            report["onboard"] = "ok"
        except Exception as e:
            log(f"onboard failed: {e}"); report["onboard"] = f"fail: {e}"; _save(_p("bootstrap_report.json"), report); return 3
        try:
            llat = await _create_llat(session, access)
            _save_raw(os.path.join(RESULTS_DIR, ".ha_token"), llat)
            report["llat"] = "created"
        except Exception as e:
            log(f"LLAT creation failed: {e}"); report["llat"] = f"fail: {e}"; _save(_p("bootstrap_report.json"), report); return 4
        # Verify integration loaded via entity registry.
        headers = {"Authorization": f"Bearer {llat}"}
        try:
            async with WS(session, llat) as ws:
                ents = await ws.cmd("config/entity_registry/list")
            idm = [e for e in ents if e.get("config_entry") == _entry_id()]
            report["idm_entries_in_registry"] = len(idm)
        except Exception as e:
            report["registry_check"] = f"fail: {e}"
        # Wait for IDM entities to appear.
        waited = await _wait_idm_entities(session, llat, timeout=180)
        report["idm_entities_appeared"] = waited
    report["ended_at"] = now_iso()
    _save(_p("bootstrap_report.json"), report)
    log(f"bootstrap done: {report}")
    return 0 if report.get("idm_entities_appeared") else 5


async def _wait_idm_entities(session: aiohttp.ClientSession, token: str, timeout: float = 180) -> bool:
    headers = {"Authorization": f"Bearer {token}"}
    deadline = time.time() + timeout
    last = 0
    while time.time() < deadline:
        try:
            async with session.get(f"{HA_URL}/api/states", headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as r:
                states = await r.json()
            idm = [s for s in states if str(s.get("entity_id", "")).startswith(("sensor.idm", "binary_sensor.idm", "number.idm", "select.idm", "switch.idm", "climate.idm", "water_heater.idm", "button.idm"))]
            if len(idm) > last:
                last = len(idm); log(f"IDM entities so far: {len(idm)}")
            if len(idm) >= 5:
                return True
        except Exception:
            pass
        await asyncio.sleep(5)
    return last > 0


def _entry_id() -> str:
    return os.environ.get("HA_ENTRY_ID", "01JULY2026-IDM-TEST-000000000001")


_IDM_PLATFORMS = ("sensor", "binary_sensor", "number", "select", "switch", "climate", "water_heater", "button")


def _is_idm_entity(entity: dict, *, idm_entry_ids: set[str]) -> bool:
    eid = str(entity.get("entity_id", ""))
    if not eid or "." not in eid:
        return False
    # In HA's entity registry, `platform` is the integration domain
    # ("idm_heatpump"); the HA platform (sensor/number/...) is the entity_id
    # prefix. Match either signal.
    ha_platform = eid.split(".", 1)[0]
    integration = entity.get("platform")
    if integration == "idm_heatpump" and ha_platform in _IDM_PLATFORMS:
        return True
    ce = entity.get("config_entry_id") or entity.get("config_entry")
    if ce and ce in idm_entry_ids and ha_platform in _IDM_PLATFORMS:
        return True
    return ("idm" in eid.lower() or eid.startswith("diagnose.")) and ha_platform in _IDM_PLATFORMS


def _p(name: str) -> str:
    return os.path.join(RESULTS_DIR, name)


async def cmd_entities(args: argparse.Namespace) -> int:
    token = await _load_token()
    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with WS(session, token) as ws:
            ents = await ws.cmd("config/entity_registry/list")
            devs = await ws.cmd("config/device_registry/list")
            try:
                raw_entries = await ws.cmd("config_entries/get")
                if isinstance(raw_entries, dict):
                    entries = raw_entries.get("entries", [])
                else:
                    entries = list(raw_entries or [])
            except Exception:
                entries = []
        idm_entry_ids = {e.get("entry_id") for e in entries if e.get("domain") == "idm_heatpump"}
        if not idm_entry_ids:
            idm_entry_ids = {_entry_id()}
        headers = {"Authorization": f"Bearer {token}"}
        async with session.get(f"{HA_URL}/api/states", headers=headers) as r:
            states = {s["entity_id"]: s for s in await r.json()}
        async with session.get(f"{HA_URL}/api/services", headers=headers) as r:
            services = await r.json()
    idm_entities = [e for e in ents if _is_idm_entity(e, idm_entry_ids=idm_entry_ids)]
    idm_device_ids = {e.get("device_id") for e in idm_entities if e.get("device_id")}
    idm_devices = [d for d in devs if d.get("id") in idm_device_ids]

    rows = []
    for e in idm_entities:
        eid = e.get("entity_id", "")
        st = states.get(eid, {})
        rows.append({
            "entity_id": eid,
            "platform": eid.split(".", 1)[0] if "." in eid else (e.get("platform") or ""),
            "unique_id": e.get("unique_id"),
            "name": e.get("name") or e.get("original_name"),
            "device_id": e.get("device_id"),
            "entity_category": e.get("entity_category"),
            "disabled_by": e.get("disabled_by"),
            "hidden_by": e.get("hidden_by"),
            "state": st.get("state"),
            "unit": (st.get("attributes") or {}).get("unit_of_measurement"),
            "available": st.get("state") not in ("unavailable", None),
        })
    by_platform: dict[str, int] = {}
    for r0 in rows:
        by_platform[r0["platform"]] = by_platform.get(r0["platform"], 0) + 1
    idm_services = []
    for s in services:
        if s.get("domain") == "idm_heatpump":
            idm_services = sorted(s.get("services", {}).keys())
    export = {
        "generated_at": now_iso(),
        "entry_id": _entry_id(),
        "entity_count": len(rows),
        "by_platform": by_platform,
        "available_count": sum(1 for r0 in rows if r0["available"]),
        "unavailable_entities": [r0["entity_id"] for r0 in rows if not r0["available"]],
        "devices": [
            {"id": d.get("id"), "name": d.get("name_by_user") or d.get("name"), "model": d.get("model"), "manufacturer": d.get("manufacturer"), "identifiers": d.get("identifiers")}
            for d in idm_devices
        ],
        "entities": rows,
        "idm_heatpump_services": idm_services,
    }
    _save(_p("entity_export.json"), export)
    log(f"exported {len(rows)} entities, {len(idm_devices)} devices; services={idm_services}")
    return 0


async def cmd_services(args: argparse.Namespace) -> int:
    token = await _load_token()
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
        headers = {"Authorization": f"Bearer {token}"}
        async with session.get(f"{HA_URL}/api/services", headers=headers) as r:
            services = await r.json()
    idm = [s for s in services if s.get("domain") == "idm_heatpump"]
    ids = sorted(idm[0].get("services", {}).keys()) if idm else []
    _save(_p("services_snapshot.json"), {"at": now_iso(), "services": ids})
    log(f"services: {ids}")
    return 0


async def cmd_reload(args: argparse.Namespace) -> int:
    """#171 regression: services survive repeated config entry reloads."""
    token = await _load_token()
    expected = {"set_external_climate", "set_system_mode", "acknowledge_errors", "write_register", "start_dhw_boost", "cancel_dhw_boost"}
    rounds = args.rounds
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
        async with WS(session, token) as ws:
            # Resolve the real idm config entry id (HA preserves the preseeded id).
            try:
                raw = await ws.cmd("config_entries/get")
                raw_entries = raw.get("entries", []) if isinstance(raw, dict) else list(raw or [])
                eid = next((e.get("entry_id") for e in raw_entries if e.get("domain") == "idm_heatpump"), _entry_id())
            except Exception:
                eid = _entry_id()

            async def snapshot() -> set[str]:
                return await _service_set(session, token)

            async def reload_entry() -> None:
                headers = {"Authorization": f"Bearer {token}"}
                async with session.post(f"{HA_URL}/api/config/config_entries/entry/{eid}/reload", headers=headers, timeout=aiohttp.ClientTimeout(total=60)) as r:
                    if r.status not in (200, 202, 204):
                        raise RuntimeError(f"reload HTTP {r.status}: {await r.text()}")

            base = await snapshot()
            results = []
            for i in range(rounds):
                log(f"reload round {i+1}/{rounds} (entry {eid})")
                await reload_entry()
                await asyncio.sleep(15)  # let platforms re-init
                after = await snapshot()
                missing = sorted(expected - after)
                results.append({"round": i + 1, "services_after": sorted(after), "missing_expected": missing})
            _save(_p("reload_test.json"), {
                "started_at": now_iso(),
                "entry_id": eid,
                "base_services": sorted(base),
                "expected_subset": sorted(expected),
                "rounds": results,
                "base_missing_expected": sorted(expected - base),
                "verdict": "pass" if all(not r["missing_expected"] for r in results) and not (expected - base) else "fail",
            })
    with open(_p("reload_test.json"), encoding="utf-8") as fh:
        rep = json.load(fh)
    log(f"reload verdict: {rep['verdict']}")
    return 0 if rep["verdict"] == "pass" else 1


async def _service_set(session: aiohttp.ClientSession, token: str) -> set[str]:
    headers = {"Authorization": f"Bearer {token}"}
    async with session.get(f"{HA_URL}/api/services", headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as r:
        services = await r.json()
    for s in services:
        if s.get("domain") == "idm_heatpump":
            return set(s.get("services", {}).keys())
    return set()


async def cmd_stability(args: argparse.Namespace) -> int:
    token = await _load_token()
    minutes = float(os.environ.get("STABILITY_MINUTES", str(args.minutes)))
    end = time.time() + minutes * 60
    samples: list[dict[str, Any]] = []
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
        headers = {"Authorization": f"Bearer {token}"}
        n = 0
        while time.time() < end:
            n += 1
            t0 = time.time()
            try:
                async with session.get(f"{HA_URL}/api/states", headers=headers) as r:
                    states = await r.json()
                idm = [s for s in states if str(s.get("entity_id", "")).startswith(("sensor.idm", "binary_sensor.idm", "number.idm", "select.idm", "switch.idm", "climate.idm", "water_heater.idm", "button.idm"))]
                unavailable = sum(1 for s in idm if s.get("state") in ("unavailable", "unknown", None))
                samples.append({
                    "t": now_iso(), "elapsed_s": round(time.time() - (end - minutes * 60), 1),
                    "idm_entities": len(idm), "unavailable": unavailable, "fetch_s": round(time.time() - t0, 2),
                })
            except Exception as e:
                samples.append({"t": now_iso(), "error": str(e)})
            await asyncio.sleep(30)
    report = {
        "started_at": now_iso(), "duration_minutes": minutes,
        "samples": samples,
        "entity_count_min": min((s.get("idm_entities", 0) for s in samples if "idm_entities" in s), default=0),
        "entity_count_max": max((s.get("idm_entities", 0) for s in samples if "idm_entities" in s), default=0),
        "max_unavailable": max((s.get("unavailable", 0) for s in samples if "unavailable" in s), default=0),
        "sample_count": len(samples),
    }
    _save(_p("stability_report.json"), report)
    log(f"stability done: samples={len(samples)} min={report['entity_count_min']} max={report['entity_count_max']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("bootstrap")
    sub.add_parser("entities")
    sub.add_parser("services")
    p_reload = sub.add_parser("reload"); p_reload.add_argument("--rounds", type=int, default=3)
    p_stab = sub.add_parser("stability"); p_stab.add_argument("--minutes", type=float, default=60)
    args = parser.parse_args()
    try:
        rc = asyncio.run({
            "bootstrap": cmd_bootstrap, "entities": cmd_entities, "services": cmd_services,
            "reload": cmd_reload, "stability": cmd_stability,
        }[args.cmd](args))
    except KeyboardInterrupt:
        rc = 130
    return rc


if __name__ == "__main__":
    sys.exit(main())
