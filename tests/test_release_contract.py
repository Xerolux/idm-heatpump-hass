"""Release contract tests for pinned runtime dependencies."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "custom_components" / "idm_heatpump" / "manifest.json"

EXPECTED_RUNTIME_REQUIREMENTS = [
    "modbus-connection==4.10.0",
    "tmodbus[async-serial]==0.6.2",
    "idm-heatpump-api[web]==2.0.0",
]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _workflow_preamble(workflow: str) -> str:
    """Return workflow-level configuration before permissions and jobs."""
    return workflow.partition("\npermissions:\n")[0]


def _release_detection_script(workflow: str) -> str:
    """Extract the release metadata shell script from the workflow."""
    step = workflow.partition("      - name: Validate tag and detect release type\n")[2].partition(
        "\n      - name: Validate prepared release metadata"
    )[0]
    script = step.partition("        run: |\n")[2]
    return "\n".join(line[10:] if line else line for line in script.splitlines())


def _detect_release(workflow: str, tmp_path: Path, tag: str, *, draft: bool = False) -> dict[str, str]:
    """Execute release metadata detection with controlled workflow inputs."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    output = tmp_path / "github-output"
    env = os.environ.copy()
    env["GITHUB_OUTPUT"] = str(output)
    env["RELEASE_DRAFT"] = str(draft).lower()
    env["RELEASE_TAG"] = tag

    subprocess.run(
        ["bash", "-euo", "pipefail", "-c", _release_detection_script(workflow)],
        check=True,
        env=env,
    )
    return dict(line.split("=", 1) for line in output.read_text(encoding="utf-8").splitlines())


def test_manifest_declares_tested_runtime_dependencies() -> None:
    manifest = json.loads(_read(MANIFEST))

    assert manifest["requirements"] == EXPECTED_RUNTIME_REQUIREMENTS


def test_ci_installs_runtime_dependencies_from_manifest() -> None:
    ci = _read(ROOT / ".github" / "workflows" / "ci.yml")
    quality = _read(ROOT / ".github" / "workflows" / "python-quality.yml")

    assert "./.github/workflows/python-quality.yml" in ci
    assert "manifest.json" in quality
    assert 'json.load(manifest_file)["requirements"]' in quality
    assert 'pip", "install", *requirements' in quality
    # The api-main leg installs the API from git in the following step, so the
    # pinned API is skipped here. Without that, the leg dies on the manifest
    # install whenever the pin points at a version that is not on PyPI yet -
    # exactly the situation during a breaking API transition.
    assert 'requirement.startswith("idm-heatpump-api")' in quality


def test_ci_tests_pinned_and_compatible_api_dependencies() -> None:
    ci = _read(ROOT / ".github" / "workflows" / "ci.yml")
    quality = _read(ROOT / ".github" / "workflows" / "python-quality.yml")

    assert "api-dependency-mode" in ci
    assert "manifest-pinned" in ci
    assert "api-main" in ci
    assert "idm-heatpump-api.git@main" in quality


def test_ci_and_release_share_complete_python_quality_workflow() -> None:
    ci = _read(ROOT / ".github" / "workflows" / "ci.yml")
    release = _read(ROOT / ".github" / "workflows" / "release.yml")
    quality = _read(ROOT / ".github" / "workflows" / "python-quality.yml")

    reusable_workflow = "uses: ./.github/workflows/python-quality.yml"
    assert reusable_workflow in ci
    assert reusable_workflow in release
    assert "workflow_call:" in quality
    assert "ruff check custom_components/idm_heatpump tests" in quality
    assert "ruff format custom_components/idm_heatpump tests --check" in quality
    assert "mypy custom_components/idm_heatpump" in quality
    assert "Smoke test production Modbus backend" in quality
    assert "from modbus_connection.tmodbus import ModbusConnection" in quality
    assert "pytest tests/" in quality
    assert "--cov=custom_components/idm_heatpump" in quality
    assert 'home-assistant-version: "2026.8.1"' in release
    assert "api-dependency-mode: manifest-pinned" in release


