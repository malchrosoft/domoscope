from __future__ import annotations

from .discovery import TUYA_PORT
from .models import Device

PORT_LABELS: dict[int, str] = {
    22: "SSH",
    23: "Telnet",
    53: "DNS",
    80: "HTTP",
    139: "NetBIOS",
    443: "HTTPS",
    445: "SMB",
    502: "Modbus",
    515: "LPD",
    631: "IPP",
    1883: "MQTT",
    1982: "Yeelight SSDP",
    3000: "Interface web",
    5000: "Synology DSM",
    5001: "Synology DSM (HTTPS)",
    5357: "WSD",
    6053: "ESPHome",
    TUYA_PORT: "Tuya local",
    8008: "Chromecast",
    8009: "Chromecast",
    8080: "Interface web",
    8081: "Interface web",
    8123: "Home Assistant",
    8443: "HTTPS",
    8888: "SSH / web",
    9000: "Interface web",
    9100: "Impression brute",
    9999: "TP-Link Kasa",
    16021: "Nanoleaf",
    32400: "Plex",
    55443: "Yeelight",
}


def port_labels(ports: list[int]) -> list[str]:
    return [f"{port} ({PORT_LABELS.get(port, 'TCP')})" for port in ports]


def guess_device_type(device: Device) -> str:
    vendor = (device.vendor or "").lower()
    ports = set(device.open_ports)
    services = device.services or {}
    ssdp_servers = " ".join(
        (item.get("server") or "") + " " + (item.get("st") or "")
        for item in services.get("ssdp", [])
    ).lower()

    if "bsh" in vendor or "bosch" in vendor or "siemens" in vendor:
        return "Appareil BSH / Home Connect"
    if "tuya" in vendor or TUYA_PORT in ports or services.get("tuya"):
        return "Ampoule / prise Tuya"
    if "synology" in vendor:
        return "NAS Synology"
    if "epson" in vendor:
        return "Imprimante Epson"
    if 8123 in ports:
        return "Home Assistant"
    if 1883 in ports:
        return "Broker MQTT"
    if 55443 in ports or services.get("yeelight"):
        return "Ampoule Yeelight"
    if 9999 in ports or services.get("kasa"):
        return "Ampoule / prise TP-Link Kasa"
    if services.get("wiz"):
        return "Ampoule WiZ"
    if services.get("lifx"):
        return "Ampoule LIFX"
    if 6053 in ports:
        return "Appareil ESPHome"
    if "tp-link" in vendor and ("internetgatewaydevice" in ssdp_servers or 80 in ports):
        return "Routeur / point d'accès TP-Link"
    if "xiaomi" in vendor:
        return "Appareil Xiaomi"
    if 631 in ports or 9100 in ports or 515 in ports:
        return "Imprimante réseau"
    if 445 in ports or 139 in ports:
        return "PC Windows / partage SMB"
    if 22 in ports:
        return "Machine Linux / SSH"
    if 80 in ports or 443 in ports:
        return "Interface web"
    return "Appareil réseau"


def describe(device: Device) -> str:
    pieces = [device.device_type]
    if device.vendor:
        pieces.append(device.vendor)
    if device.hostname:
        pieces.append(device.hostname)
    return " · ".join(pieces)
