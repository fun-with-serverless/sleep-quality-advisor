from __future__ import annotations

import json
import os
from typing import Any

import boto3
from aws_lambda_powertools import Logger

logger = Logger()
secrets = boto3.client("secretsmanager")
FITBIT_REFRESH_SECRET_NAME = "FitbitRefreshSecretName"


@logger.inject_lambda_context
def lambda_handler(event: dict[str, Any], context: object) -> dict[str, Any]:
    # Placeholder: store received code as the new refresh token for bootstrap
    # In real flow, exchange code for tokens with Fitbit and store refresh token
    params = event.get("queryStringParameters") or {}
    code = params.get("code", "")
    secret_name = os.environ.get(FITBIT_REFRESH_SECRET_NAME) or os.environ.get(
        "FITBIT_REFRESH_SECRET_NAME", "fitbit/refresh/token"
    )

    if code:
        secrets.put_secret_value(SecretId=secret_name, SecretString=code)

    return {"statusCode": 200, "body": json.dumps({"ok": True})}
