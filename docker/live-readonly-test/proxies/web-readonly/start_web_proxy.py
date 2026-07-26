"""Supervisor: run the HTTP read-only proxy (port 80) AND the Navigator 10
WebSocket read-only proxy (port 61220) in one container, so the integration's
single ``web_host`` (this service name) serves both Nav2.0 HTTP and Nav10 WS."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

from aiohttp import web, web_runner

from nav10_ws_proxy import build_app as build_ws_app, cfg as ws_cfg
from web_proxy import build_app as build_http_app, read_config as http_cfg

LOG = logging.getLogger("web-proxy-supervisor")


async def _serve(app: web.Application, host: str, port: str) -> web_runner.AppRunner:
    runner = web_runner.AppRunner(app, access_log=None)
    await runner.setup()
    site = web_runner.TCPSite(runner, host, int(port))
    await site.start()
    return runner


async def amain() -> None:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s %(message)s", stream=sys.stdout)
    http = http_cfg()
    ws = ws_cfg()
    log_dir = http["log_dir"]
    http_app = build_http_app(log_dir, http["backend"])
    ws_app = build_ws_app(log_dir, ws["backend_host"], ws["backend_port"])
    LOG.warning(
        "WEB PROXY SUPERVISOR: HTTP %s:%s -> %s | NAV10 WS %s:%s -> ws://%s:%s",
        http["listen_host"], http["listen_port"], http["backend"],
        ws["listen_host"], ws["listen_port"], ws["backend_host"], ws["backend_port"],
    )
    r1 = await _serve(http_app, http["listen_host"], http["listen_port"])
    r2 = await _serve(ws_app, ws["listen_host"], ws["listen_port"])
    try:
        while True:
            await asyncio.sleep(3600)
    finally:
        await r1.cleanup()
        await r2.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(amain())
    except KeyboardInterrupt:
        pass
