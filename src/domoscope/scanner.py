from __future__ import annotations

import ipaddress
import threading
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Any

from .db import database
from .discovery import BROADCASTERS, TUYA_PORT, mdns_discover, ssdp_discover
from .identify import PORT_LABELS, guess_device_type
from .models import Device, ScanSummary, utc_now
from .network import (
    Network,
    arp_table,
    choose_network,
    netbios_name,
    ping_sweep,
    port_scan,
    reverse_dns,
    sort_ips,
)
from .vendor import lookup_vendor

# Every port the identification heuristics rely on is scanned.
COMMON_PORTS: list[int] = sorted(PORT_LABELS)
IGNORED_MACS = {"FF:FF:FF:FF:FF:FF", "00:00:00:00:00:00"}

# One scan at a time: the startup scan and the UI button share the network and the database.
_scan_lock = threading.Lock()


class Scanner:
    def __init__(self, network: Network | None = None) -> None:
        self.network = network
        self.errors: list[str] = []

    def _discover(self, network: Network) -> dict[str, Any]:
        """Run every discovery protocol in parallel. A failed protocol yields no result."""
        local_ip = network.ip
        broadcast = str(network.network.broadcast_address)
        jobs = {
            "ssdp": partial(ssdp_discover, local_ip),
            "mdns": partial(mdns_discover, local_ip),
            **{name: partial(probe, local_ip, broadcast) for name, probe in BROADCASTERS.items()},
        }
        results: dict[str, Any] = {}
        with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
            futures = {name: pool.submit(job) for name, job in jobs.items()}
            for name, future in futures.items():
                try:
                    results[name] = future.result()
                except Exception as exc:  # noqa: BLE001 - keep the scan alive
                    results[name] = {}
                    self.errors.append(f"{name}: {exc}")
        return results

    def scan(self) -> ScanSummary:
        with _scan_lock:
            return self._scan()

    def _scan(self) -> ScanSummary:
        database.init()
        started = utc_now()
        network = self.network or choose_network()
        self.errors = []

        alive = ping_sweep(network)
        arp = arp_table()
        excluded = {network.network.network_address, network.network.broadcast_address}
        hosts = sort_ips(
            set(alive)
            | {
                ip
                for ip, mac in arp.items()
                if mac.upper() not in IGNORED_MACS and _in_network(ip, network, excluded)
            }
        )

        ports = port_scan(hosts, COMMON_PORTS, timeout=0.8)
        discoveries = self._discover(network)
        created = 0

        for ip in hosts:
            mac = arp.get(ip)
            vendor = lookup_vendor(mac)
            if vendor and "tuya" in vendor.lower() and TUYA_PORT not in ports[ip]:
                # Some Tuya modules accept TCP connections slowly; retry once.
                ports[ip] = sorted({*ports[ip], *port_scan([ip], [TUYA_PORT], timeout=1.5)[ip]})
            services: dict[str, Any] = {
                key: discoveries[key][ip] for key in ("ssdp", "mdns", "yeelight") if discoveries[key].get(ip)
            }
            services.update({key: True for key in BROADCASTERS if key != "yeelight" and ip in discoveries[key]})

            sources = [
                source
                for source, found in (
                    ("ping", ip in alive),
                    ("arp", mac),
                    ("ports", ports[ip]),
                    ("ssdp", "ssdp" in services),
                    ("mdns", "mdns" in services),
                    ("broadcast", any(key in services for key in BROADCASTERS)),
                )
                if found
            ]

            device = Device(
                key=mac or ip,
                ip=ip,
                mac=mac,
                hostname=reverse_dns(ip) or netbios_name(ip),
                vendor=vendor,
                open_ports=ports[ip],
                services=services,
                sources=sources,
            )
            device.device_type = guess_device_type(device)
            created += database.upsert_device(device)[1]

        summary = ScanSummary(
            started_at=started,
            finished_at=utc_now(),
            subnet=str(network.network),
            hosts_alive=len(alive),
            devices_found=len(hosts),
            devices_new=created,
            devices_updated=len(hosts) - created,
            errors=self.errors,
        )
        database.save_scan(summary)
        return summary


def _in_network(ip: str, network: Network, excluded: set) -> bool:
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return address in network.network and address not in excluded
