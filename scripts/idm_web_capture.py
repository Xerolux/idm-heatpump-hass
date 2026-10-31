#!/usr/bin/env python3
"""Capture raw read-only evidence from an IDM Navigator local web interface.

Support tool for issue reports: the integration logs *parsed* values, but
parser bugs need the raw pages/frames the controller actually serves. This
tool logs into the local web interface with the user-level web PIN, downloads
every known read-only page (Navigator 2.0 HTTP interface) and read-only
WebSocket frame (Navigator 10 / Pro interface), and packs them into a ZIP
the user can attach to a GitHub issue or send by e-mail.

Safety contract (deliberately narrow):

* The web PIN is prompted hidden (or passed via ``--pin``/``IDM_WEB_PIN``)
  and is **never** written into the ZIP, the manifest or any log line. The
  login request bodies are never captured either.
* Only read-only commands are sent: HTTP ``GET`` for pages, WebSocket
  ``detail``/``overview`` requests. There is no ``save``/``set``/write frame
  in this tool and no way to add one via command line.
* The tool never elevates access levels: it uses exactly the level the PIN
  grants and never sends technician-code or level-unlock requests.

Windows and Linux, Python 3.9+, standard library only — no pip install.

Usage:
    python idm_web_capture.py <host> [--pin PIN] [--web-port 80] [--ws-port 61220]
"""

from __future__ import annotations

import argparse
import base64
import getpass
import json
import os
import platform
import random
import re
import socket
import struct
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections.abc import Callable
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from http import cookiejar

SCRIPT_VERSION = "1.4.0"

DEFAULT_WEB_PORT = 80
DEFAULT_WS_PORT = 61220
DEFAULT_MODBUS_PORT = 502
DEFAULT_MODBUS_SLAVE = 1
DEFAULT_TIMEOUT = 10.0
REQUEST_DELAY = 0.1
MAX_RESPONSE_BYTES = 5 * 1024 * 1024

# Read-only Modbus sweep: fixed 50-word blocks over the documented input
# (FC04) and holding (FC03) ranges of every Navigator family. Nothing is
# decoded here — the raw words plus each block's status ARE the evidence
# (which blocks answer, which answer "illegal address", is exactly what a
# model-mismatch diagnosis needs). 50 words stays far below the 125-word
# protocol limit and keeps each block inside one documented register group.
MODBUS_INPUT_BLOCKS = tuple(range(1000, 1900, 50))
MODBUS_HOLDING_BLOCKS = tuple(range(2000, 2200, 50))
MODBUS_BLOCK_WORDS = 50

# --- Navigator 2.0 (plain HTTP interface) — mirrors idm-heatpump-api web.py ---

NAV20_LOGIN_PATHS = ("/", "/index.php", "/login.php")
NAV20_LOGIN_FIELDS = ("pin", "PIN", "password", "pass")
NAV20_DATA_PATHS = (
    "/data/settings.php",
    "/data/heatpump.php",
    "/data/info.php",
    "/data/state.php",
    "/data/status.php",
    "/data/values.php",
)
NAV20_STATISTICS_QUERIES = (
    ("heatpump", "/data/statistics.php?type=heatpump"),
    ("amountofheat", "/data/statistics.php?type=amountofheat"),
    ("baenergyhp", "/data/statistics.php?type=baenergyhp"),
)

# --- Navigator 10 / Pro (WebSocket interface) — mirrors idm-heatpump-api web.py ---

NAV10_SETTING_IDS = ("4768", "4775", "4782", "4789", "4754", "13259", "13256", "4537")
NAV10_HEATING_CIRCUITS = ("A", "B", "C", "D", "E", "F", "G")
NAV10_STATISTIC_TYPES = (0, 2, 3, 4, 5, 6)
NAV10_STATISTIC_PERIODS = (1, 7)


class CaptureError(Exception):
    """One capture step failed; the message goes into the manifest."""


# ----------------------------------------------------------------------------
# CSRF / page classification helpers (ported from idm-heatpump-api web.py)
# ----------------------------------------------------------------------------


class _CsrfTokenParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.token: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self.token:
            return
        attr_map = {name.lower(): value for name, value in attrs if value is not None}
        if tag == "input" and attr_map.get("name") == "csrf_token":
            self.token = attr_map.get("value")
        elif tag == "meta" and attr_map.get("name") == "csrf-token":
            self.token = attr_map.get("content")


_CSRF_TOKEN_PATTERNS = (
    r'csrf_token="([^"]+)"',
    r"csrf_token='([^']+)'",
    r'name="csrf_token"\s+value="([^"]+)"',
    r"name='csrf_token'\s+value='([^']+)'",
    r'content="([^"]+)"\s+name="csrf-token"',
    r'name="csrf-token"\s+content="([^"]+)"',
    r'csrfToken\s*=\s*"([^"]+)"',
    r"csrfToken\s*=\s*'([^']+)'",
    r'csrf_token\s*=\s*"([^"]+)"',
    r"csrf_token\s*=\s*'([^']+)'",
)

_LOGIN_FORM_RE = re.compile(r"<form\b", re.IGNORECASE)
_PASSWORD_INPUT_RE = re.compile(
    r'<input\b[^>]*(?:type=["\']password["\']|name=["\'](?:pin|password|pass)["\'])',
    re.IGNORECASE,
)


def extract_csrf_token(html_text: str) -> str | None:
    """Extract a NAV2 CSRF token from common HTML, meta and script variants."""
    parser = _CsrfTokenParser()
    parser.feed(html_text)
    if parser.token:
        return unescape(parser.token)
    for pattern in _CSRF_TOKEN_PATTERNS:
        match = re.search(pattern, html_text, flags=re.IGNORECASE)
        if match and match.group(1):
            return unescape(match.group(1))
    return None


def looks_like_login_page(text: str) -> bool:
    """Return True if the response looks like an HTML login page."""
    return bool(_LOGIN_FORM_RE.search(text) and _PASSWORD_INPUT_RE.search(text))


def looks_like_auth_failure(text: str) -> bool:
    """Return whether a JSON or text response explicitly rejects authentication."""
    stripped = text.strip()
    lowered = stripped.casefold()
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        payload = None
    if isinstance(payload, dict):
        if payload.get("authorized") is False or payload.get("authenticated") is False:
            return True
        status = str(payload.get("status", "")).casefold()
        if status in {"unauthorized", "forbidden", "authentication_failed"}:
            return True
    return any(
        marker in lowered
        for marker in (
            "authorization required",
            "authentication failed",
            "invalid pin",
            "pin rejected",
            "unauthorized",
            "forbidden",
        )
    )


# ----------------------------------------------------------------------------
# HTTP session for the Navigator 2.0 interface (stdlib urllib + cookies)
# ----------------------------------------------------------------------------


class HttpSession:
    """Cookie-keeping HTTP client returning rich results even on HTTP errors.

    ``request`` answers a ``(status, text, content_type, effective_url)``
    tuple: the content type and the URL after redirects tell a page that
    answers with data from one that bounces to an error handler — the exact
    difference a parser diagnosis needs.
    """

    def __init__(self, timeout: float) -> None:
        self._timeout = timeout
        self._jar = cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self._jar))

    def request(
        self,
        method: str,
        url: str,
        data: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, str, str | None, str | None]:
        body = urllib.parse.urlencode(data).encode("utf-8") if data is not None else None
        request = urllib.request.Request(url, data=body, method=method)
        for name, value in (headers or {}).items():
            request.add_header(name, value)
        request.add_header("User-Agent", f"idm-web-capture/{SCRIPT_VERSION}")
        try:
            with self._opener.open(request, timeout=self._timeout) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
                return (
                    response.status,
                    _decode_body(raw),
                    response.headers.get("Content-Type"),
                    self._effective_url(url, response.geturl()),
                )
        except urllib.error.HTTPError as err:
            # The NAV2 firmware answers rejected sessions with 401/403 and a
            # body worth keeping as evidence.
            raw = err.read(MAX_RESPONSE_BYTES + 1)
            return (
                err.code,
                _decode_body(raw),
                err.headers.get("Content-Type") if err.headers is not None else None,
                self._effective_url(url, err.geturl() if err.headers is not None else None),
            )

    @staticmethod
    def _effective_url(requested: str, after_redirects: str | None) -> str | None:
        if after_redirects is None or after_redirects == requested:
            return None
        return after_redirects


