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
* ``check_dependency_pins.py --update`` rewrites every updatable pin
  (``modbus-connection``, ``tmodbus`` and ``idm-heatpump-api``) to the newest
  release, in the manifest and in every document that states the current pins.
  The dependency-update workflow runs it daily and opens a pull request.
* ``check_dependency_pins.py --set name==version`` rewrites one pin to a version
  named by the caller instead of the newest one on PyPI.  The API repository
  announces a release that way, before the artifact is visible on the index.

Pre-releases are ignored unless the current pin is itself a pre-release — the
alpha this repository was stuck on must not be selectable by automation.
Requirements with a version range (``pymodbus>=3.12.1,<4.0``) are reported but
never fail the check: widening a range is a compatibility decision, not a bump.

Usage:
  python scripts/check_dependency_pins.py                 # check, non-zero if stale
  python scripts/check_dependency_pins.py --warn-only     # report only, always 0
  python scripts/check_dependency_pins.py --update        # rewrite stale pins
  python scripts/check_dependency_pins.py --update --only tmodbus
  python scripts/check_dependency_pins.py --set idm-heatpump-api==2.1.0
  python scripts/check_dependency_pins.py --json          # machine-readable report
  python scripts/check_dependency_pins.py --update --report updates.json
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

# Distributions this script may bump on its own: everything the integration
# declares as an exact runtime requirement.  A range requirement is never bumped
# automatically -- widening a range is a compatibility decision, not a bump.
UPDATABLE = ("modbus-connection", "tmodbus", "idm-heatpump-api")

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
    "docs/wiki/Modbus-Register.md",
    "docs/wiki/Services.md",
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
    "docs/wiki/Stability-and-Release-Readiness.md": (
        ("idm-heatpump-api", r"(?<=and `idm-heatpump-api` `){version}(?=` form the current)"),
    ),
}

# Sentences that name a version as *history* -- the release something changed
# in, not the pin the integration ships.  They must survive an update, so the
# residual scan masks them before looking for a leftover old version.  Each
# pattern is anchored on its own sentence: one that also matched the statement
# of the current pin would hide a genuinely half-finished rewrite.
HISTORY_STATEMENTS: dict[str, tuple[str, ...]] = {
    "AGENTS.md": (r"pymodbus is gone as of `idm-heatpump-api` [0-9][0-9a-z.]*",),
    "docs/dev/open-work-audit.md": (r"`idm-heatpump-api` [0-9][0-9a-z.]* provides the transport-neutral contract",),
    "docs/wiki/Stability-and-Release-Readiness.md": (r"`idm-heatpump-api` `[0-9][0-9a-z.]*` owns its own",),
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


def manifest_requirements(manifest_path: Path | None = None) -> list[Requirement]:
    """Return every runtime requirement declared by the manifest."""
    manifest = json.loads((manifest_path or MANIFEST_PATH).read_text(encoding="utf-8"))
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


def without_history_statements(relative_path: str, text: str) -> str:
    """Return ``text`` with this document's known history sentences removed."""
    for pattern in HISTORY_STATEMENTS.get(relative_path, ()):
        text = re.sub(pattern, "", text)
    return text


def residual_mentions(root: Path, name: str, version: str) -> list[str]:
    """Return the documents that still state ``name`` at ``version``.

    A pin can be written as a requirement (``name[extra]==1.2.3``, with or
    without spaces around ``==``) or in prose (``name 1.2.3``).  After an update
    none of those forms may name the old version any more, so a spelling the
    rewrite does not cover is caught here instead of silently reaching a pull
    request as a half-updated document.  Sentences listed in
    ``HISTORY_STATEMENTS`` are exempt: they date a change and keep their version
    forever.
    """
    pattern = re.compile(rf"{re.escape(name)}(?:\[[^\]]*\])?\s*(?:==\s*|`?\s+)`?{re.escape(version)}\b")
    found = []
    for relative_path in PIN_DOCUMENTS:
        path = root / relative_path
        if not path.exists():
            continue
        text = without_history_statements(relative_path, path.read_text(encoding="utf-8"))
        if pattern.search(text):
            found.append(relative_path)
    return found


def apply_update(requirement: Requirement, new_version: str, root: Path | None = None) -> list[str]:
    """Rewrite one pin in the manifest and in every document stating it.

    Returns the paths that changed.  Raises when a document still names the old
    version afterwards, so a half-finished rewrite fails the workflow instead of
    reaching a pull request.
    """
    root = root if root is not None else ROOT
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


SEMVER_RELEASE = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")


def bump_kind(old_version: str, new_version: str) -> str:
    """Classify a version change, so automation can hold a major bump back."""
    try:
        current, target = Version(old_version), Version(new_version)
    except InvalidVersion:
        return "unknown"
    if target.major != current.major:
        return "major"
    if target.minor != current.minor:
        return "minor"
    if target.micro != current.micro:
        return "patch"
    return "other"


def parse_set_argument(raw: str) -> tuple[str, str]:
    """Split a ``--set name==version`` argument, rejecting anything unstable.

    Automation is never allowed to move a pin onto a pre-release, so the
    requested version has to be a plain ``X.Y.Z`` release even when the caller
    is the API repository announcing its own build.
    """
    name, separator, version = raw.partition("==")
    name, version = name.strip(), version.strip()
    if not separator or not name or not version:
        raise ValueError(f"--set expects 'name==version', got {raw!r}")
    if SEMVER_RELEASE.match(version) is None:
        raise ValueError(f"--set version must be a stable release in X.Y.Z form, got {version!r}")
    return name, version


def _apply(requirement: Requirement, new_version: str, root: Path | None = None) -> dict[str, Any]:
    """Apply one pin update and describe it for the report."""
    old_version = requirement.pinned_version
    if old_version is None:
        raise ValueError(f"{requirement.name} is not exactly pinned")
    changed = apply_update(requirement, new_version, root=root)
    return {
        "name": requirement.name,
        "from": old_version,
        "to": new_version,
        "bump": bump_kind(old_version, new_version),
        "requirement": requirement.with_version(new_version),
        "changed": changed,
    }


def _write_report(path: Path, updates: list[dict[str, Any]]) -> None:
    """Write the applied updates as JSON, for the workflow to read back."""
    if path.parent != Path(""):
        path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(updates, indent=2) + "\n", encoding="utf-8")


