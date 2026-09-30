#!/usr/bin/env python3
"""Check or synchronize current documentation metadata against the source tree.

This is deliberately offline: the manifest owns this checkout's runtime pins,
not the newest PyPI version. Published release manifests, changelogs and release
evidence remain immutable history. Older installations must consult their tag.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

if __package__:
    from . import check_dependency_pins as pins
else:
    import check_dependency_pins as pins

ROOT = Path(__file__).resolve().parents[1]
VERSION = r"[0-9][0-9A-Za-z.+-]*"

# Current claims, with their surrounding prose. Historical "New in" sections
# are intentionally absent. A missing claim is an error, not a silent skip.
SOURCE_VERSION_PATTERNS = {
    "AGENTS.md": r"(?<=\*\*Current Version\*\*: `)" + VERSION + r"(?=`)",
    "docs/wiki/Home.md": r"(?<=\| \*\*Documentation version\*\* \| `)" + VERSION + r"(?=`)",
    "docs/wiki/de/Home.md": r"(?<=\| \*\*Dokumentationsversion\*\* \| Quellstand `)" + VERSION + r"(?=`)",
    "docs/wiki/Stability-and-Release-Readiness.md": r"(?<=Source-tree integration `)" + VERSION + r"(?=` and)",
    "docs/wiki/de/Stability-and-Release-Readiness.md": r"(?<=Integration im Quellstand `)" + VERSION + r"(?=` und)",
}


def current_documents(root: Path) -> list[str]:
    """Include registered pin documents and future current metadata claims."""
    documents = {p for p in pins.PIN_DOCUMENTS if p.endswith(".md")}
    documents.update(SOURCE_VERSION_PATTERNS)
    return sorted(documents)


def synchronize(root: Path, *, update: bool = False) -> list[str]:
    """Return precise drift findings; --update rewrites only current claims."""
    manifest = json.loads((root / "custom_components/idm_heatpump/manifest.json").read_text(encoding="utf-8"))
    requirements = {req.name: req for req in map(pins.parse_requirement, manifest["requirements"])}
    findings = []
    for relative in current_documents(root):
        path = root / relative
        if not path.exists():
            findings.append(f"{relative}: missing current documentation")
            continue
        original = text = path.read_text(encoding="utf-8")
        # Preserve history even when it mentions the same package as a current
        # requirement elsewhere in this file. Restore it after substitutions.
        history: list[str] = []

        def protect(match: re.Match[str], history: list[str] = history) -> str:
            history.append(match[0])
            return f"DOCUMENTATION_HISTORY_{len(history) - 1}_END"

        for pattern in pins.HISTORY_STATEMENTS.get(relative, ()):
            text = re.sub(pattern, protect, text)
        for name, requirement in requirements.items():
            if requirement.pinned_version is None:
                continue
            pattern = rf"(?<![\w-]){re.escape(name)}(?:\[[^\]\n]+\])?\s*==\s*{VERSION}"

            def check_pin(match: re.Match[str], expected: str = requirement.raw, relative: str = relative) -> str:
                if match[0] != expected:
                    findings.append(f"{relative}: {match[0]} must be {expected}")
                return expected if update else match[0]

            text = re.sub(pattern, check_pin, text)
        for name, pattern in pins.BARE_VERSION_STATEMENTS.get(relative, ()):
            expected = requirements[name].pinned_version
            if expected is None:
                continue

            def check_bare(
                match: re.Match[str], expected: str = expected, relative: str = relative, name: str = name
            ) -> str:
                if match[0] != expected:
                    findings.append(f"{relative}: {name} {match[0]} must be {expected}")
                return expected if update else match[0]

            text = re.sub(pattern.replace("{version}", VERSION), check_bare, text)
        pattern = SOURCE_VERSION_PATTERNS.get(relative)
        if pattern is not None:
            matches = list(re.finditer(pattern, text))
            if len(matches) != 1:
                findings.append(f"{relative}: expected exactly one current source-version claim")
            elif matches[0][0] != manifest["version"]:
                findings.append(f"{relative}: source version {matches[0][0]} must be {manifest['version']}")
                if update:
                    text = re.sub(pattern, manifest["version"], text)
        for index, statement in enumerate(history):
            text = text.replace(f"DOCUMENTATION_HISTORY_{index}_END", statement)
        if update and text != original:
            path.write_text(text, encoding="utf-8")
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--update", action="store_true", help="synchronize current claims without changing history")
    args = parser.parse_args(argv)
    findings = synchronize(ROOT, update=args.update)
    if args.update:
        findings = synchronize(ROOT)
    for finding in findings:
        print(finding)
    if not findings:
        print("Current documentation versions match the manifest.")
    return int(bool(findings))


if __name__ == "__main__":
    raise SystemExit(main())
