import logging
import os
import sys
import time

from .reader import VEML6030Reader


def _parse_int(value: str | None, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value, 0)
    except Exception:
        return default


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    bus = _parse_int(os.environ.get("I2C_BUS"), 1)
    address = _parse_int(os.environ.get("I2C_ADDRESS"), 0x48)  # Common default for VEML6030
    timeout_secs = _parse_int(os.environ.get("CHECK_TIMEOUT_SECS"), 3)
    poll_ms = _parse_int(os.environ.get("CHECK_POLL_MS"), 200)

    logging.info("Checking VEML6030 (bus=%s, addr=0x%02X)", bus, address)

    try:
        reader = VEML6030Reader(bus, address)
    except Exception as exc:  # noqa: BLE001
        print(f"VEML6030 connection failed (bus={bus}, addr=0x{address:02X}): {exc}", file=sys.stderr)
        sys.exit(1)

    logging.info("Connected. Polling up to %ss for ambient light...", timeout_secs)
    start = time.monotonic()
    sample = reader.read()
    while time.monotonic() - start < timeout_secs and sample.ambient_lux is None:
        time.sleep(poll_ms / 1000.0)
        sample = reader.read()

    if sample.ambient_lux is not None:
        logging.info("Ambient light ready: lux=%s", sample.ambient_lux)

    print(f"Sample: ambient_lux={sample.ambient_lux}")

    if sample.ambient_lux is None:
        print(
            "Note: Ambient light not ready within "
            f"{timeout_secs}s. Increase CHECK_TIMEOUT_SECS or verify wiring/address.",
            file=sys.stderr,
        )

    sys.exit(0)


if __name__ == "__main__":
    main()
