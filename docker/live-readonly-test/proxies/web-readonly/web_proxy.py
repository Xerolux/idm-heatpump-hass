"""Read-only HTTP reverse proxy for the IDM Navigator 2.0 web interface.

Safety contract
---------------
- Allows: GET, HEAD (any path)  -> covers all data reads of
  IdmNavigator20WebClient (it reads with ``session.request("GET", ...)``).
- Allows: POST only on the login-handshake paths used by idm-heatpump-api's
  IdmNavigator20WebClient._try_login(): "/", "/index.php", "/login.php".
- Blocks: PUT, DELETE, PATCH, and any POST to other paths. Also blocks other
  exotic methods. A blocked request is answered with HTTP 405, logged to the
  blocked-writes log, and counted.
- Cookies are forwarded transparently (client->backend Cookie header and
  backend->client Set-Cookie header), so the PIN login session works exactly
  as without the proxy.

Every request is appended to a JSON-lines access log; blocked requests are
additionally appended to web_blocked_writes.jsonl.

Run:  python web_proxy.py
Config via env (see read_config).
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

from aiohttp import ClientSession, ClientTimeout, web

LOG = logging.getLogger("web-ro-proxy")

LOGIN_POST_PATHS = {"/", "/index.php", "/login.php"}
ALLOWED_METHODS = {"GET", "HEAD", "POST"}
HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "host",
    "content-length",
}


def read_config() -> dict[str, Any]:
    backend = os.environ.get("BACKEND_URL", "http://192.168.178.103:80").rstrip("/")
    listen_host = os.environ.get("LISTEN_HOST", "0.0.0.0")
    listen_port = int(os.environ.get("LISTEN_PORT", "8080"))
    log_dir = Path(os.environ.get("LOG_DIR", "/var/log/web-proxy"))
    log_dir.mkdir(parents=True, exist_ok=True)
    return {
        "backend": backend,
        "listen_host": listen_host,
        "listen_port": listen_port,
        "log_dir": log_dir,
    }


class State:
    def __init__(self, log_dir: Path) -> None:
        self.log_dir = log_dir
        self.access_log = log_dir / "web_access.jsonl"
        self.blocked_log = log_dir / "web_blocked_writes.jsonl"
        self.requests_total = 0
        self.gets_allowed = 0
        self.posts_allowed = 0
        self.blocked = 0
        self.backend_errors = 0
        self.start_time = time.time()

    async def append(self, path: Path, rec: dict[str, Any]) -> None:
        line = json.dumps(rec, ensure_ascii=False, separators=(",", ":"))
        await asyncio.to_thread(_append_line, path, line)


def _append_line(path: Path, line: str) -> None:
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def _filtered_headers(headers) -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in headers.items():
        if k.lower() in HOP_BY_HOP:
            continue
        out[k] = v
    return out


async def handler(request: web.Request) -> web.StreamResponse:
    app = request.app
    state: State = app["state"]
    backend: str = app["backend"]
    method = request.method
    path = request.path_qs
    now = time.time()
    state.requests_total += 1

    blocked = False
    if method not in ALLOWED_METHODS:
        blocked = True
    elif method == "POST" and path.split("?", 1)[0] not in LOGIN_POST_PATHS:
        blocked = True

    if blocked:
        state.blocked += 1
        rec = {
            "ts": round(now, 3),
            "iso": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(now)),
            "dir": "BLOCKED_WRITE",
            "method": method,
            "path": path,
            "peer": str(request.remote),
        }
        await state.append(state.access_log, rec)
        await state.append(state.blocked_log, rec)
        LOG.warning("BLOCKED web %s %s from %s", method, path, request.remote)
        return web.Response(status=405, text="read-only proxy: method not allowed\n")

    body = await request.read() if method in ("POST", "PUT", "PATCH") else None
    fwd_headers = _filtered_headers(request.headers)
    url = backend + path

    try:
        timeout = ClientTimeout(total=float(os.environ.get("BACKEND_TIMEOUT", "10")))
        async with ClientSession(timeout=timeout) as session:
            async with session.request(method, url, headers=fwd_headers, data=body, allow_redirects=False) as upstream:
                status = upstream.status
                resp_body = await upstream.read()
                resp_headers = []
                for k, v in upstream.headers.items():
                    if k.lower() in HOP_BY_HOP:
                        continue
                    # Forward Set-Cookie so the login session cookie reaches the client.
                    resp_headers.append((k, v))
                if method == "GET":
                    state.gets_allowed += 1
                elif method == "POST":
                    state.posts_allowed += 1
                rec = {
                    "ts": round(now, 3),
                    "iso": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(now)),
                    "dir": "ALLOWED",
                    "method": method,
                    "path": path,
                    "status": status,
                    "resp_bytes": len(resp_body),
                    "peer": str(request.remote),
                }
                await state.append(state.access_log, rec)
                out = web.StreamResponse(status=status, headers=dict(resp_headers))
                if method != "HEAD":
                    out.body = resp_body
                return out
    except Exception as err:
        state.backend_errors += 1
        rec = {
            "ts": round(now, 3),
            "iso": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(now)),
            "dir": "BACKEND_ERROR",
            "method": method,
            "path": path,
            "error": str(err),
            "peer": str(request.remote),
        }
        await state.append(state.access_log, rec)
        LOG.error("backend error for %s %s: %s", method, path, err)
        return web.Response(status=502, text="read-only proxy: backend unreachable\n")


async def health(request: web.Request) -> web.Response:
    state: State = request.app["state"]
    stats = {
        "uptime_s": round(time.time() - state.start_time, 1),
        "requests_total": state.requests_total,
        "gets_allowed": state.gets_allowed,
        "posts_allowed": state.posts_allowed,
        "blocked": state.blocked,
        "backend_errors": state.backend_errors,
        "write_blocked": state.blocked > 0,
    }
    return web.json_response(stats)


def build_app(log_dir: Path, backend: str) -> web.Application:
    app = web.Application(client_max_size=10 * 1024 * 1024)
    app["state"] = State(log_dir)
    app["backend"] = backend
    app.router.add_get("/__health", health)
    app.router.add_route("*", "/{tail:.*}", handler)
    return app


def main() -> None:
    cfg = read_config()
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stdout,
    )
    app = build_app(cfg["log_dir"], cfg["backend"])
    LOG.warning(
        "WEB READ-ONLY PROXY: listening %s:%d -> backend %s (non-login writes BLOCKED)",
        cfg["listen_host"],
        cfg["listen_port"],
        cfg["backend"],
    )
    web.run_app(app, host=cfg["listen_host"], port=cfg["listen_port"], access_log=None)


if __name__ == "__main__":
    main()
