from __future__ import annotations

import os
from typing import Any

from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.data_classes import event_source
from aws_lambda_powertools.utilities.parameters import get_secret
from aws_lambda_powertools.utilities.data_classes.api_gateway_authorizer_event import (
    APIGatewayAuthorizerTokenEvent,
    APIGatewayAuthorizerResponse,
)

logger = Logger()

SECRET_HEADER = "X-Secret"
INGEST_SHARED_SECRET_NAME = "INGEST_SHARED_SECRET_NAME"

def _policy(principal_id: str, effect: str, method_arn: str) -> APIGatewayAuthorizerResponse:
    return {
        "principalId": principal_id,
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "execute-api:Invoke",
                    "Effect": effect,
                    "Resource": method_arn,
                }
            ],
        },
    }


@logger.inject_lambda_context
@event_source(data_class=APIGatewayAuthorizerTokenEvent)
def lambda_handler(event: APIGatewayAuthorizerTokenEvent, context: Any) -> APIGatewayAuthorizerResponse:
    method_arn = event.get("methodArn", "*")
    headers = event.get("headers") or {}
    provided = headers.get(SECRET_HEADER) or headers.get(SECRET_HEADER.lower())

    if not provided:
        logger.warning("Missing secret header")
        return _policy("anonymous", "Deny", method_arn)

    secret_name = os.environ.get(INGEST_SHARED_SECRET_NAME, "")
    expected = get_secret(secret_name)

    if provided == expected:
        return _policy("device", "Allow", method_arn)

    logger.warning("Invalid secret header")
    return _policy("anonymous", "Deny", method_arn)
