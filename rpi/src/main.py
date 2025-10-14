import logging

from bme680_sensor.helpers import make_bme680_read_sample
from bme680_sensor.reader import BME680Reader
from config import load_settings
from publisher import run_publisher


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s",
    )


def main() -> None:
    settings = load_settings()
    _setup_logging(settings.log_level)

    reader = BME680Reader(settings.i2c_bus, settings.i2c_address)
    run_publisher(
        endpoint_url=settings.endpoint_url,
        post_secret=settings.post_secret,
        user_agent=settings.user_agent,
        tick_seconds=settings.sample_interval_secs,
        warmup_seconds=settings.warmup_duration_secs,
        read_sample=make_bme680_read_sample(reader),
    )


if __name__ == "__main__":
    main()
