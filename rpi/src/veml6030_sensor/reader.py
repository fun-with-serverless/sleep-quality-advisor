from dataclasses import dataclass
from typing import Any

import qwiic_veml6030


@dataclass
class VEML6030Sample:
    ambient_lux: float | None


class VEML6030Reader:
    def __init__(self, _i2c_bus: int, i2c_address: int) -> None:
        self._sensor = qwiic_veml6030.QwiicVEML6030(address=i2c_address)  # type: ignore[attr-defined]
        is_connected = bool(self._sensor.is_connected())
        if not is_connected:
            raise RuntimeError("VEML6030 not detected at the specified address")
        # Initialize sensor
        ok = self._sensor.begin()
        if not ok:
            raise RuntimeError("Failed to initialize VEML6030")

    def _read_lux(self) -> float | None:
        try:
            val: Any = self._sensor.read_light()
            return float(val) if val is not None else None
        except Exception:
            return None

    def read(self) -> VEML6030Sample:
        return VEML6030Sample(ambient_lux=self._read_lux())
