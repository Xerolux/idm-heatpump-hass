"""Contract of the user-facing web capture tool (scripts/idm_web_capture.py).

The tool ships to end users as a single script and as a Windows executable,
so its behaviour matters far outside this repository. These tests pin the
promises it makes:

* protocol parity with the real ``idm-heatpump-api`` web client (endpoints,
  login field variants, setting ids) so captures stay interpretable;
* the read-only contract: every WebSocket frame is a ``detail``/``overview``
  request, no write command can enter the frame list;
* the PIN can never land in the archive (redaction guard, manifest safety
  block);
* the minimal WebSocket client interoperates with a conforming server
  (masking, length boundaries, ping/pong, fragmentation);
* the full tool runs end to-end against fake HTTP and WebSocket servers.
"""

from __future__ import annotations

import importlib.util
import inspect
import json
import socket
import struct
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "idm_web_capture.py"

_spec = importlib.util.spec_from_file_location("idm_web_capture", SCRIPT)
capture = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(capture)

from idm_heatpump import web as api_web

# ---------------------------------------------------------------------------
# Protocol parity with idm-heatpump-api
# ---------------------------------------------------------------------------


class TestApiParity:
    def test_nav20_data_paths_match_the_api(self) -> None:
        assert capture.NAV20_DATA_PATHS == api_web.DEFAULT_NAVIGATOR20_PATHS

    def test_nav20_statistics_urls_match_the_api(self) -> None:
        expected = {url for _, url in api_web.NAVIGATOR20_STATISTICS_PATHS}
        actual = {url for _, url in capture.NAV20_STATISTICS_QUERIES}
        assert actual == expected

    def test_nav20_login_field_variants_match_the_api_source(self) -> None:
        source = inspect.getsource(api_web.IdmNavigator20WebClient._try_login)
        for field in capture.NAV20_LOGIN_FIELDS:
            assert f'"{field}"' in source

    def test_nav20_login_paths_match_the_api_source(self) -> None:
        source = inspect.getsource(api_web.IdmNavigator20WebClient._try_login)
        for path in capture.NAV20_LOGIN_PATHS:
            assert f'"{path}"' in source

    def test_nav10_setting_ids_cover_the_api_defaults(self) -> None:
        assert set(api_web.DEFAULT_NAVIGATOR10_SETTING_IDS) <= set(capture.NAV10_SETTING_IDS)

    def test_csrf_extraction_matches_the_api(self) -> None:
        samples = (
            (
                '<html><form><input type="hidden" name="csrf_token" value="abc123">'
                '<input type="password" name="pin"></form></html>'
            ),
            '<html><head><meta name="csrf-token" content="tok-2"></head></html>',
            "<script>var csrfToken = 'js-token';</script>",
            "<html>no token anywhere</html>",
        )
        for sample in samples:
            assert capture.extract_csrf_token(sample) == api_web._extract_csrf_token(sample)

    def test_page_classification_matches_the_api(self) -> None:
        pages = (
            '<form action="/"><input type="password" name="pin"></form>',
            "<html>plain data page</html>",
            '{"authorized": false}',
            '{"status": "unauthorized"}',
            "Authorization Required",
        )
        for page in pages:
            assert capture.looks_like_login_page(page) == api_web._looks_like_login_page(page)
            assert capture.looks_like_auth_failure(page) == api_web._looks_like_auth_failure(page)


class TestReadOnlyContract:
    def test_every_frame_command_is_read_only(self) -> None:
        for _, _, payload in capture.build_nav10_frames():
            assert payload["command"] in ("detail", "overview")

    def test_no_write_verbs_anywhere_in_the_frame_list(self) -> None:
        # Quoted tokens, not substrings: the controller name "setting" is
        # read-only, a command "set"/"save" would not be.
        for _, label, payload in capture.build_nav10_frames():
            blob = json.dumps(payload) + label
            for verb in ("save", "set", "write", "delete", "acknowledge", "unlock"):
                assert f'"{verb}"' not in blob.casefold()

    def test_frame_list_covers_every_read_endpoint_the_api_wraps(self) -> None:
        labels = {label for _, label, _ in capture.build_nav10_frames()}
        expected_prefixes = (
            "status/overview",
            "home/detail",
            "home/overview",
            "notification/overview",
            "system/overview",
            "system.freshwater/overview",
            "system.heatpump.performance/detail",
            "weather/detail",
            "ion/overview",
            "energyflow/overview",
            "setting/detail",
            "system.heatingcircuit/detail",
            "statistic/detail",
        )
        for prefix in expected_prefixes:
            assert any(label.startswith(prefix) for label in labels), prefix


