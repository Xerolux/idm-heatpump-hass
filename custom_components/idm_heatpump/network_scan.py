"""Active network scan for IDM Modbus TCP endpoints during setup.

Why an active scan instead of passive discovery (DHCP/zeroconf):

* DHCP discovery needs Home Assistant to witness a fresh lease land on the
  network. Home routers hand out long leases, and heat pumps are exactly the
  devices installers give a static IP address or a DHCP reservation for —
  a static address never triggers any DHCP event at all.
* The IDM controllers expose no mDNS/SSDP service; their only discoverable
  surface is the Modbus TCP listener on port 502.

The scan therefore probes every host of a user-chosen IPv4 subnet with a
plain TCP connect to the Modbus port. No Modbus bytes are sent: the
connection is closed right after the kernel handshake completes, so a
single-slot Modbus device sees a stray TCP touch, not a competing Modbus
session. The scan only runs when the user explicitly submits the scan form
in the config flow — never automatically.

For every responding host the scan resolves a best-effort reverse-DNS
hostname so the result list can show ``192.168.1.50 (wp-keller.fritz.box)``
next to a bare address. Hosts without a PTR record keep their plain IP.
"""

from __future__ import annotations

import asyncio
import contextlib
import ipaddress
import logging
from dataclasses import dataclass

from homeassistant.components.network import async_get_adapters
from homeassistant.core import HomeAssistant

# IDM Heatpump for Home Assistant
# © 2026 Xerolux — unofficial community integration for IDM Navigator 2.0 / 10 heat pumps
# Created by Xerolux | https://github.com/Xerolux/idm-heatpump-hass
# SPDX-License-Identifier: MIT

_LOGGER = logging.getLogger(__name__)

#: Standard Modbus TCP port the scan probes on every host.
MODBUS_TCP_PORT = 502

#: Per-host connect timeout. A /24 with dead addresses costs one wave of
#: this timeout per 64 concurrent probes; anything slower is not on the LAN.
PROBE_TIMEOUT_SECONDS = 1.0

#: Global concurrency cap so the scan never opens hundreds of sockets at once.
MAX_CONCURRENT_PROBES = 64

#: Soft cap on scanned addresses (/22 = 1022 hosts). Anything wider is not
#: what a home user means by "my LAN" and would take minutes, not seconds.
MAX_HOSTS_PER_SCAN = 1022

#: Best-effort reverse-DNS budget per responding host.
REVERSE_DNS_TIMEOUT_SECONDS = 1.0

#: Refuse to suggest scanning anything wider than /22 as the default subnet.
MIN_SUGGESTED_PREFIX_LENGTH = 22


class InvalidSubnetError(ValueError):
    """Raised when a subnet string cannot be scanned (malformed or too large)."""


@dataclass(frozen=True)
class ModbusTcpHost:
    """One host that accepted a TCP connection on the Modbus port."""

    ip: str
    hostname: str | None = None

    @property
    def label(self) -> str:
        """Human-readable dropdown label: IP plus hostname when known."""
        if self.hostname:
            return f"{self.ip} ({self.hostname})"
        return self.ip


async def async_get_default_subnet(hass: HomeAssistant) -> str | None:
    """Return the default-routed LAN subnet in CIDR notation, or ``None``.

    Walks Home Assistant's network adapter list and turns the first IPv4
    address of the default-routed enabled adapter into a CIDR string. Wide
    corporate networks are refused so the suggestion is always a LAN-sized
    scan. Reading the adapters is best-effort: any failure simply means no
    suggestion and the user types the subnet by hand.
    """
    try:
        adapters = await async_get_adapters(hass)
    except Exception:  # noqa: BLE001 - the suggestion is optional, never gates setup
        _LOGGER.debug("Could not read Home Assistant network adapters for the scan suggestion")
        return None

    for adapter in adapters:
        if not adapter.get("enabled") or not adapter.get("default"):
            continue
        for ipv4 in adapter.get("ipv4", []):
            address = ipv4.get("address")
            prefix = ipv4.get("network_prefix")
            if address is None or prefix is None:
                continue
            try:
                network = ipaddress.IPv4Network(f"{address}/{prefix}", strict=False)
            except ValueError:
                _LOGGER.debug("Ignoring unparsable adapter address %s/%s", address, prefix)
                continue
            if network.prefixlen < MIN_SUGGESTED_PREFIX_LENGTH:
                continue
            return str(network)
    return None


