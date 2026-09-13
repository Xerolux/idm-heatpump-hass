"""Contract tests for the version-to-version changelog workflow.

Since 0.17.0 the changelog is kept between released versions: when a stable
section exists, the prerelease sections of that version must have been folded
into it. Individual betas need not be named in the stable section, but the
fold is expected to lose nothing — that is what
``scripts/consolidate_changelog.py`` guarantees mechanically, and what the
editorial pass keeps true afterwards.
"""

from __future__ import annotations

import re
from pathlib import Path

from packaging.version import Version

from scripts import consolidate_changelog as fold_module

ROOT = Path(__file__).resolve().parents[1]
CHANGELOG = ROOT / "docs" / "CHANGELOG.md"

#: The workflow starts here; 0.15.x/0.16.x history keeps its published shape.
CONSOLIDATION_BASELINE = Version("0.17.0")

_HEADING_RE = re.compile(r"^## \[([^\]]+)\]", re.MULTILINE)


def _headings() -> list[str]:
    return _HEADING_RE.findall(CHANGELOG.read_text(encoding="utf-8"))


def _version(label: str) -> Version | None:
    """Parse a heading label, returning None for Unreleased/malformed ones."""
    if label == "Unreleased":
        return None
    try:
        return Version(label)
    except Exception:  # noqa: BLE001 - malformed labels are the point here
        return None


def _is_prerelease(label: str) -> bool:
    version = _version(label)
    return version is not None and version.is_prerelease


def _stable_labels() -> set[str]:
    labels = set()
    for label in _headings():
        version = _version(label)
        if version is not None and not version.is_prerelease and version >= CONSOLIDATION_BASELINE:
            labels.add(str(version))
    return labels


def test_stable_sections_have_no_leftover_prerelease_headings() -> None:
    """Every stable cut from 0.17.0 on folds its prerelease sections away."""
    stables = _stable_labels()
    problems = [
        label
        for label in _headings()
        if (version := _version(label)) is not None and version.is_prerelease and str(version) in stables
    ]
    assert not problems, (
        "prerelease sections still present after their stable cut: "
        f"{problems}; fold them with scripts/consolidate_changelog.py"
    )


SAMPLE = """# Changelog

## [Unreleased]

## [0.18.0-beta.2] - 2026-10-02

Second beta intro.

### Fixed

- Bug A fix improved.
- Bug B.

## [0.18.0-beta.1] - 2026-10-01

First beta intro.

### Added

- Feature X.

### Fixed

- Bug A initial fix.

## [0.17.0] - 2026-09-13

Older release.

### Added

- Navigator 1.7.

## [0.16.2] - 2026-08-28

Even older.
"""


def test_fold_merges_prereleases_without_losing_bullets() -> None:
    result = fold_module.fold(SAMPLE, "0.18.0", "2026-10-03")

    assert "## [0.18.0] - 2026-10-03" in result
    assert "## [0.18.0-beta" not in result
    # Both betas' bullets survive; the superseded wording stays for the editor.
    assert "Feature X." in result
    assert "Bug A initial fix." in result
    assert "Bug A fix improved." in result
    assert "Bug B." in result
    # The older sections are untouched.
    assert "## [0.17.0] - 2026-09-13" in result
    assert "## [0.16.2] - 2026-08-28" in result
    # Intros are marked with the beta they came from.
    assert "**From `[0.18.0-beta.1]`:** First beta intro." in result


def test_fold_deduplicates_identical_bullets() -> None:
    sample = SAMPLE.replace("- Bug A fix improved.\n", "- Bug A initial fix.\n")
    result = fold_module.fold(sample, "0.18.0", "2026-10-03")

    assert result.count("- Bug A initial fix.") == 1


def test_fold_refuses_when_the_stable_already_exists() -> None:
    try:
        fold_module.fold(SAMPLE, "0.17.0", "2026-10-03")
    except SystemExit as err:
        assert "already exists" in str(err)
    else:
        raise AssertionError("folding a released stable must refuse")


def test_fold_refuses_without_prereleases() -> None:
    try:
        fold_module.fold(SAMPLE, "0.19.0", "2026-10-03")
    except SystemExit as err:
        assert "no prerelease sections" in str(err)
    else:
        raise AssertionError("folding a version without prereleases must refuse")
