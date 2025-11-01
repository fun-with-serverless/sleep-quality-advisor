import os
import sys

from .reader import BME680Reader


def _parse_int(value: str | None, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value, 0)
    except Exception:
        return default


def main() -> None:
    bus = _parse_int(os.environ.get("I2C_BUS"), 1)
    address = _parse_int(os.environ.get("I2C_ADDRESS"), 0x76)

    try:
        reader = BME680Reader(bus, address)
        sample = reader.read()
    except Exception as exc:  # noqa: BLE001
        print(f"BME680 connection failed (bus={bus}, addr=0x{address:02X}): {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"BME680 connected (bus={bus}, addr=0x{address:02X}).")
    print(
        "Sample: "
        f"temperature_c={sample.temperature_c} "
        f"humidity_pct={sample.humidity_pct} "
        f"pressure_hpa={sample.pressure_hpa} "
        f"gas_ohms={sample.gas_ohms} "
        f"gas_heat_stable={sample.gas_heat_stable}"
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