async def _probe_modbus_port(ip: str, semaphore: asyncio.Semaphore) -> bool:
    """Return ``True`` when a TCP connect to ``ip``:502 succeeds.

    No Modbus bytes are sent. The connection is closed immediately after the
    kernel-level handshake completes, so any single-slot Modbus device sees
    a stray TCP touch instead of a competing Modbus session.
    """
    async with semaphore:
        try:
            _reader, writer = await asyncio.wait_for(
                asyncio.open_connection(ip, MODBUS_TCP_PORT),
                timeout=PROBE_TIMEOUT_SECONDS,
            )
        except (TimeoutError, OSError):
            return False
        writer.close()
        with contextlib.suppress(Exception):
            await writer.wait_closed()
        return True


async def _resolve_hostname(ip: str) -> str | None:
    """Resolve the reverse-DNS hostname of ``ip``, best-effort.

    Uses the event loop's ``getnameinfo`` (a resolver thread owned by the
    loop, cancellable through ``wait_for``). Returns ``None`` when there is
    no PTR record, the resolver answers with the bare address, or the lookup
    exceeds its budget.
    """
    try:
        hostname, _service = await asyncio.wait_for(
            asyncio.get_running_loop().getnameinfo((ip, 0)),
            timeout=REVERSE_DNS_TIMEOUT_SECONDS,
        )
    except (TimeoutError, OSError, ValueError):
        return None
    if not hostname or hostname == ip:
        return None
    return hostname


async def async_scan_modbus_tcp_hosts(subnet: str) -> list[ModbusTcpHost]:
    """Scan ``subnet`` for hosts with the Modbus TCP port open.

    Raises :class:`InvalidSubnetError` when ``subnet`` is not a parsable
    IPv4 network or wider than ``MAX_HOSTS_PER_SCAN``. The result is sorted
    by numeric IP address so 192.168.1.6 lists before 192.168.1.10.
    """
    try:
        network = ipaddress.IPv4Network(subnet, strict=False)
    except ValueError as err:
        raise InvalidSubnetError(f"Invalid subnet {subnet!r}: {err}") from err

    if network.num_addresses > MAX_HOSTS_PER_SCAN + 2:
        raise InvalidSubnetError(
            f"Subnet {subnet} has {network.num_addresses} addresses; "
            f"refusing to scan more than {MAX_HOSTS_PER_SCAN}. Use a smaller CIDR (e.g. /24)."
        )

    semaphore = asyncio.Semaphore(MAX_CONCURRENT_PROBES)
    hosts = [str(host) for host in network.hosts()]
    _LOGGER.info("Scanning %d hosts in %s for Modbus TCP endpoints", len(hosts), subnet)

    probe_results = await asyncio.gather(*(_probe_modbus_port(ip, semaphore) for ip in hosts))
    open_hosts = [ip for ip, ok in zip(hosts, probe_results, strict=True) if ok]
    _LOGGER.info("%d host(s) responded on port %d", len(open_hosts), MODBUS_TCP_PORT)

    resolved = await asyncio.gather(*(_resolve_hostname(ip) for ip in open_hosts))
    candidates = [ModbusTcpHost(ip=ip, hostname=hostname) for ip, hostname in zip(open_hosts, resolved, strict=True)]
    candidates.sort(key=lambda host: ipaddress.IPv4Address(host.ip))
    return candidates
