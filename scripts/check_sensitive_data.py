"""Repository guard: refuse real plant credentials, addresses and identifiers.

Scans the whole working tree for data that must never be committed: real
IP addresses, PINs, myIDM account ids, tokens, session ids, e-mail addresses
and non-public vendor hosts. The rules are generic (any private IPv4, any
numeric PIN, any ``m123456``-style myIDM id, any JWT), so they also catch
values nobody has thought of yet; everything that is intentionally in the
repository — documentation addresses, fake fixture credentials — lives in
``.github/sensitive-data-allowlist.txt`` and has to be added there
consciously, in review.

Exits with status 1 and one line per finding (``path:line: category``).
Run locally with ``python scripts/check_sensitive_data.py``; CI runs it on
every push and every pull request.
"""

from __future__ import annotations

import argparse
import ipaddress
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ALLOWLIST_FILENAME = "sensitive-data-allowlist.txt"
SCRIPT_FILENAME = "check_sensitive_data.py"

SKIP_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "test_ha",
    "venv",
}
SKIP_SUFFIXES = {
    ".bin",
    ".gif",
    ".gz",
    ".ico",
    ".jpeg",
    ".jpg",
    ".lock",
    ".pdf",
    ".png",
    ".ttf",
    ".whl",
    ".woff",
    ".woff2",
    ".zip",
}

# Addresses from RFC 5737 (and friends) that documentation may freely use.
DOCUMENTATION_NETS = (
    ipaddress.ip_network("192.0.2.0/24"),
    ipaddress.ip_network("198.51.100.0/24"),
    ipaddress.ip_network("203.0.113.0/24"),
)
# Never sensitive: loopback, unspecified and broadcast.
BENIGN_NETS = (
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("0.0.0.0/32"),
    ipaddress.ip_network("255.255.255.255/32"),
)

IPV4_RE = re.compile(r"\b(\d{1,3}(?:\.\d{1,3}){3})\b")
IPV6_LOCAL_RE = re.compile(r"\b(?:fd[0-9a-f]{2}|fe80)(?::[0-9a-fA-F]{1,4}){2,7}\b", re.IGNORECASE)
PIN_RE = re.compile(
    r"\b(?:[A-Za-z0-9_-]*[_-])?(?:web[_-]?pin|pin|passcode|passwort|password|passwd)\b"
    r"[\"']?\s*[:=]?\s*[\"']?(\d{4,8})\b",
    re.IGNORECASE,
)
MYIDM_RE = re.compile(r"\bm(\d{4,8})\b")
MYIDM_FULL_RE = re.compile(r"\b(m\d{4,8}@[0-9a-f]{16,})\b")
JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}")
TOKEN_PREFIX_RE = re.compile(
    r"\b("
    r"ghp_[A-Za-z0-9]{16,}"
    r"|gho_[A-Za-z0-9]{16,}"
    r"|ghu_[A-Za-z0-9]{16,}"
    r"|ghs_[A-Za-z0-9]{16,}"
    r"|ghr_[A-Za-z0-9]{16,}"
    r"|github_pat_[A-Za-z0-9_]{16,}"
    r"|pypi-AgEI[A-Za-z0-9_-]{16,}"
    r"|xox[baprs]-[A-Za-z0-9-]{10,}"
    r"|AKIA[0-9A-Z]{16}"
    r")\b"
)
PRIVATE_KEY_RE = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----")
CONTEXT_SECRET_RE = re.compile(
    r"\b(token|secret|(?:remote)?session[_-]?id|password|passwd|api[_-]?key|"
    r"access[_-]?token|refresh[_-]?token)\b"
    r"[\"']?\s*[:=]\s*[\"']?([0-9A-Za-z+/=_-]{20,})",
    re.IGNORECASE,
)
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+\b")
VENDOR_TEST_HOST_RE = re.compile(r"\b(?:[a-z0-9.-]*\.)?myidm-test\.at\b", re.IGNORECASE)


@dataclass(frozen=True)
class Finding:
    """One rule violation: file, 1-based line, category and the matched value."""

    path: Path
    line: int
    category: str
    value: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.category} '{_mask(self.value)}'"


def _mask(value: str) -> str:
    if len(value) <= 4:
        return value[:1] + "***"
    return value[:4] + "..." + value[-2:]