def test_ci_runs_once_for_source_changes_and_cancels_superseded_runs() -> None:
    ci = _workflow_preamble(_read(ROOT / ".github" / "workflows" / "ci.yml"))

    assert "  push:\n    branches: [main]" in ci
    assert "  pull_request:\n    branches: [main]" in ci
    assert '  schedule:\n    - cron: "0 0 * * *"' in ci
    assert "  workflow_dispatch:" in ci
    assert "    tags:" not in ci
    assert "  release:" not in ci
    assert "group: ci-${{ github.workflow }}-${{ github.event.pull_request.number || github.ref }}" in ci
    assert "cancel-in-progress: true" in ci


def test_release_has_one_tag_trigger_and_serializes_each_version() -> None:
    release = _workflow_preamble(_read(ROOT / ".github" / "workflows" / "release.yml"))

    assert "  push:\n    tags:\n      - 'v*'" in release
    assert release.count("      - 'v*'") == 1
    assert "  release:" not in release
    assert "  workflow_dispatch:" in release
    assert "group: release-${{ inputs.tag_name || github.ref_name }}" in release
    assert "cancel-in-progress: false" in release


def test_stable_tag_push_is_published_as_the_latest_release() -> None:
    """A stable release nobody can find as "latest" is not released.

    `inputs.make_latest` is null for a tag push and GitHub coerces null to
    false, so guarding on `inputs.make_latest != false` silently left every
    tag-pushed stable release off the latest pointer.
    """
    release_workflow = _read(ROOT / ".github" / "workflows" / "release.yml")

    assert (
        "make_latest: ${{ (inputs.make_latest || github.event_name == 'push') "
        "&& steps.version.outputs.release_type == 'stable' }}" in release_workflow
    )
    assert "inputs.make_latest != false" not in release_workflow


@pytest.mark.skipif(sys.platform == "win32", reason="Bash script tests require a POSIX environment")
def test_release_type_is_derived_only_from_validated_tag(tmp_path: Path) -> None:
    workflow = _read(ROOT / ".github" / "workflows" / "release.yml")

    expected_types = {
        "v1.2.3-beta.4": ("beta", "true"),
        "v1.2.3-rc.2": ("rc", "true"),
        "v1.2.3": ("stable", "false"),
    }
    for tag, (release_type, prerelease) in expected_types.items():
        result = _detect_release(workflow, tmp_path / tag, tag)
        assert result["release_type"] == release_type
        assert result["is_prerelease"] == prerelease

    assert "inputs.release_type" not in workflow
    assert "github.event.release.tag_name" not in workflow


@pytest.mark.skipif(sys.platform == "win32", reason="Bash script tests require a POSIX environment")
def test_release_draft_is_independent_and_inputs_are_passed_via_env(
    tmp_path: Path,
) -> None:
    workflow = _read(ROOT / ".github" / "workflows" / "release.yml")
    preamble = _workflow_preamble(workflow)
    detection = workflow.partition("      - name: Validate tag and detect release type\n")[2].partition(
        "\n      - name: Validate prepared release metadata"
    )[0]

    assert "      draft:\n" in preamble
    assert "        type: boolean\n        default: false" in preamble
    assert "RELEASE_TAG: ${{ inputs.tag_name || github.ref_name }}" in detection
    assert "RELEASE_DRAFT: ${{ inputs.draft || false }}" in detection
    assert 'TAG="$RELEASE_TAG"' in detection
    assert 'IS_DRAFT="$RELEASE_DRAFT"' in detection
    assert 'TAG="${{' not in detection
    assert 'IS_DRAFT="${{' not in detection
    assert 'echo "is_draft=$IS_DRAFT" >> "$GITHUB_OUTPUT"' in detection
    assert ">> $GITHUB_OUTPUT" not in detection

    draft_beta = _detect_release(workflow, tmp_path, "v1.2.3-beta.4", draft=True)
    assert draft_beta["release_type"] == "beta"
    assert draft_beta["is_prerelease"] == "true"
    assert draft_beta["is_draft"] == "true"


