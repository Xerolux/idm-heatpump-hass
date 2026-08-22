#!/usr/bin/env python3
"""Check — and optionally update — the runtime dependency pins in the manifest.

The integration pins its runtime dependencies exactly, so a release is a
reproducible pair of integration and library versions.  The cost of that is
drift: nothing in the repository notices when a pinned library publishes a new
version, which is how the transport pin sat on the ``modbus-connection==4.0.0a3``
alpha while 4.8.1 was current.

This script closes that gap:

* ``check_dependency_pins.py`` compares every exactly pinned requirement in
  ``manifest.json`` against the newest release on PyPI and exits non-zero when a
  pin is behind.  The release workflow runs it, so a release cannot silently
  ship a stale pin.
* ``check_dependency_pins.py --update`` rewrites the transport pins
  (``modbus-connection``/``tmodbus``) to the newest release, in the manifest and
  in every document that states the current pins.  The dependency-freshness
  workflow runs it and opens a pull request.

Pre-releases are ignored unless the current pin is itself a pre-release — the
alpha this repository was stuck on must not be selectable by automation.
Requirements with a version range (``pymodbus>=3.12.1,<4.0``) are reported but
never fail the check: widening a range is a compatibility decision, not a bump.

Usage:
  python scripts/check_dependency_pins.py              # check, non-zero if stale
  python scripts/check_dependency_pins.py --warn-only  # report only, always 0
  python scripts/check_dependency_pins.py --update     # rewrite transport pins
  python scripts/check_dependency_pins.py --json       # machine-readable report
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from packaging.version import InvalidVersion, Version

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "custom_components" / "idm_heatpump" / "manifest.json"
PYPI_URL = "https://pypi.org/pypi/{name}/json"
NETWORK_TIMEOUT = 30.0

# Distributions this script may bump on its own.  The API pin has its own
# workflow (``api-dependency-update.yml``, triggered by the API repository), and
# a range requirement is never bumped automatically.
UPDATABLE = ("modbus-connection", "tmodbus")

# Documents that state the *current* pins.  Changelogs, wiki changelogs and
# release-evidence records are deliberately absent: they are history and must
# keep the versions their release shipped with.
PIN_DOCUMENTS = (
    "tests/test_release_contract.py",
    "tests/test_entity_metadata_catalog.py",
    "README.md",
    "README_de.md",
    "AGENTS.md",
    "CLAUDE.md",
    "docs/RELEASE_SMOKE_TEST.md",
    "docs/ha-core-integration-page.md",
    "docs/dev/heatpump-feature-roadmap.md",
    "docs/dev/open-work-audit.md",
    "docs/wiki/Home.md",
    "docs/wiki/_Sidebar.md",
    "docs/wiki/Configuration.md",
    "docs/wiki/Local-Web-Interface.md",
    "docs/wiki/Stability-and-Release-Readiness.md",
    ".github/ISSUE_TEMPLATE/modbus_transport_modernization.md",
)

# Places that name a version without the requirement string around it.  Each
# pattern is anchored on the surrounding sentence so only the pin is rewritten,
# never a version mentioned as history.  ``{version}`` is replaced with the
# escaped version currently pinned, so the patterns stay valid after every bump.
BARE_VERSION_STATEMENTS: dict[str, tuple[tuple[str, str], ...]] = {
    "README.md": (
        ("modbus-connection", r"(?<=modbus-connection ){version}(?= \+ tmodbus )"),
        ("tmodbus", r"(?<=\+ tmodbus ){version}(?=\n)"),
        ("modbus-connection", r"(?<=version ){version}(?= is the transport library version)"),
    ),
    "README_de.md": (
        ("modbus-connection", r"(?<=modbus-connection ){version}(?= \+ tmodbus )"),
        ("tmodbus", r"(?<=\+ tmodbus ){version}(?=\n)"),
        ("modbus-connection", r"(?<=`){version}(?=` ist die Version der Verbindungsbibliothek)"),
    ),
    "AGENTS.md": (("modbus-connection", r"(?<=`){version}(?=` is the `modbus-connection` library version)"),),
    "docs/wiki/Home.md": (("modbus-connection", r"(?<=`){version}(?=` is the connection-library version)"),),
    "docs/wiki/Configuration.md": (("modbus-connection", r"(?<=`){version}(?=` is the version of)"),),
    "docs/wiki/Local-Web-Interface.md": (
        ("modbus-connection", r"(?<=version `){version}(?=` an IDM integration release)"),
    ),
    ".github/ISSUE_TEMPLATE/modbus_transport_modernization.md": (
        ("modbus-connection", r"(?<=`){version}(?=` is the version of the connection library)"),
    ),
}

_REQUIREMENT_RE = re.compile(
    r"^(?P<name>[A-Za-z0-9._-]+)"
    r"(?:\[(?P<extras>[^\]]*)\])?"
    r"(?P<specifier>.*)$"
)


@dataclass(frozen=True)
class Requirement:
    """One runtime requirement exactly as the manifest states it."""

    raw: str
    name: str
    extras: str | None
    specifier: str

    @property
    def pinned_version(self) -> str | None:
        """Return the exactly pinned version, or ``None`` for a range."""
        if not self.specifier.startswith("=="):
            return None
        return self.specifier[2:].strip()

    def with_version(self, version: str) -> str:
        """Return this requirement re-rendered for another version."""
        extras = f"[{self.extras}]" if self.extras else ""
        return f"{self.name}{extras}=={version}"


@dataclass(frozen=True)
class Finding:
    """What the check concluded about one requirement."""

    requirement: Requirement
    latest: str | None
    status: str  # "current" | "stale" | "range" | "unknown"
    detail: str

    @property
    def is_stale(self) -> bool:
        return self.status == "stale"


def parse_requirement(raw: str) -> Requirement:
    """Split a manifest requirement into name, extras and specifier."""
    match = _REQUIREMENT_RE.match(raw.strip())
    if match is None:
        raise ValueError(f"Unparsable requirement: {raw!r}")
    return Requirement(
        raw=raw.strip(),
        name=match["name"],
        extras=match["extras"] or None,
        specifier=match["specifier"].strip(),
    )


def manifest_requirements(manifest_path: Path = MANIFEST_PATH) -> list[Requirement]:
    """Return every runtime requirement declared by the manifest."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return [parse_requirement(raw) for raw in manifest["requirements"]]


