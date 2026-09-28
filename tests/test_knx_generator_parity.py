"""The website's KNX generator must match the command-line generator exactly.

``docs/public/docs/knx-generator-core.mjs`` mirrors
``scripts/generate_knx_group_addresses.py``; this test runs the Node parity
harness, which builds XML and CSV for a set of fixtures with both
implementations and compares them byte for byte. It needs Node, exactly like
the Pages tests do.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import build_pages

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "scripts" / "check_knx_generator_parity.mjs"


@pytest.fixture(scope="module")
def catalog_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The catalogue exactly as the site build emits it."""
    return build_pages.write_knx_catalog(tmp_path_factory.mktemp("knx-catalog"))


def test_website_generator_matches_the_command_line_generator(catalog_path: Path) -> None:
    node = shutil.which("node")
    assert node is not None, "node is required, the same way the Pages tests require it"
    result = subprocess.run(
        [node, str(HARNESS), "--catalog", str(catalog_path), "--python", sys.executable],
        capture_output=True,
        text=True,
        check=False,
        cwd=ROOT,
    )
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
    assert "parity ok" in result.stdout