def load_allowlist(path: Path) -> frozenset[str]:
    """Load allowlist entries; ``*`` is a leading/trailing wildcard."""
    entries: set[str] = set()
    if path.is_file():
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if line and not line.startswith("#"):
                entries.add(line)
    return frozenset(entries)


def _allowed(value: str, allowlist: frozenset[str]) -> bool:
    if value in allowlist:
        return True
    for entry in allowlist:
        if entry.startswith("*") and value.endswith(entry[1:]):
            return True
        if entry.endswith("*") and value.startswith(entry[:-1]):
            return True
    return False


def scan_text(text: str, allowlist: frozenset[str]) -> list[tuple[str, str]]:
    """Return ``(category, value)`` pairs for every rule hit in ``text``."""
    findings: list[tuple[str, str]] = []

    for match in IPV4_RE.finditer(text):
        candidate = match.group(1)
        try:
            address = ipaddress.IPv4Address(candidate)
        except ValueError:
            continue
        if any(address in net for net in BENIGN_NETS):
            continue
        if any(address in net for net in DOCUMENTATION_NETS):
            continue
        if address.is_private and not _allowed(candidate, allowlist):
            findings.append(("private-ip", candidate))

    for match in IPV6_LOCAL_RE.finditer(text):
        candidate = match.group(0)
        if not _allowed(candidate, allowlist):
            findings.append(("private-ip", candidate))

    for match in PIN_RE.finditer(text):
        value = match.group(1)
        if not _allowed(value, allowlist):
            findings.append(("pin", value))

    for match in MYIDM_RE.finditer(text):
        value = f"m{match.group(1)}"
        if not _allowed(value, allowlist):
            findings.append(("myidm-id", value))

    for match in MYIDM_FULL_RE.finditer(text):
        findings.append(("myidm-id", _mask(match.group(1))))

    for pattern, category in (
        (JWT_RE, "jwt"),
        (TOKEN_PREFIX_RE, "token"),
        (PRIVATE_KEY_RE, "private-key"),
        (VENDOR_TEST_HOST_RE, "vendor-test-host"),
    ):
        for match in pattern.finditer(text):
            findings.append((category, match.group(0)))

    for match in CONTEXT_SECRET_RE.finditer(text):
        if not _allowed(match.group(2), allowlist):
            findings.append(("credential", match.group(2)))

    for match in EMAIL_RE.finditer(text):
        if not _allowed(match.group(0), allowlist):
            findings.append(("email", match.group(0)))

    return findings


def _is_binary_sample(chunk: bytes) -> bool:
    return b"\x00" in chunk


def scan_file(path: Path, allowlist: frozenset[str], repo_root: Path) -> list[Finding]:
    """Scan one file; returns findings with line numbers."""
    try:
        with path.open("rb") as handle:
            head = handle.read(8192)
            if _is_binary_sample(head):
                return []
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    findings: list[Finding] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        for category, value in scan_text(line, allowlist):
            findings.append(
                Finding(
                    path=path.relative_to(repo_root),
                    line=line_no,
                    category=category,
                    value=value,
                )
            )
    return findings


def scan_tree(root: Path, allowlist_path: Path | None = None) -> list[Finding]:
    """Scan every scannable file under ``root``."""
    if allowlist_path is None:
        allowlist_path = root / ".github" / ALLOWLIST_FILENAME
    allowlist = load_allowlist(allowlist_path)

    findings: list[Finding] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.name in (ALLOWLIST_FILENAME, SCRIPT_FILENAME):
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in SKIP_SUFFIXES:
            continue
        findings.extend(scan_file(path, allowlist, root))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        default=str(Path(__file__).resolve().parent.parent),
        help="repository root to scan (default: this repository)",
    )
    parser.add_argument(
        "--allowlist",
        default=None,
        help="allowlist file (default: <root>/.github/sensitive-data-allowlist.txt)",
    )
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    allowlist_path = Path(args.allowlist) if args.allowlist else None
    findings = scan_tree(root, allowlist_path)

    if findings:
        print("Sensitive data found in the repository:")
        for finding in findings:
            print(f"  {finding}")
        print(
            "\nIf a value is an intentional fake for tests or documentation, add it to"
            "\n.github/sensitive-data-allowlist.txt in the same pull request."
            "\nReal credentials must never be committed - rotate them instead."
        )
        return 1
    print("Sensitive data guard: clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
