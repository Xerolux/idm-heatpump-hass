"""Translation-key parity guard across strings.json, en.json and de.json.

Home Assistant loads a custom integration's runtime translations from
``translations/<language>.json`` only — ``strings.json`` is the source
template, not a runtime fallback. A key that exists in ``strings.json`` but
not in ``translations/en.json`` (or in ``en.json`` but not ``de.json``) makes
the UI fall back to raw field keys in one or both languages. That happened
with the energy-manager option fields (labels and descriptions existed in
``strings.json`` and in the guided-flow sections, but the plain options step
carried them in neither translation file), and the #478 flow-field guard only
validates ``strings.json``, so the gap stayed invisible.

Rules enforced here:

1. every leaf key in ``strings.json`` exists in ``translations/en.json``
   with an identical value (English source of truth);
2. every leaf key in ``translations/en.json`` exists in ``translations/de.json``
   (no English fallback in the German UI) and is non-empty;
3. ``translations/de.json`` carries no keys ``en.json`` lacks.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "idm_heatpump"
STRINGS = json.loads((COMPONENT / "strings.json").read_text(encoding="utf-8"))
EN = json.loads((COMPONENT / "translations" / "en.json").read_text(encoding="utf-8"))
DE = json.loads((COMPONENT / "translations" / "de.json").read_text(encoding="utf-8"))


def _flatten(node: object, prefix: str = "") -> dict[str, str]:
    flat: dict[str, str] = {}
    if isinstance(node, dict):
        for key, value in node.items():
            flat.update(_flatten(value, f"{prefix}.{key}" if prefix else key))
    else:
        assert isinstance(node, str)
        flat[prefix] = node
    return flat


STRINGS_FLAT = _flatten(STRINGS)
EN_FLAT = _flatten(EN)
DE_FLAT = _flatten(DE)


def test_strings_json_is_translated_in_english() -> None:
    missing = sorted(set(STRINGS_FLAT) - set(EN_FLAT))
    assert not missing, (
        "translations/en.json is missing keys that strings.json declares "
        "(the English UI would show raw field keys): " + ", ".join(missing)
    )
    diverging = [k for k in STRINGS_FLAT if EN_FLAT.get(k) != STRINGS_FLAT[k]]
    assert not diverging, (
        "translations/en.json values must equal strings.json (English source "
        "of truth); diverging: " + ", ".join(diverging)
    )


def test_english_is_fully_translated_to_german() -> None:
    missing = sorted(set(EN_FLAT) - set(DE_FLAT))
    assert not missing, (
        "translations/de.json is missing keys that translations/en.json has "
        "(the German UI would fall back to English): " + ", ".join(missing)
    )
    empty = sorted(k for k in EN_FLAT if not DE_FLAT.get(k, "").strip())
    assert not empty, "empty German translations: " + ", ".join(empty)


def test_german_has_no_orphan_keys() -> None:
    orphans = sorted(set(DE_FLAT) - set(EN_FLAT))
    assert not orphans, "translations/de.json carries keys the English file lacks (dead or renamed keys): " + ", ".join(
        orphans
    )
