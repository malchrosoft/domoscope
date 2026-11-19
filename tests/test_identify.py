from domoscope.identify import guess_device_type
from domoscope.models import Device


def make_device(**kwargs) -> Device:
    defaults = {"key": "test", "ip": "192.168.0.10"}
    defaults.update(kwargs)
    return Device(**defaults)


def test_tuya_device_by_port():
    device = make_device(open_ports=[6668])
    assert guess_device_type(device) == "Ampoule / prise Tuya"


def test_tuya_device_by_vendor():
    device = make_device(vendor="Tuya Smart Inc.")
    assert guess_device_type(device) == "Ampoule / prise Tuya"


def test_bsh_appliance():
    device = make_device(vendor="BSH Hausgeräte GmbH")
    assert guess_device_type(device) == "Appareil BSH / Home Connect"


def test_printer():
    device = make_device(vendor="Seiko Epson Corporation", open_ports=[631, 9100])
    assert guess_device_type(device) == "Imprimante Epson"


def test_unknown_device():
    device = make_device(open_ports=[])
    assert guess_device_type(device) == "Appareil réseau"


def test_ports_used_for_identification_are_scanned():
    from domoscope.scanner import COMMON_PORTS

    assert {445, 55443} <= set(COMMON_PORTS)
