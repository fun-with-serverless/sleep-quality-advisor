from typing import Any

import pytest

from config import Settings
from publisher import run_publisher
from timeutil import day_from_epoch_minutes


def test_payload_matches_env_reading_model(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings.model_validate(
        {
            "ENDPOINT_URL": "https://example.com/ingest",
            "POST_SECRET": "secret",
            "SAMPLE_INTERVAL_SECS": 10,
            "WARMUP_DURATION_SECS": 0,
        }
    )

    captured: dict[str, Any] | None = None

    def fake_post(url: str, secret: str, ua: str, payload: dict[str, Any]) -> int:  # noqa: ARG001
        nonlocal captured
        captured = payload
        raise SystemExit  # stop the loop after first send

    monkeypatch.setattr("publisher._post_json", fake_post)
    # Disable warm-up in this test and avoid real sleeping
    # No warm-up via function param
    monkeypatch.setattr("time.sleep", lambda *_args, **_kwargs: None)

    fixed_ts = 1735689600  # 2025-01-01 00:00:00Z
    monkeypatch.setattr("time.time", lambda: float(fixed_ts))

    def read_sample() -> dict[str, Any]:
        return {"temperature_c": 22.5, "humidity_pct": 40.0, "pressure_hpa": 1007.3}

    with pytest.raises(SystemExit):
        run_publisher(
            endpoint_url=settings.endpoint_url,
            post_secret=settings.post_secret,
            user_agent=settings.user_agent,
            tick_seconds=settings.sample_interval_secs,
            warmup_seconds=0,
            read_sample=read_sample,
        )

    assert captured is not None
    assert captured["day"] == day_from_epoch_minutes(fixed_ts // 60)
    assert captured["ts_min"] == fixed_ts // 60
    assert captured["temp_c"] == 22.5
    assert captured["humidity_pct"] == 40.0
    assert captured["pressure_hpa"] == 1007.3
