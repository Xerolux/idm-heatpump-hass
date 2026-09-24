"""Real-Home-Assistant smoke-test fixtures.

The suite in ``tests/`` stubs the entire ``homeassistant`` package, which is
fast but blind to lifecycle bugs: registries, stores and the config-entry
machinery never run (audit package E1). This directory is the opposite leg:
a genuine Home Assistant instance boots in a temporary config directory whose
``custom_components`` is this repository, and the integration walks its real
setup, reload and unload path.

Run it with a Home Assistant runtime installed, e.g.

    test_ha/Scripts/python -m pytest tests_ha/

It is outside ``testpaths`` in ``pytest.ini``, so the stubbed suite never
collects it and no test here runs without a real Home Assistant.
"""

from __future__ import annotations

import shutil
from collections.abc import AsyncIterator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant import loader
from homeassistant.config_entries import SOURCE_USER, ConfigEntries, ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from idm_heatpump import IdmModelInfo

from custom_components.idm_heatpump.const import DOMAIN
from custom_components.idm_heatpump.modbus_client import IdmModbusConnectionClient

REPO_ROOT = Path(__file__).resolve().parent.parent


def make_fake_client() -> MagicMock:
    """A client answering like a Navigator 10 standing next door.

    ``spec`` keeps the fake honest about the real client's API surface, so a
    renamed or removed method fails the smoke leg instead of silently
    succeeding. ``read_batch`` returns a plausible value for every requested
    register, the first refresh succeeds and entities report available; no
    socket is ever opened.
    """
    client: MagicMock = MagicMock(spec=IdmModbusConnectionClient)
    client.connect = AsyncMock(return_value=None)
    client.disconnect = AsyncMock(return_value=None)
    client.detect_model = AsyncMock(
        return_value=IdmModelInfo(
            model_name="Navigator 10",
            active_heating_circuits=["a"],
            zone_modules=0,
            has_solar=True,
            has_isc=True,
            has_pv=True,
            has_cascade=False,
            features=set(),
        )
    )
    client.read_batch = AsyncMock(side_effect=lambda registers: {register.name: 20.0 for register in registers})
    client.write_register = AsyncMock(return_value=None)
    client.get_unsupported_registers = MagicMock(return_value=set())
    return client


def _expose_custom_components(config_dir: Path) -> None:
    """Make loader resolve this repository's custom_components inside the temp dir."""
    target = config_dir / "custom_components"
    target.mkdir(exist_ok=True)
    link = target / DOMAIN
    if link.exists():
        return
    try:
        link.symlink_to(REPO_ROOT / "custom_components" / DOMAIN, target_is_directory=True)
    except OSError:
        # Windows without symlink privilege: the integration is small enough
        # that a per-session copy is cheaper than fighting the filesystem.
        shutil.copytree(REPO_ROOT / "custom_components" / DOMAIN, link)


@pytest.fixture
async def smoke_hass(tmp_path: Path) -> AsyncIterator[HomeAssistant]:
    """A real Home Assistant whose config directory also hosts the integration."""
    _expose_custom_components(tmp_path)
    hass = HomeAssistant(str(tmp_path))
    loader.async_setup(hass)
    dr.async_setup(hass)
    await dr.async_load(hass)
    await er.async_load(hass)
    hass.config_entries = ConfigEntries(hass, {})
    await hass.config_entries.async_initialize()
    yield hass
    await hass.async_stop()


@pytest.fixture
def fake_client() -> MagicMock:
    return make_fake_client()


@pytest.fixture
def patched_client(fake_client: MagicMock) -> AsyncIterator[MagicMock]:
    """Replace the Modbus client factory with the fake for the block's duration."""
    with patch(
        "custom_components.idm_heatpump.get_idm_client",
        return_value=fake_client,
    ) as patched:
        yield patched


@pytest.fixture
def smoke_entry() -> ConfigEntry:
    """A config entry shaped like the config flow persists it."""
    return ConfigEntry(
        version=1,
        minor_version=3,
        domain=DOMAIN,
        entry_id="idm_smoke_entry",
        title="IDM Smoke",
        data={"host": "192.0.2.1", "port": 502, "slave_id": 1, "name": "IDM Smoke"},
        source=SOURCE_USER,
        unique_id=None,
        options={},
        discovery_keys={},
        subentries_data={},
    )
