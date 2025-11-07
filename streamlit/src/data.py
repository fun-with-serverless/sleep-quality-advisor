import os
from decimal import Decimal
from typing import Any, Dict, List

import boto3
from boto3 import session as boto3_session
from botocore.exceptions import ClientError
_DEBUG_PRINTED = False


def _session() -> boto3_session.Session:
    env_region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
    if env_region:
        return boto3_session.Session(region_name=env_region)
    return boto3_session.Session()


def _debug_print_once(ddb_client: Any, table_name: str | None) -> None:
    global _DEBUG_PRINTED
    if _DEBUG_PRINTED:
        return
    try:
        sess = _session()
        region = sess.region_name
    except Exception:
        region = None

    try:
        tables: List[str] = []
        kwargs: Dict[str, Any] = {}
        while True:
            resp = ddb_client.list_tables(**kwargs)
            tables.extend(resp.get("TableNames", []))
            lek = resp.get("LastEvaluatedTableName")
            if not lek:
                break
            kwargs["ExclusiveStartTableName"] = lek
    except Exception:
        tables = []

    print(
        "[SQA Streamlit] DynamoDB debug =>",
        " env.AWS_REGION=", os.environ.get("AWS_REGION"),
        " env.AWS_DEFAULT_REGION=", os.environ.get("AWS_DEFAULT_REGION"),
        " session.region=", region,
        " TABLE_NAME=", table_name,
        " tables=", tables,
    )
    _DEBUG_PRINTED = True

import pandas as pd
from boto3.dynamodb.conditions import Key


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except Exception:
        return None


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None


def _table():
    table_name = os.environ.get("TABLE_NAME")
    if not table_name:
        raise RuntimeError("TABLE_NAME environment variable is required")
    sess = _session()
    ddb = sess.resource("dynamodb")
    _debug_print_once(sess.client("dynamodb"), table_name)
    return ddb.Table(table_name)


def _sleep_table():
    table_name = os.environ.get("SLEEP_SESSIONS_TABLE")
    if not table_name:
        raise RuntimeError("SLEEP_SESSIONS_TABLE environment variable is required for sleep views")
    sess = _session()
    ddb = sess.resource("dynamodb")
    _debug_print_once(sess.client("dynamodb"), table_name)
    return ddb.Table(table_name)


def fetch_env_readings(day: str) -> pd.DataFrame:
    """Fetch env readings for a given day (YYYY-MM-DD) from DynamoDB.

    Returns a pandas DataFrame with columns: ts_min, temp_c, humidity_pct.
    """
    table = _table()
    items: List[Dict[str, Any]] = []
    kwargs: Dict[str, Any] = {
        "KeyConditionExpression": Key("day").eq(day),
        "ScanIndexForward": True,
    }
    try:
        while True:
            resp = table.query(**kwargs)
            items.extend(resp.get("Items", []))
            lek = resp.get("LastEvaluatedKey")
            if not lek:
                break
            kwargs["ExclusiveStartKey"] = lek
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code")
        if code == "ResourceNotFoundException":
            raise RuntimeError(
                f"DynamoDB table not found. Ensure TABLE_NAME is set to the actual physical table name. TABLE_NAME='{os.environ.get('TABLE_NAME','')}'."
            ) from e
        raise

    if not items:
        return pd.DataFrame(columns=["ts_min", "temp_c", "humidity_pct"]).astype({"ts_min": "int64"})

    rows = [
        {
            "ts_min": int(it.get("ts_min")),
            "temp_c": _to_float(it.get("temp_c")),
            "humidity_pct": _to_float(it.get("humidity_pct")),
        }
        for it in items
        if "ts_min" in it
    ]
    df = pd.DataFrame(rows)
    df = df.sort_values("ts_min").reset_index(drop=True)
    return df


