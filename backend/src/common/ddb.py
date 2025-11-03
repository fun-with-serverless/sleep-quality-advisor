from collections.abc import Mapping
from decimal import Decimal
from typing import Any

import boto3

from .config import ENV_READINGS_TABLE, SLEEP_SESSIONS_TABLE


def get_dynamodb() -> Any:
    """Return DynamoDB resource to be used by helpers below."""
    return boto3.resource("dynamodb")


def _decimalize(value: Any) -> Any:
    """Recursively convert floats to Decimal for DynamoDB compatibility."""
    if isinstance(value, float):
        # Use string constructor to avoid binary float artifacts
        return Decimal(str(value))
    if isinstance(value, Mapping):
        return {k: _decimalize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return type(value)(_decimalize(v) for v in value)
    return value


def put_env_reading(ddb: Any, item: Mapping[str, Any]) -> None:
    """Write env reading using DynamoDB resource.Table API with idempotency condition."""
    table = ddb.Table(ENV_READINGS_TABLE)
    table.put_item(
        Item=_decimalize({**item}),
        ConditionExpression="attribute_not_exists(#d) AND attribute_not_exists(#t)",
        ExpressionAttributeNames={"#d": "day", "#t": "ts_min"},
    )


def put_sleep_stage_segment(ddb: Any, item: Mapping[str, Any]) -> None:
    """Write a sleep stage segment; ensure key types match table (segmentStart is String)."""
    table = ddb.Table(SLEEP_SESSIONS_TABLE)
    payload = _decimalize({**item})
    payload["sleepDate"] = str(item["sleepDate"])  # HASH key is String
    payload["segmentStart"] = str(item["segmentStart"])  # RANGE key is String
    table.put_item(
        Item=payload,
        ConditionExpression="attribute_not_exists(#d) AND attribute_not_exists(#s)",
        ExpressionAttributeNames={"#d": "sleepDate", "#s": "segmentStart"},
    )


def put_daily_summary(ddb: Any, item: Mapping[str, Any]) -> None:
    """Write daily summary row (SK='SUMMARY'); ensure key types match table."""
    table = ddb.Table(SLEEP_SESSIONS_TABLE)
    payload = _decimalize({**item})
    payload["sleepDate"] = str(item["sleepDate"])  # HASH key
    payload["segmentStart"] = "SUMMARY"  # RANGE key must be String
    table.put_item(
        Item=payload,
        ConditionExpression="attribute_not_exists(#d) AND attribute_not_exists(#s)",
        ExpressionAttributeNames={"#d": "sleepDate", "#s": "segmentStart"},
    )
