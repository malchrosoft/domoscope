from __future__ import annotations

import ipaddress
import math
import platform
import re
import socket
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from .config import settings


@dataclass(slots=True)
class Network:
    interface: str
    ip: str
    netmask: str
    prefix: int
    gateway: str | None
    mac: str | None
    network: ipaddress.IPv4Network

    @property
    def hosts(self) -> list[str]:
        return [str(host) for host in self.network.hosts()]


_VIRTUAL_HINTS = (
    "virtualbox",
    "vbox",
    "vmware",
    "hyper-v",
    "vethernet",
    "loopback",
    "bluetooth",
    "openvpn",
    "tap-windows",
    "wi-fi direct",
    "connexion au réseau local*",
    "media disconnected",
)


def _field(text: str, *patterns: str) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def _clean_interface(header: str) -> str:
    header = header.strip().rstrip(":")
    for prefix in (
        "Carte Ethernet ",
        "Carte réseau sans fil ",
        "Carte inconnue ",
        "Ethernet adapter ",
        "Wireless LAN adapter ",
        "Unknown adapter ",
    ):
        if header.lower().startswith(prefix.lower()):
            header = header[len(prefix) :]
    return header.strip()


def _parse_ipconfig(output: str) -> list[Network]:
    networks: list[Network] = []
    blocks = re.split(r"(?m)^(?=\S.*:\s*$)", output)
    for block in blocks:
        lines = [line for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        header = lines[0].strip()
        if not header.endswith(":") or header.lower().startswith(("configuration", "windows")):
            continue
        ip = _field(block, r"Adresse IPv4[^:]*:\s*([0-9.]+)", r"IPv4 Address[^:]*:\s*([0-9.]+)")
        mask = _field(
            block,
            r"Masque de sous-r[^:]*:\s*([0-9.]+)",
            r"Subnet Mask[^:]*:\s*([0-9.]+)",
        )
        if not ip or not mask:
            continue
        interface = _clean_interface(header)
        if any(hint in interface.lower() for hint in _VIRTUAL_HINTS):
            continue
        gateway = _field(
            block,
            r"Passerelle par d[^:]*:\s*([0-9.]+)",
            r"Default Gateway[^:]*:\s*([0-9.]+)",
        )
        mac = _field(
            block,
            r"Adresse physique[^:]*:\s*([0-9A-Fa-f-]{17})",
            r"Physical Address[^:]*:\s*([0-9A-Fa-f-]{17})",
        )
        try:
            network = ipaddress.ip_network(f"{ip}/{mask}", strict=False)
        except ValueError:
            continue
        networks.append(
            Network(
                interface=interface,
                ip=ip,
                netmask=mask,
                prefix=network.prefixlen,
                gateway=gateway,
                mac=mac,
                network=network,
            )
        )
    return networks


def _parse_linux() -> list[Network]:
    networks: list[Network] = []
    try:
        result = subprocess.run(
            ["ip", "-4", "-o", "addr", "show"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        route = subprocess.run(
            ["ip", "route", "show", "default"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return networks
    gateways = re.findall(r"default via ([0-9.]+)", route)
    gateway = gateways[0] if gateways else None
    for line in result.stdout.splitlines():
        match = re.search(r"\d+:\s+(\S+)\s+inet\s+([0-9.]+)/(\d+)", line)
        if not match:
            continue
        interface, ip, prefix = match.group(1), match.group(2), int(match.group(3))
        if interface.startswith(("lo", "docker", "veth", "virbr", "br-")):
            continue
        network = ipaddress.ip_network(f"{ip}/{prefix}", strict=False)
        networks.append(
            Network(
                interface=interface,
                ip=ip,
                netmask=str(network.netmask),
                prefix=prefix,
                gateway=gateway,
                mac=None,
                network=network,
            )
        )
    return networks


def local_networks() -> list[Network]:
    if platform.system().lower() == "windows":
        try:
            output = subprocess.run(
                ["ipconfig", "/all"],
                capture_output=True,
                text=True,
                encoding="cp850",
                timeout=15,
                check=False,
                errors="replace",
            ).stdout
            return _parse_ipconfig(output)
        except (OSError, subprocess.SubprocessError):
            pass
    return _parse_linux()


def choose_network(subnet: str | None = None) -> Network:
    requested = subnet or settings.subnet
    networks = local_networks()
    if requested:
        try:
            wanted = ipaddress.ip_network(requested, strict=False)
        except ValueError as exc:
            raise ValueError(f"Invalid subnet: {requested}") from exc
        for network in networks:
            if network.network.overlaps(wanted):
                return network
        # The subnet can be forced even if ipconfig did not expose it.
        first_ip = next(wanted.hosts(), None)
        return Network(
            interface="forced",
            ip=str(first_ip) if first_ip else str(wanted.network_address),
            netmask=str(wanted.netmask),
            prefix=wanted.prefixlen,
            gateway=None,
            mac=None,
            network=wanted,
        )
    if not networks:
        raise RuntimeError("No IPv4 network found. Set DOMOSCOPE_SUBNET to override.")
    with_gateway = [network for network in networks if network.gateway]
    return with_gateway[0] if with_gateway else networks[0]


def ping_host(ip: str, timeout_ms: int = 600) -> bool:
    if platform.system().lower() == "windows":
        cmd = ["ping", "-n", "1", "-w", str(timeout_ms), ip]
    else:
        cmd = ["ping", "-c", "1", "-W", str(max(1, math.ceil(timeout_ms / 1000))), ip]
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=max(2, timeout_ms / 1000 + 1),
            check=False,
        )
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def ping_sweep(network: Network, timeout_ms: int = 600, workers: int = 64) -> list[str]:
    hosts = network.hosts
    alive: list[str] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(ping_host, ip, timeout_ms): ip for ip in hosts}
        for future in as_completed(futures):
            if future.result():
                alive.append(futures[future])
    return sorted(alive, key=lambda value: tuple(int(part) for part in value.split(".")))


def arp_table() -> dict[str, str]:
    table: dict[str, str] = {}
    if platform.system().lower() == "windows":
        try:
            output = subprocess.run(
                ["arp", "-a"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
                errors="replace",
            ).stdout
        except (OSError, subprocess.SubprocessError):
            return table
        for line in output.splitlines():
            match = re.search(
                r"([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)\s+([0-9A-Fa-f]{2}(?:-[0-9A-Fa-f]{2}){5})",
                line,
            )
            if match:
                table[match.group(1)] = match.group(2).upper().replace("-", ":")
        return table
    try:
        output = subprocess.run(
            ["ip", "neigh"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return table
    for line in output.splitlines():
        match = re.search(
            r"([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+).*?([0-9a-f]{2}(?::[0-9a-f]{2}){5})",
            line,
            re.IGNORECASE,
        )
        if match:
            table[match.group(1)] = match.group(2).upper()
    return table


def port_scan(hosts: list[str], ports: list[int], timeout: float = 0.35, workers: int = 100) -> dict[str, list[int]]:
    results: dict[str, list[int]] = {host: [] for host in hosts}

    def probe(host: str, port: int) -> tuple[str, int, bool]:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            try:
                return host, port, sock.connect_ex((host, port)) == 0
            except OSError:
                return host, port, False

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(probe, host, port) for host in hosts for port in ports]
        for future in as_completed(futures):
            host, port, is_open = future.result()
            if is_open:
                results[host].append(port)
    for host, open_ports in results.items():
        open_ports.sort()
    return results


def reverse_dns(ip: str) -> str | None:
    try:
        hostname = socket.gethostbyaddr(ip)[0]
        return hostname.rstrip(".") if hostname else None
    except (OSError, socket.herror):
        return None


def netbios_name(ip: str) -> str | None:
    if platform.system().lower() != "windows":
        return None
    try:
        output = subprocess.run(
            ["nbtstat", "-A", ip],
            capture_output=True,
            text=True,
            encoding="cp850",
            timeout=3,
            check=False,
            errors="replace",
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    for line in output.splitlines():
        match = re.search(r"^\s*(\S+)\s+<00>\s+UNIQUE", line)
        if match:
            return match.group(1).strip()
    return None


def local_ip_for_interface(network: Network) -> str:
    return network.ip