def fetch_env_readings_days(days: List[str]) -> pd.DataFrame:
    """Fetch env readings for multiple day partitions and concatenate.

    `days` must be strings in YYYY-MM-DD (UTC) format.
    """
    frames: List[pd.DataFrame] = []
    for d in days:
        frames.append(fetch_env_readings(d))
    if not frames:
        return pd.DataFrame(columns=["ts_min", "temp_c", "humidity_pct"]).astype({"ts_min": "int64"})
    return pd.concat(frames, ignore_index=True).sort_values("ts_min").reset_index(drop=True)


def fetch_sleep_segments(sleep_date: str) -> pd.DataFrame:
    """Fetch per-segment sleep stages for a given sleep_date (YYYY-MM-DD).

    Returns a DataFrame with columns: start_ts, end_ts, stage, duration_s.
    Timestamps are epoch seconds (UTC).
    """
    table = _sleep_table()
    items: List[Dict[str, Any]] = []
    kwargs: Dict[str, Any] = {
        "KeyConditionExpression": Key("sleepDate").eq(sleep_date),
        "ScanIndexForward": True,
    }
    try:
        while True:
            resp = table.query(**kwargs)
            items.extend(resp.get("Items", []))
            lek = resp.get("LastEvaluatedKey")
            if not lek:
                break
            kwargs["ExclusiveStartKey"] = lek
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code")
        if code == "ResourceNotFoundException":
            raise RuntimeError(
                f"DynamoDB table not found. Ensure SLEEP_SESSIONS_TABLE is set to the actual physical table name. SLEEP_SESSIONS_TABLE='{os.environ.get('SLEEP_SESSIONS_TABLE','')}'."
            ) from e
        raise

    # Exclude the SUMMARY row and any incomplete items
    rows: List[Dict[str, Any]] = []
    for it in items:
        if str(it.get("segmentStart")) == "SUMMARY":
            continue
        # segmentStart stored as epoch minutes in the backend
        start_min = _to_int(it.get("segmentStart"))
        duration_s = _to_int(it.get("duration_s"))
        stage = it.get("stage")
        if start_min is None or duration_s is None or stage is None:
            continue
        start_ts = start_min * 60
        rows.append(
            {
                "start_ts": start_ts,
                "end_ts": start_ts + duration_s,
                "stage": str(stage),
                "duration_s": duration_s,
            }
        )

    if not rows:
        return pd.DataFrame(columns=["start_ts", "end_ts", "stage", "duration_s"]).astype({"start_ts": "int64"})

    df = pd.DataFrame(rows).sort_values("start_ts").reset_index(drop=True)
    return df


def fetch_sleep_summary(sleep_date: str) -> Dict[str, Any] | None:
    """Fetch the daily summary row for a given sleep_date.

    Returns a dict with keys: score, efficiency, rem_min, deep_min, light_min,
    total_min, bedtime, risetime. Returns None if not found.
    """
    table = _sleep_table()
    try:
        resp = table.get_item(Key={"sleepDate": sleep_date, "segmentStart": "SUMMARY"})
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code")
        if code == "ResourceNotFoundException":
            raise RuntimeError(
                f"DynamoDB table not found. Ensure SLEEP_SESSIONS_TABLE is set to the actual physical table name. SLEEP_SESSIONS_TABLE='{os.environ.get('SLEEP_SESSIONS_TABLE','')}'."
            ) from e
        raise

    item = resp.get("Item")
    if not item:
        return None

    out: Dict[str, Any] = {
        "sleepDate": str(item.get("sleepDate")),
        "score": _to_int(item.get("score")),
        "efficiency": _to_float(item.get("efficiency")),
        "rem_min": _to_int(item.get("rem_min")) or 0,
        "deep_min": _to_int(item.get("deep_min")) or 0,
        "light_min": _to_int(item.get("light_min")) or 0,
        "total_min": _to_int(item.get("total_min")) or 0,
        "bedtime": _to_int(item.get("bedtime")),
        "risetime": _to_int(item.get("risetime")),
    }
    return out

