"""Release-notes style contract for the changelog (issue #575).

The changelog section of a version is the release notes users read in the
HACS/Marketplace update dialog. Since the 0.23.0 stable cut the contract is
mechanical: every section that is not yet released history opens with the
``⚠️ Upgrade notes`` block, uses only the emoji headers defined in
``docs/CONTRIBUTING.md`` and keeps bullets at about 60 words. Sections
already released keep the shape they were published with — the rule applies
to the ``Unreleased`` section and to every version newer than the baseline
only, so a fold or editorial pass never rewrites history.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from packaging.version import Version

ROOT = Path(__file__).resolve().parents[1]
CHANGELOG = ROOT / "docs" / "CHANGELOG.md"
CONTRIBUTING = ROOT / "docs" / "CONTRIBUTING.md"

#: The last version published before the style rule landed. Its section and
#: every older one stay exactly as released.
STYLE_BASELINE = Version("0.23.0")

#: Longest allowed bullet, counted in whitespace-separated words.
MAX_BULLET_WORDS = 60

#: Most bullets allowed in the upgrade-notes block.
MAX_UPGRADE_BULLETS = 5

UPGRADE_HEADER = "⚠️ Upgrade notes"

_HEADING_RE = re.compile(r"^## \[([^\]]+)\]", re.MULTILINE)


@dataclass
class _Category:
    """One ``###`` block: its header text and the bullets below it."""

    name: str
    bullets: list[str] = field(default_factory=list)


@dataclass
class _Section:
    """One ``## [version]`` section with its ``###`` blocks in file order."""

    label: str
    categories: list[_Category] = field(default_factory=list)

    @property
    def bullets(self) -> list[str]:
        return [bullet for category in self.categories for bullet in category.bullets]


def _parse_section(label: str, body: str) -> _Section:
    section = _Section(label=label)
    category: _Category | None = None
    bullet: list[str] | None = None

    def _flush_bullet() -> None:
        nonlocal bullet
        if bullet is not None and category is not None:
            joined = " ".join(line.strip() for line in bullet).strip()
            category.bullets.append(joined.removeprefix("- "))
        bullet = None

    for line in body.splitlines():
        if line.startswith("### "):
            _flush_bullet()
            category = _Category(name=line.removeprefix("### ").strip())
            section.categories.append(category)
        elif line.lstrip().startswith("- "):
            _flush_bullet()
            if category is None:
                category = _Category(name="")
                section.categories.append(category)
            bullet = [line]
        elif bullet is not None and (line.startswith(" ") or not line.strip()):
            bullet.append(line)
        else:
            _flush_bullet()
    _flush_bullet()
    return section


def _parse_sections(text: str) -> list[_Section]:
    matches = list(_HEADING_RE.finditer(text))
    sections: list[_Section] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        # Start after the heading's own line: "## [x.y.z] - date" would
        # otherwise leak the date in as a bullet.
        start = text.find("\n", match.end()) + 1
        sections.append(_parse_section(match.group(1), text[start:end]))
    return sections


def _version(label: str) -> Version | None:
    """Parse a heading label, returning None for Unreleased/malformed ones."""
    try:
        return Version(label)
    except Exception:  # noqa: BLE001 - heading shape is guarded by the consolidation tests
        return None


def _style_applies(label: str) -> bool:
    if label == "Unreleased":
        return True
    version = _version(label)
    return version is not None and version > STYLE_BASELINE


def _checked_sections() -> list[_Section]:
    """The sections the style rule governs: the head of the file only.

    A fossil ``## [Unreleased]`` heading sits deep inside the 0.8.0-era
    history of the changelog; everything from the first released stable
    heading down is history and keeps the shape it was published with.
    """
    checked: list[_Section] = []
    for section in _parse_sections(CHANGELOG.read_text(encoding="utf-8")):
        if _style_applies(section.label):
            checked.append(section)
        version = _version(section.label)
        if version is not None and not version.is_prerelease:
            break
    return checked


def _allowed_headers() -> list[str]:
    """The closed header set, derived from CONTRIBUTING.md so doc and test cannot drift."""
    style = CONTRIBUTING.read_text(encoding="utf-8").partition("## Release Notes Style")[2].partition("\n## ")[0]
    return sorted({header for header in re.findall(r"`### ([^`]+)`", style)})


def test_contribution_style_defines_the_closed_header_set() -> None:
    headers = _allowed_headers()

    assert headers == sorted({UPGRADE_HEADER, "✨ New", "🐛 Bugfixes", "💼 Maintenance", "❤️ Thanks"})


