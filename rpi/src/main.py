import logging

from .bme680_sensor.helpers import make_bme680_read_sample
from .bme680_sensor.reader import BME680Reader
from .config import load_settings
from .helpers import make_multi_sensor_read_sample
from .led import LedController
from .publisher import run_publisher
from .veml6030_sensor.helpers import make_veml6030_read_sample
from .veml6030_sensor.reader import VEML6030Reader


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s",
    )


def main() -> None:
    settings = load_settings()
    _setup_logging(settings.log_level)

    bme_reader = BME680Reader(settings.i2c_bus, settings.bme680_i2c_address)
    veml_reader = VEML6030Reader(settings.i2c_bus, settings.veml6030_i2c_address)
    led = LedController(settings.led_blink_on_ms, settings.led_blink_off_ms)
    # Normal state: LED off
    led.off()
    read_sample = make_multi_sensor_read_sample(
        make_bme680_read_sample(bme_reader),
        make_veml6030_read_sample(veml_reader),
    )
    run_publisher(
        endpoint_url=settings.endpoint_url,
        post_secret=settings.post_secret,
        user_agent=settings.user_agent,
        tick_seconds=settings.sample_interval_secs,
        warmup_seconds=settings.warmup_duration_secs,
        read_sample=read_sample,
        spool_db_path=settings.spool_db_path,
        spool_max_rows=settings.spool_max_rows,
        spool_flush_batch=settings.spool_flush_batch,
        on_send_success=lambda: led.off(),
        on_send_failure=lambda _e: led.blink(),
        on_flush_success=lambda flushed: (led.off() if flushed > 0 else None),
        on_flush_error=lambda _e: led.blink(),
    )


if __name__ == "__main__":
    main()
