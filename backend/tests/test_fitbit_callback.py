from __future__ import annotations

import json
import os
from typing import Any
from unittest.mock import Mock, patch

import boto3


def _invoke(event: dict[str, Any]) -> dict[str, Any]:
    from src.fitbit_callback.handler import lambda_handler

    return lambda_handler(event, {})


def test_happy_path_persists_refresh_token(aws_moto: None) -> None:  # type: ignore[unused-ignore]
    ssm = boto3.client("ssm")
    secrets = boto3.client("secretsmanager")

    ssm.put_parameter(
        Name=os.environ["FITBIT_CLIENT_ID_PARAM_NAME"],
        Type="String",
        Value="CLIENT123",
        Overwrite=True,
    )
    # Provide code_verifier in secrets; client secret is provided by conftest
    secrets.put_secret_value(SecretId=os.environ["FITBIT_CODE_VERIFIER_SECRET_NAME"], SecretString="VERIFIER")
    
    # Mock network call
    token_payload = {"refresh_token": "REFRESH"}
    mock_resp = Mock()
    mock_resp.read.return_value = json.dumps(token_payload).encode("utf-8")
    mock_cm = Mock()
    mock_cm.__enter__ = lambda s: mock_resp
    mock_cm.__exit__ = lambda *args, **kwargs: False

    with patch("src.fitbit_callback.handler.urllib.request.urlopen", return_value=mock_cm):
        res = _invoke({"queryStringParameters": {"code": "AUTHCODE"}})

    assert res["statusCode"] == 200
    stored = secrets.get_secret_value(SecretId=os.environ["FITBIT_REFRESH_SECRET_NAME"])  # type: ignore[assignment]
    assert stored["SecretString"] == "REFRESH"


def test_token_exchange_failure_returns_502(aws_moto: None) -> None:  # type: ignore[unused-ignore]
    ssm = boto3.client("ssm")
    secrets = boto3.client("secretsmanager")

    ssm.put_parameter(
        Name=os.environ["FITBIT_CLIENT_ID_PARAM_NAME"],
        Type="String",
        Value="CLIENT123",
        Overwrite=True,
    )
    # Provide code_verifier in secrets; client secret is provided by conftest
    secrets.put_secret_value(SecretId=os.environ["FITBIT_CODE_VERIFIER_SECRET_NAME"], SecretString="VERIFIER")

    with patch("src.fitbit_callback.handler.urllib.request.urlopen", side_effect=Exception("boom")):
        res = _invoke({"queryStringParameters": {"code": "AUTHCODE"}})

    assert res["statusCode"] == 502
    body = json.loads(res["body"])
    assert body["error"] == "token_exchange_failed"


