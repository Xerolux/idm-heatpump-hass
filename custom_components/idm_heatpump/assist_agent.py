"""Deterministic local Assist agent answering natural-language plant questions.

The integration ships a ``conversation`` entity so users can ask Home
Assistant's Assist (text or voice) about their heat pump: ``Warum läuft die
Wärmepumpe gerade?``, ``Welche Empfehlung gibt es?``, ``Wie ist der
Warmwasserzustand?``.  Everything is answered locally and deterministically —
keyword routing onto the coordinator snapshot, the operation-reason composer
and the read-only predictive advisor.  No utterance leaves the instance and
no language model is involved.

The answer language follows the conversation language (German or English);
unknown questions get a capability list instead of a guess.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from typing import Any

from homeassistant.components.conversation import (
    ConversationEntity,
    ConversationInput,
    ConversationResult,
)
from homeassistant.helpers import intent

from .advisor_operation_reason import compose_operation_reason
from .const import CONF_HEATING_CIRCUITS
from .entity import IdmCoordinatorEntityBase, build_entity_unique_id
from .predictive_advisor import PredictiveAdvisor

_LOGGER = logging.getLogger(__name__)

#: Keyword routing table: first matching group wins, so the most specific
#: questions (why → recommendation) are checked before the generic status.
_INTENT_KEYWORDS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("warum", "why", "läuft die", "running"), "why_running"),
    (("empfehlung", "empfiehl", "optimier", "recommend", "advice", "optimi"), "recommendation"),
    (("warmwasser", "speicher", "hot water", "dhw", "storage tank"), "hot_water"),
    (
        ("temperatur", "vorlauf", "rücklauf", "außen", "temperature", "flow", "return", "outdoor"),
        "temperature",
    ),
    (("verbrauch", "energie", "cop", "strom", "energy", "consumption", "power"), "energy"),
    (("status", "störung", "fehler", "state", "error", "fault"), "status"),
    (("hilfe", "help", "was kannst du", "what can you"), "help"),
)

_TEMPERATURE_KEYS: tuple[tuple[str, str, str], ...] = (
    ("outdoor_temp", "Außentemperatur", "outdoor temperature"),
    ("hp_flow_temp", "Vorlauftemperatur", "flow temperature"),
    ("hp_return_temp", "Rücklauftemperatur", "return temperature"),
    ("dhw_temp_top", "Warmwassertemperatur", "hot-water temperature"),
)

_HELP_TEXT = {
    "de": (
        "Ich beantworte Fragen zu deiner IDM Wärmepumpe: „Warum läuft die "
        "Wärmepumpe gerade?“, „Welche Empfehlung gibt es?“, „Wie ist der "
        "Warmwasserzustand?“, „Wie sind die Temperaturen?“, „Wie ist der "
        "Verbrauch?“ und „Wie ist der Status?“."
    ),
    "en": (
        'I answer questions about your IDM heat pump: "Why is the heat pump '
        'running?", "Any recommendation?", "How is the hot water?", '
        '"What are the temperatures?", "What is the consumption?" and '
        '"What is the status?".'
    ),
}


def _match_language(language: str | None) -> str:
    """Return the answer language for a conversation language tag."""
    tagged = (language or "").lower()
    return "de" if tagged.startswith("de") else "en"


def _route_intent(utterance: str) -> str:
    """Return the intent id for an utterance (lowercased, punctuation split)."""
    text = re.sub(r"[^\w\s]", " ", utterance.lower())
    for keywords, intent_id in _INTENT_KEYWORDS:
        if any(keyword in text for keyword in keywords):
            return intent_id
    return "help"


def _number(value: Any) -> float | None:
    """Return a plain float for numeric snapshot values."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return round(float(value), 1)
    return None


def _format(value: float) -> str:
    """Render a snapshot number without trailing zeros."""
    text = f"{value:.1f}".rstrip("0").rstrip(".")
    return text if text else "0"


