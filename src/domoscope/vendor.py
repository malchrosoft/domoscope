from __future__ import annotations

import urllib.request

from .config import settings

# A small offline OUI table. It covers the devices found in this home lab plus
# common vendors. Unknown OUIs can optionally be looked up online.
OUI_VENDORS: dict[str, str] = {
    "00:11:32": "Synology Incorporated",
    "00:1A:79": "Roku, Inc.",
    "00:1B:63": "Apple, Inc.",
    "00:1E:C2": "Apple, Inc.",
    "00:50:56": "VMware, Inc.",
    "08:D4:0C": "Intel Corporate",
    "0C:37:96": "BIZLINK TECHNOLOGY, INC.",
    "10:D5:61": "Tuya Smart Inc.",
    "18:69:D8": "Tuya Smart Inc.",
    "3C:18:A0": "Realtek Semiconductor Corp.",
    "50:57:9C": "Seiko Epson Corporation",
    "68:57:2D": "Tuya Smart Inc.",
    "68:7F:F0": "TP-Link Systems Inc",
    "70:CF:49": "Intel Corporate",
    "84:E3:42": "Tuya Smart Inc.",
    "9C:EB:E8": "BizLink (Kunshan) Co.,Ltd",
    "B0:BE:76": "TP-Link Systems Inc",
    "C8:D7:78": "BSH Hausgeräte GmbH",
    "E0:DC:FF": "Xiaomi Communications Co Ltd",
    "F0:9F:C2": "Ubiquiti Inc.",
}

_online_cache: dict[str, str | None] = {}


def normalize_mac(mac: str | None) -> str | None:
    if not mac:
        return None
    cleaned = mac.replace("-", ":").replace(".", ":").strip().upper()
    parts = [part.zfill(2) for part in cleaned.split(":") if part]
    if len(parts) != 6:
        return None
    return ":".join(parts)


def oui_of(mac: str | None) -> str | None:
    normalized = normalize_mac(mac)
    if not normalized:
        return None
    return ":".join(normalized.split(":")[:3])


def lookup_vendor(mac: str | None, online: bool | None = None) -> str | None:
    oui = oui_of(mac)
    if not oui:
        return None
    if oui in OUI_VENDORS:
        return OUI_VENDORS[oui]
    use_online = settings.online_lookup if online is None else online
    if not use_online:
        return None
    if oui in _online_cache:
        return _online_cache[oui]
    try:
        with urllib.request.urlopen(f"https://api.macvendors.com/{oui}", timeout=4) as response:
            value = response.read().decode("utf-8", errors="replace").strip()
            _online_cache[oui] = value or None
            return value or None
    except (OSError, ValueError):
        _online_cache[oui] = None
        return None
