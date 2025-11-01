import logging
import os
import sys
import time

from .reader import BME680Reader


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
    address = _parse_int(os.environ.get("I2C_ADDRESS"), 0x76)
    timeout_secs = _parse_int(os.environ.get("CHECK_TIMEOUT_SECS"), 3)
    poll_ms = _parse_int(os.environ.get("CHECK_POLL_MS"), 200)
    wait_gas_secs = _parse_int(os.environ.get("WAIT_FOR_GAS_STABLE_SECS"), 0)

    logging.info("Checking BME680 (bus=%s, addr=0x%02X)", bus, address)

    try:
        reader = BME680Reader(bus, address)
    except Exception as exc:  # noqa: BLE001
        print(f"BME680 connection failed (bus={bus}, addr=0x{address:02X}): {exc}", file=sys.stderr)
        sys.exit(1)

    logging.info("Connected. Polling up to %ss for T/H/P...", timeout_secs)

    # Poll for temperature/humidity/pressure readiness
    start = time.monotonic()
    sample = reader.read()
    while (
        time.monotonic() - start < timeout_secs
        and sample.temperature_c is None
        and sample.humidity_pct is None
        and sample.pressure_hpa is None
    ):
        time.sleep(poll_ms / 1000.0)
        sample = reader.read()

    # Optionally wait for gas heater stability
    if wait_gas_secs > 0 and not sample.gas_heat_stable:
        logging.info("Waiting up to %ss for gas heater to stabilize...", wait_gas_secs)
        gas_deadline = time.monotonic() + wait_gas_secs
        while time.monotonic() < gas_deadline and not sample.gas_heat_stable:
            time.sleep(poll_ms / 1000.0)
            sample = reader.read()

    if not (sample.temperature_c is None and sample.humidity_pct is None and sample.pressure_hpa is None):
        logging.info(
            "T/H/P ready: temp=%sC hum=%s%% pres=%shPa",
            sample.temperature_c,
            sample.humidity_pct,
            sample.pressure_hpa,
        )

    print(
        "Sample: "
        f"temperature_c={sample.temperature_c} "
        f"humidity_pct={sample.humidity_pct} "
        f"pressure_hpa={sample.pressure_hpa} "
        f"gas_ohms={sample.gas_ohms} "
        f"gas_heat_stable={sample.gas_heat_stable}"
    )

    if sample.temperature_c is None and sample.humidity_pct is None and sample.pressure_hpa is None:
        print(
            "Note: Temperature/humidity/pressure not ready within "
            f"{timeout_secs}s. Increase CHECK_TIMEOUT_SECS or verify wiring/address.",
            file=sys.stderr,
        )
    if wait_gas_secs > 0 and not sample.gas_heat_stable:
        print(
            f"Note: Gas heater did not reach stable state within {wait_gas_secs}s. This is normal during warm-up.",
            file=sys.stderr,
        )

    sys.exit(0)


if __name__ == "__main__":
    main()
