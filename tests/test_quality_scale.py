"""Drift guard between quality_scale.yaml and the official quality scale.

Home Assistant grades only its own core integrations, so the quality_scale.yaml
of this custom integration is a self-assessment — but it must still track the
real scale. The rule sets below are pinned from the official rules page, which
follows hassfest's ``script/hassfest/quality_scale.py``:

https://developers.home-assistant.io/docs/core/integration-quality-scale/
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCALE = ROOT / "custom_components" / "idm_heatpump" / "quality_scale.yaml"
MANIFEST = ROOT / "custom_components" / "idm_heatpump" / "manifest.json"

BRONZE = frozenset(
    {
        "action-setup",
        "appropriate-polling",
        "brands",
        "common-modules",
        "config-flow",
        "config-flow-test-coverage",
        "dependency-transparency",
        "docs-actions",
        "docs-conditions",
        "docs-high-level-description",
        "docs-installation-instructions",
        "docs-removal-instructions",
        "docs-triggers",
        "entity-event-setup",
        "entity-unique-id",
        "has-entity-name",
        "runtime-data",
        "test-before-configure",
        "test-before-setup",
        "unique-config-entry",
    }
)
SILVER = frozenset(
    {
        "action-exceptions",
        "config-entry-unloading",
        "docs-configuration-parameters",
        "docs-installation-parameters",
        "entity-unavailable",
        "integration-owner",
        "log-when-unavailable",
        "parallel-updates",
        "reauthentication-flow",
        "test-coverage",
    }
)
GOLD = frozenset(
    {
        "devices",
        "diagnostics",
        "discovery",
        "discovery-update-info",
        "docs-data-update",
        "docs-examples",
        "docs-known-limitations",
        "docs-supported-devices",
        "docs-supported-functions",
        "docs-troubleshooting",
        "docs-use-cases",
        "dynamic-devices",
        "entity-category",
        "entity-device-class",
        "entity-disabled-by-default",
        "entity-translations",
        "exception-translations",
        "icon-translations",
        "reconfiguration-flow",
        "repair-issues",
        "stale-devices",
    }
)
PLATINUM = frozenset({"async-dependency", "inject-websession", "strict-typing"})

#: Tier order from the scale: a tier needs every rule of itself and below.
TIERS: tuple[tuple[str, frozenset[str]], ...] = (
    ("bronze", BRONZE),
    ("silver", SILVER),
    ("gold", GOLD),
    ("platinum", PLATINUM),
)
ALL_RULES = BRONZE | SILVER | GOLD | PLATINUM

#: Exemptions that are properties of the integration, not open work: a local
#: Modbus TCP device has no discovery protocol, no credentials to refresh and
#: no integration-specific conditions or triggers to document.
EXPECTED_EXEMPT = frozenset(
    {
        "discovery",
        "discovery-update-info",
        "docs-conditions",
        "docs-triggers",
        "reauthentication-flow",
    }
)

#: The statuses hassfest knows for a rule; "todo" would be honest open work.
VALID_STATUSES = frozenset({"done", "todo", "exempt"})

_BANNER_RE = re.compile(r"^  # ── ([A-Z]+) ", re.MULTILINE)
_KEY_RE = re.compile(r"^  ([a-z][a-z-]*):$", re.MULTILINE)
_FULFILLED_STATUSES = frozenset({"done", "exempt"})


def _rules() -> dict[str, dict[str, str]]:
    return yaml.safe_load(SCALE.read_text(encoding="utf-8"))["rules"]


def _banner_sections() -> dict[str, list[set[str]]]:
    """Rules found under each tier banner in the file, in file order."""
    text = SCALE.read_text(encoding="utf-8")
    matches = list(_BANNER_RE.finditer(text))
    sections: dict[str, list[set[str]]] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections.setdefault(match.group(1).lower(), []).append(set(_KEY_RE.findall(text[match.end() : end])))
    return sections


def test_pinned_tiers_match_the_official_scale_shape() -> None:
    """Guard the guard: the pinned sets are the official 20/10/21/3 split."""
    every_rule = [rule for _, tier_rules in TIERS for rule in tier_rules]

    assert [(name, len(rules)) for name, rules in TIERS] == [
        ("bronze", 20),
        ("silver", 10),
        ("gold", 21),
        ("platinum", 3),
    ]
    assert len(every_rule) == len(set(every_rule)) == 54, "pinned tiers overlap or lost a rule"


def test_file_lists_every_official_rule_exactly_once() -> None:
    keys = _KEY_RE.findall(SCALE.read_text(encoding="utf-8"))

    assert len(keys) == len(set(keys)), "duplicate rule keys would silently shadow each other in YAML"
    assert set(keys) == ALL_RULES, (
        f"quality_scale.yaml lost rules {sorted(ALL_RULES - set(keys))} or grew unknown rules "
        f"{sorted(set(keys) - ALL_RULES)}; align it with the official scale and update the pinned sets here"
    )
    assert set(_rules()) == ALL_RULES


def test_tier_banners_group_the_official_rules() -> None:
    """A rule placed under the wrong banner reads as fulfilled too early."""
    sections = _banner_sections()

    for tier, tier_rules in TIERS:
        occurrences = sections.get(tier, [])
        assert len(occurrences) == 1, f"expected exactly one '{tier}' banner, found {len(occurrences)}"
        assert occurrences[0] == tier_rules, (
            f"the '{tier}' banner holds {sorted(occurrences[0] ^ tier_rules)} besides its own rules"
        )


def test_every_rule_has_a_valid_status_and_a_written_reason() -> None:
    problems = []
    for name, rule in _rules().items():
        if rule.get("status") not in VALID_STATUSES:
            problems.append(f"{name}: status {rule.get('status')!r} is not one of {sorted(VALID_STATUSES)}")
        reason = " ".join(str(rule.get("comment", "")).split())
        if len(reason) < 40:
            problems.append(f"{name}: comment is too short to be a reason ({reason!r})")

    assert not problems, problems


def test_no_rule_is_left_open() -> None:
    """The self-assessment claims completeness: done, or exempt with a reason."""
    rules = _rules()
    open_rules = {name for name, rule in rules.items() if rule["status"] == "todo"}
    invalid = {name for name, rule in rules.items() if rule["status"] not in _FULFILLED_STATUSES}
    exempt = {name for name, rule in rules.items() if rule["status"] == "exempt"}

    assert not open_rules, f"open rules: {sorted(open_rules)}"
    assert not invalid, f"rules with a non-fulfilling status: {sorted(invalid)}"
    assert exempt == EXPECTED_EXEMPT, (
        "exemptions changed: a new exemption needs a reason in quality_scale.yaml and an entry here "
        f"(new: {sorted(exempt - EXPECTED_EXEMPT)}, removed: {sorted(EXPECTED_EXEMPT - exempt)})"
    )


def test_manifest_tier_is_the_highest_fulfilled_one() -> None:
    """hassfest grades a tier as met when its rules (and below) are done/exempt."""
    rules = _rules()
    below: set[str] = set()
    expected = "none"
    for tier, tier_rules in TIERS:
        below |= tier_rules
        if all(rules.get(name, {}).get("status") in _FULFILLED_STATUSES for name in below):
            expected = tier

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["quality_scale"] == expected, (
        f"manifest claims {manifest['quality_scale']!r} while the rules only support {expected!r}"
    )
