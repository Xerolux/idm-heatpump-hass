"""The stability page must carry a release decision for the newest stable cut.

``docs/wiki/Stability-and-Release-Readiness.md`` (and its German mirror) is
the hand-written record of what was verified before a stable tag was cut —
deliberately stricter than the changelog. Nothing generates it; like the
wiki changelog summary, it is written in the release pull request, and these
tests keep that contract enforced: the moment ``docs/CHANGELOG.md`` names a
newer stable version, both stability pages must open its release decision
(``## <version> release decision`` / ``## Release-Entscheidung zu <version>``),
or the build fails.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHANGELOG = ROOT / "docs" / "CHANGELOG.md"
STABILITY_PAGES = {
    "en": (
        ROOT / "docs" / "wiki" / "Stability-and-Release-Readiness.md",
        "## {version} release decision",
    ),
    "de": (
        ROOT / "docs" / "wiki" / "de" / "Stability-and-Release-Readiness.md",
        "## Release-Entscheidung zu {version}",
    ),
}


def _newest_stable_version() -> str:
    """Return the newest changelog version without a prerelease suffix."""
    for match in re.finditer(r"^## \[([^\]]+)\]", CHANGELOG.read_text(encoding="utf-8"), re.MULTILINE):
        version = match.group(1)
        if "-" not in version:
            return version
    raise AssertionError("docs/CHANGELOG.md has no stable (non-prerelease) section")


def test_stability_pages_decide_the_newest_stable_release() -> None:
    version = _newest_stable_version()
    for language, (page, template) in STABILITY_PAGES.items():
        text = page.read_text(encoding="utf-8")
        expected = template.format(version=version)
        assert expected in text, (
            f"{page} does not carry '{expected}'. Record the {language.upper()} release "
            f"decision for {version} in the same pull request that cuts the release."
        )


def test_stability_decision_is_not_left_below_earlier_heading() -> None:
    """The newest decision owns its own section, above 'Earlier release decisions'."""
    version = _newest_stable_version()
    for page, template in STABILITY_PAGES.values():
        text = page.read_text(encoding="utf-8")
        decision = text.find(template.format(version=version))
        earlier = (
            text.find("## Earlier release decisions")
            if "Earlier release decisions" in text
            else text.find("## Frühere Release-Entscheidungen")
        )
        assert decision != -1 and earlier != -1
        assert decision < earlier, f"{page}: the {version} decision belongs above the earlier-decisions section"
