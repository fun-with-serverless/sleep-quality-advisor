from __future__ import annotations

import base64
import json
import os
import urllib.parse
import urllib.request
from typing import Any

from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities import parameters


logger = Logger()

ENV_REFRESH_SECRET_NAME = "FITBIT_REFRESH_SECRET_NAME"
ENV_CLIENT_SECRET_NAME = "FITBIT_CLIENT_SECRET_NAME"
ENV_CLIENT_ID_PARAM_NAME = "FITBIT_CLIENT_ID_PARAM_NAME"
ENV_CODE_VERIFIER_SECRET_NAME = "FITBIT_CODE_VERIFIER_SECRET_NAME"


def _basic_auth_header(client_id: str, client_secret: str) -> str:
    token = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("ascii")
    return f"Basic {token}"


@logger.inject_lambda_context
def lambda_handler(event: dict[str, Any], context: object) -> dict[str, Any]:
    params = event.get("queryStringParameters") or {}
    code = params.get("code", "")
    if not code:
        return {"statusCode": 400, "body": json.dumps({"error": "missing code"})}

    # Resolve configuration
    refresh_secret_name = os.environ.get(ENV_REFRESH_SECRET_NAME, "fitbit/refresh/token")
    client_id_param_name = os.environ.get(ENV_CLIENT_ID_PARAM_NAME, "fitbit/client/id")
    code_verifier_secret_name = os.environ.get(ENV_CODE_VERIFIER_SECRET_NAME, "fitbit/code/verifier")
    client_secret_name = os.environ.get(ENV_CLIENT_SECRET_NAME, "")

    # Fetch values
    client_id = parameters.get_parameter(client_id_param_name)
    code_verifier = parameters.get_secret(code_verifier_secret_name)
    if not client_secret_name:
        return {"statusCode": 500, "body": json.dumps({"error": "missing_client_secret_name_env"})}
    client_secret = parameters.get_secret(client_secret_name)
    if not client_secret:
        return {"statusCode": 500, "body": json.dumps({"error": "missing_client_secret_value"})}

    if not code_verifier:
        return {"statusCode": 500, "body": json.dumps({"error": "missing code_verifier"})}

    # Build token request
    token_url = "https://api.fitbit.com/oauth2/token"
    form = {
        "client_id": client_id,
        "code": code,
        "code_verifier": code_verifier,
        "grant_type": "authorization_code",
    }
    data = urllib.parse.urlencode(form).encode("utf-8")

    headers: dict[str, str] = {"Content-Type": "application/x-www-form-urlencoded"}
    headers["Authorization"] = _basic_auth_header(client_id, client_secret)

    req = urllib.request.Request(token_url, data=data, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
            payload = json.loads(body)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Token exchange failed")
        return {"statusCode": 502, "body": json.dumps({"error": "token_exchange_failed", "detail": str(exc)})}

    refresh_token = payload.get("refresh_token", "")
    if not refresh_token:
        return {"statusCode": 502, "body": json.dumps({"error": "missing_refresh_token", "payload": payload})}

    # Persist refresh token
    parameters.set_secret(refresh_secret_name, refresh_token)

    return {"statusCode": 200, "body": json.dumps({"ok": True})}
