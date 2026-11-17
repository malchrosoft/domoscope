from __future__ import annotations

from typing import Any

from ..config import settings
from ..models import Device
from .base import CommandResult, DriverError

try:  # optional dependency
    import tinytuya
except ImportError:  # pragma: no cover
    tinytuya = None  # type: ignore[assignment]


class TuyaDriver:
    """Local control for Tuya/Smart Life devices (including Superia Milano bulbs).

    Requires the device ID and local key. The key is obtained from the Tuya IoT
    platform or with ``python -m tinytuya wizard``.
    """

    def __init__(self, device: Device) -> None:
        if not device.tuya_device_id or not device.tuya_local_key:
            raise DriverError("Device ID and local key are required for Tuya control")
        if tinytuya is None:
            raise DriverError("tinytuya is not installed. Run: uv sync --extra tuya")
        self.device = device

    def _make(self):
        version_text = self.device.tuya_version or settings.tuya_version or "3.3"
        try:
            version = float(version_text)
        except ValueError:
            version = 3.3
        return tinytuya.BulbDevice(
            self.device.tuya_device_id,
            self.device.ip,
            self.device.tuya_local_key,
            version=version,
        )

    def status(self) -> dict[str, Any]:
        dev = self._make()
        result = dev.status()
        if not isinstance(result, dict) or "Error" in result:
            raise DriverError(str(result))
        return result

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
                current = dev.status()
                dps = current.get("dps", {}) if isinstance(current, dict) else {}
                is_on = bool(dps.get("1"))
                result = dev.turn_off() if is_on else dev.turn_on()
                message = "Basculé"
            elif action == "brightness":
                if brightness is None:
                    raise DriverError("brightness is required")
                result = dev.set_brightness(max(0, min(100, int(brightness))))
                message = f"Luminosité réglée à {brightness}%"
            elif action == "color_temp":
                if color_temp is None:
                    raise DriverError("color_temp is required")
                result = dev.set_colourtemp(max(0, min(100, int(color_temp))))
                message = f"Température réglée à {color_temp}"
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
        if isinstance(result, dict) and "Error" in result:
            return CommandResult(False, str(result.get("Error")))
        state = result if isinstance(result, dict) else {}
        return CommandResult(True, message, state)
