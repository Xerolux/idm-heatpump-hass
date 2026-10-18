"""Parity guard between the English and German generated register reference.

``scripts/generate_modbus_register_reference.py`` regenerates only the English
wiki page. The German mirror (``docs/wiki/de/Modbus-Register.md``) is carried
by hand in the same pull request, per the repository's mirror rule — and that
carrying was missed once (register 1072 was re-typed UCHAR → FLOAT for
discussion #516 and only the English row changed). This test normalizes the
known German column vocabulary and then requires the two generated tables to
be row-for-row identical, so an English regeneration without its German
mirror fails the build instead of silently diverging.
"""

from __future__ import annotations

import re
from pathlib import Path

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
