import logging
import os
from typing import Final

_LED_BASE: Final[str] = "/sys/class/leds/PWR"


def _write_sysfs(path: str, value: str) -> bool:
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(value)
        return True
    except Exception as exc:
        logging.debug("LED write failed: %s -> %s (%s)", path, value, exc)
        return False


class LedController:
    """PWR LED controller (Pi 3B+).

    - OFF: trigger=none, brightness=0
    - BLINK: trigger=timer, configure delay_on/off (ms)
    - Graceful: never raises; returns bool for success.
    """

    def __init__(self, blink_on_ms: int, blink_off_ms: int) -> None:
        self._blink_on_ms = max(0, int(blink_on_ms))
        self._blink_off_ms = max(0, int(blink_off_ms))
        self._base = _LED_BASE
        self._available = os.path.isdir(self._base)
        self._warned_unavailable = False

    def _path(self, name: str) -> str:
        return os.path.join(self._base, name)

    def _ensure_available(self) -> bool:
        if self._available and os.path.exists(self._path("trigger")):
            return True
        if not self._warned_unavailable:
            logging.debug("PWR LED sysfs not available at %s", self._base)
            self._warned_unavailable = True
        return False

    def off(self) -> bool:
        """Turn LED off. Returns True if writes succeeded."""
        if not self._ensure_available():
            return False
        ok1 = _write_sysfs(self._path("trigger"), "none")
        ok2 = _write_sysfs(self._path("brightness"), "0")
        return bool(ok1 and ok2)

    def blink(self) -> bool:
        """Enable kernel timer blinking with configured timings. Returns True if writes succeeded."""
        if not self._ensure_available():
            return False
        ok1 = _write_sysfs(self._path("trigger"), "timer")
        ok2 = _write_sysfs(self._path("delay_on"), str(self._blink_on_ms))
        ok3 = _write_sysfs(self._path("delay_off"), str(self._blink_off_ms))
        return bool(ok1 and ok2 and ok3)