def _decode_body(raw: bytes) -> str:
    if len(raw) > MAX_RESPONSE_BYTES:
        raise CaptureError(f"response exceeds {MAX_RESPONSE_BYTES} bytes")
    return raw.decode("utf-8", errors="replace")


def _http_base(host: str, port: int) -> str:
    host_part = f"[{host}]" if ":" in host and not host.startswith("[") else host
    return f"http://{host_part}:{port}"


def _safe_name(path_or_label: str) -> str:
    name = path_or_label.strip("/").replace("/", "_")
    return re.sub(r"[^A-Za-z0-9._=-]", "_", name) or "response"


def _extend_http_meta(entry: dict, content_type: str | None, effective_url: str | None) -> None:
    """Attach response metadata a parser diagnosis needs: what the server
    says it is serving, and whether the request was redirected."""
    if content_type:
        entry["content_type"] = content_type
    if effective_url:
        entry["redirected_to"] = effective_url


ProgressSink = Callable[[float, str], None]


def _silent_progress(_fraction: float, _label: str) -> None:
    """Progress sink for callers that do not show a progress bar."""


def capture_nav20(
    host: str,
    port: int,
    pin: str,
    timeout: float,
    files: dict[str, str],
    entries: list[dict],
    progress: ProgressSink | None = None,
) -> dict:
    """Log into the NAV2 HTTP interface and capture every known read-only page."""
    session = HttpSession(timeout)
    base = _http_base(host, port)
    summary: dict = {"variant": "nav20", "outcome": "unavailable", "login": None}

    report = progress or _silent_progress
    report(0.05, "Web-Seiten: Startseite laden")
    try:
        status, text, content_type, effective_url = session.request("GET", base + "/")
    except (urllib.error.URLError, OSError, CaptureError) as err:
        entries.append({"variant": "nav20", "step": "initial_get", "status": "error", "detail": _err_text(err)})
        return summary
    files["nav20/initial_page.html"] = text
    csrf_token = extract_csrf_token(text)
    initial_entry: dict = {
        "variant": "nav20",
        "step": "initial_get",
        "status": "ok" if 200 <= status < 300 else f"http_{status}",
        "http_status": status,
        "file": "nav20/initial_page.html",
        "looks_like_login_page": looks_like_login_page(text),
    }
    _extend_http_meta(initial_entry, content_type, effective_url)
    entries.append(initial_entry)

    # Login handshake: try each form field name the firmwares use. Request
    # bodies are deliberately never captured — one of them contains the PIN.
    login_status: int | None = None
    login_error = ""
    for path in NAV20_LOGIN_PATHS:
        accepted = False
        for field in NAV20_LOGIN_FIELDS:
            try:
                login_status, text, _, _ = session.request("POST", base + path, data={field: pin})
            except (urllib.error.URLError, OSError, CaptureError) as err:
                login_error = _err_text(err)
                continue
            if login_status in (401, 403) or "authorization required" in text.lower():
                login_error = f"HTTP {login_status} / authorization required on {path}"
                continue
            token = extract_csrf_token(text)
            if token:
                csrf_token = token
            if not text.strip():
                # Empty/bad response: keep trying field-name variants (API parity).
                continue
            if looks_like_login_page(text):
                login_error = f"login form returned again on {path}"
                break
            accepted = True
            summary["login"] = {"path": path, "field": field, "http_status": login_status}
            break
        if accepted:
            break
    if summary["login"] is None:
        summary["outcome"] = "login_failed"
        summary["login_error"] = login_error or "no login variant was accepted"
        entries.append(
            {"variant": "nav20", "step": "login", "status": "login_failed", "detail": summary["login_error"]}
        )
        return summary

    headers = {"X-Requested-With": "XMLHttpRequest"}
    if csrf_token:
        headers["CSRF-Token"] = csrf_token
        headers["X-CSRF-Token"] = csrf_token
        headers["X-CSRFToken"] = csrf_token

    captured = 0
    targets = [(f"data_{_safe_name(path)}", path) for path in NAV20_DATA_PATHS]
    targets += [(f"statistics_{name}", url) for name, url in NAV20_STATISTICS_QUERIES]
    for index, (label, path) in enumerate(targets):
        report(0.3 + 0.7 * index / len(targets), f"Web-Seiten: {path}")
        try:
            status, text, content_type, effective_url = session.request("GET", base + path, headers=headers)
        except (urllib.error.URLError, OSError, CaptureError) as err:
            entries.append({"variant": "nav20", "step": path, "status": "error", "detail": _err_text(err)})
            continue
        entry: dict = {"variant": "nav20", "step": path, "http_status": status}
        lowered = text.lower()
        if "invalid csrf token" in lowered:
            entry["status"] = "csrf_rejected"
        elif looks_like_auth_failure(text) or looks_like_login_page(text):
            entry["status"] = "auth_response"
        elif not 200 <= status < 300:
            # A 404/5xx answer is evidence too (Nav-10-generation modules
            # serve a 404 stub on the old PHP pages) — save the body, but do
            # not count it as a page carrying data.
            entry["status"] = f"http_{status}"
        else:
            entry["status"] = "ok"
        _extend_http_meta(entry, content_type, effective_url)
        # Save every classified body: stubs and error pages are exactly the
        # evidence a parser diagnosis needs.
        files[f"nav20/{label}.capture"] = text
        entry["file"] = f"nav20/{label}.capture"
        if entry["status"] == "ok":
            captured += 1
        entries.append(entry)
        time.sleep(REQUEST_DELAY)

    report(1.0, "Web-Seiten abgeschlossen")
    summary["outcome"] = "ok" if captured else "no_usable_pages"
    summary["pages_captured"] = captured
    return summary


# ----------------------------------------------------------------------------
# Minimal RFC 6455 WebSocket client (stdlib sockets, client side only)
# ----------------------------------------------------------------------------


