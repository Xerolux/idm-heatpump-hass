"""Tests for the generated entity metadata catalog."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "generate_entity_metadata_catalog.py"
CATALOG = ROOT / "docs" / "dev" / "entity-metadata-catalog.md"


def test_entity_metadata_catalog_is_up_to_date() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--check"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout


def test_entity_metadata_catalog_documents_expert_profile() -> None:
    catalog = CATALOG.read_text(encoding="utf-8")

    assert "Generated expert default profile" in catalog
    assert "`booster_`" in catalog
    assert "`cascade_`" in catalog
    assert "`_relay`" in catalog


def test_entity_registry_migration_contract_documents_user_activation_safety() -> None:
    contract = (ROOT / "docs" / "dev" / "entity-registry-migration-contract.md").read_text(encoding="utf-8")

    assert "Unique IDs bleiben stabil" in contract
    assert "Default-Profile sind nur Defaults" in contract
    assert "Keine nachträgliche Zwangsdeaktivierung" in contract
    assert "Keine nachträgliche Zwangsaktivierung" in contract


def test_field_diagnostics_template_is_read_only_and_privacy_safe() -> None:
    template = (ROOT / ".github" / "ISSUE_TEMPLATE" / "field_diagnostics.md").read_text(encoding="utf-8")
    guide = (ROOT / "docs" / "dev" / "field-diagnostics-guide.md").read_text(encoding="utf-8")

    assert "I only collected read-only data" in template
    assert "I did not run direct `write_register` tests" in template
    assert "Redact host names" in template
    assert "Keine Live-Schreibtests" in guide
    assert "Datenschutz" in guide


def test_modbus_transport_issue_template_keeps_runtime_guardrails() -> None:
    template = (ROOT / ".github" / "ISSUE_TEMPLATE" / "modbus_transport_modernization.md").read_text(encoding="utf-8")

    assert "modbus-connection==4.0.0a3" in template
    assert "tmodbus==0.5.0" in template
    assert "supports_shared_connection=False" in template
    assert "Existing config entries and entity Unique IDs need no user migration" in template
    assert "IdmCoordinator.async_write_register" in template


def test_open_work_audit_separates_local_work_from_external_blockers() -> None:
    todo = (ROOT / "docs" / "IMPLEMENTATION_TODO.md").read_text(encoding="utf-8")
    audit = (ROOT / "docs" / "dev" / "open-work-audit.md").read_text(encoding="utf-8")

    assert "docs/dev/open-work-audit.md" in todo
    assert "Lokal erledigt" in audit
    assert "Extern blockiert" in audit
    assert "nicht veröffentlichen, nicht schätzen und keine Schreibpfade" in audit
    assert "stabilen Vertrag für Custom\nIntegrations" in audit
    assert "supports_shared_connection=False" in audit
