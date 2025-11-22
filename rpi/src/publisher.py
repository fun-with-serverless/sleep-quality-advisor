import logging
import socket
import time
from collections.abc import Callable

from requests import Response, post

from .models import EnvReadingModel
from .offline_queue import OfflineQueue
from .timeutil import day_from_epoch_minutes

# Fixed warm-up duration for BME680 gas sensor (seconds)
WARMUP_DURATION_SECS_BME680 = 300


def _get_device_id() -> str:
    try:
        with open("/etc/machine-id", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return socket.gethostname()


def _post_json(url: str, secret: str, user_agent: str, payload: dict[str, object]) -> int:
    headers = {
        "Content-Type": "application/json",
        "Authorization": secret,
        "User-Agent": user_agent,
    }
    resp: Response = post(url, json=payload, headers=headers, timeout=5)
    return int(resp.status_code)


def run_publisher(
    endpoint_url: str,
    post_secret: str,
    user_agent: str,
    tick_seconds: int,
    warmup_seconds: int,
    read_sample: Callable[[], dict[str, float | int | bool | None]],
    spool_db_path: str = "./spool.db",
    spool_max_rows: int = 10_000,
    spool_flush_batch: int = 100,
    on_send_success: Callable[[], None] | None = None,
    on_send_failure: Callable[[Exception | str], None] | None = None,
    on_flush_success: Callable[[int], None] | None = None,
    on_flush_error: Callable[[Exception], None] | None = None,
) -> None:
    tick = max(1, int(tick_seconds))
    logging.info(
        "Publisher starting: tick=%ss, warmup=%ss, endpoint=%s",
        tick,
        warmup_seconds,
        endpoint_url,
    )
    if warmup_seconds > 0:
        logging.info("Warming up gas sensor for %ss...", int(warmup_seconds))
        time.sleep(int(warmup_seconds))
        logging.info("Warmup complete; starting sampling every %ss", tick)

    device_id = _get_device_id()
    queue = OfflineQueue(db_path=spool_db_path, max_rows=spool_max_rows)

    def _send_once(payload: dict[str, object]) -> int:
        return _post_json(endpoint_url, post_secret, user_agent, payload)

    first_sent = False
    while True:
        sample = read_sample()

        ts_sec = int(time.time())
        ts_min = ts_sec // 60
        day = day_from_epoch_minutes(ts_min)

        model = EnvReadingModel(
            day=day,
            ts_min=ts_min,
            temp_c=sample.get("temperature_c"),
            humidity_pct=sample.get("humidity_pct"),
            pressure_hpa=sample.get("pressure_hpa"),
            ambient_lux=sample.get("ambient_lux"),
            iaq=None,
            noise_db=None,
            deviceId=device_id,
        )

        payload = model.model_dump(exclude_none=True)

        # First, attempt to flush previously queued payloads
        try:
            flushed = queue.flush_once(max_batch=spool_flush_batch, send_func=_send_once)
            if flushed > 0:
                logging.info("Flushed %s queued samples", flushed)
            if on_flush_success is not None:
                try:
                    on_flush_success(flushed)
                except Exception:
                    # Callback errors must not affect the loop
                    logging.debug("on_flush_success callback error", exc_info=True)
        except Exception as exc:
            # Flushing failure is non-fatal; we will try again next tick
            logging.debug("Flush attempt failed: %s", exc)
            if on_flush_error is not None:
                try:
                    on_flush_error(exc)
                except Exception:
                    logging.debug("on_flush_error callback error", exc_info=True)

        # Now send current payload; on failure, enqueue it for later
        try:
            logging.info("Sending sample: %s", payload)
            code = _send_once(payload)
            if not (200 <= code < 300):
                raise RuntimeError(f"HTTP status {code}")
        except SystemExit:
            # Preserve test behavior that uses SystemExit to stop the loop
            raise
        except Exception as exc:
            logging.warning("Send failed; enqueuing for retry: %s", exc)
            if on_send_failure is not None:
                try:
                    on_send_failure(exc)
                except Exception:
                    logging.debug("on_send_failure callback error", exc_info=True)
            try:
                queue.enqueue(payload)
            except Exception as qexc:
                logging.error("Failed to enqueue payload for retry: %s", qexc)
            else:
                logging.info("Queued sample for later retry: ts_min=%s", ts_min)
            # Skip first_sent logging on failure
            time.sleep(tick)
            continue
        if not first_sent:
            logging.info(
                "First sample sent: temp=%sC hum=%s%% pres=%shPa",
                model.temp_c,
                model.humidity_pct,
                model.pressure_hpa,
            )
            first_sent = True
        if on_send_success is not None:
            try:
                on_send_success()
            except Exception:
                logging.debug("on_send_success callback error", exc_info=True)

        time.sleep(tick)
