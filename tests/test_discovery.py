from domoscope.discovery import LIFX_GET_SERVICE


def test_lifx_get_service_packet():
    assert len(LIFX_GET_SERVICE) == 36
    assert int.from_bytes(LIFX_GET_SERVICE[:2], "little") == 36  # size field
    assert int.from_bytes(LIFX_GET_SERVICE[32:34], "little") == 2  # GetService


def test_parse_headers_keeps_first_value():
    from domoscope.discovery import _parse_headers

    payload = b"HTTP/1.1 200 OK\r\nServer: Linux UPnP\r\nST: upnp:rootdevice\r\nST: other\r\nno header\r\n"
    assert _parse_headers(payload) == {"SERVER": "Linux UPnP", "ST": "upnp:rootdevice"}


def test_summarize_services():
    from domoscope.discovery import summarize_services

    services = {
        "ssdp": [{"server": "Linux UPnP", "st": "upnp:rootdevice"}],
        "mdns": ["_hap._tcp.local"],
        "tuya": True,
        "yeelight": {"model": "color"},
    }
    assert summarize_services(services) == [
        "TUYA",
        "UPnP : Linux UPnP",
        "UPnP type : upnp:rootdevice",
        "YEELIGHT",
        "mDNS : _hap._tcp.local",
    ]
