"""Tests for the runtime dependency pin check and its automated update."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import check_dependency_pins as pins

ROOT = Path(__file__).resolve().parents[1]

# Documents that keep the versions of the release they describe.  They must
# never be rewritten by an update, which is why they are not in PIN_DOCUMENTS.
HISTORY_PREFIXES = (
    "docs/CHANGELOG.md",
    "docs/wiki/Changelog.md",
    "docs/release-evidence/",
    "docs/IMPLEMENTATION_TODO.md",
    "docs/dev/modbus-transport-preparation.md",
)


def _payload(*versions: str, yanked: tuple[str, ...] = ()) -> dict:
    """Build a PyPI-shaped release index for the given versions."""
    return {
        "releases": {version: [{"filename": f"pkg-{version}.whl", "yanked": version in yanked}] for version in versions}
    }


def test_requirement_parsing_keeps_extras_and_specifier() -> None:
    # Deliberately not the version the manifest pins: this file must not read as
    # a document that states the current pins.
    requirement = pins.parse_requirement("tmodbus[async-serial]==0.4.2")

    assert requirement.name == "tmodbus"
    assert requirement.extras == "async-serial"
    assert requirement.pinned_version == "0.4.2"
    assert requirement.with_version("0.6.0") == "tmodbus[async-serial]==0.6.0"


def test_range_requirement_has_no_pinned_version() -> None:
    requirement = pins.parse_requirement("pymodbus>=3.12.1,<4.0")

    assert requirement.name == "pymodbus"
    assert requirement.extras is None
    assert requirement.pinned_version is None


def test_manifest_requirements_are_all_parsable() -> None:
    """The shipped manifest must stay readable by the check."""
    requirements = pins.manifest_requirements()

    assert {requirement.name for requirement in requirements} >= {
        "modbus-connection",
        "tmodbus",
        "pymodbus",
        "idm-heatpump-api",
    }


def test_prereleases_are_never_selected_for_a_stable_pin() -> None:
    """The alpha this repository was stuck on must not be reachable again.

    ``modbus-connection`` published 8.9.0a1..a4 alongside stable releases; a
    stable pin must resolve to the newest stable, never to an alpha.
    """
    payload = _payload("8.9.0", "9.1.0", "9.2.0a1")

    assert str(pins.latest_version(payload, allow_prerelease=False)) == "9.1.0"
    assert str(pins.latest_version(payload, allow_prerelease=True)) == "9.2.0a1"


def test_yanked_and_fileless_releases_are_not_candidates() -> None:
    payload = _payload("1.0.0", "1.1.0", yanked=("1.1.0",))
    payload["releases"]["1.2.0"] = []

    assert str(pins.latest_version(payload, allow_prerelease=False)) == "1.0.0"


def test_newer_release_marks_the_pin_stale() -> None:
    requirement = pins.parse_requirement("modbus-connection==9.0.0")

    finding = pins.evaluate(requirement, _payload("9.0.0", "9.1.0"))

    assert finding.status == "stale"
    assert finding.is_stale
    assert finding.latest == "9.1.0"


def test_current_pin_is_not_stale() -> None:
    requirement = pins.parse_requirement("modbus-connection==9.1.0")

    finding = pins.evaluate(requirement, _payload("9.0.0", "9.1.0"))

    assert finding.status == "current"
    assert not finding.is_stale


def test_version_range_is_reported_but_never_stale() -> None:
    """Widening a range is a compatibility decision, not an automated bump."""
    requirement = pins.parse_requirement("pymodbus>=3.12.1,<4.0")

    finding = pins.evaluate(requirement, _payload("3.15.0", "8.9.0"))

    assert finding.status == "range"
    assert not finding.is_stale


def test_unreachable_index_never_fails_the_check() -> None:
    """A PyPI outage must not block a release."""
    requirement = pins.parse_requirement("modbus-connection==9.1.0")

    finding = pins.evaluate(requirement, None)

    assert finding.status == "unknown"
    assert not finding.is_stale


def _write(root: Path, relative: str, text: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_update_rewrites_manifest_and_documents(tmp_path: Path) -> None:
    manifest = _write(
        tmp_path,
        "custom_components/idm_heatpump/manifest.json",
        json.dumps(
            {
                "domain": "idm_heatpump",
                "codeowners": ["@xerolux"],
                "requirements": ["modbus-connection==9.0.0", "pymodbus>=3.12.1,<4.0"],
                "version": "0.15.0-beta.1",
            },
            indent=2,
        )
        + "\n",
    )
    readme = _write(
        tmp_path,
        "README.md",
        "uses `modbus-connection==9.0.0` here\n"
        "    |       +-- modbus-connection 9.0.0 + tmodbus 0.4.0\n"
        "version 9.0.0 is the transport library version\n"
        "unrelated: since modbus-connection 8.5.0 the backend imports serialx\n",
    )

    changed = pins.apply_update(pins.parse_requirement("modbus-connection==9.0.0"), "9.1.0", root=tmp_path)

    assert json.loads(manifest.read_text(encoding="utf-8"))["requirements"][0] == "modbus-connection==9.1.0"
    assert "custom_components/idm_heatpump/manifest.json" in changed[0]
    assert "README.md" in changed

    text = readme.read_text(encoding="utf-8")
    assert "`modbus-connection==9.1.0`" in text
    assert "modbus-connection 9.1.0 + tmodbus 0.4.0" in text
    assert "version 9.1.0 is the transport library version" in text
    # A version named as history stays untouched.
    assert "since modbus-connection 8.5.0 the backend imports serialx" in text


def test_update_keeps_untouched_manifest_formatting(tmp_path: Path) -> None:
    """A bump must not reflow the manifest — that would hide the real diff."""
    manifest = _write(
        tmp_path,
        "custom_components/idm_heatpump/manifest.json",
        '{\n  "codeowners": ["@xerolux"],\n  "requirements": ["tmodbus[async-serial]==0.4.0"]\n}\n',
    )

    pins.apply_update(pins.parse_requirement("tmodbus[async-serial]==0.4.0"), "0.4.1", root=tmp_path)

    assert manifest.read_text(encoding="utf-8") == (
        '{\n  "codeowners": ["@xerolux"],\n  "requirements": ["tmodbus[async-serial]==0.4.1"]\n}\n'
    )


def test_update_fails_loudly_when_a_document_keeps_the_old_pin(tmp_path: Path, monkeypatch) -> None:
    """A half-finished rewrite must fail the workflow, not reach a pull request.

    Here the document spells the pin with spaces around ``==``, which the plain
    requirement replacement does not cover — exactly the kind of spelling that
    would otherwise leave a stale version in the docs.
    """
    _write(
        tmp_path,
        "custom_components/idm_heatpump/manifest.json",
        '{\n  "requirements": ["modbus-connection==9.0.0"]\n}\n',
    )
    _write(tmp_path, "docs/pinned.md", "pinned to `modbus-connection == 9.0.0`\n")
    monkeypatch.setattr(pins, "PIN_DOCUMENTS", ("docs/pinned.md",))

    with pytest.raises(RuntimeError, match="still stated"):
        pins.apply_update(pins.parse_requirement("modbus-connection==9.0.0"), "9.1.0", root=tmp_path)


def test_residual_mentions_finds_prose_and_requirement_spellings(tmp_path: Path, monkeypatch) -> None:
    _write(tmp_path, "docs/a.md", "runtime `modbus-connection==9.0.0`\n")
    _write(tmp_path, "docs/b.md", "the tree shows modbus-connection 9.0.0 next to tmodbus\n")
    _write(tmp_path, "docs/c.md", "history: modbus-connection 8.9.0a3 was the old alpha\n")
    monkeypatch.setattr(pins, "PIN_DOCUMENTS", ("docs/a.md", "docs/b.md", "docs/c.md"))

    assert pins.residual_mentions(tmp_path, "modbus-connection", "9.0.0") == ["docs/a.md", "docs/b.md"]


def _repository_documents() -> list[Path]:
    """Return the Markdown and test files a pin statement could hide in."""
    skip = {".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache", "node_modules"}
    found = []
    for path in ROOT.rglob("*"):
        if any(part in skip for part in path.parts):
            continue
        if path.is_file() and (path.suffix == ".md" or (path.suffix == ".py" and path.parent.name == "tests")):
            found.append(path)
    return found


def test_every_document_stating_a_pin_is_covered_by_the_updater() -> None:
    """A new document naming the pins must not silently escape the automation.

    Without this, a bump would update fifteen files and leave the sixteenth
    claiming a version the integration no longer ships — the failure mode that
    made the stale alpha pin so easy to miss in the first place.
    """
    transport = [req for req in pins.manifest_requirements() if req.name in pins.UPDATABLE]
    assert transport, "expected transport requirements in the manifest"

    uncovered = set()
    for path in _repository_documents():
        relative = path.relative_to(ROOT).as_posix()
        if relative in pins.PIN_DOCUMENTS or relative.startswith(HISTORY_PREFIXES):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(requirement.raw in text for requirement in transport):
            uncovered.add(relative)

    assert not uncovered, (
        f"These documents state the transport pins but are not updated automatically: {sorted(uncovered)}. "
        "Add them to PIN_DOCUMENTS in scripts/check_dependency_pins.py, or to HISTORY_PREFIXES if they are history."
    )
