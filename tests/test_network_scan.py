"""Tests for the active network scan used by the config flow."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.idm_heatpump import network_scan
from custom_components.idm_heatpump.network_scan import (
    InvalidSubnetError,
    ModbusTcpHost,
    async_get_default_subnet,
    async_scan_modbus_tcp_hosts,
)


def _adapter(
    address="192.168.1.10",
    prefix=24,
    *,
    enabled=True,
    default=True,
):
    return {
        "name": "eth0",
        "enabled": enabled,
        "auto": True,
        "default": default,
        "ipv4": [{"address": address, "network_prefix": prefix}],
        "ipv6": [],
    }


class TestDefaultSubnet:
    async def test_returns_default_routed_enabled_adapter_network(self, monkeypatch):
        adapters = AsyncMock(return_value=[_adapter("10.0.0.5", 24)])
        monkeypatch.setattr(network_scan, "async_get_adapters", adapters)
        assert await async_get_default_subnet(MagicMock()) == "10.0.0.0/24"

    async def test_skips_disabled_and_non_default_adapters(self, monkeypatch):
        adapters = AsyncMock(
            return_value=[
                _adapter("10.0.0.1", 24, enabled=False),
                _adapter("10.0.0.9", 24, default=False),
                _adapter("10.0.0.5", 24),
            ]
        )
        monkeypatch.setattr(network_scan, "async_get_adapters", adapters)
        assert await async_get_default_subnet(MagicMock()) == "10.0.0.0/24"

    async def test_refuses_wide_corporate_networks(self, monkeypatch):
        adapters = AsyncMock(return_value=[_adapter("10.0.0.1", 16)])
        monkeypatch.setattr(network_scan, "async_get_adapters", adapters)
        assert await async_get_default_subnet(MagicMock()) is None

    async def test_skips_incomplete_or_unparsable_adapter_entries(self, monkeypatch):
        adapter = _adapter("192.168.1.10", 24)
        adapter["ipv4"] = [
            {"address": "192.168.1.10"},
            {"network_prefix": 24},
            {"address": "not-an-ip", "network_prefix": 24},
            {"address": "192.168.1.50", "network_prefix": 24},
        ]
        monkeypatch.setattr(network_scan, "async_get_adapters", AsyncMock(return_value=[adapter]))
        assert await async_get_default_subnet(MagicMock()) == "192.168.1.0/24"

    async def test_returns_none_without_usable_adapter(self, monkeypatch):
        monkeypatch.setattr(network_scan, "async_get_adapters", AsyncMock(return_value=[]))
        assert await async_get_default_subnet(MagicMock()) is None

    async def test_returns_none_when_adapter_read_fails(self, monkeypatch):
        async def _boom(_hass):
            raise RuntimeError("no network integration")

        monkeypatch.setattr(network_scan, "async_get_adapters", _boom)
        assert await async_get_default_subnet(MagicMock()) is None


class TestProbe:
    async def test_open_port_is_reported(self, monkeypatch):
        writer = MagicMock()
        writer.wait_closed = AsyncMock()
        connect = AsyncMock(return_value=(MagicMock(), writer))
        monkeypatch.setattr(asyncio, "open_connection", connect)
        assert await network_scan._probe_modbus_port("192.168.1.50", asyncio.Semaphore(1)) is True
        writer.close.assert_called_once()

    async def test_close_errors_after_handshake_do_not_hide_the_hit(self, monkeypatch):
        writer = MagicMock()
        writer.wait_closed = AsyncMock(side_effect=OSError("gone"))
        monkeypatch.setattr(asyncio, "open_connection", AsyncMock(return_value=(MagicMock(), writer)))
        assert await network_scan._probe_modbus_port("192.168.1.50", asyncio.Semaphore(1)) is True

    @pytest.mark.parametrize(
        "error",
        [ConnectionRefusedError, TimeoutError, OSError],
    )
    async def test_unreachable_hosts_are_skipped(self, monkeypatch, error):
        async def _fail(_ip, _port):
            raise error("no")

        monkeypatch.setattr(asyncio, "open_connection", _fail)
        assert await network_scan._probe_modbus_port("192.168.1.50", asyncio.Semaphore(1)) is False


class TestResolveHostname:
    async def test_resolved_name_is_returned(self, monkeypatch):
        loop = asyncio.get_running_loop()
        monkeypatch.setattr(loop, "getnameinfo", AsyncMock(return_value=("wp-keller.fritz.box", "0")))
        assert await network_scan._resolve_hostname("192.168.1.50") == "wp-keller.fritz.box"

    async def test_bare_address_answer_is_treated_as_no_name(self, monkeypatch):
        loop = asyncio.get_running_loop()
        monkeypatch.setattr(loop, "getnameinfo", AsyncMock(return_value=("192.168.1.50", "0")))
        assert await network_scan._resolve_hostname("192.168.1.50") is None

    async def test_empty_name_is_treated_as_no_name(self, monkeypatch):
        loop = asyncio.get_running_loop()
        monkeypatch.setattr(loop, "getnameinfo", AsyncMock(return_value=("", "0")))
        assert await network_scan._resolve_hostname("192.168.1.50") is None

    @pytest.mark.parametrize("error", [TimeoutError, OSError, ValueError])
    async def test_resolver_failures_are_tolerated(self, monkeypatch, error):
        async def _fail(_addr, _flags=0):
            raise error("no")

        monkeypatch.setattr(asyncio.get_running_loop(), "getnameinfo", _fail)
        assert await network_scan._resolve_hostname("192.168.1.50") is None


class TestScanHosts:
    async def test_invalid_subnet_is_rejected(self):
        with pytest.raises(InvalidSubnetError):
            await async_scan_modbus_tcp_hosts("not-a-subnet")

    async def test_oversized_subnet_is_rejected(self):
        with pytest.raises(InvalidSubnetError):
            await async_scan_modbus_tcp_hosts("10.0.0.0/8")

    async def test_largest_allowed_subnet_is_accepted(self, monkeypatch):
        monkeypatch.setattr(network_scan, "_probe_modbus_port", AsyncMock(return_value=False))
        assert await async_scan_modbus_tcp_hosts("10.0.0.0/22") == []

    async def test_open_hosts_are_listed_with_hostnames_in_numeric_order(self, monkeypatch):
        # 192.168.1.6 must list before 192.168.1.10 although a plain string
        # sort would put "192.168.1.10" first.
        open_ips = {"192.168.1.6", "192.168.1.10"}

        async def _probe(ip, _semaphore):
            return ip in open_ips

        async def _resolve(ip):
            return "wp-keller.fritz.box" if ip == "192.168.1.6" else None

        monkeypatch.setattr(network_scan, "_probe_modbus_port", _probe)
        monkeypatch.setattr(network_scan, "_resolve_hostname", _resolve)
        results = await async_scan_modbus_tcp_hosts("192.168.1.0/28")

        assert [host.ip for host in results] == ["192.168.1.6", "192.168.1.10"]
        assert results[0].hostname == "wp-keller.fritz.box"
        assert results[0].label == "192.168.1.6 (wp-keller.fritz.box)"
        assert results[1].hostname is None
        assert results[1].label == "192.168.1.10"


def test_modbus_tcp_host_is_plain_without_hostname():
    assert ModbusTcpHost("192.168.1.50").label == "192.168.1.50"
