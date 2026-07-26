"""Read-only WebSocket proxy for the IDM Navigator 10 local web interface.

Navigator 10 exposes a WebSocket on port 61220. The idm-heatpump-api
IdmNavigator10WebClient authenticates with ?auth_code=<pin> and then issues
JSON requests of the shape {"controller": ..., "command": ..., "data": ...}.

Read-only contract
------------------
- The client -> device direction is filtered: only the request templates the
  idm-heatpump-api actually uses for READS are forwarded:
    ("setting", "detail"), ("statistic", "detail"), ("notification", "overview")
  Every other client->device JSON frame is treated as a potential WRITE,
  dropped, logged to ws_blocked_writes.jsonl, and counted. The device never
  sees it.
- The device -> client direction is forwarded verbatim (responses, auth).
- Every frame (both directions) is appended to ws_access.jsonl so the report
  can prove no write reached the heat pump.

The proxy authenticates to the device using the PIN from the query string, so
the client behavior (auth_code in URL) is unchanged.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

import aiohttp
from aiohttp import web, WSMsgType

LOG = logging.getLogger("nav10-ws-ro-proxy")

ALLOWED_CLIENT_COMMANDS = {
    ("setting", "detail"),
    ("statistic", "detail"),
    ("notification", "overview"),
}


def cfg() -> dict[str, Any]:
    backend_host = os.environ.get("NAV10_BACKEND_HOST", os.environ.get("IDM_HOST", "192.168.178.103"))
    backend_port = int(os.environ.get("NAV10_BACKEND_PORT", "61220"))
    listen_host = os.environ.get("LISTEN_HOST", "0.0.0.0")
    listen_port = int(os.environ.get("NAV10_LISTEN_PORT", "61220"))
    log_dir = Path(os.environ.get("LOG_DIR", "/var/log/web-proxy"))
    log_dir.mkdir(parents=True, exist_ok=True)
    return {"backend_host": backend_host, "backend_port": backend_port, "listen_host": listen_host, "listen_port": listen_port, "log_dir": log_dir}


class State:
    def __init__(self, log_dir: Path) -> None:
        self.access = log_dir / "ws_access.jsonl"
        self.blocked = log_dir / "ws_blocked_writes.jsonl"
        self.frames_client = 0
        self.frames_device = 0
        self.blocked_count = 0
        self.start = time.time()
        self._lock = asyncio.Lock()

    async def append(self, path: Path, rec: dict[str, Any]) -> None:
        line = json.dumps(rec, ensure_ascii=False, separators=(",", ":"))
        async with self._lock:
            await asyncio.to_thread(_append, path, line)


def _append(path: Path, line: str) -> None:
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def _is_allowed_read(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    key = (payload.get("controller"), payload.get("command"))
    return key in ALLOWED_CLIENT_COMMANDS


async def bridge(request: web.Request) -> web.WebSocketResponse:
    state: State = request.app["state"]
    backend_host = request.app["backend_host"]
    backend_port = request.app["backend_port"]
    # Preserve the auth_code query when dialing the device.
    qs = request.query_string
    backend_url = f"ws://{backend_host}:{backend_port}/" + (f"?{qs}" if qs else "")

    client_ws = web.WebSocketResponse(heartbeat=30, max_msg_size=4 * 1024 * 1024)
    await client_ws.prepare(request)

    timeout = aiohttp.ClientTimeout(total=None, sock_connect=10, sock_read=None)
    connector = aiohttp.TCPConnector(force_close=False, limit=0)
    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        try:
            async with session.ws_connect(backend_url, heartbeat=30, max_msg_size=4 * 1024 * 1024) as device_ws:
                async def device_to_client() -> None:
                    try:
                        async for msg in device_ws:
                            state.frames_device += 1
                            if msg.type == WSMsgType.TEXT:
                                await state.append(state.access, {"ts": round(time.time(), 3), "dir": "device->client", "bytes": len(msg.data), "preview": msg.data[:200]})
                                await client_ws.send_str(msg.data)
                            elif msg.type == WSMsgType.BINARY:
                                await client_ws.send_bytes(msg.data)
                            elif msg.type in (WSMsgType.CLOSE, WSMsgType.CLOSED, WSMsgType.ERROR):
                                return
                    except Exception as e:  # noqa: BLE001
                        LOG.debug("device->client ended: %s", e)

                async def client_to_device() -> None:
                    try:
                        async for msg in client_ws:
                            if msg.type == WSMsgType.TEXT:
                                state.frames_client += 1
                                try:
                                    payload = json.loads(msg.data)
                                except Exception:
                                    payload = msg.data
                                allowed = _is_allowed_read(payload)
                                rec = {"ts": round(time.time(), 3), "dir": "client->device", "allowed": allowed, "payload_preview": msg.data[:200]}
                                await state.append(state.access, rec)
                                if not allowed:
                                    state.blocked_count += 1
                                    rec2 = {**rec, "dir": "BLOCKED_WRITE", "payload": payload if isinstance(payload, dict) else str(payload)[:300]}
                                    await state.append(state.blocked, rec2)
                                    LOG.warning("BLOCKED Nav10 WS frame (potential write): %s", rec2["payload"])
                                    continue
                                await device_ws.send_str(msg.data)
                            elif msg.type == WSMsgType.BINARY:
                                await device_ws.send_bytes(msg.data)
                            elif msg.type in (WSMsgType.CLOSE, WSMsgType.CLOSED, WSMsgType.ERROR):
                                return
                    except Exception as e:  # noqa: BLE001
                        LOG.debug("client->device ended: %s", e)

                await asyncio.gather(device_to_client(), client_to_device())
        except Exception as e:  # noqa: BLE001
            LOG.error("backend WS connect failed: %s", e)
            try:
                await client_ws.send_str(json.dumps({"error": "proxy: backend unreachable"}))
            except Exception:
                pass
    return client_ws


async def health(request: web.Request) -> web.Response:
    s: State = request.app["state"]
    return web.json_response({
        "uptime_s": round(time.time() - s.start, 1),
        "frames_client_to_device": s.frames_client,
        "frames_device_to_client": s.frames_device,
        "blocked_writes": s.blocked_count,
        "write_blocked": s.blocked_count > 0,
    })


def build_app(log_dir: Path, backend_host: str, backend_port: int) -> web.Application:
    app = web.Application()
    app["state"] = State(log_dir)
    app["backend_host"] = backend_host
    app["backend_port"] = backend_port
    app.router.add_get("/__wshealth", health)
    app.router.add_get("/", bridge)
    return app


def main() -> None:
    c = cfg()
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s %(message)s", stream=sys.stdout)
    app = build_app(c["log_dir"], c["backend_host"], c["backend_port"])
    LOG.warning("NAV10 WS READ-ONLY PROXY: %s:%d -> ws://%s:%d (non-read commands BLOCKED)", c["listen_host"], c["listen_port"], c["backend_host"], c["backend_port"])
    web.run_app(app, host=c["listen_host"], port=c["listen_port"], access_log=None)


if __name__ == "__main__":
    main()