def test_api_dependency_update_workflow_delegates_to_the_shared_pipeline() -> None:
    """An announced API release takes exactly the path the daily run takes."""
    workflow = _read(ROOT / ".github" / "workflows" / "api-dependency-update.yml")

    assert "idm_heatpump_api_release" in workflow
    assert "uses: ./.github/workflows/dependency-update.yml" in workflow
    assert "set-pin: idm-heatpump-api==${{ needs.resolve.outputs.version }}" in workflow
    # The pipeline validates, opens and merges; nothing rewrites pins here.
    assert "peter-evans/create-pull-request" not in workflow
    assert "manifest.json" not in workflow
    assert "concurrency:\n  group: dependency-update" in workflow


def test_api_dependency_update_validates_input_before_output() -> None:
    workflow = _read(ROOT / ".github" / "workflows" / "api-dependency-update.yml")
    resolve_step = workflow.partition("      - name: Resolve API version\n")[2]

    assert "REQUESTED_API_VERSION:" in resolve_step
    assert "github.event.client_payload.version" in resolve_step
    assert "inputs.api_version" in resolve_step
    assert "^(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)$" in resolve_step
    assert resolve_step.index("API version must be a stable SemVer") < resolve_step.index(
        'echo "version=$VERSION" >> "$GITHUB_OUTPUT"'
    )


def test_api_dependency_update_passes_version_safely_to_the_shell() -> None:
    """A version from another repository is read from the environment."""
    workflow = _read(ROOT / ".github" / "workflows" / "api-dependency-update.yml")
    resolve_step = workflow.partition("      - name: Resolve API version\n")[2].partition("\n  update:")[0]

    assert 'VERSION="$REQUESTED_API_VERSION"' in resolve_step
    assert 'VERSION="${{ github.event.client_payload.version }}"' not in resolve_step


def test_dependency_update_pipeline_covers_every_runtime_pin() -> None:
    """The pipeline that reaches main must update all of the pins, not some."""
    workflow = _read(ROOT / ".github" / "workflows" / "dependency-update.yml")

    assert "python scripts/check_dependency_pins.py --update" in workflow
    assert 'python scripts/check_dependency_pins.py --set "$SET_PIN"' in workflow
    # A newer API ships a different register set; the generated documents are
    # part of the same commit, or their --check tests are red on main.
    for generator in (
        "python scripts/generate_modbus_register_reference.py",
        "python scripts/generate_entity_metadata_catalog.py",
        "python scripts/generate_entity_translations.py",
    ):
        assert generator in workflow
    # The import that catches an upstream release needing a new extra.
    assert "from modbus_connection.tmodbus import ModbusConnection" in workflow
    for test_file in (
        "tests/test_dependency_pins.py",
        "tests/test_release_contract.py",
        "tests/test_cross_repo_contract.py",
    ):
        assert test_file in workflow
    assert "peter-evans/create-pull-request" in workflow


def test_dependency_update_runs_real_ci_before_merging() -> None:
    """A pull request opened with GITHUB_TOKEN starts no workflow of its own.

    Without CI inside this run, an automatically merged pin would reach main
    having been validated by nothing at all.
    """
    workflow = _read(ROOT / ".github" / "workflows" / "dependency-update.yml")
    validate = workflow.partition("  validate:\n")[2].partition("\n  hassfest:")[0]
    merge = workflow.partition("  merge:\n")[2]

    assert "uses: ./.github/workflows/python-quality.yml" in validate
    assert "ref: ${{ needs.propose.outputs.branch }}" in validate
    assert "api-main" in validate and "manifest-pinned" in validate
    assert "needs: [propose, validate, hassfest]" in merge
    assert "--squash" in merge


def test_dependency_update_can_open_the_pull_request_as_a_human_would() -> None:
    """A pull request opened with GITHUB_TOKEN starts no checks of its own.

    Where main requires status checks, that pull request can never satisfy
    them, so the pipeline accepts an optional token that can.
    """
    workflow = _read(ROOT / ".github" / "workflows" / "dependency-update.yml")

    assert "DEPENDENCY_UPDATE_TOKEN:\n        required: false" in workflow
    assert "token: ${{ secrets.DEPENDENCY_UPDATE_TOKEN || secrets.GITHUB_TOKEN }}" in workflow
    # Merging outright comes first: this run already produced the evidence.
    merge = workflow.partition("      - name: Merge the pull request\n")[2]
    assert merge.index("--squash --delete-branch;") < merge.index("--squash --delete-branch --auto")


