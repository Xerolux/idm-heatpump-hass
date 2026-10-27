"""Tests for the shared COP-sample plausibility guard (#610)."""

from __future__ import annotations

from custom_components.idm_heatpump.cop_plausibility import (
    MAX_COP,
    MAX_POWER_KW,
    cop_interval_is_plausible,
)


def test_accepts_a_plausible_interval() -> None:
    assert cop_interval_is_plausible(thermal=4.0, electric=1.0) is True
    assert cop_interval_is_plausible(thermal=4.0, electric=1.0, electric_kw=2.0) is True


def test_rejects_non_positive_energy() -> None:
    assert cop_interval_is_plausible(thermal=4.0, electric=0.0) is False
    assert cop_interval_is_plausible(thermal=4.0, electric=-1.0) is False
    assert cop_interval_is_plausible(thermal=0.0, electric=1.0) is False
    assert cop_interval_is_plausible(thermal=-1.0, electric=1.0) is False


def test_rejects_implausible_cop() -> None:
    assert cop_interval_is_plausible(thermal=MAX_COP + 0.1, electric=1.0) is False
    assert cop_interval_is_plausible(thermal=MAX_COP - 0.1, electric=1.0) is True


def test_rejects_implausible_power_when_provided() -> None:
    assert cop_interval_is_plausible(thermal=4.0, electric=1.0, electric_kw=MAX_POWER_KW + 1.0) is False
    assert cop_interval_is_plausible(thermal=4.0, electric=1.0, electric_kw=MAX_POWER_KW - 1.0) is True
    # Without the power bound the interval stays plausible.
    assert cop_interval_is_plausible(thermal=4.0, electric=1.0) is True
