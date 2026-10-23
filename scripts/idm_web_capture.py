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
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from http import cookiejar

SCRIPT_VERSION = "1.0.0"

DEFAULT_WEB_PORT = 80
DEFAULT_WS_PORT = 61220
DEFAULT_TIMEOUT = 10.0
REQUEST_DELAY = 0.1
MAX_RESPONSE_BYTES = 5 * 1024 * 1024

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
    """Cookie-keeping HTTP client returning (status, text) even on HTTP errors."""

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
    ) -> tuple[int, str]:
        body = urllib.parse.urlencode(data).encode("utf-8") if data is not None else None
        request = urllib.request.Request(url, data=body, method=method)
        for name, value in (headers or {}).items():
            request.add_header(name, value)
        request.add_header("User-Agent", f"idm-web-capture/{SCRIPT_VERSION}")
        try:
            with self._opener.open(request, timeout=self._timeout) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
                return response.status, _decode_body(raw)
        except urllib.error.HTTPError as err:
            # The NAV2 firmware answers rejected sessions with 401/403 and a
            # body worth keeping as evidence.
            raw = err.read(MAX_RESPONSE_BYTES + 1)
            return err.code, _decode_body(raw)


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


def capture_nav20(
    host: str,
    port: int,
    pin: str,
    timeout: float,
    files: dict[str, str],
    entries: list[dict],
) -> dict:
    """Log into the NAV2 HTTP interface and capture every known read-only page."""
    session = HttpSession(timeout)
    base = _http_base(host, port)
    summary: dict = {"variant": "nav20", "outcome": "unavailable", "login": None}

    try:
        status, text = session.request("GET", base + "/")
    except (urllib.error.URLError, OSError, CaptureError) as err:
        entries.append({"variant": "nav20", "step": "initial_get", "status": "error", "detail": _err_text(err)})
        return summary
    files["nav20/initial_page.html"] = text
    csrf_token = extract_csrf_token(text)
    entries.append(
        {
            "variant": "nav20",
            "step": "initial_get",
            "status": "ok",
            "http_status": status,
            "file": "nav20/initial_page.html",
            "looks_like_login_page": looks_like_login_page(text),
        }
    )

    # Login handshake: try each form field name the firmwares use. Request
    # bodies are deliberately never captured — one of them contains the PIN.
    login_status: int | None = None
    login_error = ""
    for path in NAV20_LOGIN_PATHS:
        accepted = False
        for field in NAV20_LOGIN_FIELDS:
            try:
                login_status, text = session.request("POST", base + path, data={field: pin})
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
    for label, path in targets:
        try:
            status, text = session.request("GET", base + path, headers=headers)
        except (urllib.error.URLError, OSError, CaptureError) as err:
            entries.append({"variant": "nav20", "step": path, "status": "error", "detail": _err_text(err)})
            continue
        entry: dict = {"variant": "nav20", "step": path, "status": "ok", "http_status": status}
        lowered = text.lower()
        if "invalid csrf token" in lowered:
            entry["status"] = "csrf_rejected"
        elif looks_like_auth_failure(text) or looks_like_login_page(text):
            entry["status"] = "auth_response"
        if entry["status"] == "ok":
            files[f"nav20/{label}.capture"] = text
            entry["file"] = f"nav20/{label}.capture"
            captured += 1
        entries.append(entry)
        time.sleep(REQUEST_DELAY)

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
        for filename, label, request in build_nav10_frames():
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
        summary["outcome"] = "ok" if captured else "no_frames"
        summary["frames_captured"] = captured
        return summary
    finally:
        client.close()


def _err_text(err: BaseException) -> str:
    return f"{type(err).__name__}: {err}"[:300]


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
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "safety": safety,
        "variants": {"nav20": nav20, "nav10": nav10},
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

Please send the whole ZIP file as it is (GitHub issue: drag & drop; e-mail:
attachment). It helps fix parsing problems like unreadable web values.

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

Bitte senden Sie die komplette ZIP-Datei unveraendert (GitHub-Issue: per
Drag & Drop anhängen; E-Mail: als Anhang). Sie hilft bei der Fehlersuche,
zum Beispiel bei nicht lesbaren Web-Werten.
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
    parser.add_argument("--only", choices=("nav20", "nav10"), help="capture only one interface variant (default: both)")
    args = parser.parse_args(argv)

    pin = args.pin or os.environ.get("IDM_WEB_PIN") or ""
    if not pin:
        try:
            pin = getpass.getpass("Web-PIN des Navigators / Navigator web PIN: ")
        except (EOFError, OSError):
            print("No PIN entered — aborting.", file=sys.stderr)
            return 2
    if not pin:
        print("An empty PIN cannot log in — aborting.", file=sys.stderr)
        return 2

    files: dict[str, str] = {}
    entries: list[dict] = []
    nav20: dict = {"variant": "nav20", "outcome": "skipped"}
    nav10: dict = {"variant": "nav10", "outcome": "skipped"}

    if args.only != "nav10":
        print(f"Capturing Navigator 2.0 HTTP interface at {args.host}:{args.web_port} ...")
        nav20 = capture_nav20(args.host, args.web_port, pin, args.timeout, files, entries)
        print(f"  nav20: {nav20['outcome']}")
    if args.only != "nav20":
        print(f"Capturing Navigator 10/Pro WebSocket at {args.host}:{args.ws_port} ...")
        nav10 = capture_nav10(args.host, args.ws_port, pin, args.timeout, files, entries)
        print(f"  nav10: {nav10['outcome']}")

    redacted = redact_pin(files, pin)
    if redacted:
        print(f"Warning: PIN redacted inside {len(redacted)} captured file(s): {', '.join(redacted)}", file=sys.stderr)
    manifest_text = build_manifest(args.host, args.web_port, args.ws_port, nav20, nav10, entries, redacted)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = os.path.abspath(args.out)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"idm_web_capture_{_sanitize_for_filename(args.host)}_{stamp}.zip")
    write_zip(out_path, files, manifest_text)

    ok = nav20.get("outcome") == "ok" or nav10.get("outcome") == "ok"
    print()
    print(f"ZIP erstellt / ZIP created: {out_path}")
    print("Bitte die komplette Datei anhängen / please attach the whole file.")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
