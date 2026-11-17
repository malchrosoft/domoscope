from domoscope.vendor import lookup_vendor, normalize_mac, oui_of


def test_normalize_mac():
    assert normalize_mac("84-e3-42-e2-b4-e1") == "84:E3:42:E2:B4:E1"
    assert normalize_mac("84:e3:42:e2:b4:e1") == "84:E3:42:E2:B4:E1"
    assert normalize_mac("not-a-mac") is None


def test_oui_and_vendor():
    assert oui_of("84:E3:42:E2:B4:E1") == "84:E3:42"
    assert lookup_vendor("84:E3:42:E2:B4:E1", online=False) == "Tuya Smart Inc."
    assert lookup_vendor("C8:D7:78:33:C9:2E", online=False) == "BSH Hausgeräte GmbH"
    assert lookup_vendor("00:00:00:00:00:00", online=False) is None