def test_section_headers_come_from_the_contribution_style_set() -> None:
    allowed = set(_allowed_headers())
    problems = [
        f"{section.label}: '{category.name}'"
        for section in _checked_sections()
        for category in section.categories
        if category.name and category.name not in allowed
    ]

    assert not problems, (
        f"changelog headers outside the CONTRIBUTING.md set: {problems}; "
        f"keep to {sorted(allowed)} and fold documentation detail into maintenance"
    )


def test_bullets_stay_within_the_word_budget() -> None:
    over: list[str] = []
    for section in _checked_sections():
        for category in section.categories:
            for bullet in category.bullets:
                words = len(bullet.split())
                if words > MAX_BULLET_WORDS:
                    lead = " ".join(bullet.split()[:6])
                    over.append(f"{section.label} ({words} words): {lead}…")

    assert not over, (
        f"bullets beyond {MAX_BULLET_WORDS} words: {over}; lead with a bold phrase, "
        "explain in one or two sentences and link the issue instead of restating it"
    )


def test_upgrade_notes_block_leads_every_section() -> None:
    problems: list[str] = []
    for section in _checked_sections():
        if not section.bullets:
            continue  # an empty section has nothing to upgrade yet
        blocks = [category for category in section.categories if category.name == UPGRADE_HEADER]
        if len(blocks) != 1:
            problems.append(f"{section.label}: {len(blocks)} upgrade blocks, expected exactly one")
            continue
        if section.categories[0].name != UPGRADE_HEADER:
            problems.append(f"{section.label}: the upgrade block is not the first section heading")
        if not 1 <= len(blocks[0].bullets) <= MAX_UPGRADE_BULLETS:
            problems.append(
                f"{section.label}: {len(blocks[0].bullets)} upgrade bullets, expected 1..{MAX_UPGRADE_BULLETS}"
            )

    assert not problems, (
        f"upgrade-notes block problems: {problems}; state resets, fresh counters, "
        "options worth enabling and rollback safety — five bullets or fewer, a lone "
        "rollback bullet is enough"
    )


#: A changelog in the post-baseline style plus a released section that breaks
#: every rule and must not be flagged: released sections keep the shape they
#: were published with.
SAMPLE = (
    """# Changelog

## [Unreleased]

### ⚠️ Upgrade notes

- Rollback to 0.24.0 keeps working.

### ✨ New

- Short feature bullet.

## [0.24.0-b1] - 2026-11-01

### ⚠️ Upgrade notes

- Nothing resets; rollback to 0.23.0 keeps working.

### 🐛 Bugfixes

- Bug fix bullet.

## [0.23.0] - 2026-10-21

### Added

- """
    + " ".join(["published"] * 61)
    + """

### Notes

- Released section prose stays as published even when the headers and bullet
  lengths predate the style rule, because history is never rewritten.
"""
)


def _use_sample(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, text: str) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(text, encoding="utf-8")
    monkeypatch.setattr(f"{__name__}.CHANGELOG", changelog)


def test_released_sections_keep_their_published_shape(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_sample(monkeypatch, tmp_path, SAMPLE)

    test_section_headers_come_from_the_contribution_style_set()
    test_bullets_stay_within_the_word_budget()
    test_upgrade_notes_block_leads_every_section()


def test_new_sections_are_word_checked(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_sample(
        monkeypatch,
        tmp_path,
        SAMPLE.replace("- Short feature bullet.", "- " + " ".join(["word"] * 61)),
    )

    with pytest.raises(AssertionError, match="61 words"):
        test_bullets_stay_within_the_word_budget()


def test_new_sections_reject_headers_outside_the_set(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_sample(monkeypatch, tmp_path, SAMPLE.replace("### ✨ New", "### Added"))

    with pytest.raises(AssertionError, match="'Added'"):
        test_section_headers_come_from_the_contribution_style_set()


def test_new_sections_need_the_upgrade_block_first(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    missing = SAMPLE.replace("### ⚠️ Upgrade notes\n\n- Rollback to 0.24.0 keeps working.\n\n", "")
    _use_sample(monkeypatch, tmp_path, missing)

    with pytest.raises(AssertionError, match="0 upgrade blocks"):
        test_upgrade_notes_block_leads_every_section()

    late = SAMPLE.replace(
        "### ⚠️ Upgrade notes\n\n- Nothing resets; rollback to 0.23.0 keeps working.\n\n"
        "### 🐛 Bugfixes\n\n- Bug fix bullet.",
        "### 🐛 Bugfixes\n\n- Bug fix bullet.\n\n"
        "### ⚠️ Upgrade notes\n\n- Nothing resets; rollback to 0.23.0 keeps working.",
    )
    _use_sample(monkeypatch, tmp_path, late)

    with pytest.raises(AssertionError, match="not the first section heading"):
        test_upgrade_notes_block_leads_every_section()
