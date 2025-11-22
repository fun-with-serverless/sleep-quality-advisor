from collections.abc import Callable
from typing import Any

from .reader import VEML6030Reader


def make_veml6030_read_sample(reader: VEML6030Reader) -> Callable[[], dict[str, Any]]:
    def read_sample() -> dict[str, Any]:
        s = reader.read()
        return {
            "ambient_lux": s.ambient_lux,
        }

    return read_sample
