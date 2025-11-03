import os
from typing import Any

import boto3

from .utils import FakeLambdaContext


def _invoke(event: dict[str, Any]) -> dict[str, Any]:
    from src.env_ingest_authorizer.handler import lambda_handler  # import after env/moto ready

    return lambda_handler(event, FakeLambdaContext())


def test_missing_header_denied(aws_moto: None) -> None:  # type: ignore[unused-ignore]
    event: dict[str, Any] = {
        "type": "TOKEN",
        "methodArn": "arn:aws:execute-api:xxx",
        # Simulate missing token by providing empty string
        "authorizationToken": "",
    }
    res = _invoke(event)
    assert res["policyDocument"]["Statement"][0]["Effect"] == "Deny"


def test_wrong_secret_denied(aws_moto: None) -> None:  # type: ignore[unused-ignore]
    secrets = boto3.client("secretsmanager")
    secrets.put_secret_value(SecretId=os.environ["INGEST_SHARED_SECRET_NAME"], SecretString="EXPECTED")

    event: dict[str, Any] = {
        "type": "TOKEN",
        "methodArn": "arn:aws:execute-api:xxx",
        "authorizationToken": "WRONG",
    }
    res = _invoke(event)
    assert res["policyDocument"]["Statement"][0]["Effect"] == "Deny"


def test_correct_secret_allowed(aws_moto: None) -> None:  # type: ignore[unused-ignore]
    secrets = boto3.client("secretsmanager")
    secrets.put_secret_value(SecretId=os.environ["INGEST_SHARED_SECRET_NAME"], SecretString="EXPECTED")

    event: dict[str, Any] = {
        "type": "TOKEN",
        "methodArn": "arn:aws:execute-api:xxx",
        "authorizationToken": "EXPECTED",
    }
    res = _invoke(event)
    stmt = res["policyDocument"]["Statement"][0]
    assert stmt["Effect"] == "Allow"
