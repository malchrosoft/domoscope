import pytest

from domoscope.drivers import INVALID_KEY, READY, UNREACHABLE
from domoscope.drivers.tuya import classify


@pytest.mark.parametrize(
    ("response", "status"),
    [
        ({"dps": {"20": True}}, READY),
        ({"Error": "Check device key or version", "Err": "914"}, INVALID_KEY),
        ({"Error": "Unexpected Payload from Device", "Err": "904"}, INVALID_KEY),
        ({"Error": "Network Error: Unable to Connect", "Err": "901"}, UNREACHABLE),
        ({"Error": "Network Error: Device Unreachable", "Err": "905"}, UNREACHABLE),
        (None, UNREACHABLE),
    ],
)
def test_classify(response, status):
    assert classify(response).status == status
