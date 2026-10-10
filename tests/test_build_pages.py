"""The catalogue the website's KNX generator runs on must mirror the integration.

``build_pages.write_knx_catalog`` emits the JSON from the same modules the
command-line generator uses, so the interactive page can never serve a stale
or edited object list. These tests pin that link.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import build_pages
from scripts import generate_knx_group_addresses as generator


@pytest.mark.parametrize("target", [".", "..", "docs", "docs/wiki", "scripts", "tests", "custom_components", ".git"])
def test_build_rejects_source_directories_before_deleting(tmp_path: Path, monkeypatch, target: str) -> None:
    root = tmp_path / "repository"
    root.mkdir()
    source = root / "docs" / "wiki" / "Home.md"
    source.parent.mkdir(parents=True)
    source.write_text("Keep this source", encoding="utf-8")
    monkeypatch.setattr(build_pages, "ROOT", root)

    with pytest.raises(ValueError, match="Unsafe Pages output directory"):
        build_pages.build_site(root / target)

    assert source.read_text(encoding="utf-8") == "Keep this source"


def test_catalogue_json_mirrors_the_knx_catalogue(tmp_path: Path) -> None:
    path = build_pages.write_knx_catalog(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["version"] == build_pages._metadata()[0]
    assert payload["default_base"] == "8/0/0"
    assert payload["project_name"] == "Wärmepumpe"
    assert payload["prefix"] == "WP"
    assert payload["compact_registers"] == list(generator.COMPACT_REGISTERS)

    objects = payload["objects"]
    catalogue = generator.KNX_OBJECTS
    assert len(objects) == len(catalogue)
    assert [entry["number"] for entry in objects] == [obj.number for obj in catalogue]
    first = catalogue[0]
    assert objects[0] == {
        "number": first.number,
        "register": first.register,
        "dpt": first.dpt,
        "group": first.group,
        "writable": first.writable,
        "name": generator.object_name(first.register),
    }

    counts: dict[str, int] = {}
    for entry in objects:
        counts[entry["group"]] = counts.get(entry["group"], 0) + 1
    assert payload["groups"] == [
        {"id": group, "label": generator.GROUP_LABELS[group], "count": counts.get(group, 0)}
        for group in generator.OBJECT_GROUPS
    ]

    known_registers = {entry["register"] for entry in objects}
    assert set(payload["compact_registers"]) <= known_registers
