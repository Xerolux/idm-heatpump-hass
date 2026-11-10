"""Tests for passive request-level Modbus transport metrics (0.27/WP1)."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from idm_heatpump import (
    IdmConnectionError,
    IdmDeviceError,
    IdmTransportError,
    IllegalAddressError,
)
from idm_heatpump.transport import IdmModbusTransport

from custom_components.idm_heatpump.coordinator import IdmCoordinator
from custom_components.idm_heatpump.modbus_client import IdmModbusConnectionClient
from custom_components.idm_heatpump.modbus_transport import (
    ModbusTcpEndpoint,
    ModbusTransportCapabilities,
)
from custom_components.idm_heatpump.request_metrics import (
    REQUEST_METRICS_WINDOW_SIZE,
    RequestMetricsRecorder,
    RequestMetricsTransport,
    _classify_error,
)

_ENDPOINT = ModbusTcpEndpoint("192.0.2.10", 502, 1, 10.0, 3)


class InnerTransport:
    """Configurable transport double: answers or raises per function code."""

    capabilities = ModbusTransportCapabilities(source="test", owns_socket=True)
    connects_lazily = True

    def __init__(self) -> None:
        self.connected = True
        self.connect_calls = 0
        self.close_calls = 0
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.errors: dict[str, Exception] = {}

    @property
    def endpoint(self) -> ModbusTcpEndpoint:
        return _ENDPOINT

    async def connect(self) -> None:
        self.connect_calls += 1

    async def close(self) -> None:
        self.close_calls += 1

    async def read_holding_registers(self, *, address: int, count: int) -> list[int]:
        self.calls.append(("fc03", {"address": address, "count": count}))
        if error := self.errors.get("fc03"):
            raise error
        return [address + offset for offset in range(count)]

    async def read_input_registers(self, *, address: int, count: int) -> list[int]:
        self.calls.append(("fc04", {"address": address, "count": count}))
        if error := self.errors.get("fc04"):
            raise error
        return [0x1000 + address + offset for offset in range(count)]

    async def write_registers(self, *, address: int, values: list[int]) -> None:
        self.calls.append(("fc16", {"address": address, "count": len(values)}))
        if error := self.errors.get("fc16"):
            raise error

    async def read_coils(self, *, address: int, count: int) -> list[bool]:
        self.calls.append(("fc01", {"address": address, "count": count}))
        if error := self.errors.get("fc01"):
            raise error
        return [True] * count

    async def write_coil(self, *, address: int, value: bool) -> None:
        self.calls.append(("fc05", {"address": address, "count": 1}))
        if error := self.errors.get("fc05"):
            raise error

    def as_redacted_diagnostics(self) -> dict[str, object]:
        return {"endpoint": {"host": "**REDACTED**"}, "connected": self.connected}


class TestRecorder:
    def test_empty_snapshot_names_the_window_without_samples(self) -> None:
        snapshot = RequestMetricsRecorder().snapshot()

        assert snapshot == {"window_size": REQUEST_METRICS_WINDOW_SIZE, "requests_recorded": 0}

    def test_window_size_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="window_size"):
            RequestMetricsRecorder(0)

    def test_records_drop_out_of_the_bounded_window(self) -> None:
        recorder = RequestMetricsRecorder(window_size=3)
        for index in range(5):
            recorder.record("fc04", 2, 0.1 * (index + 1))

        assert len(recorder) == 3
        snapshot = recorder.snapshot()
        assert snapshot["requests_recorded"] == 3
        # Only the last three durations (0.3, 0.4, 0.5) remain in the window.
        assert snapshot["duration_seconds"]["min"] == pytest.approx(0.3, abs=1e-6)
        assert snapshot["duration_seconds"]["max"] == pytest.approx(0.5, abs=1e-6)

    def test_snapshot_aggregates_outcomes_and_function_codes(self) -> None:
        recorder = RequestMetricsRecorder()
        recorder.record("fc03", 10, 0.2)
        recorder.record("fc03", 10, 0.4)
        recorder.record("fc04", 20, 0.1, "timeout")
        recorder.record("fc16", 4, 0.3, "device_error")

        snapshot = recorder.snapshot()

        assert snapshot["requests_recorded"] == 4
        assert snapshot["outcomes"] == {"device_error": 1, "success": 2, "timeout": 1}
        assert snapshot["duration_seconds"]["median"] == pytest.approx(0.2, abs=1e-6)
        assert snapshot["duration_seconds"]["average"] == pytest.approx(0.25, abs=1e-6)
        assert snapshot["duration_seconds"]["p95"] == pytest.approx(0.4, abs=1e-6)
        by_code = snapshot["by_function_code"]
        assert by_code["fc03"]["requests"] == 2
        assert by_code["fc03"]["registers"] == 20
        assert by_code["fc03"]["errors"] == 0
        assert by_code["fc04"]["errors"] == 1
        assert by_code["fc16"]["errors"] == 1
        assert by_code["fc03"]["label"] == "read holding registers (FC03)"
        assert snapshot["function_codes"] == ["fc03", "fc04", "fc16"]

    def test_median_is_none_without_samples(self) -> None:
        assert RequestMetricsRecorder().median_duration_seconds() is None

    def test_median_over_even_window_interpolates_by_nearest_rank(self) -> None:
        recorder = RequestMetricsRecorder()
        for duration in (0.1, 0.2, 0.3, 0.4):
            recorder.record("fc04", 1, duration)

        assert recorder.median_duration_seconds() == pytest.approx(0.2, abs=1e-6)


class TestErrorClassification:
    @pytest.mark.parametrize(
        ("error", "expected"),
        [
            (IllegalAddressError("exception_code=2"), "illegal_address"),
            (IdmDeviceError("exception_code=5", exception_code=5), "device_error"),
            (TimeoutError("too slow"), "timeout"),
            (IdmConnectionError("refused"), "connection_error"),
            (IdmTransportError("desync"), "transport_error"),
            (RuntimeError("unexpected"), "other_error"),
        ],
    )
    def test_classes_mirror_the_transport_translation(self, error: Exception, expected: str) -> None:
        assert _classify_error(error) == expected

    def test_illegal_address_wins_over_device_error_parent(self) -> None:
        assert issubclass(IllegalAddressError, IdmDeviceError)
        assert _classify_error(IllegalAddressError("x")) == "illegal_address"


class TestRequestMetricsTransport:
    def _wrapped(self) -> tuple[RequestMetricsTransport, InnerTransport]:
        inner = InnerTransport()
        return RequestMetricsTransport(inner), inner

    def test_satisfies_the_api_transport_protocol(self) -> None:
        assert isinstance(self._wrapped()[0], IdmModbusTransport)

    def test_passthrough_surface_of_the_wrapped_transport(self) -> None:
        wrapper, inner = self._wrapped()

        assert wrapper.endpoint is _ENDPOINT or isinstance(wrapper.endpoint, ModbusTcpEndpoint)
        assert wrapper.connected is inner.connected
        assert wrapper.capabilities is inner.capabilities
        assert wrapper.connects_lazily is True

    def test_lazy_declaration_defaults_to_false_without_the_inner_flag(self) -> None:
        class EagerInner(InnerTransport):
            connects_lazily = False

        wrapper = RequestMetricsTransport(EagerInner())

        assert wrapper.connects_lazily is False

    @pytest.mark.asyncio
    async def test_connect_and_close_delegate_without_recording(self) -> None:
        wrapper, inner = self._wrapped()

        await wrapper.connect()
        await wrapper.close()

        assert inner.connect_calls == 1
        assert inner.close_calls == 1
        assert len(wrapper.request_metrics) == 0

    @pytest.mark.asyncio
    async def test_every_request_method_records_function_code_and_count(self) -> None:
        wrapper, _ = self._wrapped()

        assert await wrapper.read_holding_registers(address=100, count=2) == [100, 101]
        expected_input = [0x1000 + 100 + offset for offset in range(3)]
        assert await wrapper.read_input_registers(address=100, count=3) == expected_input
        await wrapper.write_registers(address=200, values=[1, 2, 3, 4])
        assert await wrapper.read_coils(address=3000, count=5) == [True] * 5
        await wrapper.write_coil(address=3000, value=True)

        snapshot = wrapper.request_metrics_snapshot()
        by_code = snapshot["by_function_code"]
        assert by_code["fc03"]["registers"] == 2
        assert by_code["fc04"]["registers"] == 3
        assert by_code["fc16"]["registers"] == 4
        assert by_code["fc01"]["registers"] == 5
        assert by_code["fc05"]["registers"] == 1
        assert snapshot["outcomes"] == {"success": 5}

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("function", "error", "outcome"),
        [
            ("fc03", IllegalAddressError("exception_code=2"), "illegal_address"),
            ("fc04", TimeoutError("slow"), "timeout"),
            ("fc16", IdmDeviceError("busy", exception_code=6), "device_error"),
            ("fc01", IdmConnectionError("refused"), "connection_error"),
            ("fc05", IdmTransportError("desync"), "transport_error"),
        ],
    )
    async def test_failed_requests_are_classified_and_reraised(
        self, function: str, error: Exception, outcome: str
    ) -> None:
        inner = InnerTransport()
        inner.errors[function] = error
        wrapper = RequestMetricsTransport(inner)

        calls = {
            "fc03": lambda: wrapper.read_holding_registers(address=1, count=1),
            "fc04": lambda: wrapper.read_input_registers(address=1, count=1),
            "fc16": lambda: wrapper.write_registers(address=1, values=[1]),
            "fc01": lambda: wrapper.read_coils(address=1, count=1),
            "fc05": lambda: wrapper.write_coil(address=1, value=True),
        }
        with pytest.raises(type(error)):
            await calls[function]()

        snapshot = wrapper.request_metrics_snapshot()
        assert snapshot["outcomes"] == {outcome: 1}
        assert snapshot["by_function_code"][function]["errors"] == 1
        assert snapshot["duration_seconds"] is not None

    def test_diagnostics_merge_the_inner_payload_with_the_metrics(self) -> None:
        wrapper, _ = self._wrapped()

        diagnostics = wrapper.as_redacted_diagnostics()

        assert diagnostics["endpoint"] == {"host": "**REDACTED**"}
        assert diagnostics["request_metrics"]["requests_recorded"] == 0


class TestClientExposure:
    def _client(self, transport: Any) -> IdmModbusConnectionClient:
        return IdmModbusConnectionClient(
            "192.0.2.10",
            502,
            1,
            10.0,
            3,
            transport=transport,
        )

    def test_wrapped_client_publishes_the_metrics_snapshot(self) -> None:
        wrapper = RequestMetricsTransport(InnerTransport())
        client = self._client(wrapper)

        asyncio.run(wrapper.read_holding_registers(address=100, count=2))

        metrics = client.request_metrics

        assert isinstance(metrics, dict)
        assert metrics["requests_recorded"] == 1

    def test_plain_transport_answers_none(self) -> None:
        client = self._client(InnerTransport())

        assert client.request_metrics is None

    def test_transport_diagnostics_carry_the_metrics_for_the_export(self) -> None:
        client = self._client(RequestMetricsTransport(InnerTransport()))

        diagnostics = client.transport_diagnostics()

        assert "request_metrics" in diagnostics


class TestCoordinatorExposure:
    def test_returns_the_client_snapshot(self, mock_hass, mock_config_entry) -> None:
        client = MagicMock()
        client.read_batch = AsyncMock(return_value={})
        client.request_metrics = {"requests_recorded": 7}
        coordinator = IdmCoordinator(
            hass=mock_hass,
            config_entry=mock_config_entry,
            client=client,
            scan_interval=timedelta(seconds=10),
            sensor_descriptions=[],
            binary_sensor_descriptions=[],
            number_descriptions=[],
            select_descriptions=[],
            switch_descriptions=[],
        )

        assert coordinator.request_metrics == {"requests_recorded": 7}

    def test_clients_without_metrics_answer_an_empty_snapshot(self, mock_hass, mock_config_entry) -> None:
        class PlainClient:
            host = "192.0.2.10"

            read_batch = AsyncMock(return_value={})

        coordinator = IdmCoordinator(
            hass=mock_hass,
            config_entry=mock_config_entry,
            client=PlainClient(),
            scan_interval=timedelta(seconds=10),
            sensor_descriptions=[],
            binary_sensor_descriptions=[],
            number_descriptions=[],
            select_descriptions=[],
            switch_descriptions=[],
        )

        assert coordinator.request_metrics == {}


class TestCommunicationDiagnosticSensor:
    def _coordinator(self, metrics: dict[str, Any]) -> MagicMock:
        coordinator = MagicMock()
        coordinator.request_metrics = metrics
        return coordinator

    def test_entity_list_includes_the_request_metrics_sensor(self) -> None:
        from custom_components.idm_heatpump.sensor import _communication_diagnostic_entities

        keys = {entity.entity_description.key for entity in _communication_diagnostic_entities(self._coordinator({}))}

        assert "modbus_request_metrics" in keys

    def test_state_is_the_median_request_duration(self) -> None:
        from custom_components.idm_heatpump.sensor import _communication_diagnostic_entities

        metrics = {"duration_seconds": {"median": 0.1234}}
        entities = {
            entity.entity_description.key: entity
            for entity in _communication_diagnostic_entities(self._coordinator(metrics))
        }
        sensor = entities["modbus_request_metrics"]

        assert sensor.native_value == 0.1234
        assert sensor.extra_state_attributes is metrics

    def test_state_is_none_without_samples(self) -> None:
        from custom_components.idm_heatpump.sensor import _communication_diagnostic_entities

        entities = {
            entity.entity_description.key: entity
            for entity in _communication_diagnostic_entities(self._coordinator({}))
        }
        sensor = entities["modbus_request_metrics"]

        assert sensor.native_value is None
        assert sensor.extra_state_attributes == {}
        assert sensor.available is True

    def test_existing_failure_sensor_keeps_its_attributes(self) -> None:
        from custom_components.idm_heatpump.sensor import _communication_diagnostic_entities

        statistics = MagicMock()
        statistics.total_polls = 12
        statistics.total_failures = 3
        coordinator = MagicMock()
        coordinator.request_metrics = {}
        coordinator.poll_statistics = statistics
        entities = {entity.entity_description.key: entity for entity in _communication_diagnostic_entities(coordinator)}

        assert entities["modbus_consecutive_failures"].extra_state_attributes == {
            "total_polls": 12,
            "total_failures": 3,
        }