def test_dependency_update_holds_a_major_bump_for_review() -> None:
    """A breaking upstream release is proposed and validated, never merged."""
    workflow = _read(ROOT / ".github" / "workflows" / "dependency-update.yml")
    merge = workflow.partition("  merge:\n")[2]

    assert "needs.propose.outputs.has-major == 'true' && inputs.merge-major != true" in merge
    assert "if: inputs.auto-merge && (needs.propose.outputs.has-major != 'true' || inputs.merge-major)" in merge
    assert "needs-review" in merge


def test_dependency_update_does_not_commit_its_own_reports() -> None:
    """The report is workflow state; committed, it would land in the release."""
    workflow = _read(ROOT / ".github" / "workflows" / "dependency-update.yml")

    assert '--report "$RUNNER_TEMP/update-report.json"' in workflow
    assert '--report "$RUNNER_TEMP/set-report.json"' in workflow
    assert "--report update-report.json" not in workflow


def test_dependabot_pull_requests_merge_without_running_their_code() -> None:
    """pull_request_target hands out a write token — never to a checkout."""
    workflow = _read(ROOT / ".github" / "workflows" / "dependabot-auto-merge.yml")

    assert "pull_request_target:" in workflow
    assert "github.event.pull_request.user.login == 'dependabot[bot]'" in workflow
    assert "actions/checkout" not in workflow
    assert "--watch --fail-fast" in workflow
    assert "--squash" in workflow


def test_dependabot_does_not_claim_to_read_the_manifest() -> None:
    """Dependabot has no pip manifest here; the pin check owns those versions."""
    config = _read(ROOT / ".github" / "dependabot.yml")

    assert 'package-ecosystem: "github-actions"' in config
    assert 'package-ecosystem: "pip"' not in config
    assert "scripts/check_dependency_pins.py" in config


def test_release_artifact_is_built_from_manifest_directory() -> None:
    release_workflow = _read(ROOT / ".github" / "workflows" / "release.yml")

    assert "cd custom_components/idm_heatpump" in release_workflow
    assert "zip -r ../../idm_heatpump.zip ." in release_workflow
    assert "manifest.json" not in release_workflow.partition("zip -r ../../idm_heatpump.zip .")[2].partition("\n\n")[0]


def test_release_announces_non_draft_versions_in_discussions() -> None:
    release_workflow = _read(ROOT / ".github" / "workflows" / "release.yml")

    assert "  discussions: write" in release_workflow
    assert "Announce published release in GitHub Discussions" in release_workflow
    assert "if: steps.version.outputs.is_draft == 'false'" in release_workflow
    assert "RELEASE_NOTES_PATH: temp_release_notes.md" in release_workflow
    assert "DISCUSSION_CATEGORY_SLUG: announcements" in release_workflow
    assert "run: python scripts/publish_release_discussion.py" in release_workflow


def test_release_smoke_test_is_candidate_bound_without_stale_version() -> None:
    smoke = _read(ROOT / "docs" / "RELEASE_SMOKE_TEST.md")

    assert 'export RELEASE_VERSION="${RELEASE_VERSION:?set the candidate version first}"' in smoke
    assert 'assert manifest["version"] == os.environ["RELEASE_VERSION"]' in smoke
    assert 'assert manifest["version"] == "0.8.1-beta.' not in smoke
    assert "docs/release-evidence/TEMPLATE.md" in smoke
    for result in ("`PASS`", "`FAIL`", "`N/A`"):
        assert result in smoke
    assert "A `BLOCKED` result is not a pass" in smoke


def test_stable_release_requires_measured_soak_and_signed_smoke_evidence() -> None:
    process = _read(ROOT / "docs" / "RELEASE_PROCESS.md")
    stability = _read(ROOT / "docs" / "wiki" / "Stability-and-Release-Readiness.md")
    template = _read(ROOT / "docs" / "release-evidence" / "TEMPLATE.md")

    for content in (process, stability):
        normalized = " ".join(content.split())
        assert "seven consecutive 24-hour periods" in normalized
        assert "Documentation-only" in normalized
        assert "restart" in normalized.lower()

    for required_check in ("SMOKE-01", "SMOKE-06", "SMOKE-09", "Overall result", "Signed at (UTC)"):
        assert required_check in template


