"""Tests for the sensitive-data guard scanner.

All offending samples are constructed at runtime (string concatenation,
repeat operators) so this test file itself stays clean for the scanner.
"""

from __future__ import annotations

from pathlib import Path

from scripts import check_sensitive_data as guard

REPO_ROOT = Path(__file__).resolve().parent.parent


def _write_sample(directory: Path, content: str) -> Path:
    path = directory / "sample.txt"
    path.write_text(content, encoding="utf-8")
    return path


class TestDetection:
    def test_private_ip_is_flagged(self, tmp_path: Path) -> None:
        address = ".".join(["192", "168", "178", "99"])
        path = _write_sample(tmp_path, f"host = {address}\n")

        findings = guard.scan_file(path, frozenset(), tmp_path)

        assert [f.category for f in findings] == ["private-ip"]

    def test_documentation_addresses_are_never_flagged(self, tmp_path: Path) -> None:
        path = _write_sample(tmp_path, "a = 192.0.2.10\nb = 198.51.100.4\nc = 203.0.113.7\n")

        assert guard.scan_file(path, frozenset(), tmp_path) == []

    def test_loopback_and_broadcast_are_never_flagged(self, tmp_path: Path) -> None:
        path = _write_sample(tmp_path, "a = 127.0.0.1\nb = 0.0.0.0\nc = 255.255.255.255\n")

        assert guard.scan_file(path, frozenset(), tmp_path) == []

    def test_allowlisted_private_ip_passes(self, tmp_path: Path) -> None:
        address = "192.168.1.100"
        path = _write_sample(tmp_path, f"host = {address}\n")

        assert guard.scan_file(path, frozenset({address}), tmp_path) == []

    def test_numeric_pin_is_flagged(self, tmp_path: Path) -> None:
        pin = "9" * 4
        path = _write_sample(tmp_path, f'CONF_WEB_PIN: "{pin}"\n')

        findings = guard.scan_file(path, frozenset(), tmp_path)

        assert [f.category for f in findings] == ["pin"]

    def test_allowlisted_fake_pin_passes(self, tmp_path: Path) -> None:
        path = _write_sample(tmp_path, 'CONF_WEB_PIN: "1234"\n')

        assert guard.scan_file(path, frozenset({"1234"}), tmp_path) == []

    def test_myidm_id_is_flagged(self, tmp_path: Path) -> None:
        myidm = "m" + "7" * 6
        path = _write_sample(tmp_path, f"id = {myidm}\n")

        findings = guard.scan_file(path, frozenset(), tmp_path)

        assert [f.category for f in findings] == ["myidm-id"]

    def test_full_myidm_id_is_always_flagged(self, tmp_path: Path) -> None:
        myidm = "m" + "5" * 6 + "@" + "a" * 20
        path = _write_sample(tmp_path, f"id = {myidm}\n")

        findings = guard.scan_file(path, frozenset(), tmp_path)

        assert "myidm-id" in [f.category for f in findings]

    def test_jwt_is_flagged(self, tmp_path: Path) -> None:
        jwt = "eyJ" + "A" * 20 + "." + "B" * 20
        path = _write_sample(tmp_path, f"auth = {jwt}\n")

        categories = [f.category for f in guard.scan_file(path, frozenset(), tmp_path)]

        assert "jwt" in categories

    def test_session_id_value_is_flagged(self, tmp_path: Path) -> None:
        session = "f" * 32
        path = _write_sample(tmp_path, f'frame = {{"remoteSessionId": "{session}"}}\n')

        findings = guard.scan_file(path, frozenset(), tmp_path)

        assert [f.category for f in findings] == ["credential"]

    def test_unknown_email_is_flagged(self, tmp_path: Path) -> None:
        address = "leak@" + "nowhere" + ".xyz"
        path = _write_sample(tmp_path, f"contact: {address}\n")

        findings = guard.scan_file(path, frozenset(), tmp_path)

        assert [f.category for f in findings] == ["email"]

    def test_email_wildcard_allowlist_passes(self, tmp_path: Path) -> None:
        path = _write_sample(tmp_path, "contact: someone@example.org\n")

        assert guard.scan_file(path, frozenset({"*@example.org"}), tmp_path) == []

    def test_vendor_test_host_is_flagged(self, tmp_path: Path) -> None:
        host = "myidm-test" + ".at"
        path = _write_sample(tmp_path, f"url = https://{host}/\n")

        findings = guard.scan_file(path, frozenset(), tmp_path)

        assert [f.category for f in findings] == ["vendor-test-host"]

    def test_binary_files_are_skipped(self, tmp_path: Path) -> None:
        address = ".".join(["192", "168", "178", "99"])  # noqa: FLY002
        path = tmp_path / "blob.bin"
        path.write_bytes(address.encode() + b"\x00rest")

        assert guard.scan_file(path, frozenset(), tmp_path) == []


class TestRepositoryIsClean:
    def test_the_repository_passes_the_guard(self) -> None:
        assert guard.scan_tree(REPO_ROOT) == []