# ---------------------------------------------------------------------------
# Minimal WebSocket client
# ---------------------------------------------------------------------------


def _server_frame(payload: bytes, opcode: int = 0x1, fin: bool = True) -> bytes:
    header = bytearray([(0x80 if fin else 0) | opcode])
    length = len(payload)
    if length < 126:
        header.append(length)
    elif length < (1 << 16):
        header.append(126)
        header += struct.pack("!H", length)
    else:
        header.append(127)
        header += struct.pack("!Q", length)
    return bytes(header) + payload


def _read_client_frame(sock: socket.socket) -> tuple[int, bytes]:
    def read_exact(count: int) -> bytes:
        data = b""
        while len(data) < count:
            chunk = sock.recv(count - len(data))
            assert chunk
            data += chunk
        return data

    header = read_exact(2)
    opcode = header[0] & 0x0F
    length = header[1] & 0x7F
    if length == 126:
        length = struct.unpack("!H", read_exact(2))[0]
    elif length == 127:
        length = struct.unpack("!Q", read_exact(8))[0]
    mask_key = read_exact(4)
    payload = read_exact(length)
    return opcode, bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))


class TestWebSocketClient:
    def _connected_pair(self) -> tuple[capture.WebSocketClient, socket.socket]:
        server_sock, client_sock = socket.socketpair()
        server_sock.settimeout(5)
        client = capture.WebSocketClient("127.0.0.1", 1, timeout=5)
        client._sock = client_sock
        client_sock.settimeout(5)
        return client, server_sock

    def test_client_frames_are_masked(self) -> None:
        client, server = self._connected_pair()
        try:
            client.send_text('{"a": 1}')
            header = server.recv(2)
            assert header[0] & 0x0F == 0x1
            assert header[1] & 0x80, "client-to-server frames must be masked"
        finally:
            client.close()
            server.close()

    def test_round_trip_small_and_boundary_lengths(self) -> None:
        client, server = self._connected_pair()
        try:
            for size in (0, 5, 125, 126, 65535, 65536, 70000):
                payload = "x" * size
                client.send_text(payload)
                opcode, decoded = _read_client_frame(server)
                assert opcode == 0x1
                assert decoded.decode() == payload
        finally:
            client.close()
            server.close()

    def test_recv_handles_ping_and_fragmentation(self) -> None:
        client, server = self._connected_pair()
        try:
            server.sendall(_server_frame(b"ping-payload", opcode=0x9))
            server.sendall(_server_frame(b"frag1", fin=False))
            server.sendall(_server_frame(b"frag2", fin=False, opcode=0x0))
            server.sendall(_server_frame(b"frag3", opcode=0x0))
            assert client.recv_text() == "frag1frag2frag3"
            opcode, pong = _read_client_frame(server)
            assert opcode == 0xA
            assert pong == b"ping-payload"
        finally:
            client.close()
            server.close()


# ---------------------------------------------------------------------------
# PIN never ships
# ---------------------------------------------------------------------------


class TestPinSafety:
    def test_redact_pin_replaces_and_reports(self) -> None:
        files = {"nav20/page.html": "value 1234 ok", "nav10/x.json": '{"v": 1}'}
        redacted = capture.redact_pin(files, "1234")
        assert redacted == ["nav20/page.html"]
        assert files["nav20/page.html"] == "value [PIN-REDACTED] ok"
        assert files["nav10/x.json"] == '{"v": 1}'

    def test_manifest_states_safety_and_takes_no_pin(self) -> None:
        text = capture.build_manifest(
            "192.0.2.10",
            80,
            61220,
            {"variant": "nav20", "outcome": "ok"},
            {"variant": "nav10", "outcome": "skipped"},
            [],
            [],
        )
        manifest = json.loads(text)
        assert manifest["safety"]["pin_included"] is False
        assert manifest["safety"]["write_commands_sent"] is False
        assert manifest["safety"]["level_elevation_attempted"] is False
        assert "pin" not in inspect.signature(capture.build_manifest).parameters

    def test_zip_contains_readme_manifest_and_files(self, tmp_path: Path) -> None:
        target = tmp_path / "out.zip"
        capture.write_zip(str(target), {"nav20/page.html": "<html>ok</html>"}, "{}")
        with zipfile.ZipFile(target) as archive:
            names = set(archive.namelist())
        assert {"README.txt", "manifest.json", "nav20/page.html"} == names