class IdmHeatpumpConversationEntity(IdmCoordinatorEntityBase, ConversationEntity):
    """Assist agent answering plant questions from the local snapshot."""

    _attr_translation_key = "assist_agent"
    _attr_entity_category = None

    @property
    def supported_languages(self) -> list[str]:
        """Return the languages this agent answers in (abstract in HA)."""
        return ["de", "en"]

    def __init__(
        self,
        coordinator: Any,
        advisor: PredictiveAdvisor | None,
    ) -> None:
        """Store the coordinator and the optional read-only advisor."""
        super().__init__(coordinator)
        self._advisor = advisor
        entry_id = (
            coordinator.config_entry.entry_id
            if getattr(coordinator, "config_entry", None) is not None
            else "unknown_entry"
        )
        self._attr_unique_id = build_entity_unique_id(entry_id, "assist_agent")

    @property
    def circuits(self) -> tuple[str, ...]:
        """Return the configured heating circuits for the reason composer."""
        entry = getattr(self.coordinator, "config_entry", None)
        circuits = getattr(entry, "options", {}).get(CONF_HEATING_CIRCUITS)
        if isinstance(circuits, (list, tuple)) and circuits:
            return tuple(str(circuit) for circuit in circuits)
        return ("a",)

    def _answer(self, intent_id: str, language: str) -> str:
        """Compose the deterministic answer for one routed intent."""
        data: Mapping[str, Any] = self.coordinator.data or {}
        if intent_id == "why_running":
            reason = compose_operation_reason(
                data,
                demand_reason=(
                    str(data["web_demand_reason"]) if isinstance(data.get("web_demand_reason"), str) else None
                ),
                circuits=self.circuits,
            )
            if reason is not None:
                return reason.explanation
            return (
                "Ich kann den Betriebszustand gerade nicht lesen."
                if language == "de"
                else "I cannot read the operating state right now."
            )
        if intent_id == "recommendation":
            return self._recommendation_answer(data, language)
        if intent_id == "hot_water":
            return self._temperature_answer(data, language, ("dhw_temp_top",))
        if intent_id == "temperature":
            return self._temperature_answer(data, language, tuple(key for key, _, _ in _TEMPERATURE_KEYS))
        if intent_id == "energy":
            return self._energy_answer(data, language)
        if intent_id == "status":
            return self._status_answer(data, language)
        return _HELP_TEXT[language]

    def _recommendation_answer(self, data: Mapping[str, Any], language: str) -> str:
        advisor = self._advisor
        recommendations = list(getattr(advisor, "active_recommendations", None) or [])
        if not recommendations:
            return (
                "Der predictive Advisor hat im Moment keine aktive Empfehlung."
                if language == "de"
                else "The predictive advisor has no active recommendation right now."
            )
        parts: list[str] = []
        for record in recommendations[:3]:
            summary = record.summary() if callable(getattr(record, "summary", None)) else {}
            title = str(summary.get("title") or getattr(record, "title", ""))
            if title:
                parts.append(title)
        if not parts:
            return (
                "Der predictive Advisor hat Empfehlungen, aber keinen lesbaren Titel."
                if language == "de"
                else "The predictive advisor has recommendations, but no readable title."
            )
        intro = "Aktuelle Empfehlungen:" if language == "de" else "Current recommendations:"
        return f"{intro} " + "; ".join(parts)

    def _temperature_answer(self, data: Mapping[str, Any], language: str, keys: tuple[str, ...]) -> str:
        parts: list[str] = []
        index = {key: (label_de, label_en) for key, label_de, label_en in _TEMPERATURE_KEYS}
        for key in keys:
            value = _number(data.get(key))
            if value is None or key not in index:
                continue
            label_de, label_en = index[key]
            parts.append(f"{label_de if language == 'de' else label_en}: {_format(value)} °C")
        if not parts:
            return (
                "Ich habe gerade keine plausiblen Temperaturen."
                if language == "de"
                else "I have no plausible temperatures right now."
            )
        return "; ".join(parts) + "."

    def _energy_answer(self, data: Mapping[str, Any], language: str) -> str:
        power = _number(data.get("power_consumption_hp"))
        thermal = _number(data.get("thermal_power_flow_sensor"))
        cop = _number(data.get("calculated_cop"))
        parts: list[str] = []
        if power is not None:
            label = "Elektrische Leistung" if language == "de" else "electrical power"
            parts.append(f"{label}: {_format(power)} kW")
        if thermal is not None:
            label = "Thermische Leistung" if language == "de" else "thermal power"
            parts.append(f"{label}: {_format(thermal)} kW")
        if cop is not None and cop > 0:
            parts.append(f"COP: {_format(cop)}")
        if not parts:
            return (
                "Ich habe gerade keine Verbrauchswerte."
                if language == "de"
                else "I have no consumption values right now."
            )
        return "; ".join(parts) + "."

    def _status_answer(self, data: Mapping[str, Any], language: str) -> str:
        mode = data.get("hp_operating_mode")
        mode = mode if isinstance(mode, int) and not isinstance(mode, bool) else None
        if mode is None:
            return (
                "Ich kann den Betriebsmodus gerade nicht lesen."
                if language == "de"
                else "I cannot read the operating mode right now."
            )
        reason = compose_operation_reason(
            data,
            demand_reason=(str(data["web_demand_reason"]) if isinstance(data.get("web_demand_reason"), str) else None),
            circuits=self.circuits,
        )
        if reason is not None:
            return reason.explanation
        label = "Betriebsmodus" if language == "de" else "operating mode"
        return f"{label}: {mode}."

    async def async_process(self, user_input: ConversationInput) -> ConversationResult:
        """Answer one utterance locally from the coordinator snapshot."""
        language = _match_language(getattr(user_input, "language", None))
        utterance = str(getattr(user_input, "text", "") or "")
        intent_id = _route_intent(utterance)
        answer = self._answer(intent_id, language)
        _LOGGER.debug("Assist question routed to %s: %s", intent_id, utterance)
        response = intent.IntentResponse(language=language)
        response.async_set_speech(answer)
        return ConversationResult(
            conversation_id=getattr(user_input, "conversation_id", None),
            response=response,
        )


__all__ = ["IdmHeatpumpConversationEntity"]
