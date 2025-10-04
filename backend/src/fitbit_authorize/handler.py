from __future__ import annotations

import base64
import hashlib
import os
import secrets
from typing import Any

from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities import parameters


logger = Logger()

ENV_CLIENT_ID_PARAM = "FITBIT_CLIENT_ID_PARAM_NAME"
ENV_CODE_VERIFIER_SECRET = "FITBIT_CODE_VERIFIER_SECRET_NAME"


def _generate_code_verifier(length: int = 64) -> str:
    """Generate a PKCE code_verifier using unreserved characters.

    Length must be between 43 and 128.
    """
    length = 64 if length < 43 or length > 128 else length
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _base64url_no_padding(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _code_challenge_s256(code_verifier: str) -> str:
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    return _base64url_no_padding(digest)


@logger.inject_lambda_context
def lambda_handler(event: dict[str, Any], context: object) -> dict[str, Any]:
    # Read configuration
    client_id_param = os.environ.get(ENV_CLIENT_ID_PARAM, "fitbit/client/id")
    code_verifier_secret_name = os.environ.get(ENV_CODE_VERIFIER_SECRET, "fitbit/code/verifier")

    # Fetch Fitbit client_id from SSM Parameter Store
    client_id = parameters.get_parameter(client_id_param)

    # Generate PKCE values
    code_verifier = _generate_code_verifier()
    code_challenge = _code_challenge_s256(code_verifier)

    # Persist code_verifier to Secrets Manager for later use by callback
    parameters.set_secret(code_verifier_secret_name, code_verifier)

    # Build Fitbit authorize URL (no redirect_uri included; uses registered one)
    scope = "sleep"
    authorize_url = (
        "https://www.fitbit.com/oauth2/authorize"
        f"?client_id={client_id}"
        "&response_type=code"
        f"&code_challenge={code_challenge}"
        "&code_challenge_method=S256"
        f"&scope={scope}"
    )

    return {
        "statusCode": 302,
        "headers": {"Location": authorize_url},
        "body": "",
    }


