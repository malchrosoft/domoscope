from domoscope.db import Database
from domoscope.models import Device


def test_scan_keeps_manual_edits(tmp_path):
    db = Database(tmp_path / "test.db")
    db.init()
    device_id, _ = db.upsert_device(Device(key="AA", ip="192.168.0.10", hostname="esp-1234"))

    db.update_device(device_id, hostname="Salon", device_type="Ampoule salon", notes="")
    db.upsert_device(Device(key="AA", ip="192.168.0.11", hostname="esp-1234", device_type="Interface web"))

    device = db.get_device(device_id)
    assert (device.hostname, device.device_type, device.ip) == ("Salon", "Ampoule salon", "192.168.0.11")


def test_unchanged_prefilled_form_does_not_freeze_detected_values(tmp_path):
    db = Database(tmp_path / "test.db")
    db.init()
    device_id, _ = db.upsert_device(Device(key="AA", ip="192.168.0.10", hostname="esp-1234"))

    db.update_device(device_id, hostname="esp-1234", device_type="Appareil réseau", notes="note")
    db.upsert_device(Device(key="AA", ip="192.168.0.10", hostname="esp-5678", device_type="Interface web"))

    device = db.get_device(device_id)
    assert (device.hostname, device.device_type) == ("esp-5678", "Interface web")


def test_init_migrates_database_without_manual_fields(tmp_path):
    import sqlite3

    path = tmp_path / "old.db"
    with sqlite3.connect(path) as con:
        con.execute(
            "CREATE TABLE devices (id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT NOT NULL UNIQUE, "
            "ip TEXT NOT NULL, mac TEXT, hostname TEXT, vendor TEXT, device_type TEXT NOT NULL "
            "DEFAULT 'Appareil réseau', open_ports TEXT NOT NULL DEFAULT '[]', services TEXT NOT NULL "
            "DEFAULT '{}', sources TEXT NOT NULL DEFAULT '[]', first_seen TEXT NOT NULL, last_seen "
            "TEXT NOT NULL, notes TEXT NOT NULL DEFAULT '', tuya_device_id TEXT, tuya_local_key_enc "
            "TEXT, tuya_version TEXT)"
        )
        con.execute("INSERT INTO devices (key, ip, first_seen, last_seen) VALUES ('AA', '1.2.3.4', 'x', 'x')")
    con.close()

    db = Database(path)
    db.init()
    db.init()  # idempotent

    assert db.update_device(1, hostname="Salon", notes="").hostname == "Salon"
