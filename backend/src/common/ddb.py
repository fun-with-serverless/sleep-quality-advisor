from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import boto3
from botocore.client import BaseClient

from .config import ENV_READINGS_TABLE, SLEEP_SESSIONS_TABLE


def get_dynamodb() -> BaseClient:
    return boto3.client("dynamodb")


def put_env_reading(ddb: BaseClient, item: Mapping[str, Any]) -> None:
    attributes: dict[str, Any] = {
        "day": {"S": str(item["day"])},
        "ts_min": {"N": str(int(item["ts_min"]))},
    }
    if "temp_c" in item:
        attributes["temp_c"] = {"N": str(float(item["temp_c"]))}
    if "humidity_pct" in item:
        attributes["humidity_pct"] = {"N": str(float(item["humidity_pct"]))}
    if "pressure_hpa" in item:
        attributes["pressure_hpa"] = {"N": str(float(item["pressure_hpa"]))}
    if "iaq" in item:
        attributes["iaq"] = {"N": str(float(item["iaq"]))}
    if "noise_db" in item:
        attributes["noise_db"] = {"N": str(float(item["noise_db"]))}
    if "deviceId" in item:
        attributes["deviceId"] = {"S": str(item["deviceId"])}

    ddb.put_item(
        TableName=ENV_READINGS_TABLE,
        Item=attributes,
        ConditionExpression="attribute_not_exists(#d) AND attribute_not_exists(#t)",
        ExpressionAttributeNames={"#d": "day", "#t": "ts_min"},
    )


def put_sleep_stage_segment(ddb: BaseClient, item: Mapping[str, Any]) -> None:
    """Write a sleep stage segment to `SLEEP_SESSIONS_TABLE`.

    Expected keys: sleepDate (str), segmentStart (int), stage (str), duration_s (int).
    """
    sleep_date = str(item["sleepDate"])
    segment_start = str(item["segmentStart"])  # table uses String RANGE key
    ddb.put_item(
        TableName=SLEEP_SESSIONS_TABLE,
        Item={
            "sleepDate": {"S": sleep_date},
            "segmentStart": {"S": segment_start},
            "stage": {"S": str(item["stage"])},
            "duration_s": {"N": str(int(item["duration_s"]))},
        },
        ConditionExpression="attribute_not_exists(#d) AND attribute_not_exists(#s)",
        ExpressionAttributeNames={"#d": "sleepDate", "#s": "segmentStart"},
    )


def put_daily_summary(ddb: BaseClient, item: Mapping[str, Any]) -> None:
    """Write daily summary (row with SK='SUMMARY').

    Expects keys: sleepDate (str) plus score, efficiency, stage minutes, and times.
    """
    sleep_date = str(item["sleepDate"])
    ddb.put_item(
        TableName=SLEEP_SESSIONS_TABLE,
        Item={
            "sleepDate": {"S": sleep_date},
            "segmentStart": {"S": "SUMMARY"},
            "score": {"N": str(int(item["score"]))},
            "efficiency": {"N": str(float(item["efficiency"]))},
            "rem_min": {"N": str(int(item["rem_min"]))},
            "deep_min": {"N": str(int(item["deep_min"]))},
            "light_min": {"N": str(int(item["light_min"]))},
            "total_min": {"N": str(int(item["total_min"]))},
            "bedtime": {"N": str(int(item["bedtime"]))},
            "risetime": {"N": str(int(item["risetime"]))},
        },
        ConditionExpression="attribute_not_exists(#d) AND attribute_not_exists(#s)",
        ExpressionAttributeNames={"#d": "sleepDate", "#s": "segmentStart"},
    )
