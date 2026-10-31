"""Tests for the operation-reason composer (why is the heat pump running)."""

from __future__ import annotations

from custom_components.idm_heatpump.advisor_operation_reason import compose_operation_reason


def test_returns_none_without_mode_and_power() -> None:
    assert compose_operation_reason({}, demand_reason=None) is None
    assert compose_operation_reason({"outdoor_temp": 5.0}, demand_reason=None) is None


def test_off() -> None:
    reason = compose_operation_reason({"hp_operating_mode": 0, "power_consumption_hp": 0.0}, demand_reason=None)
    assert reason is not None
    assert reason.label == "Off"
    assert reason.explanation == "The heat pump is not running."


def test_pv_surplus_wins_over_mode() -> None:
    reason = compose_operation_reason(
        {
            "hp_operating_mode": 4,
            "power_consumption_hp": 2.0,
            "pv_surplus": 1.2,
            "smart_grid_status": 4,
        },
        demand_reason=None,
    )
    assert reason is not None
    assert reason.label == "PV surplus"
    assert reason.details["pv_surplus_kw"] == 1.2


def test_hot_water_from_mode_and_from_temperature() -> None:
    by_mode = compose_operation_reason({"hp_operating_mode": 4, "power_consumption_hp": 1.5}, demand_reason=None)
    assert by_mode is not None and by_mode.label == "Hot water"
    by_temp = compose_operation_reason(
        {"hp_operating_mode": 1, "dhw_temp_top": 41.0, "dhw_setpoint": 48.0, "power_consumption_hp": 1.5},
        demand_reason=None,
    )
    assert by_temp is not None and by_temp.label == "Hot water"
    assert "7.0 K" in by_temp.explanation


def test_requesting_heating_circuit() -> None:
    reason = compose_operation_reason(
        {
            "hp_operating_mode": 1,
            "power_consumption_hp": 2.0,
            "hc_a_setpoint_flow_temp": 32.0,
            "hc_a_flow_temp": 28.7,
            "hc_a_room_temp": 21.5,
            "hc_a_room_setpoint_heat_normal": 22.0,
        },
        demand_reason=None,
        circuits=("a",),
    )
    assert reason is not None
    assert reason.label == "Heating circuit A"
    assert reason.details["flow_setpoint"] == 32.0
    assert "under target" in reason.explanation


def test_web_demand_reason_used_as_fallback() -> None:
    reason = compose_operation_reason({"hp_operating_mode": 1, "power_consumption_hp": 1.0}, demand_reason="Warmwasser")
    assert reason is not None
    assert reason.label == "Warmwasser"
    assert "demand reason" in reason.explanation


def test_idle_web_demand_reason_ignored_when_running() -> None:
    for idle_label in ("Keine Anforderung", "Aus", "System aus"):
        reason = compose_operation_reason(
            {
                "hp_operating_mode": 1,
                "power_consumption_hp": 1.46,
                "hc_a_setpoint_flow_temp": 29.9,
                "hc_a_flow_temp": 30.8,
            },
            demand_reason=idle_label,
            circuits=("a",),
        )
        assert reason is not None
        assert reason.label == "Heating"
        assert reason.mode_label == "Heating"


def test_defrosting_takes_precedence_over_heating_circuit_flow_drop() -> None:
    reason = compose_operation_reason(
        {
            "hp_operating_mode": 8,
            "power_consumption_hp": 1.8,
            "hc_a_setpoint_flow_temp": 32.0,
            "hc_a_flow_temp": 24.5,
        },
        demand_reason="Keine Anforderung",
        circuits=("a",),
    )
    assert reason is not None
    assert reason.label == "Defrosting"
    assert reason.mode_label == "Defrosting"


def test_mode_label_as_last_resort() -> None:
    reason = compose_operation_reason({"hp_operating_mode": 2, "power_consumption_hp": 1.0}, demand_reason=None)
    assert reason is not None
    assert reason.label == "Cooling"
    assert reason.mode_label == "Cooling"


def test_garbage_values_do_not_crash() -> None:
    reason = compose_operation_reason(
        {
            "hp_operating_mode": "x",
            "power_consumption_hp": float("nan"),
            "dhw_temp_top": None,
            "hc_a_flow_temp": "warm",
        },
        demand_reason=None,
        circuits=("a",),
    )
    assert reason is None  # neither mode nor a finite power reading


