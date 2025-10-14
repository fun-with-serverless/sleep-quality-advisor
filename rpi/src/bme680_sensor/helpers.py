from collections.abc import Callable
from typing import Any

from .reader import BME680Reader


def make_bme680_read_sample(reader: BME680Reader) -> Callable[[], dict[str, Any]]:
    def read_sample() -> dict[str, Any]:
        s = reader.read()
        return {
            "temperature_c": s.temperature_c,
            "humidity_pct": s.humidity_pct,
            "pressure_hpa": s.pressure_hpa,
            "gas_ohms": s.gas_ohms,
            "gas_heat_stable": s.gas_heat_stable,
        }

    return read_sample
