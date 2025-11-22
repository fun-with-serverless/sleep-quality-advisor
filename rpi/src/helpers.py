from collections.abc import Callable
from typing import Any


def make_multi_sensor_read_sample(
    *read_funcs: Callable[[], dict[str, Any]],
) -> Callable[[], dict[str, Any]]:
    def read_sample() -> dict[str, Any]:
        merged: dict[str, Any] = {}
        for fn in read_funcs:
            try:
                data = fn()
            except Exception:
                data = {}
            if isinstance(data, dict):
                merged.update(data)
        return merged

    return read_sample
