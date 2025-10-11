import os
from datetime import UTC, datetime
from typing import Any
from unittest.mock import patch

import boto3

from .utils import FakeLambdaContext


def _invoke(event: dict[str, Any]) -> dict[str, Any]:
    from src.fitbit_fetch.handler import lambda_handler

    return lambda_handler(event, FakeLambdaContext())


def _set_refresh_token(value: str) -> None:
    secrets = boto3.client("secretsmanager")
    secrets.put_secret_value(SecretId=os.environ["FITBIT_REFRESH_SECRET_NAME"], SecretString=value)


def _token_response(access: str = "AT", refresh: str = "RT") -> Any:
    class _Resp:
        status_code = 200

        def __init__(self) -> None:
            self.headers = {"fitbit-rate-limit-remaining": "150"}

        def json(self) -> dict[str, Any]:
            return {"access_token": access, "refresh_token": refresh}

    return _Resp()


def _sleep_response(date_str: str) -> Any:
    # Single stages record with 2 segments
    dt1 = f"{date_str}T00:00:00.000"
    dt2 = f"{date_str}T00:30:00.000"

    class _Resp:
        status_code = 200

        def __init__(self) -> None:
            self.headers = {"fitbit-rate-limit-remaining": "149"}

        def json(self) -> dict[str, Any]:
            return {
                "sleep": [
                    {
                        "dateOfSleep": date_str,
                        "type": "stages",
                        "levels": {
                            "data": [
                                {"dateTime": dt1, "level": "light", "seconds": 1200},
                                {"dateTime": dt2, "level": "deep", "seconds": 1800},
                            ]
                        },
                    }
                ]
            }

    return _Resp()


def test_happy_path_writes_segments(aws_moto: None) -> None:  # type: ignore[unused-ignore]
    # Arrange
    _set_refresh_token("REFRESH0")
    today = datetime.now(UTC).strftime("%Y-%m-%d")

    with (
        patch("src.common.fitbit_client.requests.post", return_value=_token_response()),
        patch("src.common.fitbit_client.requests.get", return_value=_sleep_response(today)),
    ):
        res = _invoke({"source": "aws.events"})

    assert res["ok"] is True
    assert res["segments"] == 2

    # Validate they were written
    ddb = boto3.client("dynamodb")
    items = ddb.scan(TableName=os.environ["SLEEP_SESSIONS_TABLE"])  # type: ignore[assignment]
    # Two segments should exist
    assert len(items["Items"]) == 2


def test_skips_classic_logs(aws_moto: None) -> None:  # type: ignore[unused-ignore]
    _set_refresh_token("REFRESH0")
    today = datetime.now(UTC).strftime("%Y-%m-%d")

    class _SleepResp:
        status_code = 200

        def __init__(self) -> None:
            self.headers = {}

        def json(self) -> dict[str, Any]:
            return {
                "sleep": [
                    {"dateOfSleep": today, "type": "classic", "levels": {"data": []}},
                ]
            }

    with (
        patch("src.common.fitbit_client.requests.post", return_value=_token_response()),
        patch("src.common.fitbit_client.requests.get", return_value=_SleepResp()),
    ):
        res = _invoke({})

    assert res["ok"] is True
    assert res["segments"] == 0


def test_error_from_token_refresh_is_reported(aws_moto: None) -> None:  # type: ignore[unused-ignore]
    _set_refresh_token("REFRESH0")

    class _BadResp:
        status_code = 400

        def __init__(self) -> None:
            self.headers = {}

        def json(self) -> dict[str, Any]:  # pragma: no cover - not used
            return {}

    with patch("src.common.fitbit_client.requests.post", return_value=_BadResp()):
        res = _invoke({})

    assert res["ok"] is False
    assert "failed" in res["error"]