def _summarize(updates: list[dict[str, Any]], report: Path | None) -> None:
    """Write the report file and print what changed."""
    if report is not None:
        _write_report(report, updates)
    if updates:
        changed = sorted({path for update in updates for path in update["changed"]})
        print("changed files: " + ", ".join(changed))
    else:
        print("nothing to update")


def _report(findings: list[Finding]) -> None:
    for finding in findings:
        marker = {"current": "ok  ", "stale": "STALE", "range": "range", "unknown": "?   "}[finding.status]
        print(f"{marker} {finding.detail}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--update", action="store_true", help="rewrite stale pins in place")
    parser.add_argument(
        "--only",
        action="append",
        metavar="NAME",
        help="restrict --update to this distribution (repeatable)",
    )
    parser.add_argument(
        "--set",
        action="append",
        dest="pin",
        metavar="NAME==VERSION",
        help="pin one requirement to an exact stable version instead of the newest on PyPI (repeatable)",
    )
    parser.add_argument("--warn-only", action="store_true", help="report stale pins without failing")
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    parser.add_argument("--report", type=Path, metavar="PATH", help="write the applied updates to PATH as JSON")
    args = parser.parse_args(argv)

    # --set names its own versions, so it must not depend on PyPI being
    # reachable or on the release being visible there yet.
    if args.pin:
        return _run_set(args)

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
        selected = {name.strip() for name in args.only} if args.only else None
        updates: list[dict[str, Any]] = []
        for finding in stale:
            name = finding.requirement.name
            if name not in UPDATABLE:
                print(f"skip {name}: not an exact pin this script owns", file=sys.stderr)
                continue
            if selected is not None and name not in selected:
                print(f"skip {name}: not selected by --only", file=sys.stderr)
                continue
            assert finding.latest is not None
            updates.append(_apply(finding.requirement, finding.latest))
            print(f"updated {name} to {finding.latest}")
        _summarize(updates, args.report)
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


def _run_set(args: argparse.Namespace) -> int:
    """Rewrite the pins named on the command line, without asking PyPI.

    The API repository announces a release before pip can see it, so this path
    deliberately does not consult the index.  It still refuses anything that is
    not a stable release, and anything the manifest does not pin exactly.
    """
    requirements = {requirement.name: requirement for requirement in manifest_requirements()}
    updates: list[dict[str, Any]] = []
    for raw in args.pin:
        try:
            name, version = parse_set_argument(raw)
        except ValueError as error:
            print(f"error: {error}", file=sys.stderr)
            return 2
        requirement = requirements.get(name)
        if requirement is None:
            print(f"error: {name} is not a runtime requirement of this integration", file=sys.stderr)
            return 2
        if requirement.pinned_version is None:
            print(f"error: {name} is a version range, not an exact pin", file=sys.stderr)
            return 2
        if requirement.pinned_version == version:
            print(f"{name} already pinned to {version}")
            continue
        updates.append(_apply(requirement, version))
        print(f"updated {name} to {version}")

    _summarize(updates, args.report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
