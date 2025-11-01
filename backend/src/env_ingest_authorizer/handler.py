import os
from typing import Any, cast

from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.data_classes import event_source
from aws_lambda_powertools.utilities.data_classes.api_gateway_authorizer_event import (
    APIGatewayAuthorizerResponse,
    APIGatewayAuthorizerTokenEvent,
)
from aws_lambda_powertools.utilities.parameters import get_secret

logger = Logger()

SECRET_HEADER = "Authorization"
INGEST_SHARED_SECRET_NAME = "INGEST_SHARED_SECRET_NAME"


def _policy(principal_id: str, effect: str, method_arn: str) -> APIGatewayAuthorizerResponse:
    return cast(
        APIGatewayAuthorizerResponse,
        {
            "principalId": principal_id,
            "policyDocument": {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Action": "execute-api:Invoke",
                        "Effect": effect,
                        "Resource": [method_arn],
                    }
                ],
            },
        },
    )


@logger.inject_lambda_context
@event_source(data_class=APIGatewayAuthorizerTokenEvent)
def lambda_handler(event: APIGatewayAuthorizerTokenEvent, context: Any) -> APIGatewayAuthorizerResponse:
    method_arn = str(event.get("methodArn", "*"))
    headers = event.get("headers") or {}
    provided = headers.get(SECRET_HEADER) or headers.get(SECRET_HEADER.lower())

    if not provided:
        logger.warning("Missing secret header")
        return _policy("anonymous", "Deny", method_arn)

    secret_name = os.environ.get(INGEST_SHARED_SECRET_NAME, "")
    expected = get_secret(secret_name)

    if provided == expected:
        logger.info("Valid secret header")
        return _policy("device", "Allow", method_arn)

    logger.warning("Invalid secret header")
    return _policy("anonymous", "Deny", method_arn)
