from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass(slots=True)
class Device:
    key: str
    ip: str
    mac: str | None = None
    hostname: str | None = None
    vendor: str | None = None
    device_type: str = "Appareil réseau"
    open_ports: list[int] = field(default_factory=list)
    services: dict[str, Any] = field(default_factory=dict)
    sources: list[str] = field(default_factory=list)
    first_seen: str = field(default_factory=utc_now)
    last_seen: str = field(default_factory=utc_now)
    notes: str = ""
    tuya_device_id: str | None = None
    tuya_local_key: str | None = None
    tuya_version: str | None = None
    id: int | None = None

    @property
    def is_tuya(self) -> bool:
        return bool(self.tuya_device_id and self.tuya_local_key) or 6668 in self.open_ports or (
            "tuya" in (self.vendor or "").lower()
        )

    @property
    def controllable(self) -> bool:
        return bool(self.tuya_device_id and self.tuya_local_key)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "key": self.key,
            "ip": self.ip,
            "mac": self.mac,
            "hostname": self.hostname,
            "vendor": self.vendor,
            "device_type": self.device_type,
            "open_ports": self.open_ports,
            "services": self.services,
            "sources": self.sources,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "notes": self.notes,
            "tuya_device_id": self.tuya_device_id,
            "tuya_local_key": "***" if self.tuya_local_key else None,
            "tuya_version": self.tuya_version,
            "controllable": self.controllable,
        }


@dataclass(slots=True)
class ScanSummary:
    started_at: str
    finished_at: str
    subnet: str
    hosts_alive: int
    devices_found: int
    devices_new: int
    devices_updated: int
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "subnet": self.subnet,
            "hosts_alive": self.hosts_alive,
            "devices_found": self.devices_found,
            "devices_new": self.devices_new,
            "devices_updated": self.devices_updated,
            "errors": self.errors,
        }
