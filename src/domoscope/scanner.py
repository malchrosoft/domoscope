from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any

from . import discovery
from .config import settings
from .db import database
from .identify import guess_device_type
from .models import Device, ScanSummary, utc_now
from .network import (
    Network,
    arp_table,
    choose_network,
    netbios_name,
    ping_sweep,
    port_scan,
    reverse_dns,
)
from .vendor import lookup_vendor

COMMON_PORTS: list[int] = [
    22,
    23,
    53,
    80,
    139,
    443,
    502,
    515,
    631,
    1883,
    1982,
    3000,
    5000,
    5001,
    5357,
    55443,
    6053,
    6668,
    8008,
    8009,
    8080,
    8081,
    8123,
    8443,
    8888,
    9000,
    9100,
    9999,
    16021,
    32400,
]


class Scanner:
    def __init__(self, network: Network | None = None) -> None:
        self.network = network
        self.errors: list[str] = []

    def _discover(self, network: Network) -> dict[str, Any]:
        local_ip = network.ip
        broadcast = str(network.network.broadcast_address)
        results: dict[str, Any] = {
            "ssdp": {},
            "mdns": {},
            "kasa": [],
            "wiz": [],
            "lifx": [],
            "miio": [],
            "yeelight": {},
            "tuya": [],
        }
        jobs = {
            "ssdp": lambda: discovery.ssdp_discover(local_ip),
            "mdns": lambda: discovery.mdns_discover(local_ip),
            "kasa": lambda: discovery.kasa_discover(local_ip, broadcast),
            "wiz": lambda: discovery.wiz_discover(local_ip, broadcast),
            "lifx": lambda: discovery.lifx_discover(local_ip, broadcast),
            "miio": lambda: discovery.miio_discover(local_ip, broadcast),
            "yeelight": lambda: discovery.yeelight_discover(local_ip, broadcast),
            "tuya": lambda: discovery.tuya_discover(local_ip, broadcast),
        }
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = {name: pool.submit(func) for name, func in jobs.items()}
            for name, future in futures.items():
                try:
                    results[name] = future.result()
                except Exception as exc:  # noqa: BLE001 - keep the scan alive
                    self.errors.append(f"{name}: {exc}")
        return results

    def scan(self) -> ScanSummary:
        database.init()
        started = utc_now()
        network = self.network or choose_network()
        self.errors = []

        alive = ping_sweep(network)
        arp = arp_table()
        known = set(alive)
        ignored_macs = {"FF:FF:FF:FF:FF:FF", "00:00:00:00:00:00"}
        for ip, mac in arp.items():
            if ip in {str(network.network.network_address), str(network.network.broadcast_address)}:
                continue
            if mac.upper() in ignored_macs:
                continue
            try:
                if ipaddress_in_network(ip, network):
                    known.add(ip)
            except ValueError:
                continue
        hosts = sorted(known, key=lambda value: tuple(int(part) for part in value.split(".")))

        ports = port_scan(hosts, COMMON_PORTS, timeout=0.8)
        discoveries = self._discover(network)
        created = 0
        updated = 0

        for ip in hosts:
            mac = arp.get(ip)
            vendor = lookup_vendor(mac)
            if vendor and "tuya" in vendor.lower() and 6668 not in ports.get(ip, []):
                # Some Tuya modules accept TCP connections slowly; retry once.
                retry = port_scan([ip], [6668], timeout=1.5)
                if retry.get(ip):
                    ports.setdefault(ip, []).extend(retry[ip])
                    ports[ip] = sorted(set(ports[ip]))
            hostname = reverse_dns(ip) or netbios_name(ip)
            services: dict[str, Any] = {}
            if discoveries["ssdp"].get(ip):
                services["ssdp"] = discoveries["ssdp"][ip]
            if discoveries["mdns"].get(ip):
                services["mdns"] = discoveries["mdns"][ip]
            for key in ("kasa", "wiz", "lifx", "miio", "tuya"):
                if ip in discoveries[key]:
                    services[key] = True
            if discoveries["yeelight"].get(ip):
                services["yeelight"] = discoveries["yeelight"][ip]

            sources = ["ping"] if ip in alive else []
            if mac:
                sources.append("arp")
            if ports.get(ip):
                sources.append("ports")
            if services.get("ssdp"):
                sources.append("ssdp")
            if services.get("mdns"):
                sources.append("mdns")
            if any(services.get(key) for key in ("kasa", "wiz", "lifx", "miio", "tuya", "yeelight")):
                sources.append("broadcast")

            device = Device(
                key=mac or ip,
                ip=ip,
                mac=mac,
                hostname=hostname,
                vendor=vendor,
                open_ports=ports.get(ip, []),
                services=services,
                sources=sources,
            )
            device.device_type = guess_device_type(device)
            _, is_new = database.upsert_device(device)
            created += 1 if is_new else 0
            updated += 0 if is_new else 1

        finished = utc_now()
        summary = ScanSummary(
            started_at=started,
            finished_at=finished,
            subnet=str(network.network),
            hosts_alive=len(alive),
            devices_found=len(hosts),
            devices_new=created,
            devices_updated=updated,
            errors=self.errors,
        )
        database.save_scan(summary)
        return summary


def ipaddress_in_network(ip: str, network: Network) -> bool:
    import ipaddress

    return ipaddress.ip_address(ip) in network.network


def scan_once() -> ScanSummary:
    return Scanner().scan()


def find_controllable_devices() -> list[Device]:
    return [device for device in database.list_devices() if device.controllable]


def settings_hint() -> dict[str, Any]:
    return {
        "subnet": settings.subnet,
        "db": str(settings.db_path),
        "tuya_version": settings.tuya_version,
    }