# ---------------------------------------------------------------------------
# End to end against fake servers
# ---------------------------------------------------------------------------


class _FakeNav20Handler(BaseHTTPRequestHandler):
    pin = "4321"

    def log_message(self, *args: object) -> None:  # silence the test server
        return

    def do_GET(self) -> None:
        if self.path == "/":
            body = (
                '<html><form><input name="csrf_token" value="tok-initial">'
                '<input type="password" name="pin"></form></html>'
            )
            self._serve(200, body)
            return
        if self.path == "/data/state.php":
            # Nav-10-generation modules answer the old PHP pages with a 404
            # stub — the body is evidence, but not a page carrying data.
            self._serve(404, "<html><body><h1>404 Not Found</h1></body></html>")
            return
        if self.path.startswith("/data/"):
            self._serve(200, "<html><table><tr><td>Au&szlig;entemperatur</td><td>17.5 &deg;C</td></tr></table></html>")
            return
        self._serve(404, "not found")

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        form = self.rfile.read(length).decode()
        if f"pin={_FakeNav20Handler.pin}" in form:
            self._serve(200, '<html><body>main page<meta name="csrf-token" content="tok-session"></body></html>')
        else:
            self._serve(200, '<html><form><input type="password" name="pin"></form></html>')

    def _serve(self, status: int, body: str) -> None:
        raw = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def test_end_to_end_nav20(tmp_path: Path) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _FakeNav20Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        code = capture.main(
            [
                "127.0.0.1",
                "--web-port",
                str(server.server_address[1]),
                "--only",
                "nav20",
                "--pin",
                _FakeNav20Handler.pin,
                "--out",
                str(tmp_path),
            ]
        )
    finally:
        server.shutdown()

    assert code == 0
    zips = list(tmp_path.glob("idm_web_capture_127.0.0.1_*.zip"))
    assert len(zips) == 1
    with zipfile.ZipFile(zips[0]) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        pages = [n for n in archive.namelist() if n.startswith("nav20/data_")]
    nav20 = manifest["variants"]["nav20"]
    assert nav20["outcome"] == "ok"
    assert nav20["login"]["field"] == "pin"
    assert manifest["safety"]["pin_included"] is False
    assert _FakeNav20Handler.pin not in json.dumps(manifest)
    # Five of the six data pages answer with data; the 404 stub is saved as
    # evidence but neither counted as captured nor marked "ok".
    assert nav20["pages_captured"] == len(capture.NAV20_DATA_PATHS) - 1 + len(capture.NAV20_STATISTICS_QUERIES)
    stub_entry = next(e for e in manifest["captures"] if e["step"] == "/data/state.php")
    assert stub_entry["status"] == "http_404"
    assert stub_entry["http_status"] == 404
    assert stub_entry["file"].startswith("nav20/")
    assert stub_entry["file"] in pages
    ok_entries = [e for e in manifest["captures"] if e.get("status") == "ok" and e["variant"] == "nav20"]
    assert all(200 <= e["http_status"] < 300 for e in ok_entries)


