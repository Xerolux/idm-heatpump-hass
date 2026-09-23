"""Tests for the Navigator 10 web demand reason decoding and entities."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import pytest

from custom_components.idm_heatpump.web_data import IdmWebSupplement, _read_optional_demand_reason
from custom_components.idm_heatpump.web_demand_reason import (
    async_read_home_detail_demand_reason,
    decode_demand_reason,
    evaluate_demand_reason,
)
from custom_components.idm_heatpump.web_demand_reason_entities import (
    web_demand_reason_binary_entities,
    web_demand_reason_sensor_entities,
)


def test_heating_reason_table_decodes_every_documented_bit() -> None:
    expected = {
        2: "no_info",
        4: "external_input",
        8: "external_bus",
        16: "isc",
        32: "pv",
        64: "frost_protection",
        128: "hc_a",
        256: "hc_b",
        512: "hc_c",
        1024: "hc_d",
        2048: "hc_e",
        4096: "hc_f",
        8192: "hc_g",
        16384: "system_off",
        32768: "ion",
    }
    for bit, reason in expected.items():
        assert decode_demand_reason(1, bit) == reason


def test_dhw_reason_table_decodes_every_documented_bit() -> None:
    expected = {
        2: "single_loading",
        4: "single_loading_boost",
        8: "external_input",
        16: "external_bus",
        32: "pv",
        64: "isc",
        128: "schedule",
        256: "schedule_boost",
        512: "system_off",
        1024: "dhw_comfort",
        2048: "ion",
        4096: "cascade",
        8192: "dhw_booster",
    }
    for bit, reason in expected.items():
        assert decode_demand_reason(4, bit) == reason


def test_priority_order_matches_the_web_ui() -> None:
    # Frost protection (64) and heating circuit A (128) set together decode
    # to the first matching bit in the SPA's check order.
    assert decode_demand_reason(1, 64 | 128 | 1) == "more_demands"
    assert decode_demand_reason(1, 32 | 1) == "pv"  # bit 0 never counts as multiple
    assert decode_demand_reason(1, 4 | 8) == "more_demands"


def test_operation_modes_without_demand() -> None:
    assert decode_demand_reason(0, 32) == "no_info"
    assert decode_demand_reason(8, 32) == "off"
    assert decode_demand_reason(3, 32) is None
    assert decode_demand_reason(1, None) is None


def test_evaluate_collects_request_widgets_from_real_frame_shape() -> None:
    payload: dict[str, Any] = {
        "home": {
            "1": {"3x2": {"grid": {"value": "11.8460"}, "pv": {"value": "5.5030"}, "signal": 16, "type": 4}},
            "10": {"1x2": {"operationMode": 0}},
            "17": {"1x1": {"operationMode": 0}},
            "18": {"1x1": {"activeMode": 1, "displayName": "A OG", "pumpActive": False}},
        }
    }
    state = evaluate_demand_reason(payload)
    assert [node.operation_mode for node in state.nodes] == [0, 0]
    assert state.pv_active is False
    assert state.label == "Keine Information"


def test_evaluate_detects_pv_demand() -> None:
    payload: dict[str, Any] = {
        "homeDetail": {
            "data": {
                "10": {"operationMode": 1, "info": 32},
                "17": {"operationMode": 0},
            }
        }
    }
    state = evaluate_demand_reason(payload)
    assert state.pv_active is True
    assert state.label == "PV"
    binary = state.nodes[0]
    assert binary.reason == "pv"


def test_evaluate_multiple_active_reasons_reports_more_demands() -> None:
    payload: dict[str, Any] = {
        "homeDetail": {
            "data": {
                "10": {"operationMode": 1, "info": 128},
                "17": {"operationMode": 4, "info": 32},
            }
        }
    }
    state = evaluate_demand_reason(payload)
    assert state.pv_active is True
    assert state.label == "Mehrere Anforderungen"


def test_evaluate_empty_frame_is_undecidable() -> None:
    state = evaluate_demand_reason({"home": {}})
    assert state.nodes == ()
    assert state.pv_active is False
    assert state.label is None


@pytest.mark.asyncio
async def test_client_seam_reads_home_detail() -> None:
    frame = json.dumps({"homeDetail": {"data": {"10": {"operationMode": 1, "info": 32}}}})
    client = MagicMock()
    client._send_json_and_receive_text = MagicMock(side_effect=_async_return(frame))

    state = await async_read_home_detail_demand_reason(client, 5.0)

    assert state is not None
    assert state.pv_active is True
    request = client._send_json_and_receive_text.call_args[0][0]
    assert request == {"controller": "home", "command": "detail"}


@pytest.mark.asyncio
async def test_client_seam_failures_are_non_fatal() -> None:
    failing = MagicMock()
    failing._send_json_and_receive_text = MagicMock(side_effect=RuntimeError("boom"))
    assert await async_read_home_detail_demand_reason(failing, 5.0) is None

    inert = MagicMock(spec=[])
    assert await async_read_home_detail_demand_reason(inert, 5.0) is None

    garbage = MagicMock()
    garbage._send_json_and_receive_text = MagicMock(side_effect=_async_return("not json"))
    assert await async_read_home_detail_demand_reason(garbage, 5.0) is None


@pytest.mark.asyncio
async def test_supplement_augmentation_only_for_nav10() -> None:
    frame = json.dumps({"homeDetail": {"data": {"10": {"operationMode": 4, "info": 32}}}})
    client = MagicMock()
    client._send_json_and_receive_text = MagicMock(side_effect=_async_return(frame))

    nav10 = await _read_optional_demand_reason(client, IdmWebSupplement(web_variant="nav10"))
    assert nav10.demand_reason is not None
    assert nav10.demand_reason.pv_active is True

    nav20 = IdmWebSupplement(web_variant="nav20")
    assert await _read_optional_demand_reason(client, nav20) is nav20


def _async_return(value: str):
    async def _return(*args: Any, **kwargs: Any) -> str:
        return value

    return _return


def _coordinator(supplement: IdmWebSupplement | None) -> MagicMock:
    coordinator = MagicMock()
    coordinator.web_supplement = supplement
    coordinator.last_update_success = True
    coordinator.config_entry.entry_id = "test_entry"
    coordinator.config_entry.title = "IDM"
    return coordinator


def test_entities_created_only_for_nav10_with_state() -> None:
    with_state = _coordinator(IdmWebSupplement(web_variant="nav10", demand_reason=evaluate_demand_reason({"home": {}})))
    assert len(web_demand_reason_sensor_entities(with_state)) == 1
    assert len(web_demand_reason_binary_entities(with_state)) == 1

    assert web_demand_reason_sensor_entities(_coordinator(None)) == []
    assert web_demand_reason_binary_entities(_coordinator(None)) == []
    assert web_demand_reason_sensor_entities(_coordinator(IdmWebSupplement(web_variant="nav10"))) == []
    assert web_demand_reason_binary_entities(_coordinator(IdmWebSupplement(web_variant="nav20"))) == []


def test_entity_states_follow_the_supplement() -> None:
    coordinator = _coordinator(
        IdmWebSupplement(
            web_variant="nav10",
            demand_reason=evaluate_demand_reason({"homeDetail": {"data": {"10": {"operationMode": 1, "info": 32}}}}),
        )
    )
    sensor = web_demand_reason_sensor_entities(coordinator)[0]
    binary = web_demand_reason_binary_entities(coordinator)[0]

    assert sensor.native_value == "PV"
    assert binary.is_on is True
    assert binary.extra_state_attributes["reason"] == "PV"
    assert binary.extra_state_attributes["pv_bit"] == 32
    assert sensor._attr_unique_id == "test_entry_web_demand_reason"
    assert binary._attr_unique_id == "test_entry_web_demand_reason_pv"

    # A later poll without the extra leaves the entities unavailable.
    coordinator.web_supplement = IdmWebSupplement(web_variant="nav10")
    assert sensor.available is False
    assert binary.available is False