def test_beta_31_release_evidence_matches_published_candidate() -> None:
    evidence = _read(ROOT / "docs" / "release-evidence" / "0.8.1-beta.31.md")

    assert "`044115b0bbfecd4086f995612846e27c97c953d6`" in evidence
    assert "`9789414d9697d0272800537b8c90df331ab5e916da31b3caf463c0f7f1b37c31`" in evidence
    assert "`2026-07-11T18:59:52Z`" in evidence
    assert "`2026-07-18T18:59:52Z`" in evidence
    assert "Status: `BLOCKED`" in evidence
    assert "Overall result: `BLOCKED`" in evidence


def test_release_workflow_validates_prepared_version_and_changelog() -> None:
    release_workflow = _read(ROOT / ".github" / "workflows" / "release.yml")

    assert "Validate prepared release metadata" in release_workflow
    assert 'manifest_version = json.loads(manifest_path.read_text(encoding="utf-8"))["version"]' in release_workflow
    assert "if manifest_version != version:" in release_workflow
    assert 'expected_heading = f"## [{version}]"' in release_workflow
    assert "docs/CHANGELOG.md has no heading for release" in release_workflow


def test_release_workflow_never_mutates_or_pushes_release_metadata() -> None:
    release_workflow = _read(ROOT / ".github" / "workflows" / "release.yml")

    assert "update-changelog:" not in release_workflow
    assert "Update version in manifest" not in release_workflow
    assert "sed -i" not in release_workflow
    assert "git commit" not in release_workflow
    assert "git push" not in release_workflow


def test_release_workflow_selects_previous_tag_without_substring_exclusions() -> None:
    release_workflow = _read(ROOT / ".github" / "workflows" / "release.yml")

    assert "(-[0-9A-Za-z.-]+)?$" in release_workflow
    assert 'grep -Fxv "$CURRENT_TAG"' in release_workflow
    assert 'grep -v "$CURRENT_TAG"' not in release_workflow
    assert 'if [ "$RELEASE_TYPE" = "stable" ]' in release_workflow
    assert "TAG_PATTERN='^v[0-9]+\\.[0-9]+\\.[0-9]+$'" in release_workflow
    assert "| head -1 || true)" in release_workflow


def test_release_workflow_uses_curated_changelog_section_by_default() -> None:
    release_workflow = _read(ROOT / ".github" / "workflows" / "release.yml")

    assert 'changelog_lines = Path("docs/CHANGELOG.md").read_text(encoding="utf-8").splitlines()' in release_workflow
    assert 'heading = f"## [{version}]"' in release_workflow
    assert 'changelog_lines[index].startswith("## [")' in release_workflow
    assert 'release_notes = "\\n".join(changelog_lines[start:end]).strip()' in release_workflow
    assert "### Support" in release_workflow
    assert "### What changed" not in release_workflow


def test_wiki_sync_exactly_mirrors_source_pages_safely() -> None:
    workflow = _read(ROOT / ".github" / "workflows" / "wiki-sync.yml")
    mirror_step = workflow.partition("      - name: Mirror wiki files\n")[2].partition(
        "\n      - name: Commit and push to wiki"
    )[0]

    assert "find /tmp/wiki -maxdepth 1 -type f -name '*.md' -delete" in mirror_step
    assert "cp docs/wiki/*.md /tmp/wiki/" in mirror_step
    assert ".git" not in mirror_step
    assert "rm -rf" not in mirror_step
    assert "git diff --cached --quiet" in workflow
    assert "No changes to wiki pages." in workflow


def test_wiki_sync_runs_only_for_main_and_cancels_superseded_runs() -> None:
    workflow = _read(ROOT / ".github" / "workflows" / "wiki-sync.yml")
    preamble = workflow.partition("\njobs:\n")[0]

    assert "    branches: [main]" in preamble
    assert "master" not in preamble
    assert "concurrency:\n  group: wiki-sync\n  cancel-in-progress: true" in preamble
    assert "timeout-minutes: 10" in workflow