def _fake_nav10_server(sock_in: socket.socket) -> None:
    """Accept one WebSocket handshake, then echo one JSON reply per request."""
    request = b""
    while b"\r\n\r\n" not in request:
        chunk = sock_in.recv(4096)
        assert chunk
        request += chunk
    assert b"auth_code=9999" in request
    # Headers and the auth frame deliberately travel in ONE send: controllers
    # coalesce them into a single TCP segment, and a client that discards the
    # bytes after the handshake terminator loses the auth frame (found as a
    # flake here, but it would fail against every real device).
    sock_in.sendall(
        b"HTTP/1.1 101 Switching Protocols\r\n"
        b"Upgrade: websocket\r\nConnection: Upgrade\r\n"
        b"Sec-WebSocket-Accept: fixed\r\n\r\n" + _server_frame(b'{"authorized": true, "userlevel": 0}')
    )
    for _ in range(40):
        try:
            opcode, payload = _read_client_frame(sock_in)
        except (OSError, AssertionError):
            break
        if opcode == 0x8:
            break
        request_json = json.loads(payload.decode())
        reply = {"echo": request_json["controller"], "command": request_json["command"]}
        sock_in.sendall(_server_frame(json.dumps(reply).encode()))
    sock_in.close()


def test_end_to_end_nav10(tmp_path: Path) -> None:
    listener = socket.socket()
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    port = listener.getsockname()[1]
    server_done = threading.Event()

    def serve() -> None:
        sock_in, _ = listener.accept()
        sock_in.settimeout(5)
        _fake_nav10_server(sock_in)
        server_done.set()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    try:
        code = capture.main(
            [
                "127.0.0.1",
                "--ws-port",
                str(port),
                "--only",
                "nav10",
                "--pin",
                "9999",
                "--out",
                str(tmp_path),
            ]
        )
    finally:
        listener.close()

    assert code == 0
    zips = list(tmp_path.glob("idm_web_capture_127.0.0.1_*.zip"))
    assert len(zips) == 1
    with zipfile.ZipFile(zips[0]) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        frames = [n for n in archive.namelist() if n.startswith("nav10/")]
    assert manifest["variants"]["nav10"]["outcome"] == "ok"
    assert manifest["variants"]["nav10"]["frames_captured"] == len(capture.build_nav10_frames())
    assert "nav10/auth_response.json" in frames
    assert "9999" not in json.dumps(manifest)


def test_total_failure_still_writes_evidence_zip(tmp_path: Path) -> None:
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(
            capture,
            "capture_nav20",
            lambda *a, **k: (
                a[5].append({"variant": "nav20", "step": "connect", "status": "error"}),
                {"variant": "nav20", "outcome": "unavailable"},
            )[1],
        )
        patch.setattr(
            capture,
            "capture_nav10",
            lambda *a, **k: (
                a[5].append({"variant": "nav10", "step": "connect", "status": "error"}),
                {"variant": "nav10", "outcome": "unavailable"},
            )[1],
        )
        code = capture.main(["127.0.0.1", "--pin", "1", "--out", str(tmp_path)])
    assert code == 2
    zips = list(tmp_path.glob("idm_web_capture_*.zip"))
    assert len(zips) == 1
    with zipfile.ZipFile(zips[0]) as archive:
        manifest = json.loads(archive.read("manifest.json"))
    assert manifest["variants"]["nav20"]["outcome"] == "unavailable"


# ---------------------------------------------------------------------------
# Guided GUI (logic only — no Tk window is ever instantiated here)
# ---------------------------------------------------------------------------


