"""Parity and freshness guards for the English and German register references.

``scripts/generate_modbus_register_reference.py`` regenerates both the English
wiki page (``docs/wiki/Modbus-Register.md``) and its German mirror
(``docs/wiki/de/Modbus-Register.md``) from the pinned ``idm-heatpump-api``
package, including pre-release pins such as ``2.16.0b2``. These tests enforce
that both committed catalogs match the generator output and remain row-for-row
equivalent after normalizing the German column vocabulary.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from scripts import generate_modbus_register_reference as generator

ROOT = Path(__file__).resolve().parents[1]
EN_PAGE = ROOT / "docs" / "wiki" / "Modbus-Register.md"
DE_PAGE = ROOT / "docs" / "wiki" / "de" / "Modbus-Register.md"
BLOCK = re.compile(
    r"<!-- BEGIN GENERATED REGISTER REFERENCE -->.*?<!-- END GENERATED REGISTER REFERENCE -->",
    re.DOTALL,
)

# German renderings of the English column vocabulary. The generator emits
# English; the German mirror translates these exact terms. Extend this map
# when the generator learns a new vocabulary word, never to paper over a
# diverging register row.
TRANSLATIONS = (
    ("Address(es)", "Adresse(n)"),
    ("Description (DE)", "Beschreibung (DE)"),
    ("Register name", "Registername"),
    ("Type", "Typ"),
    ("Unit", "Einheit"),
    ("Access", "Zugriff"),
    ("Note", "Anmerkung"),
    ("Binary", "Binär"),
    ("· cyclic", "· zyklisch"),
    ("· write-only", "· nur schreibend"),
    ("disabled by default", "standardmäßig deaktiviert"),
    ("PV supplement", "PV-Supplement"),
)


def _table_rows(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    match = BLOCK.search(text)
    assert match is not None, f"{path} has no generated register-reference block"
    return [line for line in match.group(0).splitlines() if line.startswith("| ")]


def _normalized(row: str) -> str:
    for english, german in TRANSLATIONS:
        row = row.replace(english, german)
    return row


def test_german_register_reference_matches_english() -> None:
    english = _table_rows(EN_PAGE)
    german = _table_rows(DE_PAGE)

    assert len(english) == len(german), (
        f"generated register tables diverge in length: {len(english)} English rows "
        f"vs {len(german)} German rows — regenerate the English reference and carry "
        "the change into the German mirror in the same pull request"
    )

    diverging = [(index, row, german[index]) for index, row in enumerate(english) if _normalized(row) != german[index]]
    assert not diverging, (
        "register rows that exist in English but diverge in the German mirror "
        "(after translation normalization): "
        + "; ".join(f"row {i}: EN {en!r} vs DE {de!r}" for i, en, de in diverging)
        + " — carry the regenerated English table into the German mirror"
    )


def test_committed_register_references_match_generator_output() -> None:
    assert generator.main(["--check"]) == 0


@pytest.mark.parametrize(
    ("requirement", "expected"),
    [
        ("idm-heatpump-api[web]==2.16.0", "2.16.0"),
        ("idm-heatpump-api[web]==2.16.0a1", "2.16.0a1"),
        ("idm-heatpump-api[web]==2.16.0b2", "2.16.0b2"),
        ("idm-heatpump-api==2.16.0rc3", "2.16.0rc3"),
    ],
)
def test_pinned_api_version_accepts_stable_and_prerelease_pins(
    tmp_path: Path, requirement: str, expected: str
) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"requirements": [requirement]}), encoding="utf-8")

    assert generator._pinned_api_version(manifest) == expected


def test_pinned_api_version_rejects_unpinned_requirement(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"requirements": ["idm-heatpump-api[web]>=2.16.0"]}), encoding="utf-8")

    with pytest.raises(RuntimeError, match="must be pinned exactly"):
        generator._pinned_api_version(manifest)
