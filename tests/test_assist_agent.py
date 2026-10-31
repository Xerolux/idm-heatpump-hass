"""Tests for the deterministic local Assist agent."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from homeassistant.components.conversation import ConversationInput

from custom_components.idm_heatpump.assist_agent import (
    IdmHeatpumpConversationEntity,
    _match_language,
    _route_intent,
)
from custom_components.idm_heatpump.conversation import async_setup_entry


def _coordinator(data: dict[str, Any], circuits: list[str] | None = None) -> SimpleNamespace:
    options: dict[str, Any] = {}
    if circuits is not None:
        options["heating_circuits"] = circuits
    return SimpleNamespace(
        data=data,
        config_entry=SimpleNamespace(entry_id="test_entry", options=options),
    )


def _input(text: str, language: str = "de") -> ConversationInput:
    return ConversationInput(text=text, conversation_id="conv1", language=language)


async def _answer(entity: IdmHeatpumpConversationEntity, text: str, language: str = "de") -> str:
    result = await entity.async_process(_input(text, language))
    return str(result.response.speech["plain"])


def test_intent_routing_maps_utterances() -> None:
    assert _route_intent("Warum läuft die Wärmepumpe gerade?") == "why_running"
    assert _route_intent("why is the heat pump running?") == "why_running"
    assert _route_intent("Welche Empfehlung gibt es?") == "recommendation"
    assert _route_intent("any recommendation?") == "recommendation"
    assert _route_intent("Wie ist der Warmwasserzustand?") == "hot_water"
    assert _route_intent("Wie ist die Vorlauftemperatur?") == "temperature"
    assert _route_intent("Wie ist der Stromverbrauch?") == "energy"
    assert _route_intent("Gibt es eine Störung?") == "status"
    assert _route_intent("Hilfe") == "help"
    assert _route_intent("Erzähl mir was über das Wetter in Tokyo") == "help"


def test_language_matching() -> None:
    assert _match_language("de") == "de"
    assert _match_language("de-DE") == "de"
    assert _match_language("en-US") == "en"
    assert _match_language(None) == "en"


async def test_why_running_answers_from_operation_reason() -> None:
    data = {
        "hp_operating_mode": 1,
        "power_consumption_hp": 1.8,
        "outdoor_temp": 2.4,
        "hp_flow_temp": 41.0,
    }
    entity = IdmHeatpumpConversationEntity(_coordinator(data), None)
    answer = await _answer(entity, "Warum läuft die Wärmepumpe gerade?")
    assert isinstance(answer, str) and answer


async def test_why_running_without_data_stays_honest() -> None:
    entity = IdmHeatpumpConversationEntity(_coordinator({}), None)
    answer = await _answer(entity, "Warum läuft die Wärmepumpe?")
    assert "nicht lesen" in answer


async def test_recommendation_lists_advisor_titles() -> None:
    record = SimpleNamespace(
        summary=lambda: {"title": "Heizkurve HK A um 0.02 senken"},
    )
    advisor = SimpleNamespace(active_recommendations=[record])
    entity = IdmHeatpumpConversationEntity(_coordinator({}), advisor)
    answer = await _answer(entity, "Welche Empfehlung gibt es?")
    assert "Heizkurve HK A" in answer


async def test_recommendation_without_advisor() -> None:
    entity = IdmHeatpumpConversationEntity(_coordinator({}), None)
    answer = await _answer(entity, "Empfehlung?")
    assert "keine aktive Empfehlung" in answer


async def test_temperature_answer_contains_values() -> None:
    data = {"outdoor_temp": 3.5, "hp_flow_temp": 40.2, "hp_return_temp": 35.1}
    entity = IdmHeatpumpConversationEntity(_coordinator(data), None)
    answer = await _answer(entity, "Wie ist die Vorlauftemperatur?")
    assert "Außentemperatur: 3,5" in answer or "Außentemperatur: 3.5" in answer
    assert "Vorlauftemperatur: 40,2" in answer or "Vorlauftemperatur: 40.2" in answer
    assert "°C" in answer


async def test_hot_water_answer_is_scoped_to_dhw() -> None:
    data = {"outdoor_temp": 3.5, "dhw_temp_top": 47.0}
    entity = IdmHeatpumpConversationEntity(_coordinator(data), None)
    answer = await _answer(entity, "Wie ist der Warmwasserzustand?")
    assert "47" in answer
    assert "Außentemperatur" not in answer


async def test_energy_answer_contains_power_and_cop() -> None:
    data = {"power_consumption_hp": 2.1, "calculated_cop": 3.8}
    entity = IdmHeatpumpConversationEntity(_coordinator(data), None)
    answer = await _answer(entity, "Wie ist der Verbrauch?")
    assert "kW" in answer
    assert "COP" in answer


async def test_status_answer_explains_operation() -> None:
    data = {"hp_operating_mode": 1, "power_consumption_hp": 1.5}
    entity = IdmHeatpumpConversationEntity(_coordinator(data), None)
    answer = await _answer(entity, "Wie ist der Status?")
    assert isinstance(answer, str) and answer


async def test_unknown_question_returns_help_de_and_en() -> None:
    entity = IdmHeatpumpConversationEntity(_coordinator({}), None)
    german = await _answer(entity, "Erzähl mir einen Witz", "de")
    english = await _answer(entity, "tell me a joke", "en")
    assert "Wärmepumpe" in german
    assert "heat pump" in english


async def test_entity_identity_and_circuits() -> None:
    entity = IdmHeatpumpConversationEntity(_coordinator({}, circuits=["a", "d"]), None)
    assert entity._attr_unique_id == "test_entry_assist_agent"
    assert entity.circuits == ("a", "d")
    assert entity.supported_languages == ["de", "en"]
    fallback = IdmHeatpumpConversationEntity(_coordinator({}), None)
    assert fallback.circuits == ("a",)


async def test_platform_setup_adds_agent() -> None:
    added: list[Any] = []
    coordinator = _coordinator({})
    advisor = SimpleNamespace(active_recommendations=[])
    entry = SimpleNamespace(
        entry_id="test_entry",
        runtime_data=SimpleNamespace(coordinator=coordinator, predictive_advisor=advisor),
    )

    def add_entities(entities: list[Any]) -> None:
        added.extend(entities)

    await async_setup_entry(None, entry, add_entities)
    assert len(added) == 1
    assert isinstance(added[0], IdmHeatpumpConversationEntity)


async def test_fault_query_answers_alarm_and_clean_state() -> None:
    coord_clean = _coordinator({})
    entity_clean = IdmHeatpumpConversationEntity(coord_clean, None)
    ans_clean_de = await _answer(entity_clean, "Gibt es eine Störung?", "de")
    ans_clean_en = await _answer(entity_clean, "Any errors?", "en")
    assert "keine Störung" in ans_clean_de
    assert "no active faults" in ans_clean_en

    coord_alarm = _coordinator({"hp_sum_alarm": 1})
    entity_alarm = IdmHeatpumpConversationEntity(coord_alarm, None)
    ans_alarm_de = await _answer(entity_alarm, "Gibt es eine Störung?", "de")
    ans_alarm_en = await _answer(entity_alarm, "Any faults?", "en")
    assert "Sammelstörung" in ans_alarm_de
    assert "active plant alarm" in ans_alarm_en

    coord_err = _coordinator({"error_number": 42})
    entity_err = IdmHeatpumpConversationEntity(coord_err, None)
    ans_err_de = await _answer(entity_err, "Gibt es einen Fehler?", "de")
    assert "Fehlercode 42" in ans_err_de


async def test_sentinels_and_unused_registers_ignored() -> None:
    data = {
        "outdoor_temp": -1.0,
        "hp_flow_temp": float("nan"),
        "hp_return_temp": 35.0,
    }
    coord = _coordinator(data)
    coord.unused_registers = frozenset({"outdoor_temp"})
    entity = IdmHeatpumpConversationEntity(coord, None)
    ans = await _answer(entity, "Wie sind die Temperaturen?", "de")
    assert "Außentemperatur" not in ans
    assert "Vorlauftemperatur" not in ans
    assert "Rücklauftemperatur: 35 °C" in ans


async def test_why_running_german_translation() -> None:
    data = {
        "hp_operating_mode": 1,
        "power_consumption_hp": 1.5,
    }
    entity = IdmHeatpumpConversationEntity(_coordinator(data), None)
    ans = await _answer(entity, "Warum läuft die Wärmepumpe gerade?", "de")
    assert "Heizen" in ans or "Wärmepumpe" in ans
    assert "The heat pump" not in ans


def test_short_keywords_do_not_falsely_match_substrings() -> None:
    assert _route_intent("is the telescope working?") == "help"
    assert _route_intent("check the statement") == "help"

