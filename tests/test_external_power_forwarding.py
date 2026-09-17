"""Exercise the optional forwarder without writing to a real controller."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.idm_heatpump import external_power_forwarding as module


def _state(value: object, unit: str | None = "kW") -> SimpleNamespace:
    return SimpleNamespace(state=value, attributes={"unit_of_measurement": unit} if unit else {})


def _forwarder(
    states: dict[str, SimpleNamespace], entities: dict[str, str], *, battery_sign: str = "as_is"
) -> tuple[module.ExternalPowerForwarder, MagicMock]:
    hass = MagicMock()
    hass.states.get.side_effect = states.get
    coordinator = MagicMock()
    coordinator.get_register.side_effect = lambda name: SimpleNamespace(
        name=name, writable=True, min_val=0 if name != "battery_discharge" else -20, max_val=100
    )
    coordinator.async_write_register = AsyncMock()
    return (
        module.ExternalPowerForwarder(
            hass,
            coordinator,
            module.ExternalPowerForwardingConfig(entities, 30, battery_sign),
        ),
        coordinator,
    )


@pytest.mark.parametrize(
    ("value", "unit", "expected"),
    [(1000, "W", 1.0), (1, "kW", 1.0), (0.001, "MW", 1.0), (1, None, None), ("unknown", "W", None)],
)
def test_power_conversion(value: object, unit: str | None, expected: float | None) -> None:
    forwarder, _ = _forwarder({}, {})
    assert forwarder._value("pv_production", _state(value, unit)) == expected


def test_soc_and_battery_sign_are_validated() -> None:
    forwarder, _ = _forwarder({}, {}, battery_sign="invert")
    assert forwarder._value("battery_discharge", _state(500, "W")) == -0.5
    assert forwarder._value("battery_soc", _state(75, "%")) == 75.0
    assert forwarder._value("battery_soc", _state(-1, "%")) is None
    assert forwarder._value("battery_soc", _state(75.5, "%")) is None
    assert forwarder._value("battery_soc", _state(101, "%")) is None
    assert forwarder._value("battery_soc", _state("unavailable", "%")) is None
    assert forwarder._value("pv_production", None) is None
    assert module._unit(SimpleNamespace(attributes=None)) is None
    assert module._number(object()) is None
    assert module._soc(50, "kWh") is None


async def test_valid_values_are_forwarded_and_invalid_values_skipped() -> None:
    forwarder, coordinator = _forwarder(
        {"sensor.pv": _state(1500, "W"), "sensor.bad": _state("unknown")},
        {"pv_production": "sensor.pv", "house_consumption": "sensor.bad", "bogus": "sensor.pv"},
    )
    await forwarder.async_forward()
    coordinator.async_write_register.assert_awaited_once()
    assert coordinator.async_write_register.await_args.args[1] == 1.5


async def test_battery_soc_unavailable_sentinel_is_not_written() -> None:
    forwarder, coordinator = _forwarder({"sensor.soc": _state(-1, "%")}, {"battery_soc": "sensor.soc"})
    await forwarder.async_forward()
    coordinator.async_write_register.assert_not_awaited()


async def test_register_guards_and_transport_error(caplog: pytest.LogCaptureFixture) -> None:
    forwarder, coordinator = _forwarder({"sensor.pv": _state(2)}, {"pv_production": "sensor.pv"})
    coordinator.get_register.return_value = None
    coordinator.get_register.side_effect = None
    await forwarder.async_forward()
    coordinator.async_write_register.assert_not_awaited()

    register = SimpleNamespace(name="pv_production", writable=False, min_val=0, max_val=10)
    coordinator.get_register.return_value = register
    await forwarder.async_forward()
    coordinator.async_write_register.assert_not_awaited()

    register.writable = True
    register.max_val = 1
    await forwarder.async_forward()
    coordinator.async_write_register.assert_not_awaited()
    register.max_val = 10
    register.min_val = 3
    await forwarder.async_forward()
    coordinator.async_write_register.assert_not_awaited()

    register.min_val = 0
    coordinator.async_write_register.side_effect = RuntimeError("offline")
    await forwarder.async_forward()
    assert "Could not forward" in caplog.text


async def test_run_cleans_up_listener_on_cancellation(monkeypatch: pytest.MonkeyPatch) -> None:
    forwarder, _ = _forwarder({}, {})
    unsubscribe = MagicMock()
    monkeypatch.setattr(module, "async_track_state_change_event", lambda *_: unsubscribe)
    forwarder.async_forward = AsyncMock()
    task = asyncio.create_task(forwarder.async_run())
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    unsubscribe.assert_called_once()
    forwarder.async_forward.assert_awaited_once()


async def test_state_changes_debounce_to_one_forward() -> None:
    forwarder, _ = _forwarder({}, {})
    forwarder._hass.async_create_task.side_effect = asyncio.create_task
    forwarder.async_forward = AsyncMock()
    forwarder._state_changed(None)
    await asyncio.sleep(0)
    forwarder._state_changed(None)
    await asyncio.sleep(1.1)
    forwarder.async_forward.assert_awaited_once()
    assert forwarder._pending_task is None