def test_pages_deploy_triggers_only_for_deployed_content() -> None:
    workflow = _read(ROOT / ".github" / "workflows" / "pages.yml")
    preamble = workflow.partition("\npermissions:\n")[0]

    assert "    branches: [main]" in preamble
    assert "      - 'docs/public/**'" in preamble
    assert "README.md" not in preamble
    assert 'concurrency:\n  group: "pages"\n  cancel-in-progress: true' in workflow


def test_user_facing_dependency_docs_match_manifest() -> None:
    runtime_docs = [
        ROOT / "README.md",
        ROOT / "README_de.md",
        ROOT / "docs" / "wiki" / "Home.md",
        ROOT / "docs" / "wiki" / "_Sidebar.md",
    ]
    api_pin_docs = [
        *runtime_docs,
        ROOT / "AGENTS.md",
        ROOT / "docs" / "RELEASE_SMOKE_TEST.md",
        ROOT / "docs" / "wiki" / "Configuration.md",
        ROOT / "docs" / "wiki" / "Local-Web-Interface.md",
    ]

    for requirement in EXPECTED_RUNTIME_REQUIREMENTS:
        assert all(requirement in _read(path) for path in runtime_docs)

    api_requirement = next(
        requirement for requirement in EXPECTED_RUNTIME_REQUIREMENTS if requirement.startswith("idm-heatpump-api")
    )
    assert all(api_requirement in _read(path).replace(" == ", "==") for path in api_pin_docs)

    api_version = api_requirement.partition("==")[2]
    configuration = _read(ROOT / "docs" / "wiki" / "Configuration.md")
    stability = _read(ROOT / "docs" / "wiki" / "Stability-and-Release-Readiness.md")
    assert api_requirement in configuration.replace(" == ", "==")
    assert f"`idm-heatpump-api` `{api_version}`" in stability


def test_dependency_freshness_workflow_runs_the_pipeline_daily() -> None:
    """Pins must be checked on a schedule, not only when somebody remembers."""
    workflow = _read(ROOT / ".github" / "workflows" / "dependency-freshness.yml")

    assert "schedule:" in _workflow_preamble(workflow)
    assert 'cron: "0 4 * * *"' in workflow
    assert "workflow_dispatch:" in workflow
    assert "  pull-requests: write" in workflow
    assert "uses: ./.github/workflows/dependency-update.yml" in workflow
    assert "auto-merge: ${{ inputs.auto-merge != false }}" in workflow
    assert "concurrency:\n  group: dependency-update" in workflow


def test_release_refuses_stale_runtime_pins_unless_overridden() -> None:
    """A release must not silently ship a pin that upstream has moved past."""
    workflow = _read(ROOT / ".github" / "workflows" / "release.yml")

    assert "allow_stale_pins" in workflow
    assert "Check runtime dependency pins are current" in workflow
    assert "python scripts/check_dependency_pins.py" in workflow
    # The check only degrades to a warning when the override is set explicitly.
    assert 'if [ "$ALLOW_STALE_PINS" = "true" ]; then' in workflow
    assert "python scripts/check_dependency_pins.py --warn-only" in workflow
    # The guard runs before anything is built or published.
    assert workflow.index("Check runtime dependency pins are current") < workflow.index("Create ZIP artifact")


def test_modbus_activation_guidance_is_consistent_in_ui_and_docs() -> None:
    paths = [
        ROOT / "README.md",
        ROOT / "README_de.md",
        ROOT / "docs" / "wiki" / "Home.md",
        ROOT / "docs" / "wiki" / "Installation-and-Setup.md",
        ROOT / "docs" / "wiki" / "Troubleshooting.md",
        ROOT / "custom_components" / "idm_heatpump" / "strings.json",
        ROOT / "custom_components" / "idm_heatpump" / "translations" / "de.json",
        ROOT / "custom_components" / "idm_heatpump" / "translations" / "en.json",
    ]

    for path in paths:
        content = _read(path)
        assert "Gebäudeleittechnik" in content, path
        assert "Modbus TCP" in content, path

    installation = _read(ROOT / "docs" / "wiki" / "Installation-and-Setup.md")
    assert "PV inverter" in installation
    assert "port 502" in installation
    assert "slave/unit ID 1" in installation
