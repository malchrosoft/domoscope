from domoscope.models import Device
from domoscope.reporting import devices_as_csv, devices_as_json, render_report


def test_exports():
    devices = [
        Device(
            id=1,
            key="84:E3:42:E2:B4:E1",
            ip="192.168.0.37",
            mac="84:E3:42:E2:B4:E1",
            vendor="Tuya Smart Inc.",
            device_type="Ampoule / prise Tuya",
            open_ports=[6668],
            tuya_device_id="abc",
            tuya_local_key="secret",
        )
    ]
    payload = devices_as_json(devices)
    assert "192.168.0.37" in payload
    assert "***" in payload  # local key must never be exported in clear

    csv_payload = devices_as_csv(devices)
    assert "192.168.0.37" in csv_payload
    assert "secret" not in csv_payload

    html = render_report(devices, scans=[])
    assert "Domoscope" in html
    assert "192.168.0.37" in html
