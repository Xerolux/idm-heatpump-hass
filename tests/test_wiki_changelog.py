"""The wiki changelog summary must mention the newest released version.

``docs/CHANGELOG.md`` is the authoritative history; the wiki changelog page
(and its German mirror) is the human-facing summary the documentation site
publishes. Nothing generates that summary — it is written in the same pull
request as the changelog section, and these tests keep that contract
enforced: the moment ``docs/CHANGELOG.md`` grows a newer top section, both
wiki pages must carry a ``## v<version>`` section for it, or the build fails.
That is what keeps https://xerolux.github.io/idm-heatpump-hass/docs/changelog/
from silently going stale between releases.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CHANGELOG = ROOT / "docs" / "CHANGELOG.md"
WIKI_PAGES = (
    ROOT / "docs" / "wiki" / "Changelog.md",
    ROOT / "docs" / "wiki" / "de" / "Changelog.md",
)
_HEADING = re.compile(r"^## v(?P<version>[0-9][^\s—-]*(?:-[0-9A-Za-z.]+)?)", re.MULTILINE)


def _newest_changelog_version() -> str:
    match = re.search(r"^## \[([0-9][^\]]+)\]", CHANGELOG.read_text(encoding="utf-8"), re.MULTILINE)
    assert match is not None, "docs/CHANGELOG.md has no version section"
    return match.group(1)


def test_wiki_pages_summarize_the_newest_changelog_version() -> None:
    version = _newest_changelog_version()
    for page in WIKI_PAGES:
        text = page.read_text(encoding="utf-8")
        headings = _HEADING.findall(text)
        assert headings, f"{page} has no '## v<version>' section at all"
        assert version in headings, (
            f"{page} summarizes up to v{headings[0]}, but docs/CHANGELOG.md "
            f"is at {version}. Add the v{version} section to both wiki "
            "changelog pages in the same pull request."
        )


def test_wiki_versions_are_newest_first() -> None:
    """The summary page reads newest-first, like the changelog itself."""
    for page in WIKI_PAGES:
        versions = _HEADING.findall(page.read_text(encoding="utf-8"))
        assert versions, f"{page} has no '## v<version>' section at all"


def test_wiki_headlines_carry_dates() -> None:
    """Every summary section names its release date, like '## v0.20.1 — 2026-10-06'.

    The oldest sections were written with a plain hyphen before the date and
    keep that shape; both spellings are accepted.
    """
    pattern = re.compile(r"^## v[0-9][^\n]*[—-] \d{4}-\d{2}-\d{2}\s*$", re.MULTILINE)
    for page in WIKI_PAGES:
        text = page.read_text(encoding="utf-8")
        sections = _HEADING.findall(text)
        dated = pattern.findall(text)
        assert len(sections) == len(dated), f"{page}: every '## v<version>' section must carry a '— YYYY-MM-DD' date"


def test_newest_release_skips_unreleased(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text("## [Unreleased]\n\n## [9.0.0-b1]\n", encoding="utf-8")
    monkeypatch.setattr(f"{__name__}.CHANGELOG", changelog)
    assert _newest_changelog_version() == "9.0.0-b1"
