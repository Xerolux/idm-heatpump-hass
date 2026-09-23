"""Tests for the Navigator 10 web demand reason presentation and entities."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from idm_heatpump import IdmWebHomeDetail, parse_navigator_home_response

from custom_components.idm_heatpump.web_data import IdmWebSupplement, _read_optional_demand_reason
from custom_components.idm_heatpump.web_demand_reason import (
    async_read_home_detail,
    demand_reason_label,
)
from custom_components.idm_heatpump.web_demand_reason_entities import (
    web_demand_reason_binary_entities,
    web_demand_reason_sensor_entities,
)


def _detail(payload: dict[str, Any]) -> IdmWebHomeDetail:
    return parse_navigator_home_response(json.dumps(payload))


def test_label_aggregates_idle_and_off_states() -> None:
    idle = _detail({"homeDetail": {"data": {"10": {"operationMode": 0}}}})
    assert demand_reason_label(idle) == "Keine Information"

    off = _detail({"homeDetail": {"data": {"10": {"operationMode": 8}}}})
    assert demand_reason_label(off) == "Aus"

    empty = _detail({"home": {}})
    assert demand_reason_label(empty) is None


def test_label_reports_single_active_reason() -> None:
    detail = _detail({"homeDetail": {"data": {"10": {"operationMode": 1, "info": 32}}}})
    assert detail.pv_demand_active is True
    assert demand_reason_label(detail) == "PV"


def test_label_reports_multiple_active_reasons() -> None:
    detail = _detail(
        {
            "homeDetail": {
                "data": {
                    "10": {"operationMode": 1, "info": 128},
                    "17": {"operationMode": 4, "info": 32},
                }
            }
        }
    )
    assert detail.pv_demand_active is True
    assert demand_reason_label(detail) == "Mehrere Anforderungen"


@pytest.mark.asyncio
async def test_async_read_uses_the_public_api_method() -> None:
    detail = _detail({"homeDetail": {"data": {"10": {"operationMode": 4, "info": 32}}}})
    client = MagicMock()
    client.read_home_detail = AsyncMock(return_value=detail)

    result = await async_read_home_detail(client)

    assert result is detail
    client.read_home_detail.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_async_read_failures_are_non_fatal() -> None:
    failing = MagicMock()
    failing.read_home_detail = MagicMock(side_effect=RuntimeError("boom"))
    assert await async_read_home_detail(failing) is None

    inert = MagicMock(spec=[])
    assert await async_read_home_detail(inert) is None


@pytest.mark.asyncio
async def test_supplement_augmentation_only_for_nav10() -> None:
    detail = _detail({"homeDetail": {"data": {"10": {"operationMode": 4, "info": 32}}}})
    client = MagicMock()
    client.read_home_detail = MagicMock(side_effect=_async_return(detail))

    nav10 = await _read_optional_demand_reason(client, IdmWebSupplement(web_variant="nav10"))
    assert nav10.demand_reason is detail

    nav20 = IdmWebSupplement(web_variant="nav20")
    assert await _read_optional_demand_reason(client, nav20) is nav20


def _async_return(value: IdmWebHomeDetail):
    async def _return(*args: Any, **kwargs: Any) -> IdmWebHomeDetail:
        return value

    return _return


def _coordinator(supplement: IdmWebSupplement | None) -> MagicMock:
    coordinator = MagicMock()
    coordinator.web_supplement = supplement
    coordinator.last_update_success = True
    coordinator.config_entry.entry_id = "test_entry"
    coordinator.config_entry.title = "IDM"
    return coordinator


def _nav10_supplement(payload: dict[str, Any]) -> IdmWebSupplement:
    return IdmWebSupplement(web_variant="nav10", demand_reason=_detail(payload))


def test_entities_created_only_for_nav10_with_state() -> None:
    with_state = _coordinator(_nav10_supplement({"homeDetail": {"data": {"10": {"operationMode": 0}}}}))
    assert len(web_demand_reason_sensor_entities(with_state)) == 1
    assert len(web_demand_reason_binary_entities(with_state)) == 1

    assert web_demand_reason_sensor_entities(_coordinator(None)) == []
    assert web_demand_reason_binary_entities(_coordinator(None)) == []
    assert web_demand_reason_sensor_entities(_coordinator(IdmWebSupplement(web_variant="nav10"))) == []
    assert web_demand_reason_binary_entities(_coordinator(IdmWebSupplement(web_variant="nav20"))) == []


def test_entity_states_follow_the_supplement() -> None:
    coordinator = _coordinator(_nav10_supplement({"homeDetail": {"data": {"10": {"operationMode": 1, "info": 32}}}}))
    sensor = web_demand_reason_sensor_entities(coordinator)[0]
    binary = web_demand_reason_binary_entities(coordinator)[0]

    assert sensor.native_value == "PV"
    assert binary.is_on is True
    assert binary.extra_state_attributes["reason"] == "PV"
    assert binary.extra_state_attributes["pv_bit"] == 32
    nodes = sensor.extra_state_attributes["nodes"]
    assert nodes == [{"path": "home/homeDetail/data/10", "operation_mode": 1, "info": 32, "reason": "pv"}]
    assert sensor._attr_unique_id == "test_entry_web_demand_reason"
    assert binary._attr_unique_id == "test_entry_web_demand_reason_pv"

    # A later poll without the extra leaves the entities unavailable.
    coordinator.web_supplement = IdmWebSupplement(web_variant="nav10")
    assert sensor.available is False
    assert binary.available is False