def test_german_web_demand_labels_map_onto_english_vocabulary() -> None:
    """#538: the controller's German web labels must not leak into the state.

    The composer's own labels are English ("Heating circuit A", "PV
    surplus"); the web supplement reports the same causes in the
    controller's German UI wording. Known labels map onto the composer
    vocabulary so the state stops alternating between languages.
    """
    heating = compose_operation_reason(
        {"hp_operating_mode": 1, "power_consumption_hp": 1.2},
        demand_reason="Heizkreis A",
    )
    assert heating is not None and heating.label == "Heating circuit A"
    assert heating.details["demand_reason_raw"] == "Heizkreis A"

    pv = compose_operation_reason(
        {"hp_operating_mode": 1, "power_consumption_hp": 1.2},
        demand_reason="PV",
    )
    assert pv is not None and pv.label == "PV surplus"

    schedule = compose_operation_reason(
        {"hp_operating_mode": 1, "power_consumption_hp": 1.2},
        demand_reason="Zeitprogramm",
    )
    assert schedule is not None and schedule.label == "Schedule"


def test_unknown_web_demand_label_stays_verbatim() -> None:
    """A controller wording the table does not know stays recognizable."""
    unknown = compose_operation_reason(
        {"hp_operating_mode": 1, "power_consumption_hp": 1.2},
        demand_reason="Sonderfall",
    )
    assert unknown is not None and unknown.label == "Sonderfall"


def test_idle_german_web_labels_still_ignored() -> None:
    """The idle suppression (0.23.0-b3) keeps working with the mapping in place."""
    idle = compose_operation_reason(
        {"hp_operating_mode": 1, "power_consumption_hp": 1.2},
        demand_reason="Keine Anforderung",
    )
    assert idle is not None and idle.label != "Keine Anforderung"


def test_defrosting_and_cooling_take_precedence_over_dhw_temperature_delta() -> None:
    """A cool DHW tank during Defrosting (8) or Cooling (2) must not misclassify the mode as Hot water."""
    defrosting = compose_operation_reason(
        {
            "hp_operating_mode": 8,
            "power_consumption_hp": 1.8,
            "dhw_temp_top": 42.0,
            "dhw_setpoint": 50.0,
        },
        demand_reason=None,
    )
    assert defrosting is not None
    assert defrosting.label == "Defrosting"

    cooling = compose_operation_reason(
        {
            "hp_operating_mode": 2,
            "power_consumption_hp": 1.4,
            "dhw_temp_top": 42.0,
            "dhw_setpoint": 50.0,
        },
        demand_reason=None,
    )
    assert cooling is not None
    assert cooling.label == "Cooling"


def test_dhw_mode_above_setpoint_never_emits_negative_shortfall() -> None:
    """When mode == 4 and dhw_temp >= dhw_setpoint (e.g. legionella/boost), explanation has no negative K."""
    reason = compose_operation_reason(
        {
            "hp_operating_mode": 4,
            "power_consumption_hp": 2.1,
            "dhw_temp_top": 52.0,
            "dhw_setpoint": 48.0,
        },
        demand_reason=None,
    )
    assert reason is not None
    assert reason.label == "Hot water"
    assert "below setpoint" not in reason.explanation
    assert "-4.0 K" not in reason.explanation


def test_operation_reason_german_language() -> None:
    off = compose_operation_reason({"hp_operating_mode": 0, "power_consumption_hp": 0.0}, demand_reason=None, language="de")
    assert off is not None
    assert off.label == "Aus"
    assert "Die Wärmepumpe läuft nicht." in off.explanation

    heating = compose_operation_reason(
        {
            "hp_operating_mode": 1,
            "power_consumption_hp": 1.5,
            "hc_a_setpoint_flow_temp": 40.0,
            "hc_a_flow_temp": 35.0,
            "hc_a_room_setpoint_heat_normal": 22.0,
            "hc_a_room_temp": 20.0,
        },
        demand_reason=None,
        language="de",
    )
    assert heating is not None
    assert heating.label == "Heizkreis A"
    assert "Heizkreis A fordert Wärme an" in heating.explanation
    assert "2.0 K unter dem Soll" in heating.explanation


def test_operation_reason_unused_registers_and_sentinels() -> None:
    # If room temp is -1.0 (disconnected sensor), do not say room is 22 K under target
    reason = compose_operation_reason(
        {
            "hp_operating_mode": 1,
            "power_consumption_hp": 1.5,
            "hc_a_setpoint_flow_temp": 40.0,
            "hc_a_flow_temp": 35.0,
            "hc_a_room_setpoint_heat_normal": 21.0,
            "hc_a_room_temp": -1.0,
        },
        demand_reason=None,
    )
    assert reason is not None
    assert reason.label == "Heating circuit A"
    assert "under target" not in reason.explanation

