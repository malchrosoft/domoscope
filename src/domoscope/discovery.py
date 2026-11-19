from __future__ import annotations

import socket
import struct
import time
from typing import Any

SSDP_ADDR = "239.255.255.250"
SSDP_PORT = 1900
MDNS_ADDR = "224.0.0.251"
MDNS_PORT = 5353
TUYA_PORT = 6668
# LIFX GetService (type 2): 36-byte header, size 0x24, tagged + addressable, protocol 1024.
LIFX_GET_SERVICE = bytes.fromhex("24000034" + "00" * 28 + "02000000")


def _parse_headers(payload: bytes) -> dict[str, str]:
    """First value of each header of an SSDP-style reply."""
    headers: dict[str, str] = {}
    for line in payload.decode("utf-8", errors="replace").splitlines()[1:]:
        key, sep, value = line.partition(":")
        if sep:
            headers.setdefault(key.strip().upper(), value.strip())
    return headers


def _udp_request(
    local_ip: str, targets: set[str], port: int, payload: bytes, timeout: float
) -> list[tuple[str, bytes]]:
    """Send `payload` to each target and collect every reply until `timeout`."""
    replies: list[tuple[str, bytes]] = []
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.bind((local_ip, 0))
        sock.settimeout(1.0)
        for target in targets:
            try:
                sock.sendto(payload, (target, port))
            except OSError:
                pass
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                data, address = sock.recvfrom(65535)
            except TimeoutError:
                continue
            replies.append((address[0], data))
    except OSError:
        pass
    finally:
        sock.close()
    return replies


def ssdp_discover(local_ip: str, timeout: float = 4.0) -> dict[str, list[dict[str, Any]]]:
    """Send an SSDP M-SEARCH and group distinct replies by source IP."""
    results: dict[str, list[dict[str, Any]]] = {}
    message = (
        "M-SEARCH * HTTP/1.1\r\n"
        f"HOST: {SSDP_ADDR}:{SSDP_PORT}\r\n"
        'MAN: "ssdp:discover"\r\n'
        "MX: 3\r\n"
        "ST: ssdp:all\r\n\r\n"
    ).encode("ascii")
    for ip, payload in _udp_request(local_ip, {SSDP_ADDR}, SSDP_PORT, message, timeout):
        headers = _parse_headers(payload)
        if not headers:
            continue
        entry = {name: headers.get(name.upper(), "") for name in ("server", "st", "usn", "location")}
        bucket = results.setdefault(ip, [])
        if all((item["st"], item["usn"]) != (entry["st"], entry["usn"]) for item in bucket):
            bucket.append(entry)
    return results


def _dns_query(name: str, qtype: int = 12, unicast_response: bool = False) -> bytes:
    header = struct.pack("!HHHHHH", 0, 0, 1, 0, 0, 0)
    labels = b"".join(bytes([len(part)]) + part.encode("ascii") for part in name.split("."))
    qclass = 0x8001 if unicast_response else 0x0001
    return header + labels + b"\x00" + struct.pack("!HH", qtype, qclass)


def mdns_discover(local_ip: str, timeout: float = 4.0) -> dict[str, list[str]]:
    """Best-effort mDNS service enumeration."""
    results: dict[str, list[str]] = {}
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("", MDNS_PORT))
        membership = socket.inet_aton(MDNS_ADDR) + socket.inet_aton(local_ip)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, membership)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(local_ip))
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        sock.settimeout(1.0)
        query = _dns_query("_services._dns-sd._udp.local")
        sock.sendto(query, (MDNS_ADDR, MDNS_PORT))
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                payload, address = sock.recvfrom(65535)
            except TimeoutError:
                continue
            text = payload.decode("ascii", errors="replace")
            services = set()
            for token in text.replace("\x00", " ").split():
                if "._tcp.local" in token or "._udp.local" in token:
                    cleaned = token.strip(".,;\"'")
                    if cleaned:
                        services.add(cleaned)
            if services:
                bucket = results.setdefault(address[0], [])
                for service in sorted(services):
                    if service not in bucket:
                        bucket.append(service)
    except OSError:
        return results
    finally:
        sock.close()
    return results


def _broadcast_ips(local_ip: str, broadcast: str, port: int, payload: bytes, timeout: float) -> list[str]:
    replies = _udp_request(local_ip, {broadcast, "255.255.255.255"}, port, payload, timeout)
    return sorted({ip for ip, _ in replies})


def kasa_discover(local_ip: str, broadcast: str, timeout: float = 3.0) -> list[str]:
    return _broadcast_ips(local_ip, broadcast, 9999, b'{"system":{"get_sysinfo":{}}}', timeout)


def wiz_discover(local_ip: str, broadcast: str, timeout: float = 3.0) -> list[str]:
    return _broadcast_ips(local_ip, broadcast, 38899, b'{"method":"getPilot","params":{}}', timeout)


def lifx_discover(local_ip: str, broadcast: str, timeout: float = 3.0) -> list[str]:
    return _broadcast_ips(local_ip, broadcast, 56700, LIFX_GET_SERVICE, timeout)


def miio_discover(local_ip: str, broadcast: str, timeout: float = 3.0) -> list[str]:
    return _broadcast_ips(local_ip, broadcast, 54321, bytes([0x21, 0x31, 0x00, 0x20] + [0xFF] * 28), timeout)


def tuya_discover(local_ip: str, broadcast: str, timeout: float = 3.0) -> list[str]:
    return _broadcast_ips(local_ip, broadcast, 6666, bytes.fromhex("000055aa000000000000000900000000"), timeout)


def yeelight_discover(local_ip: str, broadcast: str, timeout: float = 3.0) -> dict[str, dict[str, str]]:
    message = (
        "M-SEARCH * HTTP/1.1\r\n"
        f"HOST: {SSDP_ADDR}:1982\r\n"
        'MAN: "ssdp:discover"\r\n'
        "ST: wifi_bulb\r\n\r\n"
    ).encode("ascii")
    replies: dict[str, dict[str, str]] = {}
    for ip, payload in _udp_request(local_ip, {SSDP_ADDR}, 1982, message, timeout):
        headers = _parse_headers(payload)
        replies[ip] = {name: headers.get(name.upper(), "") for name in ("location", "model", "support")}
    return replies


# Vendor-specific broadcast probes, keyed by their name in `Device.services`.
BROADCASTERS = {
    "tuya": tuya_discover,
    "kasa": kasa_discover,
    "wiz": wiz_discover,
    "lifx": lifx_discover,
    "miio": miio_discover,
    "yeelight": yeelight_discover,
}


def summarize_services(device_services: dict[str, Any]) -> list[str]:
    """Human-readable services for the UI."""
    labels: set[str] = set()
    for item in device_services.get("ssdp", []):
        if item.get("server"):
            labels.add(f"UPnP : {item['server']}")
        if item.get("st"):
            labels.add(f"UPnP type : {item['st']}")
    labels.update(f"mDNS : {service}" for service in device_services.get("mdns", []))
    labels.update(key.upper() for key in BROADCASTERS if device_services.get(key))
    return sorted(labels)