def usable_versions(payload: dict[str, Any]) -> list[Version]:
    """Return the versions of a PyPI project that are actually installable.

    Releases whose every file is yanked are dropped, as are releases with no
    files at all: neither can be installed, so neither is a candidate.
    """
    versions: list[Version] = []
    for raw, files in (payload.get("releases") or {}).items():
        if not files or all(file.get("yanked") for file in files):
            continue
        try:
            versions.append(Version(raw))
        except InvalidVersion:
            continue
    return sorted(versions)


def latest_version(payload: dict[str, Any], *, allow_prerelease: bool) -> Version | None:
    """Return the newest usable version, skipping pre-releases by default.

    ``allow_prerelease`` is only ever true when the current pin is itself a
    pre-release: automation must never move a stable pin onto an alpha.
    """
    candidates = usable_versions(payload)
    if not allow_prerelease:
        candidates = [version for version in candidates if not version.is_prerelease]
    return candidates[-1] if candidates else None


def fetch_project(name: str) -> dict[str, Any]:
    """Fetch one project's release index from PyPI."""
    with urllib.request.urlopen(PYPI_URL.format(name=name), timeout=NETWORK_TIMEOUT) as response:
        return json.loads(response.read().decode("utf-8"))


def evaluate(requirement: Requirement, payload: dict[str, Any] | None) -> Finding:
    """Compare one requirement against the release index of its project."""
    pinned = requirement.pinned_version
    if pinned is None:
        detail = f"{requirement.name}: version range {requirement.specifier} — reviewed by hand, not bumped here"
        if payload is not None:
            newest = latest_version(payload, allow_prerelease=False)
            if newest is not None:
                detail = f"{requirement.name}: range {requirement.specifier}, newest release {newest}"
        return Finding(requirement, None, "range", detail)

    if payload is None:
        return Finding(requirement, None, "unknown", f"{requirement.name}: release index unavailable")

    try:
        current = Version(pinned)
    except InvalidVersion:
        return Finding(requirement, None, "unknown", f"{requirement.name}: unparsable pin {pinned!r}")

    newest = latest_version(payload, allow_prerelease=current.is_prerelease)
    if newest is None:
        return Finding(requirement, None, "unknown", f"{requirement.name}: no installable release found")
    if newest > current:
        return Finding(
            requirement,
            str(newest),
            "stale",
            f"{requirement.name}: pinned {current}, newest {newest}",
        )
    return Finding(requirement, str(newest), "current", f"{requirement.name}: {current} is current")


def check(requirements: list[Requirement]) -> list[Finding]:
    """Evaluate every requirement against PyPI, tolerating network failures."""
    findings = []
    for requirement in requirements:
        try:
            payload: dict[str, Any] | None = fetch_project(requirement.name)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            print(f"warning: could not reach PyPI for {requirement.name}: {error}", file=sys.stderr)
            payload = None
        findings.append(evaluate(requirement, payload))
    return findings


