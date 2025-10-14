import socket
import time
from collections.abc import Callable

from requests import Response, post
from tenacity import Retrying, stop_after_attempt, wait_exponential_jitter

from .models import EnvReadingModel
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
        "X-Secret": secret,
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
) -> None:
    tick = max(1, int(tick_seconds))
    if warmup_seconds > 0:
        time.sleep(int(warmup_seconds))

    device_id = _get_device_id()

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
            iaq=None,
            noise_db=None,
            deviceId=device_id,
        )

        payload = model.model_dump(exclude_none=True)

        for attempt in Retrying(stop=stop_after_attempt(3), wait=wait_exponential_jitter(initial=0.2, max=2.0)):
            with attempt:
                code = _post_json(endpoint_url, post_secret, user_agent, payload)
                if not (200 <= code < 300):
                    raise RuntimeError(f"HTTP status {code}")

        time.sleep(tick)
