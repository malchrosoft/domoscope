from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from .config import settings
from .models import Device, ScanSummary, utc_now
from .secrets import secret_box

SCHEMA = """
CREATE TABLE IF NOT EXISTS devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL UNIQUE,
    ip TEXT NOT NULL,
    mac TEXT,
    hostname TEXT,
    vendor TEXT,
    device_type TEXT NOT NULL DEFAULT 'Appareil réseau',
    open_ports TEXT NOT NULL DEFAULT '[]',
    services TEXT NOT NULL DEFAULT '{}',
    sources TEXT NOT NULL DEFAULT '[]',
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    tuya_device_id TEXT,
    tuya_local_key_enc TEXT,
    tuya_version TEXT,
    manual_fields TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS scans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT NOT NULL,
    subnet TEXT NOT NULL,
    hosts_alive INTEGER NOT NULL DEFAULT 0,
    devices_found INTEGER NOT NULL DEFAULT 0,
    devices_new INTEGER NOT NULL DEFAULT 0,
    devices_updated INTEGER NOT NULL DEFAULT 0,
    errors TEXT NOT NULL DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS idx_devices_last_seen ON devices(last_seen);
CREATE INDEX IF NOT EXISTS idx_scans_finished_at ON scans(finished_at);
"""


def _loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def _row_to_device(row: sqlite3.Row) -> Device:
    return Device(
        id=row["id"],
        key=row["key"],
        ip=row["ip"],
        mac=row["mac"],
        hostname=row["hostname"],
        vendor=row["vendor"],
        device_type=row["device_type"],
        open_ports=_loads(row["open_ports"], []),
        services=_loads(row["services"], {}),
        sources=_loads(row["sources"], []),
        first_seen=row["first_seen"],
        last_seen=row["last_seen"],
        notes=row["notes"] or "",
        tuya_device_id=row["tuya_device_id"],
        tuya_local_key=secret_box.decrypt(row["tuya_local_key_enc"]),
        tuya_version=row["tuya_version"],
    )


