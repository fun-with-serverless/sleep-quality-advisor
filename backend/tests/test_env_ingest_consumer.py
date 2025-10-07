import json
from typing import Any

import boto3
import pytest
from aws_lambda_powertools.utilities.data_classes.sqs_event import SQSRecord
from botocore.exceptions import ClientError
from pydantic import ValidationError

from src.env_ingest_consumer.handler import record_handler

from .utils import FakeLambdaContext


def test_record_handler_happy_path(aws_moto: None) -> None:  # type: ignore[unused-ignore]
    from aws_lambda_powertools.utilities.data_classes.sqs_event import SQSRecord

    from src.env_ingest_consumer.handler import record_handler

    payload = {
        "day": "2025-01-01",
        "ts_min": 1,
    }
    record = SQSRecord(
        {
            "messageId": "1",
            "receiptHandle": "r",
            "body": json.dumps(payload),
            "attributes": {},
            "messageAttributes": {},
            "md5OfBody": "x",
            "eventSource": "aws:sqs",
            "eventSourceARN": "arn",
            "awsRegion": "us-east-1",
        }
    )

    record_handler(record)

    ddb = boto3.resource("dynamodb")
    table = ddb.Table("env_readings")
    resp = table.get_item(Key={"day": "2025-01-01", "ts_min": 1})
    assert "Item" in resp


def test_record_handler_duplicate_treated_as_success(aws_moto: None) -> None:  # type: ignore[unused-ignore]
    # Seed an existing item to trigger ConditionalCheckFailedException
    ddb = boto3.resource("dynamodb")
    table = ddb.Table("env_readings")
    table.put_item(Item={"day": "2025-01-01", "ts_min": 1})

    record = SQSRecord(
        {
            "messageId": "1",
            "receiptHandle": "r",
            "body": json.dumps({"day": "2025-01-01", "ts_min": 1}),
            "attributes": {},
            "messageAttributes": {},
            "md5OfBody": "x",
            "eventSource": "aws:sqs",
            "eventSourceARN": "arn",
            "awsRegion": "us-east-1",
        }
    )

    # The helper will attempt a conditional put; because item exists, boto3 will raise
    # ConditionalCheckFailedException; handler should swallow it and not raise.
    record_handler(record)


def test_record_handler_invalid_json_raises(aws_moto: None) -> None:  # type: ignore[unused-ignore]
    # Provide syntactically valid JSON that fails pydantic validation (missing required keys)
    record = SQSRecord(
        {
            "messageId": "1",
            "receiptHandle": "r",
            "body": json.dumps({"temp_c": 20.0}),
            "attributes": {},
            "messageAttributes": {},
            "md5OfBody": "x",
            "eventSource": "aws:sqs",
            "eventSourceARN": "arn",
            "awsRegion": "us-east-1",
        }
    )

    with pytest.raises(ValidationError):
        record_handler(record)


def test_record_handler_other_client_error_propagates(monkeypatch: pytest.MonkeyPatch, aws_moto: None) -> None:  # type: ignore[unused-ignore]
    import src.env_ingest_consumer.handler as consumer

    def fake_put_env_reading(_ddb: Any, _item: dict[str, Any]) -> None:
        error_response = {"Error": {"Code": "ProvisionedThroughputExceededException"}}
        raise ClientError(error_response, "PutItem")

    monkeypatch.setattr(consumer, "put_env_reading", fake_put_env_reading)

    record = SQSRecord(
        {
            "messageId": "1",
            "receiptHandle": "r",
            "body": json.dumps({"day": "2025-01-01", "ts_min": 1}),
            "attributes": {},
            "messageAttributes": {},
            "md5OfBody": "x",
            "eventSource": "aws:sqs",
            "eventSourceARN": "arn",
            "awsRegion": "us-east-1",
        }
    )

    with pytest.raises(ClientError):
        consumer.record_handler(record)


def test_lambda_handler_single_record_success(aws_moto: None) -> None:  # type: ignore[unused-ignore]
    from src.env_ingest_consumer.handler import lambda_handler

    event = {
        "Records": [
            {
                "messageId": "1",
                "receiptHandle": "r",
                "body": json.dumps({"day": "2025-01-01", "ts_min": 1}),
                "attributes": {},
                "messageAttributes": {},
                "md5OfBody": "x",
                "eventSource": "aws:sqs",
                "eventSourceARN": "arn",
                "awsRegion": "us-east-1",
            }
        ]
    }

    res = lambda_handler(event, FakeLambdaContext())
    assert "batchItemFailures" in res
    assert res["batchItemFailures"] == []
