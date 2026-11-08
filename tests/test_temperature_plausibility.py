"""Tests for the shared uninitialized-temperature guard (#668)."""

from __future__ import annotations

import math

from custom_components.idm_heatpump.temperature_plausibility import (
    UNINITIALIZED_TEMPERATURE_C,
    is_uninitialized_temperature,
)


def test_band_covers_observed_field_values():
    # Observed on Navigator 2.0 register 1364 without a wired room sensor
    # (#504: -327.33, #668: -327.22); scaled INT16 minimum is -327.68.
    assert is_uninitialized_temperature(-327.33)
    assert is_uninitialized_temperature(-327.22)
    assert is_uninitialized_temperature(-327.68)
    assert is_uninitialized_temperature(UNINITIALIZED_TEMPERATURE_C)


def test_realistic_temperatures_are_measurements():
    assert not is_uninitialized_temperature(-25.0)
    assert not is_uninitialized_temperature(0.0)
    assert not is_uninitialized_temperature(21.4)
    assert not is_uninitialized_temperature(130.0)


def test_out_of_band_but_not_memory_stays_a_reading():
    # -60 °C is impossible for a heat pump but is not uninitialized memory;
    # plausibility checks must still observe it.
    assert not is_uninitialized_temperature(-60.0)
    assert not is_uninitialized_temperature(327.0)


def test_non_numeric_and_non_finite_inputs():
    assert not is_uninitialized_temperature(None)
    assert not is_uninitialized_temperature("cold")
    assert not is_uninitialized_temperature(True)
    assert not is_uninitialized_temperature(float("nan"))
    assert not is_uninitialized_temperature(float("-inf"))
    assert is_uninitialized_temperature(-327.22) is True
    assert math.isfinite(UNINITIALIZED_TEMPERATURE_C)
