from __future__ import annotations

from typing import Any

import tinytuya

from ..config import settings
from ..models import Device
from .base import INVALID_KEY, READY, UNREACHABLE, CommandResult, DriverError, Health

# tinytuya error codes meaning the device answered but rejected the local key or protocol version.
_KEY_ERRORS = {"904", "914"}


def classify(response: Any) -> Health:
    """Turn a tinytuya `status()` response into a health status."""
    if not isinstance(response, dict):
        return Health(UNREACHABLE, f"Réponse inattendue : {response!r}")
    if "Error" in response:
        status = INVALID_KEY if str(response.get("Err")) in _KEY_ERRORS else UNREACHABLE
        return Health(status, str(response["Error"]))
    return Health(READY)


class TuyaDriver:
    """Local control for Tuya/Smart Life devices (including Superia Milano bulbs).

    Requires the device ID and local key. The key is obtained from the Tuya IoT
    platform or with ``python -m tinytuya wizard``.
    """

    def __init__(self, device: Device) -> None:
        if not device.tuya_device_id or not device.tuya_local_key:
            raise DriverError("Device ID and local key are required for Tuya control")
        self.device = device

    def _make(self) -> tinytuya.BulbDevice:
        version_text = self.device.tuya_version or settings.tuya_version or "3.3"
        try:
            version = float(version_text)
        except ValueError:
            version = 3.3
        # Short timeouts: tinytuya's defaults (5 tries, 5 s apart) freeze the UI on an offline bulb.
        # Persistent socket: state() then reuses the status() just read instead of asking again.
        return tinytuya.BulbDevice(
            self.device.tuya_device_id,
            self.device.ip,
            self.device.tuya_local_key,
            version=version,
            connection_timeout=3,
            connection_retry_limit=1,
            persist=True,
        )

    def check(self) -> Health:
        """Ask the device for its status: is it reachable, and is the local key still valid?"""
        dev = self._make()
        try:
            health = classify(dev.status())
            if health.status == READY:
                health.state = _bulb_state(dev)
            return health
        except Exception as exc:  # noqa: BLE001 - socket errors surface as exceptions
            return Health(UNREACHABLE, str(exc))
        finally:
            dev.close()

    def command(
        self,
        action: str,
        *,
        brightness: int | None = None,
        color_temp: int | None = None,
        red: int | None = None,
        green: int | None = None,
        blue: int | None = None,
    ) -> CommandResult:
        dev = self._make()
        try:
            if action == "on":
                result = dev.turn_on()
                message = "Allumé"
            elif action == "off":
                result = dev.turn_off()
                message = "Éteint"
            elif action == "toggle":
                is_on = _bulb_state(dev).get("is_on")
                result = dev.turn_off() if is_on else dev.turn_on()
                message = "Éteint" if is_on else "Allumé"
            elif action == "brightness":
                if brightness is None:
                    raise DriverError("brightness is required")
                brightness = max(0, min(100, int(brightness)))
                result = dev.set_brightness_percentage(brightness)
                message = f"Luminosité réglée à {brightness} %"
            elif action == "color_temp":
                if color_temp is None:
                    raise DriverError("color_temp is required")
                color_temp = max(0, min(100, int(color_temp)))
                result = dev.set_colourtemp_percentage(color_temp)
                message = f"Température réglée à {color_temp} %"
            elif action == "color":
                if None in (red, green, blue):
                    raise DriverError("red, green and blue are required")
                result = dev.set_colour(int(red), int(green), int(blue))
                message = f"Couleur réglée à ({red}, {green}, {blue})"
            else:
                raise DriverError(f"Unknown action: {action}")
        except DriverError:
            raise
        except Exception as exc:  # noqa: BLE001 - tinytuya raises various errors
            return CommandResult(False, f"Erreur Tuya: {exc}")
        finally:
            dev.close()
        if isinstance(result, dict) and "Error" in result:
            return CommandResult(False, str(result.get("Error")))
        state = result if isinstance(result, dict) else {}
        return CommandResult(True, message, state)


def _bulb_state(dev: tinytuya.BulbDevice) -> dict[str, Any]:
    """On/off, brightness (%) and colour, read from the bulb's own data points. Missing values are omitted."""
    state = dev.state()
    if not isinstance(state, dict) or "Error" in state:
        return {}
    result: dict[str, Any] = {"is_on": bool(state.get("is_on")), "mode": state.get("mode")}
    for key, read in (
        ("brightness", lambda: round(dev.get_brightness_percentage(state=state))),
        ("colour", lambda: "#{:02x}{:02x}{:02x}".format(*dev.colour_rgb(state=state))),
    ):
        try:
            result[key] = read()
        except (RuntimeError, ValueError, TypeError):
            pass
    return result