def residual_mentions(root: Path, name: str, version: str) -> list[str]:
    """Return the documents that still state ``name`` at ``version``.

    A pin can be written as a requirement (``name[extra]==1.2.3``, with or
    without spaces around ``==``) or in prose (``name 1.2.3``).  After an update
    none of those forms may name the old version any more, so a spelling the
    rewrite does not cover is caught here instead of silently reaching a pull
    request as a half-updated document.
    """
    pattern = re.compile(rf"{re.escape(name)}(?:\[[^\]]*\])?\s*(?:==\s*|`?\s+)`?{re.escape(version)}\b")
    found = []
    for relative_path in PIN_DOCUMENTS:
        path = root / relative_path
        if path.exists() and pattern.search(path.read_text(encoding="utf-8")):
            found.append(relative_path)
    return found


def apply_update(requirement: Requirement, new_version: str, root: Path = ROOT) -> list[str]:
    """Rewrite one pin in the manifest and in every document stating it.

    Returns the paths that changed.  Raises when a document still names the old
    version afterwards, so a half-finished rewrite fails the workflow instead of
    reaching a pull request.
    """
    old_version = requirement.pinned_version
    if old_version is None:
        raise ValueError(f"{requirement.name} is not exactly pinned")
    old_requirement = requirement.raw
    new_requirement = requirement.with_version(new_version)
    changed: list[str] = []

    # The manifest is edited as text, not re-serialized: a json.dumps round trip
    # would reflow unrelated keys and make every automated bump a formatting diff.
    manifest_path = root / "custom_components" / "idm_heatpump" / "manifest.json"
    manifest_text = manifest_path.read_text(encoding="utf-8")
    quoted_old, quoted_new = f'"{old_requirement}"', f'"{new_requirement}"'
    if quoted_old not in manifest_text:
        raise RuntimeError(f"{old_requirement} not found in {manifest_path.name}")
    manifest_path.write_text(manifest_text.replace(quoted_old, quoted_new), encoding="utf-8")
    if new_requirement not in json.loads(manifest_path.read_text(encoding="utf-8"))["requirements"]:
        raise RuntimeError(f"{new_requirement} missing from {manifest_path.name} after the update")
    changed.append(manifest_path.relative_to(root).as_posix())

    for relative_path in PIN_DOCUMENTS:
        path = root / relative_path
        if not path.exists():
            continue
        text = original = path.read_text(encoding="utf-8")
        text = text.replace(old_requirement, new_requirement)
        for target, pattern in BARE_VERSION_STATEMENTS.get(relative_path, ()):
            if target != requirement.name:
                continue
            text = re.sub(pattern.replace("{version}", re.escape(old_version)), new_version, text)
        if text != original:
            path.write_text(text, encoding="utf-8")
            changed.append(Path(relative_path).as_posix())

    residual = residual_mentions(root, requirement.name, old_version)
    if residual:
        raise RuntimeError(
            f"{requirement.name} {old_version} still stated after the update in: {', '.join(residual)}. "
            f"Extend PIN_DOCUMENTS or BARE_VERSION_STATEMENTS in {Path(__file__).name}."
        )
    return changed


def _report(findings: list[Finding]) -> None:
    for finding in findings:
        marker = {"current": "ok  ", "stale": "STALE", "range": "range", "unknown": "?   "}[finding.status]
        print(f"{marker} {finding.detail}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--update", action="store_true", help="rewrite stale transport pins in place")
    parser.add_argument("--warn-only", action="store_true", help="report stale pins without failing")
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    args = parser.parse_args(argv)

    findings = check(manifest_requirements())

    if args.json:
        print(
            json.dumps(
                [
                    {
                        "requirement": finding.requirement.raw,
                        "name": finding.requirement.name,
                        "latest": finding.latest,
                        "status": finding.status,
                    }
                    for finding in findings
                ],
                indent=2,
            )
        )
    else:
        _report(findings)

    stale = [finding for finding in findings if finding.is_stale]

    if args.update:
        updated: list[str] = []
        for finding in stale:
            if finding.requirement.name not in UPDATABLE:
                print(
                    f"skip {finding.requirement.name}: not updated here "
                    f"(see .github/workflows/api-dependency-update.yml)",
                    file=sys.stderr,
                )
                continue
            assert finding.latest is not None
            updated += apply_update(finding.requirement, finding.latest)
            print(f"updated {finding.requirement.name} to {finding.latest}")
        if updated:
            print("changed files: " + ", ".join(sorted(set(updated))))
        else:
            print("nothing to update")
        return 0

    if stale and not args.warn_only:
        names = ", ".join(finding.requirement.name for finding in stale)
        print(
            f"\nStale runtime pins: {names}. Run the 'Dependency Freshness' workflow "
            f"(or scripts/check_dependency_pins.py --update) and merge the resulting pull request.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
