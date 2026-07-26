"""Read-only Modbus TCP proxy for the IDM live test environment.

Safety contract
---------------
- Allows ONLY read function codes: 1, 2, 3, 4 (read coils/discrete inputs/
  holding registers/input registers). The idm-heatpump-api uses 0x03 and 0x04
  for all reads.
- BLOCKS every other function code, in particular the write codes used by the
  idm-heatpump-api: 0x05 (write single coil), 0x06 (write single register),
  0x0F (write multiple coils), 0x10 (write multiple registers), 0x16 (mask
  write), 0x17 (read/write multiple). Also 0x14/0x15 (read file/write file),
  0x18 (read FIFO), 0x2B (encapsulated interface) are blocked.
- For a blocked request the proxy:
    * does NOT forward anything to the backend heat pump,
    * writes a record to the blocked-writes log,
    * increments the blocked counter,
    * returns a Modbus exception response (exception code 1 = Illegal Function)
      so the client observes an unmistakable failure.

Every request (allowed or blocked) is appended to a JSON-lines access log so
the final report can prove "no write attempt reached the heat pump".

The proxy is connection-less at the Modbus level: it transparently forwards
the raw TCP frame for allowed requests, so it works regardless of pymodbus
version on the client side.

Run:  python modbus_proxy.py
Config via env (see read_config). Defaults match docker-compose.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import socket
import sys
import time
from pathlib import Path
from typing import Any

LOG = logging.getLogger("modbus-ro-proxy")

READ_FUNCTION_CODES = frozenset({1, 2, 3, 4})

# Human-readable names for the common function codes, used only for logging.
FC_NAMES = {
    1: "read_coils",
    2: "read_discrete_inputs",
    3: "read_holding_registers",
    4: "read_input_registers",
    5: "write_single_coil",
    6: "write_single_register",
    15: "write_multiple_coils",
    16: "write_multiple_registers",
    22: "mask_write_register",
    23: "read_write_multiple_registers",
    20: "read_file_record",
    21: "write_file_record",
    24: "read_fifo_queue",
    43: "encapsulated_interface",
}


def read_config() -> dict[str, Any]:
    backend_host = os.environ.get("BACKEND_HOST", "192.168.178.103")
    backend_port = int(os.environ.get("BACKEND_PORT", "502"))
    listen_host = os.environ.get("LISTEN_HOST", "0.0.0.0")
    listen_port = int(os.environ.get("LISTEN_PORT", "5020"))
    log_dir = Path(os.environ.get("LOG_DIR", "/var/log/modbus-proxy"))
    log_dir.mkdir(parents=True, exist_ok=True)
    return {
        "backend_host": backend_host,
        "backend_port": backend_port,
        "listen_host": listen_host,
        "listen_port": listen_port,
        "log_dir": log_dir,
    }


class ProxyState:
    """Shared counters written by every connection, read by health handler."""

    def __init__(self, log_dir: Path) -> None:
        self.log_dir = log_dir
        self.access_log_path = log_dir / "modbus_access.jsonl"
        self.blocked_log_path = log_dir / "modbus_blocked_writes.jsonl"
        self.requests_total = 0
        self.reads_allowed = 0
        self.writes_blocked = 0
        self.backend_errors = 0
        self.start_time = time.time()
        # One append handle per line; keep buffers tiny, flush per record.
        self._lock = asyncio.Lock()

    async def _append(self, path: Path, record: dict[str, Any]) -> None:
        line = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
        async with self._lock:
            await asyncio.to_thread(_append_line, path, line)

    async def log_access(self, record: dict[str, Any]) -> None:
        await self._append(self.access_log_path, record)

    async def log_blocked(self, record: dict[str, Any]) -> None:
        await self._append(self.blocked_log_path, record)


def _append_line(path: Path, line: str) -> None:
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def make_exception_response(transaction_id: int, unit_id: int, fc: int, code: int) -> bytes:
    """Build a Modbus TCP exception response frame (MBAP + PDU)."""
    pdu = bytes([fc | 0x80, code])
    # MBAP: transaction(2), protocol(2)=0, length(2), unit(1)
    length = len(pdu) + 1  # +1 for unit id
    mbap = transaction_id.to_bytes(2, "big") + (0).to_bytes(2, "big") + length.to_bytes(2, "big") + bytes([unit_id])
    return mbap + pdu


async def _read_exactly(reader: asyncio.StreamReader, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = await reader.read(n - len(buf))
        if not chunk:
            raise ConnectionResetError("client closed connection mid-frame")
        buf.extend(chunk)
    return bytes(buf)


async def _open_backend(host: str, port: int, timeout: float) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
    return await asyncio.wait_for(asyncio.open_connection(host, port), timeout=timeout)


async def handle_client(
    reader: asyncio.StreamReader,
    writer: StreamWriter,  # type: ignore[name-defined]
    state: ProxyState,
    backend_host: str,
    backend_port: int,
) -> None:
    peer = writer.get_extra_info("peername")
    backend: tuple[asyncio.StreamReader, asyncio.StreamWriter] | None = None
    try:
        while True:
            try:
                mbap = await _read_exactly(reader, 7)
            except ConnectionResetError:
                break
            if len(mbap) != 7:
                break
            transaction_id = int.from_bytes(mbap[0:2], "big")
            length = int.from_bytes(mbap[4:6], "big")
            unit_id = mbap[6]
            pdu_len = length - 1
            if pdu_len < 1:
                break
            try:
                pdu = await _read_exactly(reader, pdu_len)
            except ConnectionResetError:
                break
            fc = pdu[0]
            state.requests_total += 1
            fc_name = FC_NAMES.get(fc, f"fc_{fc}")
            now = time.time()

            # Extract address/count for read requests (FC 1-4) and write
            # requests (FC 5,6,15,16) for better logging.
            meta = _decode_pdu_meta(fc, pdu)

            if fc not in READ_FUNCTION_CODES:
                state.writes_blocked += 1
                rec = {
                    "ts": round(now, 3),
                    "iso": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(now)),
                    "peer": _peer(peer),
                    "dir": "BLOCKED_WRITE",
                    "fc": fc,
                    "fc_name": fc_name,
                    "unit": unit_id,
                    "transaction": transaction_id,
                    "pdu_hex": pdu.hex(),
                    **meta,
                }
                await state.log_access(rec)
                await state.log_blocked(rec)
                LOG.warning("BLOCKED write attempt fc=%d (%s) from %s %s", fc, fc_name, _peer(peer), meta)
                # Return exception code 1 (Illegal Function) so the client
                # fails loudly and any test driving a write is recorded.
                exc = make_exception_response(transaction_id, unit_id, fc, 1)
                writer.write(exc)
                await writer.drain()
                continue

            # Allowed read: forward to backend transparently.
            if backend is None:
                try:
                    backend = await _open_backend(backend_host, backend_port, timeout=5.0)
                except Exception as err:
                    state.backend_errors += 1
                    LOG.error("cannot reach backend %s:%d: %s", backend_host, backend_port, err)
                    exc = make_exception_response(transaction_id, unit_id, fc, 4)  # Server Path Unavailable-ish
                    writer.write(exc)
                    await writer.drain()
                    rec = {
                        "ts": round(now, 3),
                        "iso": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(now)),
                        "peer": _peer(peer),
                        "dir": "BACKEND_ERROR",
                        "fc": fc,
                        "fc_name": fc_name,
                        "unit": unit_id,
                        "transaction": transaction_id,
                        "error": str(err),
                        **meta,
                    }
                    await state.log_access(rec)
                    continue
            backend_reader, backend_writer = backend
            # Forward original frame verbatim.
            frame = mbap + pdu
            backend_writer.write(frame)
            await backend_writer.drain()
            try:
                resp_mbap = await asyncio.wait_for(_read_exactly(backend_reader, 7), timeout=10.0)
            except Exception as err:
                state.backend_errors += 1
                LOG.error("backend read error: %s", err)
                rec = {
                    "ts": round(now, 3),
                    "iso": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(now)),
                    "peer": _peer(peer),
                    "dir": "BACKEND_ERROR",
                    "fc": fc,
                    "fc_name": fc_name,
                    "unit": unit_id,
                    "transaction": transaction_id,
                    "error": str(err),
                    **meta,
                }
                await state.log_access(rec)
                break
            resp_len = int.from_bytes(resp_mbap[4:6], "big")
            resp_rest_len = max(0, resp_len - 1)
            try:
                resp_rest = await asyncio.wait_for(_read_exactly(backend_reader, resp_rest_len + 0), timeout=10.0)
            except Exception as err:
                state.backend_errors += 1
                LOG.error("backend read error (body): %s", err)
                break
            # Detect backend-side exception responses (FC | 0x80).
            resp_pdu_head = resp_rest[0] if resp_rest else 0
            is_exception = bool(resp_pdu_head & 0x80)
            state.reads_allowed += 1
            writer.write(resp_mbap + resp_rest)
            await writer.drain()
            rec = {
                "ts": round(now, 3),
                "iso": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(now)),
                "peer": _peer(peer),
                "dir": "READ_OK" if not is_exception else "READ_EXCEPTION",
                "fc": fc,
                "fc_name": fc_name,
                "unit": unit_id,
                "transaction": transaction_id,
                "resp_bytes": 7 + len(resp_rest),
                "backend_exception": is_exception,
                **meta,
            }
            await state.log_access(rec)
    except Exception:
        LOG.exception("connection handler crashed for %s", _peer(peer))
    finally:
        try:
            writer.close()
        except Exception:
            pass
        if backend is not None:
            try:
                backend[1].close()
            except Exception:
                pass


def _decode_pdu_meta(fc: int, pdu: bytes) -> dict[str, Any]:
    """Best-effort decode of address/count (reads) or address/value (writes)."""
    try:
        if fc in (1, 2, 3, 4) and len(pdu) >= 5:
            addr = int.from_bytes(pdu[1:3], "big")
            count = int.from_bytes(pdu[3:5], "big")
            return {"address": addr, "count": count}
        if fc in (5, 6) and len(pdu) >= 5:
            addr = int.from_bytes(pdu[1:3], "big")
            value = int.from_bytes(pdu[3:5], "big")
            return {"address": addr, "value": value}
        if fc in (15, 16) and len(pdu) >= 5:
            addr = int.from_bytes(pdu[1:3], "big")
            count = int.from_bytes(pdu[3:5], "big")
            return {"address": addr, "count": count, "byte_count": pdu[5] if len(pdu) > 5 else None}
        if fc == 22 and len(pdu) >= 7:
            addr = int.from_bytes(pdu[1:3], "big")
            return {"address": addr}
        if fc == 23 and len(pdu) >= 8:
            read_addr = int.from_bytes(pdu[1:3], "big")
            write_addr = int.from_bytes(pdu[5:7], "big")
            return {"read_address": read_addr, "write_address": write_addr}
    except Exception:
        return {}
    return {}


def _peer(peer: Any) -> str:
    if isinstance(peer, tuple) and len(peer) >= 2:
        return f"{peer[0]}:{peer[1]}"
    return str(peer)


async def health_server(state: ProxyState, host: str, port: int) -> None:
    """Tiny TCP health endpoint: connect, read JSON stats, close."""

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        stats = {
            "uptime_s": round(time.time() - state.start_time, 1),
            "requests_total": state.requests_total,
            "reads_allowed": state.reads_allowed,
            "writes_blocked": state.writes_blocked,
            "backend_errors": state.backend_errors,
            "write_blocked": state.writes_blocked > 0,
        }
        data = (json.dumps(stats) + "\n").encode()
        writer.write(data)
        await writer.drain()
        writer.close()

    server = await asyncio.start_server(handle, host, port)
    async with server:
        await server.serve_forever()


async def amain() -> None:
    cfg = read_config()
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stdout,
    )
    state = ProxyState(cfg["log_dir"])
    LOG.warning(
        "MODBUS READ-ONLY PROXY: listening %s:%d -> backend %s:%d (writes BLOCKED)",
        cfg["listen_host"],
        cfg["listen_port"],
        cfg["backend_host"],
        cfg["backend_port"],
    )
    server = await asyncio.start_server(
        lambda r, w: handle_client(r, w, state, cfg["backend_host"], cfg["backend_port"]),
        cfg["listen_host"],
        cfg["listen_port"],
    )
    health = asyncio.create_task(health_server(state, "0.0.0.0", 5021))
    async with server:
        await server.serve_forever()
    await health


if __name__ == "__main__":
    try:
        asyncio.run(amain())
    except KeyboardInterrupt:
        pass