class Database:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or settings.db_path

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(self.path, timeout=15)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA foreign_keys=ON")
        return con

    def init(self) -> None:
        with closing(self.connect()) as con, con:
            con.executescript(SCHEMA)
            columns = {row["name"] for row in con.execute("PRAGMA table_info(devices)")}
            if "manual_fields" not in columns:
                con.execute("ALTER TABLE devices ADD COLUMN manual_fields TEXT NOT NULL DEFAULT '[]'")

    def upsert_device(self, device: Device) -> tuple[int, bool]:
        """Insert or refresh a device. Returns (id, created)."""
        now = utc_now()
        with closing(self.connect()) as con, con:
            row = con.execute(
                "SELECT id, hostname, device_type, notes, manual_fields "
                "FROM devices WHERE key = ?",
                (device.key,),
            ).fetchone()
            if row is None:
                cur = con.execute(
                    """
                    INSERT INTO devices
                        (key, ip, mac, hostname, vendor, device_type, open_ports, services,
                         sources, first_seen, last_seen, notes, tuya_device_id,
                         tuya_local_key_enc, tuya_version)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        device.key,
                        device.ip,
                        device.mac,
                        device.hostname,
                        device.vendor,
                        device.device_type,
                        json.dumps(device.open_ports),
                        json.dumps(device.services, ensure_ascii=False),
                        json.dumps(device.sources, ensure_ascii=False),
                        device.first_seen or now,
                        now,
                        device.notes or "",
                        device.tuya_device_id,
                        secret_box.encrypt(device.tuya_local_key),
                        device.tuya_version,
                    ),
                )
                return int(cur.lastrowid), True

            # Fields edited by hand in the UI win over what the scan detected.
            manual = set(_loads(row["manual_fields"], []))
            con.execute(
                """
                UPDATE devices SET
                    ip = ?, mac = ?, hostname = ?, vendor = ?, device_type = ?,
                    open_ports = ?, services = ?, sources = ?, last_seen = ?,
                    notes = ?,
                    tuya_device_id = COALESCE(?, tuya_device_id),
                    tuya_local_key_enc = COALESCE(?, tuya_local_key_enc),
                    tuya_version = COALESCE(?, tuya_version)
                WHERE id = ?
                """,
                (
                    device.ip,
                    device.mac,
                    row["hostname"] if "hostname" in manual else device.hostname,
                    device.vendor,
                    row["device_type"] if "device_type" in manual else device.device_type,
                    json.dumps(device.open_ports),
                    json.dumps(device.services, ensure_ascii=False),
                    json.dumps(device.sources, ensure_ascii=False),
                    now,
                    row["notes"] or device.notes or "",
                    device.tuya_device_id,
                    secret_box.encrypt(device.tuya_local_key),
                    device.tuya_version,
                    row["id"],
                ),
            )
            return int(row["id"]), False

    def get_device(self, device_id: int) -> Device | None:
        with closing(self.connect()) as con:
            row = con.execute("SELECT * FROM devices WHERE id = ?", (device_id,)).fetchone()
            return _row_to_device(row) if row else None

    def list_devices(self) -> list[Device]:
        with closing(self.connect()) as con:
            rows = con.execute(
                "SELECT * FROM devices ORDER BY last_seen DESC, ip ASC"
            ).fetchall()
            return [_row_to_device(row) for row in rows]

    def update_device(
        self,
        device_id: int,
        *,
        hostname: str | None = None,
        device_type: str | None = None,
        notes: str | None = None,
        tuya_device_id: str | None = None,
        tuya_local_key: str | None = None,
        tuya_version: str | None = None,
        clear_tuya: bool = False,
    ) -> Device | None:
        existing = self.get_device(device_id)
        if existing is None:
            return None
        # The form is prefilled: only a changed value counts as a manual edit.
        edited = {
            name
            for name, value in (("hostname", hostname), ("device_type", device_type))
            if value and value != getattr(existing, name)
        }
        with closing(self.connect()) as con, con:
            row = con.execute("SELECT manual_fields FROM devices WHERE id = ?", (device_id,)).fetchone()
            manual = set(_loads(row["manual_fields"], [])) | edited
            if clear_tuya:
                con.execute(
                    "UPDATE devices SET tuya_device_id = NULL, tuya_local_key_enc = NULL, "
                    "tuya_version = NULL WHERE id = ?",
                    (device_id,),
                )
            else:
                con.execute(
                    """
                    UPDATE devices SET
                        hostname = COALESCE(?, hostname),
                        device_type = COALESCE(?, device_type),
                        notes = COALESCE(?, notes),
                        tuya_device_id = COALESCE(?, tuya_device_id),
                        tuya_local_key_enc = COALESCE(?, tuya_local_key_enc),
                        tuya_version = COALESCE(?, tuya_version),
                        manual_fields = ?
                    WHERE id = ?
                    """,
                    (
                        hostname,
                        device_type,
                        notes,
                        tuya_device_id,
                        secret_box.encrypt(tuya_local_key),
                        tuya_version,
                        json.dumps(sorted(manual)),
                        device_id,
                    ),
                )
        return self.get_device(device_id)

    def save_scan(self, summary: ScanSummary) -> int:
        with closing(self.connect()) as con, con:
            cur = con.execute(
                """
                INSERT INTO scans
                    (started_at, finished_at, subnet, hosts_alive, devices_found,
                     devices_new, devices_updated, errors)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    summary.started_at,
                    summary.finished_at,
                    summary.subnet,
                    summary.hosts_alive,
                    summary.devices_found,
                    summary.devices_new,
                    summary.devices_updated,
                    json.dumps(summary.errors, ensure_ascii=False),
                ),
            )
            return int(cur.lastrowid)

    def latest_scan(self) -> dict[str, Any] | None:
        return next(iter(self.list_scans(1)), None)

    def list_scans(self, limit: int = 20) -> list[dict[str, Any]]:
        with closing(self.connect()) as con:
            rows = con.execute("SELECT * FROM scans ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
            return [{**row, "errors": _loads(row["errors"], [])} for row in map(dict, rows)]

    def stats(self) -> dict[str, int]:
        with closing(self.connect()) as con:
            total = con.execute("SELECT COUNT(*) AS n FROM devices").fetchone()["n"]
            controllable = con.execute(
                "SELECT COUNT(*) AS n FROM devices WHERE tuya_device_id IS NOT NULL "
                "AND tuya_local_key_enc IS NOT NULL"
            ).fetchone()["n"]
            scans = con.execute("SELECT COUNT(*) AS n FROM scans").fetchone()["n"]
            return {"devices": total, "controllable": controllable, "scans": scans}


database = Database()