class WebSocketClient:
    """Text-frame WebSocket client: enough for the Navigator 10 protocol."""

    def __init__(self, host: str, port: int, timeout: float) -> None:
        self._host = host
        self._port = port
        self._timeout = timeout
        self._sock: socket.socket | None = None
        # Bytes read past the HTTP handshake header: controllers routinely
        # send the 101 response and the first frame in one TCP segment, and
        # discarding them would lose the authorization frame.
        self._buffer = b""

    def connect(self, path: str) -> None:
        host_part = f"[{self._host}]" if ":" in self._host else self._host
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host_part}:{self._port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        self._sock = socket.create_connection((self._host, self._port), timeout=self._timeout)
        self._sock.settimeout(self._timeout)
        self._sock.sendall(request.encode("ascii"))
        response = b""
        while b"\r\n\r\n" not in response:
            chunk = self._sock.recv(4096)
            if not chunk:
                raise CaptureError("websocket handshake ended before headers completed")
            response += chunk
            if len(response) > MAX_RESPONSE_BYTES:
                raise CaptureError("websocket handshake response too large")
        status_line = response.split(b"\r\n", 1)[0].decode("ascii", errors="replace")
        if " 101 " not in f"{status_line} ":
            raise CaptureError(f"websocket handshake refused: {status_line.strip()}")
        self._buffer = response.split(b"\r\n\r\n", 1)[1]

    def send_text(self, text: str) -> None:
        if self._sock is None:
            raise CaptureError("websocket is not connected")
        payload = text.encode("utf-8")
        mask_key = random.randbytes(4)
        header = bytearray([0x81])  # FIN + text opcode; client frames are masked
        length = len(payload)
        if length < 126:
            header.append(0x80 | length)
        elif length < (1 << 16):
            header.append(0x80 | 126)
            header += struct.pack("!H", length)
        else:
            header.append(0x80 | 127)
            header += struct.pack("!Q", length)
        header += mask_key
        masked = bytes(byte ^ mask_key[i % 4] for i, byte in enumerate(payload))
        self._sock.sendall(bytes(header) + masked)

    def recv_text(self) -> str:
        """Receive one text message, transparently answering pings."""
        if self._sock is None:
            raise CaptureError("websocket is not connected")
        fragments: list[str] = []
        while True:
            opcode, fin, payload = self._read_frame()
            if opcode == 0x9:  # ping -> pong with the same payload
                self._send_frame(0xA, payload)
                continue
            if opcode == 0x8:
                raise CaptureError("websocket closed by the device")
            if opcode not in (0x0, 0x1):
                raise CaptureError(f"unexpected websocket frame opcode {opcode}")
            if len(payload) > MAX_RESPONSE_BYTES:
                raise CaptureError("websocket frame too large")
            fragments.append(payload.decode("utf-8", errors="replace"))
            if fin:
                return "".join(fragments)

    def close(self) -> None:
        if self._sock is not None:
            try:
                self._send_frame(0x8, b"")
            except OSError:
                pass
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

    def _read_frame(self) -> tuple[int, bool, bytes]:
        assert self._sock is not None
        header = self._read_exact(2)
        fin = bool(header[0] & 0x80)
        opcode = header[0] & 0x0F
        masked = bool(header[1] & 0x80)
        length = header[1] & 0x7F
        if length == 126:
            length = struct.unpack("!H", self._read_exact(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", self._read_exact(8))[0]
        if length > MAX_RESPONSE_BYTES:
            raise CaptureError("websocket frame too large")
        mask_key = self._read_exact(4) if masked else b""
        payload = self._read_exact(length) if length else b""
        if masked:
            payload = bytes(byte ^ mask_key[i % 4] for i, byte in enumerate(payload))
        return opcode, fin, payload

    def _read_exact(self, count: int) -> bytes:
        assert self._sock is not None
        while len(self._buffer) < count:
            chunk = self._sock.recv(count - len(self._buffer))
            if not chunk:
                raise CaptureError("websocket connection ended mid-frame")
            self._buffer += chunk
        data, self._buffer = self._buffer[:count], self._buffer[count:]
        return data

    def _send_frame(self, opcode: int, payload: bytes) -> None:
        assert self._sock is not None
        mask_key = random.randbytes(4)
        header = bytearray([0x80 | opcode])
        length = len(payload)
        if length < 126:
            header.append(0x80 | length)
        elif length < (1 << 16):
            header.append(0x80 | 126)
            header += struct.pack("!H", length)
        else:
            header.append(0x80 | 127)
            header += struct.pack("!Q", length)
        header += mask_key
        masked = bytes(byte ^ mask_key[i % 4] for i, byte in enumerate(payload))
        self._sock.sendall(bytes(header) + masked)


def build_nav10_frames() -> list[tuple[str, str, dict]]:
    """Return (filename, label, payload) for every read-only frame we capture.

    Every command is ``detail`` or ``overview`` — the parity test in the
    repository enforces that no write command ever enters this list.
    """
    frames: list[tuple[str, str, dict]] = [
        ("status_overview", "status/overview", {"controller": "status", "command": "overview"}),
        ("home_detail", "home/detail", {"controller": "home", "command": "detail"}),
        ("home_overview", "home/overview", {"controller": "home", "command": "overview"}),
        ("notifications_overview", "notification/overview", {"controller": "notification", "command": "overview"}),
        ("system_overview", "system/overview", {"controller": "system", "command": "overview"}),
        (
            "freshwater_overview",
            "system.freshwater/overview",
            {"controller": "system.freshwater", "command": "overview"},
        ),
        (
            "performance_detail",
            "system.heatpump.performance/detail",
            {"controller": "system.heatpump.performance", "command": "detail"},
        ),
        ("weather_detail", "weather/detail", {"controller": "weather", "command": "detail"}),
        ("ion_overview", "ion/overview", {"controller": "ion", "command": "overview"}),
        ("energyflow_overview", "energyflow/overview", {"controller": "energyflow", "command": "overview"}),
    ]
    for setting_id in NAV10_SETTING_IDS:
        frames.append(
            (
                f"setting_{setting_id}",
                f"setting/detail {setting_id}",
                {"controller": "setting", "command": "detail", "data": {"settingId": setting_id}},
            )
        )
    for circuit in NAV10_HEATING_CIRCUITS:
        frames.append(
            (
                f"heatingcircuit_{circuit}",
                f"system.heatingcircuit/detail {circuit}",
                {"controller": "system.heatingcircuit", "command": "detail", "data": {"hcId": circuit}},
            )
        )
    for stat_type in NAV10_STATISTIC_TYPES:
        for period in NAV10_STATISTIC_PERIODS:
            frames.append(
                (
                    f"statistic_t{stat_type}_p{period}",
                    f"statistic/detail type={stat_type} period={period}",
                    {
                        "controller": "statistic",
                        "command": "detail",
                        "data": {"statisticType": stat_type, "periodType": period, "statisticSubType": None},
                    },
                )
            )
    return frames


def capture_nav10(
    host: str,
    port: int,
    pin: str,
    timeout: float,
    files: dict[str, str],
    entries: list[dict],
    progress: ProgressSink | None = None,
) -> dict:
    """Authenticate the Navigator 10 WebSocket and capture every read-only frame."""
    summary: dict = {"variant": "nav10", "outcome": "unavailable"}
    # The PIN travels in the WebSocket query string; it is never written anywhere.
    client = WebSocketClient(host, port, timeout)
    try:
        client.connect("/?auth_code=" + urllib.parse.quote(pin, safe=""))
        auth_raw = client.recv_text()
    except (OSError, CaptureError) as err:
        entries.append({"variant": "nav10", "step": "connect", "status": "unavailable", "detail": _err_text(err)})
        client.close()
        return summary

    try:
        authorized = None
        try:
            payload = json.loads(auth_raw)
            if isinstance(payload, dict) and isinstance(payload.get("authorized"), bool):
                authorized = payload["authorized"]
        except json.JSONDecodeError:
            pass
        files["nav10/auth_response.json"] = auth_raw
        entries.append(
            {
                "variant": "nav10",
                "step": "auth",
                "status": "ok",
                "authorized": authorized,
                "file": "nav10/auth_response.json",
            }
        )
        if authorized is not True:
            summary["outcome"] = "pin_rejected"
            return summary

        captured = 0
        report = progress or _silent_progress
        frames = build_nav10_frames()
        for index, (filename, label, request) in enumerate(frames):
            report(index / (len(frames) + 1), f"WebSocket-Datenkanäle: {label}")
            try:
                client.send_text(json.dumps(request))
                response = client.recv_text()
            except (OSError, CaptureError) as err:
                entries.append({"variant": "nav10", "step": label, "status": "error", "detail": _err_text(err)})
                continue
            files[f"nav10/{filename}.json"] = response
            entries.append({"variant": "nav10", "step": label, "status": "ok", "file": f"nav10/{filename}.json"})
            captured += 1
            time.sleep(REQUEST_DELAY)
        report(1.0, "WebSocket-Datenkanäle abgeschlossen")
        summary["outcome"] = "ok" if captured else "no_frames"
        summary["frames_captured"] = captured
        return summary
    finally:
        client.close()


def _err_text(err: BaseException) -> str:
    return f"{type(err).__name__}: {err}"[:300]


# ----------------------------------------------------------------------------
# Read-only Modbus TCP sweep (stdlib sockets, FC03/FC04 only)
# ----------------------------------------------------------------------------

_MODBUS_EXCEPTION_NAMES = {
    0x01: "illegal_function",
    0x02: "illegal_data_address",
    0x03: "illegal_data_value",
    0x04: "slave_device_failure",
    0x0A: "gateway_path_unavailable",
    0x0B: "gateway_target_failed",
}


class ModbusCaptureError(CaptureError):
    """A Modbus block could not be read; the reason goes into the manifest."""


class ModbusReader:
    """Minimal read-only Modbus TCP client: FC03/FC04, one connection."""

    def __init__(self, host: str, port: int, slave: int, timeout: float) -> None:
        self._host = host
        self._port = port
        self._slave = slave
        self._timeout = timeout
        self._sock: socket.socket | None = None
        self._transaction = 0

    def connect(self) -> None:
        self._sock = socket.create_connection((self._host, self._port), timeout=self._timeout)
        self._sock.settimeout(self._timeout)

    def close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

    def read_words(self, function: int, start: int, count: int) -> list[int]:
        """Read ``count`` registers starting at ``start`` (FC03/FC04 only)."""
        if self._sock is None:
            raise ModbusCaptureError("modbus connection is not open")
        if function not in (3, 4):
            raise ValueError("only read functions 3 and 4 are permitted")
        self._transaction = (self._transaction + 1) & 0xFFFF
        request = struct.pack(
            ">HHHBBHH",
            self._transaction,
            0,  # protocol id: Modbus TCP
            6,  # following length
            self._slave,
            function,
            start,
            count,
        )
        self._sock.sendall(request)
        header = self._read_exact(7)
        transaction, _protocol, length = struct.unpack(">HHH", header[:6])
        if transaction != self._transaction:
            raise ModbusCaptureError("modbus transaction id mismatch")
        if length < 3 or length > 260:
            raise ModbusCaptureError(f"modbus response length out of range: {length}")
        # ``length`` counts the unit id (already read as header[6]) plus PDU;
        # the PDU therefore starts at payload[1].
        payload = header[6:7] + self._read_exact(length - 1)
        function_code = payload[1]
        if function_code & 0x80:
            code = payload[2] if len(payload) > 2 else 0
            name = _MODBUS_EXCEPTION_NAMES.get(code, f"exception_{code}")
            raise ModbusCaptureError(f"modbus FC{function} @{start}: {name}")
        if function_code != function:
            raise ModbusCaptureError(f"modbus answered FC{function_code}, not FC{function}")
        byte_count = payload[2]
        if byte_count != count * 2 or len(payload) != 3 + byte_count:
            raise ModbusCaptureError("modbus response length does not match the request")
        return [struct.unpack(">H", payload[3 + i * 2 : 5 + i * 2])[0] for i in range(count)]

    def _read_exact(self, count: int) -> bytes:
        assert self._sock is not None
        data = b""
        while len(data) < count:
            chunk = self._sock.recv(count - len(data))
            if not chunk:
                raise ModbusCaptureError("modbus connection ended mid-frame")
            data += chunk
        return data


def _read_segment(
    reader: ModbusReader,
    function: int,
    start: int,
    count: int,
    label: str,
    slave: int,
    files: dict[str, str],
    entries: list[dict],
) -> int:
    """Read one segment, bisecting across undocumented register holes.

    Controllers refuse a multi-register read whose range crosses a hole — a
    live Navigator 10 answered single registers at 1000 and 1050 but refused
    the 50-word block spanning the gap between them. Halving the range on
    refusal reconstructs the readable segments and pins the holes down to
    single addresses; that readable-region map is exactly the evidence a
    register-map diagnosis needs.
    """
    entry: dict = {
        "variant": "modbus",
        "function": function,
        "start": start,
        "words": count,
        "step": f"FC{function} {label} {start}-{start + count - 1}",
    }
    try:
        words = reader.read_words(function, start, count)
    except (OSError, ModbusCaptureError) as err:
        bisectable = isinstance(err, ModbusCaptureError) and "illegal_data_address" in str(err)
        if bisectable and count > 1:
            half = count // 2
            read_low = _read_segment(reader, function, start, half, label, slave, files, entries)
            read_high = _read_segment(reader, function, start + half, count - half, label, slave, files, entries)
            return read_low + read_high
        entry["status"] = "hole" if bisectable else "error"
        entry["detail"] = _err_text(err)
        entries.append(entry)
        return 0
    record = {
        "function": function,
        "start": start,
        "count": count,
        "unit": slave,
        "raw_words": words,
    }
    name = f"modbus/{label}_{start}_{start + count - 1}.json"
    files[name] = json.dumps(record, indent=1)
    entry["status"] = "ok"
    entry["file"] = name
    entries.append(entry)
    return 1


def capture_modbus(
    host: str,
    port: int,
    slave: int,
    timeout: float,
    files: dict[str, str],
    entries: list[dict],
    progress: ProgressSink | None = None,
) -> dict:
    """Sweep the documented register ranges read-only and store raw words.

    A proxy setup is just a different host/port — the GUI and CLI accept both.
    Blocks are bisected across register holes, so the readable-region map of
    the controller lands in the archive next to the raw words.
    """
    summary: dict = {"variant": "modbus", "outcome": "unavailable"}
    reader = ModbusReader(host, port, slave, timeout)
    try:
        reader.connect()
    except (OSError, ModbusCaptureError) as err:
        entries.append({"variant": "modbus", "step": "connect", "status": "unavailable", "detail": _err_text(err)})
        return summary

    segments_read = 0
    report = progress or _silent_progress
    plan = [(4, start, "input") for start in MODBUS_INPUT_BLOCKS] + [
        (3, start, "holding") for start in MODBUS_HOLDING_BLOCKS
    ]
    try:
        for index, (function, start, label) in enumerate(plan):
            report(index / len(plan), f"Modbus-Register: FC{function} Block {start}")
            segments_read += _read_segment(reader, function, start, MODBUS_BLOCK_WORDS, label, slave, files, entries)
            time.sleep(REQUEST_DELAY)
        report(1.0, "Modbus-Register abgeschlossen")
    finally:
        reader.close()
    summary["outcome"] = "ok" if segments_read else "no_blocks"
    summary["segments_read"] = segments_read
    return summary


# ----------------------------------------------------------------------------
# Manifest, README and ZIP packaging
# ----------------------------------------------------------------------------

SAFETY_STATEMENTS = {
    "pin_included": False,
    "login_request_bodies_included": False,
    "write_commands_sent": False,
    "level_elevation_attempted": False,
    "note": (
        "The web PIN was used only for the login handshake. It is not part of "
        "this archive. Only read-only pages and read-only detail/overview "
        "frames were requested; no setting was changed and no access level "
        "beyond the one the PIN grants was touched."
    ),
}


def redact_pin(files: dict[str, str], pin: str) -> list[str]:
    """Last-resort guard: replace the PIN inside any captured page with a marker.

    A data page echoing the submitted PIN is not expected on any known
    firmware, but if it ever happens the evidence must not leak the secret.
    Redacted file names are recorded in the manifest so the substitution stays
    visible instead of silently altering raw evidence.
    """
    redacted: list[str] = []
    if not pin:
        return redacted
    for name, content in files.items():
        if pin in content:
            files[name] = content.replace(pin, "[PIN-REDACTED]")
            redacted.append(name)
    return redacted


def build_manifest(
    host: str,
    web_port: int,
    ws_port: int,
    nav20: dict,
    nav10: dict,
    entries: list[dict],
    redacted_files: list[str],
    modbus: dict | None = None,
    modbus_port: int = DEFAULT_MODBUS_PORT,
    modbus_slave: int = DEFAULT_MODBUS_SLAVE,
) -> str:
    safety = dict(SAFETY_STATEMENTS)
    safety["pin_redacted_files"] = redacted_files
    manifest = {
        "tool": "idm_web_capture",
        "version": SCRIPT_VERSION,
        "created_utc": datetime.now(timezone.utc).isoformat(),  # noqa: UP017 (keep 3.9/3.10 runnable)
        "host": host,
        "web_port": web_port,
        "ws_port": ws_port,
        "modbus_port": modbus_port,
        "modbus_slave": modbus_slave,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "safety": safety,
        "variants": {"nav20": nav20, "nav10": nav10, "modbus": modbus or {"outcome": "skipped"}},
        "captures": entries,
    }
    text = json.dumps(manifest, indent=2, ensure_ascii=False)
    return text


README_TEXT = """IDM Navigator Web-Capture / Weboberflaechen-Mitschnitt
=====================================================

EN — What this archive contains
-------------------------------
Raw, unmodified responses from your IDM Navigator's local web interface,
collected read-only: every known data page of the Navigator 2.0 HTTP
interface and every known read-only frame of the Navigator 10/Pro WebSocket
interface, plus a manifest.json describing what was fetched (status codes,
errors, variant outcomes).

Your web PIN is NOT included. It was used only for the login handshake, the
login request bodies were not captured, no setting was changed, and nothing
beyond the access level your PIN grants was opened. The file manifest.json
records these guarantees.

Please send the whole ZIP file as it is BY E-MAIL to the maintainer
(git@xerolux.de). Do NOT attach it to a public GitHub issue: the archive can
contain device identifiers such as your myIDM id. It helps fix parsing
problems like unreadable web values.

DE — Was dieses Archiv enthaelt
-------------------------------
Unveraenderte Roh-Antworten der lokalen Weboberflaeche Ihres IDM Navigators,
rein lesend ausgelesen: alle bekannten Datenseiten der Navigator-2.0-HTTP-
Oberflaeche und alle bekannten Nur-Lese-Frames der WebSocket-Oberflaeche des
Navigator 10 / Pro, dazu eine manifest.json mit Statuscodes, Fehlern und
Ergebnissen der einzelnen Abrufe.

Ihre Web-PIN ist NICHT enthalten. Sie wurde nur fuer den Login verwendet,
die Login-Anfragen selbst wurden nicht mitgeschnitten, es wurde keine
Einstellung geaendert und nichts ueber die Ebene hinaus geoeffnet, die Ihre
PIN freigibt. Diese Zusicherungen stehen auch in der manifest.json.

Bitte senden Sie die komplette ZIP-Datei unveraendert PER E-MAIL an den
Betreuer (git@xerolux.de) und haengen Sie sie NICHT oeffentlich in einen
GitHub-Issue: das Archiv kann Geraete-Kennungen wie Ihre myIDM-Kennung
enthalten. Es hilft bei der Fehlersuche, zum Beispiel bei nicht lesbaren
Web-Werten.
"""


def write_zip(
    out_path: str,
    files: dict[str, str],
    manifest_text: str,
) -> None:
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("README.txt", README_TEXT)
        archive.writestr("manifest.json", manifest_text)
        for name, content in files.items():
            archive.writestr(name, content)


def _sanitize_for_filename(host: str) -> str:
    return re.sub(r"[^A-Za-z0-9.-]", "-", host).strip("-") or "host"


def _silent_log(_line: str) -> None:
    """Progress sink for callers that do not care about progress lines."""


def perform_capture(
    host: str,
    pin: str,
    web_port: int = DEFAULT_WEB_PORT,
    ws_port: int = DEFAULT_WS_PORT,
    timeout: float = DEFAULT_TIMEOUT,
    out_dir: str = ".",
    only: str | None = None,
    modbus: bool = True,
    modbus_host: str | None = None,
    modbus_port: int = DEFAULT_MODBUS_PORT,
    modbus_slave: int = DEFAULT_MODBUS_SLAVE,
    log=_silent_log,
    progress: ProgressSink | None = None,
) -> tuple[str, bool, list[str]]:
    """Run the captures and write the evidence ZIP; shared by CLI and GUI.

    Returns ``(zip_path, ok, warnings)``. ``ok`` is True when at least one
    variant delivered usable data; the evidence ZIP is written either way —
    a failed capture documents its own failure and is still worth sending.
    An empty PIN leaves the web legs to fail their login (recorded) while
    the Modbus sweep still delivers its data.
    """
    files: dict[str, str] = {}
    entries: list[dict] = []
    nav20: dict = {"variant": "nav20", "outcome": "skipped"}
    nav10: dict = {"variant": "nav10", "outcome": "skipped"}
    modbus_summary: dict = {"variant": "modbus", "outcome": "skipped"}

    # Leg weights for the overall progress bar: web pages are quick, the
    # 37 WebSocket frames and the Modbus sweep dominate the runtime.
    nav20_weight, nav10_weight, modbus_weight = 0.2, 0.4, 0.4
    report = progress or _silent_progress
    done_weight = 0.0

    if only != "nav10":
        log(f"Capturing Navigator 2.0 HTTP interface at {host}:{web_port} ...")
        nav20 = capture_nav20(
            host,
            web_port,
            pin,
            timeout,
            files,
            entries,
            progress=lambda fraction, label: report(done_weight + fraction * nav20_weight, label),
        )
        done_weight += nav20_weight
        log(f"  nav20: {nav20['outcome']}")
    else:
        done_weight += nav20_weight
    if only != "nav20":
        log(f"Capturing Navigator 10/Pro WebSocket at {host}:{ws_port} ...")
        nav10 = capture_nav10(
            host,
            ws_port,
            pin,
            timeout,
            files,
            entries,
            progress=lambda fraction, label: report(done_weight + fraction * nav10_weight, label),
        )
        done_weight += nav10_weight
        log(f"  nav10: {nav10['outcome']}")
    else:
        done_weight += nav10_weight
    if modbus:
        modbus_target = modbus_host or host
        log(f"Sweeping Modbus registers read-only at {modbus_target}:{modbus_port} (slave {modbus_slave}) ...")
        modbus_summary = capture_modbus(
            modbus_target,
            modbus_port,
            modbus_slave,
            timeout,
            files,
            entries,
            progress=lambda fraction, label: report(done_weight + fraction * modbus_weight, label),
        )
        log(f"  modbus: {modbus_summary['outcome']} ({modbus_summary.get('segments_read', 0)} segments)")
    else:
        report(done_weight + modbus_weight, "")

    warnings: list[str] = []
    redacted = redact_pin(files, pin)
    if redacted:
        warnings.append(f"Warning: PIN redacted inside {len(redacted)} captured file(s): {', '.join(redacted)}")
    manifest_text = build_manifest(
        host,
        web_port,
        ws_port,
        nav20,
        nav10,
        entries,
        redacted,
        modbus=modbus_summary,
        modbus_port=modbus_port,
        modbus_slave=modbus_slave,
    )
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    abs_out_dir = os.path.abspath(out_dir)
    os.makedirs(abs_out_dir, exist_ok=True)
    out_path = os.path.join(abs_out_dir, f"idm_web_capture_{_sanitize_for_filename(host)}_{stamp}.zip")
    write_zip(out_path, files, manifest_text)

    ok = nav20.get("outcome") == "ok" or nav10.get("outcome") == "ok" or modbus_summary.get("outcome") == "ok"
    return out_path, ok, warnings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Capture read-only evidence from an IDM Navigator local web interface."
    )
    parser.add_argument("host", help="IP address or host name of the Navigator")
    parser.add_argument("--pin", help="web PIN (default: hidden prompt; or set the IDM_WEB_PIN environment variable)")
    parser.add_argument(
        "--web-port",
        type=int,
        default=DEFAULT_WEB_PORT,
        help=f"HTTP port of the web interface (default {DEFAULT_WEB_PORT})",
    )
    parser.add_argument(
        "--ws-port",
        type=int,
        default=DEFAULT_WS_PORT,
        help=f"WebSocket port, Navigator 10/Pro (default {DEFAULT_WS_PORT})",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help=f"per-request timeout in seconds (default {DEFAULT_TIMEOUT})",
    )
    parser.add_argument("--out", default=".", help="output directory for the ZIP file")
    parser.add_argument(
        "--only",
        choices=("nav20", "nav10"),
        help="capture only one interface variant (default: both)",
    )
    parser.add_argument(
        "--no-modbus",
        action="store_true",
        help="skip the read-only Modbus register sweep (default: sweep it)",
    )
    parser.add_argument(
        "--modbus-host",
        help="Modbus host when it differs from the web host (e.g. a proxy box); default: same as host",
    )
    parser.add_argument(
        "--modbus-port",
        type=int,
        default=DEFAULT_MODBUS_PORT,
        help=f"Modbus TCP port (default {DEFAULT_MODBUS_PORT}; a proxy usually has its own)",
    )
    parser.add_argument(
        "--modbus-slave",
        type=int,
        default=DEFAULT_MODBUS_SLAVE,
        help=f"Modbus slave/unit id (default {DEFAULT_MODBUS_SLAVE})",
    )
    parser.add_argument("--gui", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--cli", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    pin = args.pin or os.environ.get("IDM_WEB_PIN") or ""
    if not pin:
        try:
            pin = getpass.getpass("Web-PIN des Navigators / Navigator web PIN: ")
        except (EOFError, OSError):
            pin = ""
    if not pin:
        # A plant without a web interface still has Modbus — one data source
        # beats none, so warn and continue instead of aborting.
        print("No PIN given - the web legs cannot log in; continuing with Modbus.", file=sys.stderr)

    out_path, ok, warnings = perform_capture(
        host=args.host,
        pin=pin,
        web_port=args.web_port,
        ws_port=args.ws_port,
        timeout=args.timeout,
        out_dir=args.out,
        only=args.only,
        modbus=not args.no_modbus,
        modbus_host=args.modbus_host,
        modbus_port=args.modbus_port,
        modbus_slave=args.modbus_slave,
        log=print,
    )
    for warning in warnings:
        print(warning, file=sys.stderr)

    print()
    # Console output stays ASCII: Windows cmd.exe code pages mangle umlauts.
    print(f"ZIP erstellt / ZIP created: {out_path}")
    print("Bitte die komplette Datei senden / please send the whole file.")
    return 0 if ok else 2


# ----------------------------------------------------------------------------
# Guided Windows GUI (tkinter, standard library only)
# ----------------------------------------------------------------------------

CONTACT_EMAIL = "git@xerolux.de"
ISSUE_URL = "https://github.com/Xerolux/idm-heatpump-hass/issues/new"
UPDATE_URL = "https://idmtools.xerolux.de/version.txt"


def is_newer_version(current: str, available: str) -> bool:
    """Return whether ``available`` is a newer dotted version than ``current``."""
    try:
        current_parts = tuple(int(part) for part in current.strip().split("."))
        available_parts = tuple(int(part) for part in available.strip().split("."))
    except ValueError:
        return False
    return available_parts > current_parts


GUI_LICENSE_TEXT = """IDM Web-Capture — Haftungsausschluss & Nutzungsbedingungen

Dieses Werkzeug gehört zum Open-Source-Projekt „IDM Heatpump für Home
Assistant" (github.com/Xerolux/idm-heatpump-hass, MIT-Lizenz).

• Das Werkzeug verbindet sich ausschließlich mit dem von Ihnen angegebenen
  Gerät in Ihrem lokalen Netzwerk. Kein Cloud-Dienst, keine Telemetrie,
  kein automatischer Versand von Daten.

• Es greift ausschließlich LESEND auf die Weboberfläche zu: Es gibt keine
  Schreibbefehle, es werden keine Einstellungen geändert, und keine höheren
  Zugriffsebenen (Service-/Fachmann-Ebene) werden geöffnet.

• Ihre Web-PIN wird nur für den Login verwendet. Sie wird nicht gespeichert
  und nicht in die erzeugte ZIP-Datei geschrieben.

• Die erzeugte ZIP-Datei enthält Rohdaten Ihrer Anlage (Temperaturen,
  Betriebszustände, Einstellwerte, Geräte-Kennungen). Sie entscheiden, ob
  und an wen Sie sie senden. Beachten Sie: GitHub-Issues sind öffentlich.

Nutzung auf eigene Gefahr: Das Werkzeug wird unentgeltlich und ohne
Garantie oder Gewährleistung bereitgestellt. Eine Haftung für direkte,
indirekte oder Folgeschäden jedweder Art ist, soweit gesetzlich zulässig,
ausgeschlossen.

Mit „Akzeptieren" bestätigen Sie, diesen Text gelesen und verstanden zu
haben."""

GUI_INFO_TEXT = (
    "Was jetzt passiert: Das Werkzeug meldet sich mit Ihrer Web-PIN an der "
    "Weboberfläche Ihres Navigators an und liest ausschließlich lesend alle "
    "bekannten Datenseiten (Navigator 2.0) bzw. Nur-Lese-Datenkanäle "
    "(Navigator 10 / Pro) aus — zusätzlich immer die Modbus-Register als "
    "Rohwerte (bei einem Modbus-Proxy einfach dessen Adresse angeben). "
    "Daraus entsteht eine ZIP-Datei mit den Rohdaten und einer manifest.json, "
    "die jeden Abruf dokumentiert.\n\n"
    "Ihre PIN erscheint NICHT in der Datei. Es wird nichts geändert und "
    "nichts automatisch versendet."
)


def gui_available() -> bool:
    try:
        import tkinter  # noqa: F401
    except Exception:  # noqa: BLE001 - headless or stripped interpreters
        return False
    return True


def should_launch_gui(argv: list[str]) -> bool:
    """Decide between the guided GUI and the command line.

    Double-clicking the Windows executable arrives with no arguments at all;
    that user gets the wizard. Anyone naming a host (or passing --cli) is an
    expert and keeps the scriptable console behaviour on every platform.
    """
    if "--cli" in argv:
        return False
    if "--gui" in argv:
        return True
    return os.name == "nt" and len(argv) == 1


def run_gui() -> int:
    """Run the guided wizard: license, host+PIN entry, progress, result."""
    import queue
    import threading
    import tkinter as tk
    from tkinter import scrolledtext, ttk

    class Wizard(tk.Tk):
        def __init__(self) -> None:
            super().__init__()
            self.title(f"IDM Web-Capture {SCRIPT_VERSION} — Nur-Lese-Diagnose")
            self.minsize(620, 480)
            self.result_zip: str | None = None
            self.result_ok = False
            self._queue: queue.Queue = queue.Queue()
            self.container = ttk.Frame(self, padding=14)
            self.container.pack(fill="both", expand=True)
            self._update_notice = ("", "#5b6673")
            self._update_check_running = False
            self._show_license()

        # --- step 1: license -------------------------------------------------
        def _show_license(self) -> None:
            self._clear()
            frame = ttk.Frame(self.container)
            frame.pack(fill="both", expand=True)
            ttk.Label(
                frame,
                text=f"Haftungsausschluss & Nutzungsbedingungen — Tool-Version {SCRIPT_VERSION}",
                font=("", 13, "bold"),
            ).pack(anchor="w", pady=(0, 8))
            # An explicit crisp font: the Tk default bitmap font renders
            # blurry on Windows high-DPI displays even with DPI awareness on.
            text = scrolledtext.ScrolledText(frame, wrap="word", height=18, font=("Segoe UI", 10))
            text.insert("1.0", GUI_LICENSE_TEXT)
            text.configure(state="disabled")
            text.pack(fill="both", expand=True)
            buttons = ttk.Frame(frame)
            buttons.pack(fill="x", pady=(10, 0))
            ttk.Button(buttons, text="Abbrechen", command=self.destroy).pack(side="right")
            ttk.Button(buttons, text="Akzeptieren", command=self._show_input).pack(side="right", padx=(0, 8))

        # --- step 2: host + PIN ---------------------------------------------
        def _show_input(self) -> None:
            self._clear()
            if not self._update_check_running and not self._update_notice[0]:
                self._start_update_check()
            frame = ttk.Frame(self.container)
            frame.pack(fill="both", expand=True)
            ttk.Label(frame, text="Verbindung zur Wärmepumpe", font=("", 13, "bold")).pack(anchor="w", pady=(0, 8))
            row = ttk.Frame(frame)
            row.pack(fill="x")
            ttk.Label(row, text="IP-Adresse / Hostname:").pack(side="left")
            host_var = tk.StringVar()
            ttk.Entry(row, textvariable=host_var, width=28).pack(side="left", padx=8)
            ttk.Label(row, text="(wie in der Home-Assistant-Integration)").pack(side="left")
            row2 = ttk.Frame(frame)
            row2.pack(fill="x", pady=(8, 0))
            ttk.Label(row2, text="Web-PIN:").pack(side="left")
            pin_var = tk.StringVar()
            ttk.Entry(row2, textvariable=pin_var, show="•", width=28).pack(side="left", padx=8)
            ttk.Label(
                row2,
                text="(Eingabe bleibt verborgen; ohne PIN läuft nur Modbus)",
            ).pack(side="left")
            # tk.Label has no padding option (that broke the whole frame
            # silently in earlier builds) — the padding lives in pack().
            info = tk.Label(frame, text=GUI_INFO_TEXT, justify="left", wraplength=560, relief="groove")
            info.pack(fill="x", pady=14, ipadx=10, ipady=10)

            ttk.Label(
                frame,
                text="Modbus über Proxy / Gateway (optional — sonst leer lassen)",
                font=("", 11, "bold"),
            ).pack(anchor="w", pady=(2, 4))
            mb_row = ttk.Frame(frame)
            mb_row.pack(fill="x", pady=(4, 0))
            ttk.Label(mb_row, text="Modbus-Host:").pack(side="left")
            modbus_host_var = tk.StringVar()
            ttk.Entry(mb_row, textvariable=modbus_host_var, width=22).pack(side="left", padx=(8, 4))
            ttk.Label(mb_row, text="Port:").pack(side="left")
            modbus_port_var = tk.StringVar(value=str(DEFAULT_MODBUS_PORT))
            ttk.Entry(mb_row, textvariable=modbus_port_var, width=6).pack(side="left", padx=(8, 4))
            ttk.Label(mb_row, text="Slave-ID:").pack(side="left")
            modbus_slave_var = tk.StringVar(value=str(DEFAULT_MODBUS_SLAVE))
            ttk.Entry(mb_row, textvariable=modbus_slave_var, width=4).pack(side="left", padx=(8, 0))
            ttk.Label(
                frame,
                text="Modbus-Host leer lassen = gleiche Adresse wie oben. Läuft Modbus über einen "
                "Proxy bzw. eine Gateway-Box, deren Adresse und Port eintragen. Die Modbus-Register "
                "werden immer mit aufgezeichnet (rein lesend).",
                foreground="#5b6673",
                wraplength=560,
                justify="left",
            ).pack(anchor="w", pady=(4, 0))

            self._update_label = ttk.Label(frame, text="", foreground="#5b6673", wraplength=560, justify="left")
            self._update_label.pack(anchor="w", pady=(8, 0))
            self._render_update_notice()

            buttons = ttk.Frame(frame)
            buttons.pack(fill="x", pady=(14, 0))
            ttk.Button(buttons, text="Beenden", command=self.destroy).pack(side="right")
            start = ttk.Button(
                buttons,
                text="Aufzeichnung starten",
                command=lambda: self._start(
                    host_var.get().strip(),
                    pin_var.get(),
                    modbus_host_var.get().strip(),
                    modbus_port_var.get().strip(),
                    modbus_slave_var.get().strip(),
                ),
            )
            start.pack(side="right", padx=(0, 8))

        def _start(
            self,
            host: str,
            pin: str,
            modbus_host: str,
            modbus_port: str,
            modbus_slave: str,
        ) -> None:
            if not host:
                self._alert("Bitte die IP-Adresse oder den Hostnamen Ihres Navigators angeben.")
                return
            if not pin:
                from tkinter import messagebox

                confirmed = messagebox.askyesno(
                    "IDM Web-Capture",
                    "Ohne Web-PIN können die Webdaten nicht abgerufen werden.\n\n"
                    "Trotzdem fortfahren? Die Modbus-Register werden dann weiterhin "
                    "aufgezeichnet (lieber eine Datenquelle als keine).",
                    parent=self,
                )
                if not confirmed:
                    return
            try:
                modbus_port_value = int(modbus_port) if modbus_port else DEFAULT_MODBUS_PORT
                modbus_slave_value = int(modbus_slave) if modbus_slave else DEFAULT_MODBUS_SLAVE
            except ValueError:
                self._alert("Modbus-Port und Slave-ID müssen Zahlen sein.")
                return
            if not 1 <= modbus_port_value <= 65535 or not 1 <= modbus_slave_value <= 255:
                self._alert("Modbus-Port (1-65535) oder Slave-ID (1-255) ist außerhalb des gültigen Bereichs.")
                return
            self._show_progress()
            threading.Thread(
                target=self._worker,
                args=(host, pin, modbus_host, modbus_port_value, modbus_slave_value),
                daemon=True,
            ).start()

        def _worker(
            self,
            host: str,
            pin: str,
            modbus_host: str,
            modbus_port: int,
            modbus_slave: int,
        ) -> None:
            try:
                out_path, ok, warnings = perform_capture(
                    host=host,
                    pin=pin,
                    modbus=True,
                    modbus_host=modbus_host or None,
                    modbus_port=modbus_port,
                    modbus_slave=modbus_slave,
                    log=self._queue.put,
                    progress=lambda fraction, label: self._queue.put((fraction, label)),
                )
            except Exception as err:  # noqa: BLE001 - the GUI must never die silently
                self._queue.put(f"Unerwarteter Fehler / unexpected error: {_err_text(err)}")
                out_path, ok, warnings = None, False, []
            self.result_zip = out_path
            self.result_ok = ok
            for warning in warnings:
                self._queue.put(warning)
            self._queue.put(None)  # sentinel: finished

        # --- step 3: progress -------------------------------------------------
        def _show_progress(self) -> None:
            self._clear()
            frame = ttk.Frame(self.container)
            frame.pack(fill="both", expand=True)
            ttk.Label(frame, text="Aufzeichnung läuft …", font=("", 13, "bold")).pack(anchor="w", pady=(0, 8))
            self._progress_bar = ttk.Progressbar(frame, maximum=100, length=560)
            self._progress_bar.pack(fill="x", pady=(0, 4))
            self._progress_status = ttk.Label(frame, text="Starte … 0 % — Restzeit wird geschätzt")
            self._progress_status.pack(anchor="w", pady=(0, 8))
            self._capture_started = time.monotonic()
            self._last_fraction = 0.0
            self._log = scrolledtext.ScrolledText(frame, wrap="word", height=14)
            self._log.pack(fill="both", expand=True)
            self.after(100, self._poll)

        def _apply_progress(self, fraction: float, label: str) -> None:
            fraction = max(0.0, min(fraction, 1.0))
            self._last_fraction = fraction
            self._progress_bar["value"] = fraction * 100
            elapsed = time.monotonic() - self._capture_started
            if fraction >= 0.98:
                eta = ""
            elif fraction > 0.02:
                remaining = elapsed * (1.0 - fraction) / fraction
                eta = f" — noch ca. {max(1, round(remaining))} s"
            else:
                eta = " — Restzeit wird geschätzt"
            step = f" · {label}" if label else ""
            self._progress_status.configure(text=f"{round(fraction * 100)} %{eta}{step}")

        def _poll(self) -> None:
            finished = False
            try:
                while True:
                    item = self._queue.get_nowait()
                    if item is None:
                        finished = True
                        break
                    if isinstance(item, tuple) and len(item) == 2:
                        self._apply_progress(item[0], item[1])
                        continue
                    self._log.insert("end", item + "\n")
                    self._log.see("end")
            except queue.Empty:
                pass
            if finished:
                try:
                    self._apply_progress(1.0, "abgeschlossen")
                except Exception:  # noqa: BLE001, S110 - cosmetic only
                    pass
                self._show_result()
            else:
                self.after(100, self._poll)

        # --- step 4: result ---------------------------------------------------
        def _show_result(self) -> None:
            self._clear()
            frame = ttk.Frame(self.container)
            frame.pack(fill="both", expand=True)
            if self.result_zip is None:
                ttk.Label(frame, text="Fehler — keine Datei erstellt", font=("", 13, "bold")).pack(
                    anchor="w", pady=(0, 6)
                )
                ttk.Label(
                    frame,
                    text="Bitte die Meldung oben im Verlauf beachten und erneut versuchen.",
                    wraplength=560,
                    justify="left",
                ).pack(anchor="w")
            elif self.result_ok:
                ttk.Label(frame, text="✓ Fertig — Datei gespeichert:", font=("", 13, "bold")).pack(
                    anchor="w", pady=(0, 6)
                )
                ttk.Label(frame, text=self.result_zip, wraplength=560, justify="left").pack(anchor="w", pady=(0, 10))
                ttk.Label(
                    frame,
                    text=f"Wichtig: Die Datei kann Geräte-Kennungen (z. B. myIDM) enthalten — "
                    f"bitte NICHT öffentlich im GitHub-Issue anhängen, sondern per E-Mail an "
                    f"{CONTACT_EMAIL} senden. „E-Mail vorbereiten“ richtet alles ein; die Datei "
                    f"dann als Anhang hinzufügen.",
                    wraplength=560,
                    justify="left",
                ).pack(anchor="w")
            else:
                ttk.Label(frame, text="⚠ Keine Nutzdaten empfangen", font=("", 13, "bold")).pack(
                    anchor="w", pady=(0, 6)
                )
                ttk.Label(
                    frame,
                    text=f"Die Diagnose-Datei mit den Fehlerdetails wurde trotzdem "
                    f"gespeichert:\n{self.result_zip}\n\nAuch sie hilft der "
                    f"Fehlersuche — bitte ebenfalls per E-Mail an {CONTACT_EMAIL} senden "
                    f"(nicht öffentlich anhängen).",
                    wraplength=560,
                    justify="left",
                ).pack(anchor="w")
            buttons = ttk.Frame(frame)
            buttons.pack(fill="x", pady=(14, 0))
            if self.result_zip:
                ttk.Button(buttons, text="Ordner öffnen", command=lambda: self._open_folder()).pack(side="left")
                ttk.Button(buttons, text="Dateipfad kopieren", command=lambda: self._copy_path()).pack(
                    side="left", padx=8
                )
                ttk.Button(buttons, text="E-Mail vorbereiten", command=lambda: self._prepare_mail()).pack(side="left")
                ttk.Button(
                    buttons,
                    text="GitHub-Issue (nur Problem schildern, ohne Datei)",
                    command=lambda: self._open_issue(),
                ).pack(side="left", padx=8)
            if not self.result_ok:
                ttk.Button(buttons, text="Erneut versuchen", command=self._show_input).pack(side="left", padx=8)
            ttk.Button(buttons, text="Beenden", command=self.destroy).pack(side="right")

        def _open_folder(self) -> None:
            if self.result_zip and hasattr(os, "startfile"):
                os.startfile(os.path.dirname(self.result_zip))

        def _copy_path(self) -> None:
            if not self.result_zip:
                return
            self.clipboard_clear()
            self.clipboard_append(self.result_zip)
            self.update()  # keep the clipboard after the window closes

        def _prepare_mail(self) -> None:
            if not self.result_zip:
                return
            import webbrowser

            subject = f"IDM Web-Capture {os.path.basename(self.result_zip)}"
            body = (
                "Hallo,\n\n"
                "anbei die Aufzeichnung meiner Navigator-Weboberfläche.\n\n"
                f"Datei (bitte als Anhang hinzufügen): {self.result_zip}\n\n"
                "Viele Grüße"
            )
            webbrowser.open(
                f"mailto:{CONTACT_EMAIL}?subject={urllib.parse.quote(subject)}&body={urllib.parse.quote(body)}"
            )

        def _open_issue(self) -> None:
            import webbrowser

            webbrowser.open(ISSUE_URL)

        def _start_update_check(self) -> None:
            """Fetch the published version number once, right at startup.

            The tool's only outbound connection: one HTTPS GET of a plain-text
            version file from idmtools.xerolux.de. Nothing about the plant is
            transmitted; failures stay silent (offline = normal start).
            """
            if self._update_check_running:
                return
            self._update_check_running = True

            def worker() -> None:
                available = None
                try:
                    with urllib.request.urlopen(UPDATE_URL, timeout=5) as response:
                        available = response.read(64).decode("ascii", errors="replace").strip()
                except Exception:  # noqa: BLE001 - an update check must never disturb the tool
                    available = None
                if available and is_newer_version(SCRIPT_VERSION, available):
                    notice = (
                        (
                            f"⚠ Version {available} verfügbar — bitte die aktuelle Version von "
                            f"https://idmtools.xerolux.de laden (diese Version: {SCRIPT_VERSION})."
                        ),
                        "#9a6700",
                    )
                elif available:
                    notice = (f"✓ Aktuelle Version ({SCRIPT_VERSION}).", "#5b6673")
                else:
                    notice = ("", "#5b6673")
                self._update_notice = notice
                try:
                    self.after(0, self._render_update_notice)
                except tk.TclError:
                    pass  # window already closed

            threading.Thread(target=worker, daemon=True).start()

        def _render_update_notice(self) -> None:
            label = getattr(self, "_update_label", None)
            if label is not None:
                text, color = self._update_notice
                label.configure(text=text, foreground=color)

        def _alert(self, message: str) -> None:
            from tkinter import messagebox

            messagebox.showwarning("IDM Web-Capture", message, parent=self)

        def _clear(self) -> None:
            for child in self.container.winfo_children():
                child.destroy()

    # Crisp rendering on high-DPI Windows: without process DPI awareness the
    # window bitmap is stretched by the system and every glyph looks blurry.
    if os.name == "nt":
        try:
            import ctypes

            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(2)  # per-monitor v2
            except Exception:  # noqa: BLE001 - older Windows
                ctypes.windll.user32.SetProcessDPIAware()
        except Exception:  # noqa: BLE001 - never block the GUI for DPI setup
            _silent_log("could not set process DPI awareness")

    app = Wizard()
    app.mainloop()
    return 0


if __name__ == "__main__":
    if should_launch_gui(sys.argv) and gui_available():
        sys.exit(run_gui())
    sys.exit(main(sys.argv[1:]))
