from __future__ import annotations

import socket
import struct
import time
from typing import Any

SSDP_ADDR = "239.255.255.250"
SSDP_PORT = 1900
MDNS_ADDR = "224.0.0.251"
MDNS_PORT = 5353


def _parse_headers(payload: bytes) -> dict[str, list[str]]:
    text = payload.decode("utf-8", errors="replace")
    headers: dict[str, list[str]] = {}
    for line in text.splitlines()[1:]:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        headers.setdefault(key.strip().upper(), []).append(value.strip())
    return headers


def ssdp_discover(local_ip: str, timeout: float = 4.0) -> dict[str, list[dict[str, Any]]]:
    """Send an SSDP M-SEARCH and group replies by source IP."""
    results: dict[str, list[dict[str, Any]]] = {}
    message = (
        "M-SEARCH * HTTP/1.1\r\n"
        f"HOST: {SSDP_ADDR}:{SSDP_PORT}\r\n"
        'MAN: "ssdp:discover"\r\n'
        "MX: 3\r\n"
        "ST: ssdp:all\r\n\r\n"
    ).encode("ascii")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((local_ip, 0))
        sock.settimeout(1.0)
        sock.sendto(message, (SSDP_ADDR, SSDP_PORT))
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                payload, address = sock.recvfrom(65535)
            except TimeoutError:
                continue
            headers = _parse_headers(payload)
            if not headers:
                continue
            entry = {
                "server": (headers.get("SERVER") or [""])[0],
                "st": (headers.get("ST") or [""])[0],
                "usn": (headers.get("USN") or [""])[0],
                "location": (headers.get("LOCATION") or [""])[0],
            }
            bucket = results.setdefault(address[0], [])
            key = (entry["st"], entry["usn"])
            if all((item.get("st"), item.get("usn")) != key for item in bucket):
                bucket.append(entry)
    except OSError:
        return results
    finally:
        sock.close()
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


def _broadcast_request(
    local_ip: str,
    broadcast: str,
    port: int,
    payload: bytes,
    timeout: float = 3.0,
) -> list[tuple[str, bytes]]:
    replies: list[tuple[str, bytes]] = []
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.bind((local_ip, 0))
        sock.settimeout(1.0)
        for target in {broadcast, "255.255.255.255"}:
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


def kasa_discover(local_ip: str, broadcast: str, timeout: float = 3.0) -> list[str]:
    payload = b'{"system":{"get_sysinfo":{}}}'
    return sorted({ip for ip, _ in _broadcast_request(local_ip, broadcast, 9999, payload, timeout)})


def wiz_discover(local_ip: str, broadcast: str, timeout: float = 3.0) -> list[str]:
    payload = b'{"method":"getPilot","params":{}}'
    return sorted({ip for ip, _ in _broadcast_request(local_ip, broadcast, 38899, payload, timeout)})


def lifx_discover(local_ip: str, broadcast: str, timeout: float = 3.0) -> list[str]:
    # LIFX GetService packet: 36 bytes.
    payload = bytes.fromhex("24000004010000000000000000000000000000000000020000")
    return sorted({ip for ip, _ in _broadcast_request(local_ip, broadcast, 56700, payload, timeout)})


def miio_discover(local_ip: str, broadcast: str, timeout: float = 3.0) -> list[str]:
    payload = bytes([0x21, 0x31, 0x00, 0x20] + [0xFF] * 28)
    return sorted({ip for ip, _ in _broadcast_request(local_ip, broadcast, 54321, payload, timeout)})


def yeelight_discover(local_ip: str, broadcast: str, timeout: float = 3.0) -> dict[str, dict[str, str]]:
    message = (
        "M-SEARCH * HTTP/1.1\r\n"
        f"HOST: {SSDP_ADDR}:1982\r\n"
        'MAN: "ssdp:discover"\r\n'
        "ST: wifi_bulb\r\n\r\n"
    ).encode("ascii")
    replies: dict[str, dict[str, str]] = {}
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((local_ip, 0))
        sock.settimeout(1.0)
        sock.sendto(message, (SSDP_ADDR, 1982))
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                payload, address = sock.recvfrom(65535)
            except TimeoutError:
                continue
            headers = _parse_headers(payload)
            replies[address[0]] = {
                "location": (headers.get("LOCATION") or [""])[0],
                "model": (headers.get("MODEL") or [""])[0],
                "support": (headers.get("SUPPORT") or [""])[0],
            }
    except OSError:
        pass
    finally:
        sock.close()
    return replies


def tuya_discover(local_ip: str, broadcast: str, timeout: float = 3.0) -> list[str]:
    payload = bytes.fromhex("000055aa000000000000000900000000")
    return sorted({ip for ip, _ in _broadcast_request(local_ip, broadcast, 6666, payload, timeout)})


def summarize_services(device_services: dict[str, Any]) -> list[str]:
    """Human-readable services for the UI/report."""
    labels: list[str] = []
    for item in device_services.get("ssdp", []):
        server = item.get("server")
        st = item.get("st")
        if server:
            labels.append(f"UPnP: {server}")
        elif st:
            labels.append(f"UPnP: {st}")
    for service in device_services.get("mdns", []):
        labels.append(f"mDNS: {service}")
    for key in ("tuya", "kasa", "wiz", "lifx", "miio", "yeelight"):
        if device_services.get(key):
            labels.append(key.upper())
    return sorted(set(labels))
