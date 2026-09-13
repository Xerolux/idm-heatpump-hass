"""Fold the prerelease changelog sections of a version into the stable section.

The changelog is kept version-to-version: when a stable version is cut, every
``## [<version>-<prerelease>]`` section is folded into the single
``## [<version>]`` section. Individual betas are not listed separately after
the cut, but nothing that changed may be dropped by the fold. The full
per-beta history stays in git and in the GitHub releases of the prerelease
tags.

This script does the mechanical part of the fold so nothing is lost:

* every prerelease section of the target version is found (the file is
  newest-first, so they are read in reverse to restore chronological order);
* intro paragraphs are collected oldest-first, each marked with the beta it
  came from, so the editor sees what the release is assembling;
* category bullets (``### Added`` / ``### Changed`` / ``### Fixed`` / ...)
  are merged in chronological order and exact duplicates are dropped;
* the merged draft replaces the prerelease sections as
  ``## [<version>] - UNRELEASED DRAFT``.

The draft is deliberately rough. The editorial pass — tightening the prose,
ordering by impact, removing the per-beta markers, writing the lead paragraph
and the rollback note — is the maintainer's job, and the contract test in
``tests/test_changelog_consolidation.py`` only checks the structural rule:
once a stable section exists, its prerelease headings must be gone.

Usage::

    python scripts/consolidate_changelog.py --version 0.18.0 [--date 2026-10-01]

Refuses to run when the stable section already exists (nothing to fold) or
when no prerelease sections of that version are found (nothing to fold from).
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

CHANGELOG = Path(__file__).resolve().parents[1] / "docs" / "CHANGELOG.md"

#: Categories recognized by the fold, in the order the draft emits them.
CATEGORY_ORDER = ("Added", "Changed", "Deprecated", "Removed", "Fixed", "Security")

EDITORIAL_MARKER = (
    "<!-- consolidation draft: fold complete. Rework the prose, remove the\n"
    "     per-beta markers, add the lead paragraph and the rollback note, then\n"
    "     replace UNRELEASED DRAFT with the release date. -->"
)


@dataclass
class _Section:
    """One changelog section: its heading line, intro and categorized bullets."""

    heading: str
    intro: list[str] = field(default_factory=list)
    bullets: dict[str, list[str]] = field(default_factory=dict)
    uncategorized: list[str] = field(default_factory=list)


def _parse_sections(text: str) -> list[tuple[str, _Section]]:
    """Split the changelog into top-level ``## [...]`` sections."""
    sections: list[tuple[str, _Section]] = []
    current: _Section | None = None
    current_category: str | None = None
    bullet: list[str] | None = None

    def _flush_bullet() -> None:
        nonlocal bullet
        if current is not None and bullet:
            category = current_category or ""
            target = current.bullets.setdefault(category, [])
            target.append("\n".join(bullet).rstrip())
        bullet = None

    for line in text.splitlines():
        if line.startswith("## "):
            _flush_bullet()
            current = _Section(heading=line)
            current_category = None
            sections.append((line, current))
            continue
        if current is None:
            continue
        if line.startswith("### "):
            _flush_bullet()
            current_category = line.removeprefix("### ").strip()
            current.bullets.setdefault(current_category, [])
            continue
        if line.lstrip().startswith("- "):
            _flush_bullet()
            bullet = [line]
            continue
        if bullet is not None:
            # Continuation lines of the current bullet (indented prose).
            if line.startswith(" ") or not line.strip():
                bullet.append(line)
            else:
                _flush_bullet()
        if bullet is None and not line.startswith("#"):
            if current_category is None:
                current.intro.append(line)
            # prose inside a category but outside a bullet is kept verbatim in
            # the bullet block so it cannot be lost
            elif line.strip():
                current.bullets.setdefault(current_category, []).append(line)
    _flush_bullet()
    return sections


def _prerelease_version(heading: str) -> str | None:
    """Return the base version if the heading is a prerelease section."""
    inner = heading.removeprefix("## ").strip()
    if not (inner.startswith("[") and "]" in inner):
        return None
    label = inner[1 : inner.index("]")]
    if label in {"Unreleased", ""}:
        return None
    # Accepts both spellings the repositories use: 0.18.0-beta.1 (SemVer)
    # and 0.18.0b2 / 0.18.0rc1 (PEP 440).
    match = re.match(r"(\d+\.\d+\.\d+)", label)
    if match is None:
        return None
    base = match.group(1)
    if base == label:
        return None  # a plain stable heading
    return base


def fold(text: str, version: str, date: str) -> str:
    """Return the changelog with the version's prerelease sections folded."""
    sections = _parse_sections(text)
    pre = [(heading, section) for heading, section in sections if _prerelease_version(heading) == version]
    if any(
        heading.strip() == f"## [{version}]" or heading.strip().startswith(f"## [{version}] ")
        for heading, _ in sections
    ):
        raise SystemExit(f"stable section for {version} already exists; nothing to fold")
    if not pre:
        raise SystemExit(f"no prerelease sections found for {version}")

    # File is newest-first; read the prereleases oldest-first so later betas
    # land after the wording they supersede.
    pre.reverse()

    intros: list[str] = []
    bullets: dict[str, list[str]] = {}
    for heading, section in pre:
        label = heading[heading.index("[") + 1 : heading.index("]")]
        intro = "\n".join(section.intro).strip()
        if intro:
            intros.append(f"**From `[{label}]`:** {intro}")
        for category, items in section.bullets.items():
            merged = bullets.setdefault(category, [])
            for item in items:
                if item not in merged:
                    merged.append(item)

    lines: list[str] = [f"## [{version}] - {date}", "", EDITORIAL_MARKER, ""]
    for intro in intros:
        lines.extend([intro, ""])
    ordered = [(category, bullets[category]) for category in CATEGORY_ORDER if bullets.get(category)]
    ordered += sorted(
        (category, items) for category, items in bullets.items() if category not in CATEGORY_ORDER and items
    )
    for category, items in ordered:
        lines.extend([f"### {category}", ""])
        lines.extend(items)
        lines.append("")

    replacement = "\n".join(lines).rstrip() + "\n"

    # Replace the span from the newest prerelease heading (first in the
    # newest-first file) to just before the section that follows the oldest
    # prerelease (pre is chronological after the reverse, so pre[0] is the
    # oldest and appears last in the file).
    first_idx = min(text.index(heading) for heading, _ in pre)
    last_heading, _ = pre[0]
    last_idx = text.index(last_heading)
    after = text.index("## [", last_idx + 1) if "## [" in text[last_idx + 1 :] else len(text)
    return text[:first_idx] + replacement + "\n" + text[after:]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True, help="stable version to fold into, e.g. 0.18.0")
    parser.add_argument("--date", default="UNRELEASED DRAFT", help="release date, or the draft marker")
    args = parser.parse_args(argv)

    text = CHANGELOG.read_text(encoding="utf-8")
    updated = fold(text, args.version, args.date)
    CHANGELOG.write_text(updated, encoding="utf-8", newline="\n")
    print(f"folded prerelease sections into ## [{args.version}] ({args.date})")
    print("rework the prose before tagging; the structural test only checks the fold")
    return 0


if __name__ == "__main__":
    sys.exit(main())
