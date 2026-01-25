import contextlib
import os
from collections.abc import Iterator

import boto3
import pytest
from moto import mock_aws

# Ensure AWS SDK has a region and fake credentials for moto
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("AWS_SESSION_TOKEN", "testing")


# Environment variables read at import time by common.config
os.environ.setdefault("ENV_READINGS_TABLE", "env_readings")
os.environ.setdefault("SLEEP_SESSIONS_TABLE", "sleep_sessions")
os.environ.setdefault("INGEST_SHARED_SECRET_NAME", "ingest/shared/secret")

# Defaults for Fitbit handlers
os.environ.setdefault("FITBIT_CLIENT_ID_PARAM_NAME", "fitbit/client/id")
os.environ.setdefault("FITBIT_CODE_VERIFIER_SECRET_NAME", "fitbit/code/verifier")
os.environ.setdefault("FITBIT_REFRESH_SECRET_NAME", "fitbit/refresh/token")
os.environ.setdefault("FITBIT_CLIENT_SECRET_NAME", "fitbit/client/secret")

# Defaults for weekly report system
os.environ.setdefault("AGENT_ARN", "arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/test-agent")
os.environ.setdefault("EMAIL_PARAMETER_NAME", "/sleep-advisor/report-email")
os.environ.setdefault("SENDER_EMAIL", "test@example.com")
os.environ.setdefault("BEDROCK_MODEL_ID", "anthropic.claude-sonnet-4-20250514-v1:0")


@pytest.fixture(scope="session", autouse=True)
def aws_moto() -> Iterator[None]:
    with mock_aws():
        # Create required AWS resources in moto
        # DynamoDB tables
        ddb = boto3.client("dynamodb")
        ddb.create_table(
            TableName=os.environ["ENV_READINGS_TABLE"],
            AttributeDefinitions=[
                {"AttributeName": "day", "AttributeType": "S"},
                {"AttributeName": "ts_min", "AttributeType": "N"},
            ],
            KeySchema=[
                {"AttributeName": "day", "KeyType": "HASH"},
                {"AttributeName": "ts_min", "KeyType": "RANGE"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        ddb.create_table(
            TableName=os.environ["SLEEP_SESSIONS_TABLE"],
            AttributeDefinitions=[
                {"AttributeName": "sleepDate", "AttributeType": "S"},
                {"AttributeName": "segmentStart", "AttributeType": "S"},
            ],
            KeySchema=[
                {"AttributeName": "sleepDate", "KeyType": "HASH"},
                {"AttributeName": "segmentStart", "KeyType": "RANGE"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        # SSM parameter for Fitbit client id (placeholder default)
        ssm = boto3.client("ssm")
        ssm.put_parameter(
            Name=os.environ["FITBIT_CLIENT_ID_PARAM_NAME"],
            Type="String",
            Value="TEST_CLIENT_ID",
            Overwrite=True,
        )

        # Secrets for code verifier and refresh token must exist for put operations
        secrets = boto3.client("secretsmanager")
        for name in [
            os.environ["FITBIT_CODE_VERIFIER_SECRET_NAME"],
            os.environ["FITBIT_REFRESH_SECRET_NAME"],
            os.environ["INGEST_SHARED_SECRET_NAME"],
        ]:
            with contextlib.suppress(secrets.exceptions.ResourceExistsException):  # type: ignore[attr-defined]
                secrets.create_secret(Name=name, SecretString="x")

        # Client secret must be non-empty for happy path tests
        with contextlib.suppress(secrets.exceptions.ResourceExistsException):  # type: ignore[attr-defined]
            secrets.create_secret(Name=os.environ["FITBIT_CLIENT_SECRET_NAME"], SecretString="SECRET")

        yield