class TestGuiLaunchRules:
    def test_double_click_on_windows_opens_the_wizard(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(capture.os, "name", "nt")
        assert capture.should_launch_gui(["idm_web_capture.exe"]) is True

    def test_named_host_stays_command_line(self) -> None:
        assert capture.should_launch_gui(["prog", "192.0.2.10"]) is False

    def test_cli_flag_forces_command_line_everywhere(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(capture.os, "name", "nt")
        assert capture.should_launch_gui(["prog", "--cli"]) is False

    def test_gui_flag_forces_the_wizard(self) -> None:
        assert capture.should_launch_gui(["prog", "--gui"]) is True

    def test_linux_without_arguments_stays_command_line(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(capture.os, "name", "posix")
        assert capture.should_launch_gui(["prog"]) is False


class TestGuiContract:
    def test_license_text_carries_the_disclaimer_essentials(self) -> None:
        text = capture.GUI_LICENSE_TEXT
        for needle in (
            "Haftungsausschluss",
            "auf eigene Gefahr",
            "MIT-Lizenz",
            "ausschließlich LESEND",
            "nicht in die erzeugte ZIP-Datei geschrieben",
            "GitHub-Issues sind öffentlich",
        ):
            assert needle in text, needle

    def test_contact_constants(self) -> None:
        assert capture.CONTACT_EMAIL == "git@xerolux.de"
        assert capture.ISSUE_URL.startswith("https://github.com/Xerolux/idm-heatpump-hass")

    def test_perform_capture_tuple_contract(self, tmp_path: Path) -> None:
        lines: list[str] = []
        zip_path, ok, warnings = capture.perform_capture(
            host="192.0.2.99",
            pin="1",
            only=None,
            out_dir=str(tmp_path),
            log=lines.append,
        )
        assert zip_path.endswith(".zip")
        assert ok is False  # nothing listens on 192.0.2.99 — evidence still written
        assert warnings == []
        assert any("nav20" in line for line in lines)
        assert any("nav10" in line for line in lines)
        assert Path(zip_path).exists()


# ---------------------------------------------------------------------------
# Read-only Modbus sweep
# ---------------------------------------------------------------------------


def _fake_modbus_server(sock_in: socket.socket, holes: set[int]) -> None:
    """Answer FC03/FC04 reads; any read overlapping a hole address is refused.

    That is how the real controllers behave: a multi-register read crossing
    an undocumented hole fails as a whole, which is what the sweep's bisection
    has to untangle.
    """
    while True:
        try:
            header = b""
            while len(header) < 7:
                chunk = sock_in.recv(7 - len(header))
                if not chunk:
                    return
                header += chunk
            transaction, _proto, length = struct.unpack(">HHH", header[:6])
            # length counts the unit id (header[6]) + PDU; read only the PDU.
            unit = header[6]
            pdu = b""
            while len(pdu) < length - 1:
                chunk = sock_in.recv(length - 1 - len(pdu))
                if not chunk:
                    return
                pdu += chunk
            function, start, count = struct.unpack(">BHH", pdu)
            if any(addr in holes for addr in range(start, start + count)):
                body = struct.pack(">BB", function | 0x80, 0x02)
            elif function in (3, 4):
                words = [(start * 7 + i) & 0xFFFF for i in range(count)]
                body = struct.pack(">BB", function, count * 2) + b"".join(struct.pack(">H", w) for w in words)
            else:
                body = struct.pack(">BB", function | 0x80, 0x01)
            response = struct.pack(">HHH", transaction, 0, len(body) + 1) + bytes([unit]) + body
            sock_in.sendall(response)
        except OSError:
            return


class TestModbusSweep:
    def test_reader_round_trip_and_refusals(self) -> None:
        listener = socket.socket()
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        done = threading.Event()

        def serve() -> None:
            sock_in, _ = listener.accept()
            sock_in.settimeout(5)
            _fake_modbus_server(sock_in, {1050})
            done.set()

        threading.Thread(target=serve, daemon=True).start()
        reader = capture.ModbusReader("127.0.0.1", port, 1, timeout=5)
        reader.connect()
        try:
            words = reader.read_words(4, 1000, 50)
            assert words[0] == (1000 * 7) & 0xFFFF
            assert len(words) == 50
            with pytest.raises(capture.ModbusCaptureError, match="illegal_data_address"):
                reader.read_words(4, 1050, 50)  # crosses the hole at 1050
            with pytest.raises(capture.ModbusCaptureError, match="illegal_data_address"):
                reader.read_words(4, 1050, 1)
            with pytest.raises(ValueError, match="only read functions"):
                reader.read_words(6, 1000, 10)
        finally:
            reader.close()
            listener.close()

    def test_capture_modbus_bisects_across_holes(self) -> None:
        listener = socket.socket()
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]

        def serve() -> None:
            sock_in, _ = listener.accept()
            sock_in.settimeout(5)
            # A two-register hole inside the first input block.
            _fake_modbus_server(sock_in, {1010, 1011})

        threading.Thread(target=serve, daemon=True).start()
        files: dict[str, str] = {}
        entries: list[dict] = []
        summary = capture.capture_modbus("127.0.0.1", port, 1, 5, files, entries)
        listener.close()

        assert summary["outcome"] == "ok"
        # Bisection splits at halves, so segment boundaries land on powers of
        # two — what matters is the complete, disjoint coverage of the block.
        first_block = [
            e
            for e in entries
            if e.get("variant") == "modbus" and e.get("start", 999) < 1050 and e.get("status") in ("ok", "hole")
        ]
        covered: set[int] = set()
        for e in first_block:
            span = set(range(e["start"], e["start"] + e["words"]))
            assert not (covered & span), "segments must not overlap"
            covered |= span
        assert covered == set(range(1000, 1050))
        # The hole is pinned down to single addresses.
        holes = [e for e in entries if e.get("status") == "hole"]
        assert sorted(e["start"] for e in holes) == [1010, 1011]
        # Untouched blocks come through whole.
        record = json.loads(files["modbus/input_1100_1149.json"])
        assert record["function"] == 4 and record["count"] == 50 and len(record["raw_words"]) == 50
        assert not [e for e in entries if e.get("status") == "error"]

    def test_capture_modbus_reports_whole_range_refusals(self) -> None:
        listener = socket.socket()
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]

        def serve() -> None:
            sock_in, _ = listener.accept()
            sock_in.settimeout(5)
            # The whole holding range is one hole: bisection bottoms out and
            # records the per-address refusals as holes, not as errors.
            _fake_modbus_server(sock_in, set(range(2000, 2200)))

        threading.Thread(target=serve, daemon=True).start()
        files: dict[str, str] = {}
        entries: list[dict] = []
        summary = capture.capture_modbus("127.0.0.1", port, 1, 5, files, entries)
        listener.close()

        assert summary["outcome"] == "ok"  # input blocks answered
        holes = [e for e in entries if e.get("status") == "hole"]
        assert all(2000 <= e["start"] < 2200 for e in holes)
        assert not [e for e in entries if e.get("status") == "error"]

    def test_perform_capture_includes_modbus_by_default(self, tmp_path: Path) -> None:
        # Nothing listens on 192.0.2.99: the sweep must be recorded as
        # unavailable, the ZIP still written, ok=False only when all legs fail.
        zip_path, ok, _warnings = capture.perform_capture(
            host="192.0.2.99", pin="1", out_dir=str(tmp_path), modbus=True
        )
        assert Path(zip_path).exists()
        assert ok is False
        with zipfile.ZipFile(zip_path) as archive:
            manifest = json.loads(archive.read("manifest.json"))
        assert manifest["variants"]["modbus"]["outcome"] == "unavailable"
        assert manifest["modbus_port"] == 502

    def test_perform_capture_can_skip_modbus(self, tmp_path: Path) -> None:
        zip_path, _ok, _warnings = capture.perform_capture(
            host="192.0.2.99", pin="1", out_dir=str(tmp_path), modbus=False
        )
        with zipfile.ZipFile(zip_path) as archive:
            manifest = json.loads(archive.read("manifest.json"))
            names = archive.namelist()
        assert manifest["variants"]["modbus"]["outcome"] == "skipped"
        assert not any(n.startswith("modbus/") for n in names)


class TestEmptyPinContinues:
    def test_perform_capture_with_empty_pin_still_sweeps_modbus(self, tmp_path: Path) -> None:
        # A plant without a web interface has no PIN: the web legs fail their
        # login and get recorded, the Modbus sweep still runs — one data
        # source beats none.
        lines: list[str] = []
        zip_path, ok, _warnings = capture.perform_capture(
            host="192.0.2.99", pin="", out_dir=str(tmp_path), log=lines.append
        )
        assert Path(zip_path).exists()
        assert ok is False  # nothing answers on 192.0.2.99
        assert any("nav20" in line for line in lines)
        assert any("modbus" in line for line in lines)
        with zipfile.ZipFile(zip_path) as archive:
            manifest = json.loads(archive.read("manifest.json"))
        assert manifest["variants"]["nav20"]["outcome"] == "unavailable"
        assert manifest["variants"]["modbus"]["outcome"] == "unavailable"

    def test_cli_empty_pin_warns_and_continues(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(capture.getpass, "getpass", lambda *_a, **_k: "")
        code = capture.main(["192.0.2.99", "--pin", "", "--out", str(tmp_path)])
        assert code == 2  # total failure on the dead host, but no PIN abort
        zips = list(tmp_path.glob("idm_web_capture_*.zip"))
        assert len(zips) == 1
