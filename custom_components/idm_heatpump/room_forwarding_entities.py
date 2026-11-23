"""Runtime control entities for external room temperature forwarding.

The forwarder itself is option-driven (sources, interval, tolerance, offset,
season window), but pausing it should not require a trip through the options
flow and the resulting entry reload. These switches therefore act on the
running forwarder directly:

- one master switch per config entry that gates every room temperature write,
- one switch per configured source that includes or excludes that source
  from its heating circuit's average.

Both persist through a Home Assistant storage collection owned by the
forwarder, so a restart restores exactly the switching state the user left.
The entities exist only when room temperature forwarding is configured; they
are removed with the forwarder when the option is withdrawn.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory

from .coordinator import IdmCoordinator
from .entity import IdmCoordinatorEntityBase, build_entity_unique_id
from .room_temp_forwarding import RoomTempForwarder


def room_forwarding_switch_entities(
    coordinator: IdmCoordinator,
    forwarder: RoomTempForwarder,
) -> list[SwitchEntity]:
    """Create the master switch plus one switch per configured source."""
    entities: list[SwitchEntity] = [IdmRoomForwardingMasterSwitch(coordinator, forwarder)]
    for circuit, sources in forwarder.circuits.items():
        for source in sources:
            entities.append(IdmRoomForwardingSourceSwitch(coordinator, forwarder, circuit, source))
    return entities


def _season_label(window: tuple[int, int] | None) -> str | None:
    """Render a (month, day) pair as MM-DD, or None when unset."""
    if window is None:
        return None
    return f"{window[0]:02d}-{window[1]:02d}"


class IdmRoomForwardingMasterSwitch(IdmCoordinatorEntityBase, SwitchEntity):
    """Pause or resume external room temperature forwarding.

    Off stops every room temperature write of this entry immediately — no
    options-flow round trip, no entry reload. The season window from the
    options is honoured independently: while today lies outside it, the
    switch stays on but nothing is written, which the attributes make
    visible.
    """

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:home-thermometer"
    _attr_translation_key = "room_temp_forwarding_active"
    _attr_has_entity_name = True

    def __init__(self, coordinator: IdmCoordinator, forwarder: RoomTempForwarder) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        entry_id = entry.entry_id if entry is not None else "no_entry"
        self._attr_unique_id = build_entity_unique_id(entry_id, "room_temp_forwarding_active")
        self._forwarder = forwarder

    @property
    def available(self) -> bool:
        return True

    @property
    def is_on(self) -> bool:
        return self._forwarder.master_enabled

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        season = self._forwarder.season
        return {
            "season_start": _season_label(season.start) if season else None,
            "season_end": _season_label(season.end) if season else None,
            "in_season": self._forwarder.season_active(),
            "forwarding_active": self._forwarder.forwarding_active,
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._forwarder.async_set_master_enabled(True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._forwarder.async_set_master_enabled(False)
        self.async_write_ha_state()


class IdmRoomForwardingSourceSwitch(IdmCoordinatorEntityBase, SwitchEntity):
    """Include or exclude one source sensor from its circuit's average.

    Averaging only ever sees switched-on sources; unavailable or invalid
    sensors are skipped by the forwarder itself. Turning the last source of
    a circuit off makes the forwarder write the register's "no value"
    sentinel instead of a stale average.
    """

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:thermometer-lines"
    _attr_translation_key = "room_temp_source"
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: IdmCoordinator,
        forwarder: RoomTempForwarder,
        circuit: str,
        source: str,
    ) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        entry_id = entry.entry_id if entry is not None else "no_entry"
        self._attr_unique_id = build_entity_unique_id(
            entry_id,
            f"room_temp_source_{circuit}_{source.replace('.', '_')}",
        )
        self._forwarder = forwarder
        self._circuit = circuit
        self._source = source
        self._attr_translation_placeholders = {"circuit": circuit.upper(), "source": source}

    @property
    def available(self) -> bool:
        return True

    @property
    def is_on(self) -> bool:
        return self._forwarder.source_enabled(self._circuit, self._source)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._forwarder.async_set_source_enabled(self._circuit, self._source, True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._forwarder.async_set_source_enabled(self._circuit, self._source, False)
        self.async_write_ha_state()
