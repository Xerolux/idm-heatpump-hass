"""Number platform for IDM Heatpump."""

from __future__ import annotations

# IDM Heatpump for Home Assistant
# © 2026 Xerolux — unofficial community integration for IDM Navigator 2.0 / 10 heat pumps
# Created by Xerolux | https://github.com/Xerolux/idm-heatpump-hass
# SPDX-License-Identifier: MIT
import logging
import math

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from idm_heatpump import RegisterDef

from .adapter_glt import is_glt_measurement
from .coordinator import IdmCoordinator
from .entity import IdmEntity, should_add_entity
from .registers import sort_entity_descriptions
from .web_control_entities import (
    web_control_heatingcircuit_number_entities,
    web_control_number_entities,
)

PARALLEL_UPDATES = 0

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: IdmCoordinator = entry.runtime_data.coordinator
    entities: list[NumberEntity] = [
        IdmNumber(coordinator, desc_info["register"], desc_info["description"])
        for desc_info in sort_entity_descriptions(coordinator.number_descriptions)
        if should_add_entity(coordinator, desc_info["register"], as_writable_control=True)
    ]
    entities.extend(web_control_number_entities(coordinator))
    entities.extend(web_control_heatingcircuit_number_entities(coordinator))
    async_add_entities(entities)


class IdmNumber(IdmEntity, NumberEntity):
    _writable_control = True

    def __init__(
        self,
        coordinator: IdmCoordinator,
        reg: RegisterDef,
        entity_desc: NumberEntityDescription,
    ) -> None:
        super().__init__(coordinator, reg, entity_desc)
        if is_glt_measurement(self._register.name):
            # A building-management measurement also exists as a sensor with
            # the same unique_id base, so the number (the setpoint) needs a
            # suffix of its own.
            self._attr_unique_id = f"{self._attr_unique_id}_set"

    @property
    def native_value(self) -> float | None:
        if not self.coordinator.data:
            return None
        if self.is_writable_control() and self._value_is_sentinel():
            return None
        value = self.coordinator.data.get(self._register.name)
        if value is None or isinstance(value, bool):
            return None
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return None
        return numeric if math.isfinite(numeric) else None

    async def async_set_native_value(self, value: float) -> None:
        await self._async_write_register(value, action_label=f"write {self._register.name}={value}")

    @callback
    def _handle_coordinator_update(self) -> None:
        """Log sentinel readbacks so controller-side erases become countable.

        When a writable control's readback arrives as an unset sentinel, the
        entity reports unknown for that sample (see :attr:`native_value`).
        Home Assistant then only shows a graph dip, so there was no way to
        tell how often the controller erases a GLT RAM input between two
        forwarding writes. One debug line per affected poll cycle makes the
        events countable against the forwarding write cadence (#493).
        """
        if self.is_writable_control() and self._value_is_sentinel():
            _LOGGER.debug(
                "GLT readback of %s arrived as an unset sentinel; reporting unknown until the next forwarding write",
                self._register.name,
            )
        super()._handle_coordinator_update()
