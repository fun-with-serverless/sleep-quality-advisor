from __future__ import annotations

import os
from urllib.parse import parse_qs, urlparse

import boto3

from src.fitbit_authorize.handler import lambda_handler


def test_builds_redirect_and_persists_code_verifier(aws_moto: None) -> None:  # type: ignore[unused-ignore]
    # Ensure client id exists in SSM and code verifier secret exists in Secrets Manager
    ssm = boto3.client("ssm")
    secrets = boto3.client("secretsmanager")

    ssm.put_parameter(
        Name=os.environ["FITBIT_CLIENT_ID_PARAM_NAME"],
        Type="String",
        Value="CLIENT123",
        Overwrite=True,
    )


    res = lambda_handler({}, {})
    assert res["statusCode"] == 302
    location = res["headers"]["Location"]

    parsed = urlparse(location)
    assert parsed.scheme == "https"
    assert parsed.netloc == "www.fitbit.com"
    assert parsed.path == "/oauth2/authorize"

    q = parse_qs(parsed.query)
    assert q["client_id"] == ["CLIENT123"]
    assert q["response_type"] == ["code"]
    assert q["code_challenge_method"] == ["S256"]
    assert q["scope"] == ["sleep"]

    # A code_verifier should have been written
    secret_name = os.environ["FITBIT_CODE_VERIFIER_SECRET_NAME"]
    # moto stores latest secret value in SecretString
    val = secrets.get_secret_value(SecretId=secret_name)["SecretString"]
    assert isinstance(val, str)
    assert len(val) >= 43


