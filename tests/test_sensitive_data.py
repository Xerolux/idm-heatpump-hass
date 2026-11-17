"""Tests for the sensitive-data guard scanner.

All offending samples are constructed at runtime (string concatenation,
repeat operators) so this test file itself stays clean for the scanner.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from scripts import check_sensitive_data as guard

REPO_ROOT = Path(__file__).resolve().parent.parent


def _write_sample(directory: Path, content: str) -> Path:
    path = directory / "sample.txt"
    path.write_text(content, encoding="utf-8")
    return path


class TestDetection:
    def test_private_ip_is_flagged(self, tmp_path: Path) -> None:
        # constructed so this test file itself stays clean for the guard
        address = ".".join(["192", "168", "178", "99"])  # noqa: FLY002
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


class TestScope:
    """The guard protects what can be committed, not git-ignored runtime data."""

    _needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="needs a git binary")

    @_needs_git
    def test_git_ignored_files_are_out_of_scope(self, tmp_path: Path) -> None:
        """A runtime volume ignored by .gitignore cannot enter a commit."""
        address = ".".join(["192", "168", "178", "99"])  # noqa: FLY002
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        (tmp_path / ".gitignore").write_text("runtime/\n", encoding="utf-8")
        (tmp_path / "runtime").mkdir()
        (tmp_path / "runtime" / "log.txt").write_text(f"ip {address}\n", encoding="utf-8")
        (tmp_path / "committable.txt").write_text(f"ip {address}\n", encoding="utf-8")

        findings = guard.scan_tree(tmp_path)

        assert [finding.path.as_posix() for finding in findings] == ["committable.txt"]

    @_needs_git
    def test_tracked_files_stay_in_scope_inside_a_repository(self, tmp_path: Path) -> None:
        """Force-added (tracked) content is committable and must be flagged."""
        address = ".".join(["192", "168", "178", "99"])  # noqa: FLY002
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        (tmp_path / ".gitignore").write_text("runtime/\n", encoding="utf-8")
        (tmp_path / "runtime").mkdir()
        (tmp_path / "runtime" / "forced.txt").write_text(f"ip {address}\n", encoding="utf-8")
        subprocess.run(
            ["git", "add", "--force", "runtime/forced.txt"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        findings = guard.scan_tree(tmp_path)

        assert [finding.path.as_posix() for finding in findings] == ["runtime/forced.txt"]

    def test_without_git_the_guard_scans_everything(self, tmp_path: Path) -> None:
        """No repository, no ignore rules: the old whole-tree behavior applies."""
        address = ".".join(["192", "168", "178", "99"])  # noqa: FLY002
        (tmp_path / "plain.txt").write_text(f"ip {address}\n", encoding="utf-8")

        findings = guard.scan_tree(tmp_path)

        assert [finding.path.as_posix() for finding in findings] == ["plain.txt"]


class TestRepositoryIsClean:
    def test_the_repository_passes_the_guard(self) -> None:
        assert guard.scan_tree(REPO_ROOT) == []
