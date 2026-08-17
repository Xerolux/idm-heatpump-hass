"""Load test for a maximally expanded plant.

The roadmap lists "load tests with the maximum number of heating circuits,
zones and rooms" as an open item. A maximum configuration (7 heating circuits,
10 zone modules with 8 rooms each, cascade enabled) is the largest register set
the integration can ever be asked to poll, and it is exactly the configuration
nobody owns — so it is the one that silently breaks.

These tests pin the properties that must hold at that scale: the register set
builds, stays free of name and unique-ID collisions, the coordinator's lookup
structures cover it completely, and processing a full snapshot stays well
inside one polling cycle.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from custom_components.idm_heatpump.const import MAX_ROOM_COUNT, MAX_ZONE_COUNT
from custom_components.idm_heatpump.coordinator import IdmCoordinator
from custom_components.idm_heatpump.entity import build_entity_unique_id
from custom_components.idm_heatpump.registers import (
    _collect_all_descriptions,
    collect_alias_map,
    collect_all_registers,
    get_all_binary_sensor_descriptions,
    get_all_number_descriptions,
    get_all_select_descriptions,
    get_all_sensor_descriptions,
    get_all_switch_descriptions,
)

MAX_CIRCUITS = ["a", "b", "c", "d", "e", "f", "g"]
MAX_ZONE_ROOMS = {zone: MAX_ROOM_COUNT for zone in range(MAX_ZONE_COUNT)}

# Generous ceilings: these guard against an accidental combinatorial explosion
# (a per-room register family added at zone*room scale), not against normal
# growth of the register map.
MAX_EXPECTED_REGISTERS = 2000
MAX_SETUP_SECONDS = 10.0
MAX_SNAPSHOT_PROCESSING_SECONDS = 2.0


@pytest.fixture(scope="module")
def max_descriptions() -> list[dict]:
    """Entity descriptions for the largest configuration the UI allows."""
    return _collect_all_descriptions(MAX_CIRCUITS, MAX_ZONE_COUNT, MAX_ZONE_ROOMS, True)


@pytest.fixture(scope="module")
def max_registers() -> list:
    return collect_all_registers(MAX_CIRCUITS, MAX_ZONE_COUNT, MAX_ZONE_ROOMS, True)


class TestMaximumPlantScale:
    def test_maximum_configuration_builds_a_bounded_register_set(self, max_registers):
        assert max_registers, "maximum configuration produced no registers"
        assert len(max_registers) <= MAX_EXPECTED_REGISTERS

    def test_register_names_and_addresses_stay_unique(self, max_registers):
        """A duplicate name would make one entity silently shadow another."""
        names = [register.name for register in max_registers]
        addresses = [register.address for register in max_registers]

        assert len(set(names)) == len(names)
        assert len(set(addresses)) == len(addresses)

    def test_every_room_of_every_zone_is_represented(self, max_registers):
        """All 10 zones x 8 rooms must produce their own register family."""
        names = {register.name for register in max_registers}

        for zone in range(1, MAX_ZONE_COUNT + 1):
            for room in range(1, MAX_ROOM_COUNT + 1):
                prefix = f"zm{zone}_room{room}_"
                assert any(name.startswith(prefix) for name in names), f"no registers for zone {zone} room {room}"

    def test_every_heating_circuit_is_represented(self, max_registers):
        names = {register.name for register in max_registers}

        for circuit in MAX_CIRCUITS:
            assert any(name.startswith(f"hc_{circuit}_") for name in names), (
                f"no registers for heating circuit {circuit}"
            )

    @pytest.mark.parametrize(
        "collect",
        [
            get_all_sensor_descriptions,
            get_all_binary_sensor_descriptions,
            get_all_number_descriptions,
            get_all_select_descriptions,
            get_all_switch_descriptions,
        ],
    )
    def test_entity_unique_ids_do_not_collide_within_a_platform(self, collect):
        """Unique-ID collisions at max scale would break entity registration.

        Home Assistant requires unique IDs to be unique per platform, not
        globally: one writable register may legitimately appear as a sensor and
        as a number under the same ID. Collisions *within* one platform are the
        real defect, so each platform is checked on its own.
        """
        descriptions = collect(MAX_CIRCUITS, MAX_ZONE_COUNT, MAX_ZONE_ROOMS, True)
        unique_ids = [build_entity_unique_id("entry", desc["register"].name) for desc in descriptions]

        duplicates = {unique_id for unique_id in unique_ids if unique_ids.count(unique_id) > 1}
        assert not duplicates, f"duplicate unique IDs at maximum scale: {sorted(duplicates)[:5]}"

    def test_alias_map_only_contains_genuinely_shared_addresses(self, max_descriptions):
        alias_map = collect_alias_map(MAX_CIRCUITS, MAX_ZONE_COUNT, MAX_ZONE_ROOMS, True)

        assert all(len(names) > 1 for names in alias_map.values())
        assert all(len(set(names)) == len(names) for names in alias_map.values())

    def test_building_the_maximum_configuration_is_fast_enough(self):
        """Setup must not stall Home Assistant's startup at maximum scale."""
        started = time.perf_counter()
        collect_all_registers(MAX_CIRCUITS, MAX_ZONE_COUNT, MAX_ZONE_ROOMS, True)
        collect_alias_map(MAX_CIRCUITS, MAX_ZONE_COUNT, MAX_ZONE_ROOMS, True)
        elapsed = time.perf_counter() - started

        assert elapsed < MAX_SETUP_SECONDS, f"maximum configuration took {elapsed:.1f}s to build"


class TestCoordinatorAtMaximumScale:
    def _coordinator(self, mock_hass, mock_config_entry, descriptions: list[dict]) -> IdmCoordinator:
        coordinator = IdmCoordinator(
            mock_hass,
            mock_config_entry,
            MagicMock(),
            None,
            [],
            [],
            [],
            [],
            [],
        )
        coordinator.setup_registers(
            MAX_CIRCUITS,
            MAX_ZONE_COUNT,
            MAX_ZONE_ROOMS,
            True,
            descriptions=descriptions,
        )
        return coordinator

    def test_name_index_covers_every_register(self, mock_hass, mock_config_entry, max_descriptions):
        coordinator = self._coordinator(mock_hass, mock_config_entry, max_descriptions)

        assert len(coordinator._register_by_name) == len(coordinator._registers)
        for register in coordinator._registers:
            assert coordinator.get_register(register.name) is register

    def test_room_mode_registers_are_precomputed_for_all_rooms(self, mock_hass, mock_config_entry, max_descriptions):
        """Room modes are read individually, so their count drives poll cost."""
        coordinator = self._coordinator(mock_hass, mock_config_entry, max_descriptions)

        room_mode_names = {register.name for register in coordinator._room_mode_registers}
        assert len(room_mode_names) == MAX_ZONE_COUNT * MAX_ROOM_COUNT

    def test_full_snapshot_evaluation_stays_within_one_cycle(self, mock_hass, mock_config_entry, max_descriptions):
        """The unused-register pass runs over every register on every poll."""
        coordinator = self._coordinator(mock_hass, mock_config_entry, max_descriptions)
        snapshot = {register.name: 21.5 for register in coordinator._registers}

        started = time.perf_counter()
        for _ in range(10):
            unused = {name for name, value in snapshot.items() if coordinator.is_register_unused(name, value)}
        elapsed = time.perf_counter() - started

        assert unused == set()
        assert elapsed < MAX_SNAPSHOT_PROCESSING_SECONDS, f"10 snapshot passes took {elapsed:.2f}s"
