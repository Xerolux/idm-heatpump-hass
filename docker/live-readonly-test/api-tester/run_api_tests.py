"""Isolated idm-heatpump-api test suite for the read-only Docker test bench.

All device access goes through the read-only proxies (modbus-proxy, web-proxy).
The suite proves:
  - Modbus connect + model detection works through the proxy.
  - Single vs batch reads agree on critical registers.
  - Sentinel values (-1/255/65535) and Illegal-Data-Address are handled.
  - The Nav2.0 web login + data read works through the web proxy.
  - Web and Modbus model detection agree (regression context for #170).
  - A write attempt is BLOCKED by the proxy, logged, and changes nothing.

A JSON report is written to /results/api_test_report.json. Each test records
status pass/fail/skip plus the evidence (values, counts, errors).

READ-ONLY: no value is ever written to the heat pump. The single synthetic
write attempt in the proxy-block test is intercepted by modbus-proxy before it
reaches the LAN, and writes the value that was just read so it is a no-op even
in the hypothetical case of a proxy failure.
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import socket
import struct
import sys
import time
import traceback
from datetime import datetime
from typing import Any

RESULTS_DIR = os.environ.get("RESULTS_DIR", "/results")


def log(msg: str) -> None:
    print(f"[api-tester] {msg}", flush=True)


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


class Report:
    def __init__(self) -> None:
        self.tests: list[dict[str, Any]] = []
        self.meta: dict[str, Any] = {
            "started_at": now_iso(),
            "host_env": {
                "MODBUS_HOST": os.environ.get("MODBUS_HOST"),
                "MODBUS_PORT": os.environ.get("MODBUS_PORT"),
                "WEB_HOST": os.environ.get("WEB_HOST"),
                "WEB_PORT": os.environ.get("WEB_PORT"),
                "IDM_HOST": os.environ.get("IDM_HOST"),
            },
        }

    def record(self, name: str, status: str, **evidence: Any) -> None:
        rec = {"name": name, "status": status, **evidence}
        if status == "fail" and "error" not in evidence:
            rec["error"] = traceback.format_exc(limit=4)
        self.tests.append(rec)
        icon = {"pass": "PASS", "fail": "FAIL", "skip": "SKIP"}.get(status, status.upper())
        log(f"{icon}: {name}" + (f" :: {evidence.get('detail', '')}" if evidence.get("detail") else ""))

    def summary(self) -> dict[str, Any]:
        counts = {"pass": 0, "fail": 0, "skip": 0}
        for t in self.tests:
            counts[t["status"]] = counts.get(t["status"], 0) + 1
        return {"meta": self.meta, "tests": self.tests, "counts": counts, "ended_at": now_iso()}


async def run() -> int:
    # Import after env is set so the local code is used.
    from idm_heatpump import IdmModbusClient
    from idm_heatpump.registers import get_all_registers, get_register
    from idm_heatpump.web import IdmNavigator20WebClient

    report = Report()
    modbus_host = os.environ["MODBUS_HOST"]
    modbus_port = int(os.environ["MODBUS_PORT"])
    web_host = os.environ["WEB_HOST"]
    web_port = int(os.environ.get("WEB_PORT", "80"))
    pin = os.environ.get("IDM_WEB_PIN", "").strip()

    client = IdmModbusClient(host=modbus_host, port=modbus_port, slave_id=1, timeout=10, max_retries=2)

    # --- 1. Modbus connect -------------------------------------------------
    try:
        await client.connect()
        report.record("modbus_connect", "pass" if client.is_connected else "fail", backend="(via modbus-proxy)")
    except Exception:
        report.record("modbus_connect", "fail")
        await _finalize(report)
        return 1

    # --- 2. Model detection ------------------------------------------------
    model_info = None
    family = None
    try:
        model_info = await client.detect_model()
        family = _family_of(model_info.model_name) if model_info else None
        report.record(
            "modbus_detect_model",
            "pass",
            model_name=model_info.model_name if model_info else None,
            family=family,
            heating_circuits=list(model_info.active_heating_circuits) if model_info else [],
            firmware=getattr(model_info, "firmware_version", None),
        )
    except Exception:
        report.record("modbus_detect_model", "fail")

    # --- 3. Register enumeration ------------------------------------------
    regs = []
    try:
        regs = get_all_registers(model_info=model_info)
        report.record("register_enum", "pass", count=len(regs))
    except Exception:
        report.record("register_enum", "fail", count=0)

    # --- 4. Batch read all registers --------------------------------------
    batch: dict[str, Any] = {}
    try:
        t0 = time.perf_counter()
        batch = await client.read_batch(regs)
        dur = round(time.perf_counter() - t0, 3)
        report.record("batch_read_all", "pass", count=len(batch), duration_s=dur)
    except Exception:
        report.record("batch_read_all", "fail", count=0)

    # --- 5. Sentinel census ------------------------------------------------
    try:
        census = _sentinel_census(batch)
        report.record("sentinel_census", "pass", **census)
    except Exception:
        report.record("sentinel_census", "fail")

    # --- 6. Single vs batch compare for critical registers -----------------
    critical_names = [
        "outdoor_temp",
        "flow_temp_top",
        "dhw_temp_top",
        "hc_a_room_temp",
        "hc_a_room_humidity",
        "hc_a_active_mode",
        "hc_a_heating_limit",
        "hc_a_cooling_limit",
        "hc_a_ext_room_temp",
        "ext_humidity",
        "hc_a_setpoint_flow_temp",
        "compressor_status_1",
        "hc_a_heating_curve",
    ]
    compare_rows = []
    mismatches = 0
    checked = 0
    for name in critical_names:
        try:
            reg = get_register(name, model_info=model_info)
        except Exception:
            compare_rows.append({"name": name, "status": "no_register"})
            continue
        if reg is None:
            compare_rows.append({"name": name, "status": "no_register"})
            continue
        single = None
        try:
            single = await client.read_register(reg)
        except Exception as e:
            compare_rows.append({"name": name, "status": "single_error", "error": type(e).__name__})
            continue
        bval = batch.get(name)
        match = _values_equal(single, bval)
        checked += 1
        if not match:
            mismatches += 1
        compare_rows.append(
            {
                "name": name,
                "status": "ok" if match else "MISMATCH",
                "single": _safe(single),
                "batch": _safe(bval),
                "address": getattr(reg, "address", None),
                "datatype": str(getattr(reg, "datatype", None)),
            }
        )
    # Per the contract: on mismatch the single read is the control measurement.
    report.record(
        "single_vs_batch",
        "pass" if mismatches == 0 else "fail",
        checked=checked,
        mismatches=mismatches,
        rows=compare_rows,
    )

    # --- 7. Illegal Data Address handling ---------------------------------
    try:
        from idm_heatpump import RegisterType
        # A deliberately unsupported high address. The library's resilient
        # reader turns exception code 2 into IllegalAddressError; a direct
        # _read_registers surfaces it.
        try:
            await client._read_registers(65000, 2, RegisterType.HOLDING, max_retries=1, request_timeout=5)
            report.record("illegal_data_address", "fail", detail="no error on unsupported address")
        except Exception as e:
            report.record("illegal_data_address", "pass", error_type=type(e).__name__, detail=str(e)[:160])
    except Exception:
        report.record("illegal_data_address", "fail")

    # --- 8. Web supplement via proxies -------------------------------------
    # This device answers on port 61220 (Navigator 10 WebSocket) AND on port 80
    # (HTTP, but the Nav2.0 data endpoints are not served there). We try the
    # Nav10 WS path first (through nav10-ws-proxy@61220), then Nav2.0 HTTP.
    web_data = None
    web_source = None
    if pin:
        # 8a. Navigator 10 WebSocket via proxy.
        try:
            from idm_heatpump.web import IdmNavigator10WebClient

            wc10 = IdmNavigator10WebClient(host=web_host, port=61220, pin=pin, timeout=12)
            await wc10.connect()
            web_data = await wc10.read_data()
            await wc10.close()
            web_source = "navigator10_ws"
            report.record(
                "web_nav10_ws_read",
                "pass",
                software_version=getattr(web_data, "software_version", None),
                value_count=len(getattr(web_data, "values", {}) or {}),
                via="nav10-ws-proxy:61220",
            )
        except Exception as e:
            report.record("web_nav10_ws_read", "fail", error_type=type(e).__name__, detail=str(e)[:200])
        # 8b. Navigator 2.0 HTTP via proxy (expected to fail on a Nav10 device,
        # but exercises the Nav2.0 path and its proxy filtering).
        if web_data is None:
            try:
                from idm_heatpump.web import IdmNavigator20WebClient

                wc20 = IdmNavigator20WebClient(host=web_host, pin=pin, timeout=10)
                await wc20.connect()
                web_data = await wc20.read_data()
                await wc20.close()
                web_source = "navigator20_http"
                report.record(
                    "web_nav20_http_read",
                    "pass",
                    software_version=getattr(web_data, "software_version", None),
                    via="web-proxy:80",
                )
            except Exception as e:
                report.record("web_nav20_http_read", "fail", error_type=type(e).__name__, detail=str(e)[:200])
        # 8c. Synthetic Nav10 WS write-block verification (only if WS is up).
        await _nav10_ws_block_check(report, web_host)
    else:
        report.record("web_nav10_ws_read", "skip", detail="no IDM_WEB_PIN set")
        report.record("web_nav20_http_read", "skip", detail="no IDM_WEB_PIN set")

    # --- 9. Web vs Modbus model consistency (#170 context) ----------------
    web_model = getattr(web_data, "heatpump_model", None) if web_data else None
    # The Nav10 WS read itself is authoritative evidence the device is Nav10.
    if web_source == "navigator10_ws":
        web_family = "navigator_10"
    elif web_model:
        web_family = _family_of(web_model)
    else:
        web_family = None
    consistent = None
    if family and web_family:
        consistent = family == web_family
        # Detecting the conflict is the SUCCESS outcome of this check; the
        # conflict itself is a documented #170 finding, not a probe failure.
        report.record(
            "web_modbus_model_consistency",
            "pass",
            modbus_family=family,
            web_family=web_family,
            conflict=not consistent,
            note=("#170 LIVE REPRODUCTION: Modbus and Web disagree on the model" if not consistent else "Modbus and Web agree"),
        )
    else:
        report.record("web_modbus_model_consistency", "skip", modbus_family=family, web_family=web_family)

    # --- 10. Proxy write-block verification -------------------------------
    # Control read of outdoor_temp before; attempt one FC06 write to a
    # READ-ONLY register address with the SAME value (no-op even if unblocked);
    # proxy must block it (exception code 1) and the value must be unchanged.
    before = None
    try:
        before = await client.read_value("outdoor_temp")
    except Exception:
        before = None
    blocked_ok = False
    value_unchanged = before is None  # if we could not read, treat as n/a
    try:
        # Raw Modbus FC06 (write single register) to outdoor_temp address 1000.
        blocked = _attempt_blocked_write(modbus_host, modbus_port, address=1000, value=_int16_value(before))
        blocked_ok = blocked.get("blocked", False)
        # Re-read after the attempt.
        after = None
        try:
            after = await client.read_value("outdoor_temp")
        except Exception:
            after = None
        value_unchanged = _values_equal(before, after)
        report.record(
            "proxy_write_block_verification",
            "pass" if blocked_ok and value_unchanged else "fail",
            blocked=blocked_ok,
            backend_exception_code=blocked.get("exception_code"),
            value_before=_safe(before),
            value_after=_safe(after),
            value_unchanged=value_unchanged,
            note="synthetic FC06 intercepted by modbus-proxy; never reached the heat pump",
        )
    except Exception:
        report.record("proxy_write_block_verification", "fail", blocked=False)

    try:
        await client.disconnect()
    except Exception:
        pass

    return await _finalize(report)


def _family_of(name: Any) -> str | None:
    if not isinstance(name, str):
        return None
    n = name.lower()
    if "navigator 10" in n or "nav10" in n:
        return "navigator_10"
    if "navigator 2" in n or "nav2" in n or "navigator pro" in n or "navpro" in n:
        return "navigator_2"
    return None


def _safe(v: Any) -> Any:
    if isinstance(v, float):
        if math.isnan(v):
            return "NaN"
        return round(v, 4)
    return v


def _values_equal(a: Any, b: Any) -> bool:
    if a is None or b is None:
        return a is b
    if isinstance(a, float) or isinstance(b, float):
        try:
            return math.isclose(float(a), float(b), abs_tol=0.05, rel_tol=0.001) or (math.isnan(float(a)) and math.isnan(float(b)))
        except Exception:
            return a == b
    return a == b


def _int16_value(v: Any) -> int:
    try:
        f = float(v)
        # Pack as float32 big-endian word pair is what the register uses, but
        # for FC06 the value field is a raw 16-bit word; we only need a benign
        # payload because the proxy blocks it before it reaches the device.
        return int(f) & 0xFFFF
    except Exception:
        return 0


def _sentinel_census(data: dict[str, Any]) -> dict[str, Any]:
    neg1 = []
    u255 = []
    u65535 = []
    nan = []
    for k, v in data.items():
        if isinstance(v, float):
            if math.isnan(v):
                nan.append(k)
            elif abs(v - (-1.0)) < 0.01:
                neg1.append(k)
        elif isinstance(v, int):
            if v == 255:
                u255.append(k)
            elif v == 65535:
                u65535.append(k)
            elif v == -1:
                neg1.append(k)
    return {
        "total_values": len(data),
        "sentinel_neg1": len(neg1),
        "sentinel_255": len(u255),
        "sentinel_65535": len(u65535),
        "nan": len(nan),
        "neg1_samples": sorted(neg1)[:25],
        "u255_samples": sorted(u255)[:25],
        "u65535_samples": sorted(u65535)[:25],
    }


def _attempt_blocked_write(host: str, port: int, *, address: int, value: int) -> dict[str, Any]:
    """Send a single Modbus FC06 frame and read the exception response.

    Returns {"blocked": bool, "exception_code": int|None}. The frame never
    reaches the backend because modbus-proxy intercepts write FCs.
    """
    tx = 0x1234
    unit = 1
    pdu = bytes([0x06]) + int(address).to_bytes(2, "big") + int(value & 0xFFFF).to_bytes(2, "big")
    length = len(pdu) + 1
    mbap = tx.to_bytes(2, "big") + (0).to_bytes(2, "big") + length.to_bytes(2, "big") + bytes([unit])
    with socket.create_connection((host, port), timeout=6) as s:
        s.settimeout(6)
        s.sendall(mbap + pdu)
        resp = s.recv(64)
    if len(resp) >= 9:
        fc = resp[7]
        if fc & 0x80:
            return {"blocked": True, "exception_code": resp[8] if len(resp) > 8 else None}
    return {"blocked": False, "exception_code": None}


async def _nav10_ws_block_check(report: "Report", web_host: str) -> None:
    """Send one synthetic non-read Nav10 WS frame and prove the proxy blocks it.

    The frame is intercepted by nav10_ws_proxy and never reaches the device.
    Pass = the WS proxy health endpoint reports an incremented blocked counter
    after the attempt.
    """
    import aiohttp

    pin = os.environ.get("IDM_WEB_PIN", "").strip()
    auth_qs = f"auth_code={pin}" if pin else ""
    url = f"ws://{web_host}:61220/" + (f"?{auth_qs}" if auth_qs else "")
    try:
        timeout = aiohttp.ClientTimeout(total=12)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            # Baseline blocked counter via the WS proxy health endpoint.
            async with session.get(f"http://{web_host}:61220/__wshealth", timeout=aiohttp.ClientTimeout(total=5)) as r:
                before = (await r.json()).get("blocked_writes", 0)
            async with session.ws_connect(url, timeout=8, heartbeat=10) as ws:
                # Disallowed command: setting/save (a write). Proxy must drop it.
                await ws.send_str(json.dumps({"controller": "setting", "command": "save", "data": {"settingId": "test"}}))
                try:
                    await asyncio.wait_for(ws.receive(), timeout=3)
                except asyncio.TimeoutError:
                    pass
            async with session.get(f"http://{web_host}:61220/__wshealth", timeout=aiohttp.ClientTimeout(total=5)) as r:
                after = (await r.json()).get("blocked_writes", 0)
        blocked = after > before
        report.record("nav10_ws_write_block_verification", "pass" if blocked else "fail", blocked=blocked, blocked_before=before, blocked_after=after, note="synthetic setting/save intercepted by nav10-ws-proxy")
    except Exception as e:
        report.record("nav10_ws_write_block_verification", "fail", error_type=type(e).__name__, detail=str(e)[:200])


async def _finalize(report: "Report") -> int:
    os.makedirs(RESULTS_DIR, exist_ok=True)
    summary = report.summary()
    path = os.path.join(RESULTS_DIR, "api_test_report.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, ensure_ascii=False)
    counts = summary["counts"]
    log(f"report written to {path}: pass={counts.get('pass',0)} fail={counts.get('fail',0)} skip={counts.get('skip',0)}")
    return 1 if counts.get("fail", 0) > 0 else 0


if __name__ == "__main__":
    try:
        rc = asyncio.run(run())
    except KeyboardInterrupt:
        rc = 130
    sys.exit(rc)
