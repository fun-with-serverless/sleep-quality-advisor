"""Unit tests for MCP Server Lambda function."""

import json
from collections.abc import Iterator
from datetime import datetime, timedelta
from decimal import Decimal

import boto3
import pytest

from src.mcp_server.handler import (
    correlate_env_with_sleep,
    decimal_to_float,
    get_sleep_summary_stats,
    get_week_over_week_comparison,
    lambda_handler,
    query_env_data,
    query_sleep_data,
)

from .utils import FakeLambdaContext


@pytest.fixture
def sample_sleep_data(aws_moto: None) -> Iterator[None]:  # type: ignore[unused-ignore]
    """Populate DynamoDB with sample sleep session data."""
    ddb = boto3.resource("dynamodb")
    table = ddb.Table("sleep_sessions")

    # Add sleep data for 3 nights (2025-01-13 to 2025-01-15)
    sleep_data = [
        # Monday 2025-01-13
        {
            "sleepDate": "2025-01-13",
            "segmentStart": "SUMMARY",
            "total_min": 450,  # 7.5 hours
            "deep_min": 90,
            "rem_min": 120,
            "light_min": 210,
            "efficiency": 85,
            "score": 78,
            "bedtime": 1736726400,  # 2025-01-13 00:00:00 UTC
            "risetime": 1736753400,  # 2025-01-13 07:30:00 UTC
        },
        {
            "sleepDate": "2025-01-13",
            "segmentStart": "1736726400",
            "stage": "Light",
            "duration_s": 3600,
        },
        {
            "sleepDate": "2025-01-13",
            "segmentStart": "1736730000",
            "stage": "Deep",
            "duration_s": 5400,
        },
        # Tuesday 2025-01-14
        {
            "sleepDate": "2025-01-14",
            "segmentStart": "SUMMARY",
            "total_min": 480,  # 8 hours
            "deep_min": 100,
            "rem_min": 130,
            "light_min": 220,
            "efficiency": 90,
            "score": 82,
            "bedtime": 1736812800,
            "risetime": 1736841600,
        },
        # Wednesday 2025-01-15
        {
            "sleepDate": "2025-01-15",
            "segmentStart": "SUMMARY",
            "total_min": 420,  # 7 hours
            "deep_min": 85,
            "rem_min": 110,
            "light_min": 200,
            "efficiency": 80,
            "score": 75,
            "bedtime": 1736899200,
            "risetime": 1736924400,
        },
    ]

    for item in sleep_data:
        table.put_item(Item=item)

    yield

    # Cleanup: delete all sleep data
    scan = table.scan()
    with table.batch_writer() as batch:
        for item in scan.get('Items', []):
            batch.delete_item(Key={'sleepDate': item['sleepDate'], 'segmentStart': item['segmentStart']})


@pytest.fixture
def sample_env_data(aws_moto: None) -> Iterator[None]:  # type: ignore[unused-ignore]
    """Populate DynamoDB with sample environmental data."""
    ddb = boto3.resource("dynamodb")
    table = ddb.Table("env_readings")

    # Add environmental data for 3 days
    base_timestamp = datetime(2025, 1, 13).timestamp() / 60  # Minutes since epoch

    for day_offset in range(3):
        day = (datetime(2025, 1, 13) + timedelta(days=day_offset)).strftime("%Y-%m-%d")

        # Add hourly readings for 24 hours
        for hour in range(24):
            ts_min = int(base_timestamp + (day_offset * 24 * 60) + (hour * 60))

            # Vary temperature and humidity by hour
            temp_c = 18.0 + (hour % 12) * 0.5  # Varies between 18-24°C
            humidity_pct = 45 + (hour % 8) * 2  # Varies between 45-61%

            table.put_item(
                Item={
                    "day": day,
                    "ts_min": ts_min,
                    "temp_c": Decimal(str(temp_c)),
                    "humidity_pct": Decimal(str(humidity_pct)),
                    "pressure_hpa": Decimal("1013.25"),
                    "ambient_lux": Decimal("0.5") if 0 <= hour < 7 else Decimal("150.0"),
                    "deviceId": "test-device",
                }
            )

    yield

    # Cleanup: delete all environmental data
    scan = table.scan()
    with table.batch_writer() as batch:
        for item in scan.get('Items', []):
            batch.delete_item(Key={'day': item['day'], 'ts_min': item['ts_min']})


def test_decimal_to_float() -> None:
    """Test decimal_to_float conversion."""
    # Test Decimal conversion
    assert decimal_to_float(Decimal("123.45")) == 123.45

    # Test dict with Decimals
    data = {"temp": Decimal("18.5"), "humidity": Decimal("50.0")}
    result = decimal_to_float(data)
    assert result == {"temp": 18.5, "humidity": 50.0}

    # Test list with Decimals
    data_list = [Decimal("1.1"), Decimal("2.2")]
    result_list = decimal_to_float(data_list)
    assert result_list == [1.1, 2.2]

    # Test nested structures
    nested = {"readings": [{"value": Decimal("99.9")}]}
    result_nested = decimal_to_float(nested)
    assert result_nested == {"readings": [{"value": 99.9}]}


def test_query_sleep_data_success(sample_sleep_data: None) -> None:  # type: ignore[unused-ignore]
    """Test querying sleep data for a date range."""
    result = query_sleep_data("2025-01-13", "2025-01-15")

    assert "nights" in result
    assert "total_nights" in result
    assert result["total_nights"] == 3

    # Check first night
    night1 = result["nights"][0]
    assert night1["date"] == "2025-01-13"
    assert night1["summary"]["total_min"] == 450
    assert night1["summary"]["deep_min"] == 90
    assert night1["summary"]["efficiency"] == 85
    assert len(night1["stages"]) == 2  # Light and Deep stages


def test_query_sleep_data_no_data(aws_moto: None) -> None:  # type: ignore[unused-ignore]
    """Test querying sleep data when no data exists."""
    result = query_sleep_data("2025-01-01", "2025-01-02")

    assert result["total_nights"] == 0
    assert result["nights"] == []


def test_query_sleep_data_invalid_date() -> None:
    """Test querying sleep data with invalid date format."""
    result = query_sleep_data("invalid-date", "2025-01-15")

    assert "error" in result
    assert result["total_nights"] == 0


def test_query_env_data_success(sample_env_data: None) -> None:  # type: ignore[unused-ignore]
    """Test querying environmental data for a date range."""
    result = query_env_data("2025-01-13", "2025-01-13")

    assert "readings" in result
    assert "total_readings" in result
    assert result["total_readings"] == 24  # 24 hourly readings
    assert "temp_c" in result["metrics_available"]
    assert "humidity_pct" in result["metrics_available"]

    # Check first reading
    reading = result["readings"][0]
    assert "temp_c" in reading
    assert "humidity_pct" in reading
    assert "timestamp" in reading


def test_query_env_data_with_metric_filter(sample_env_data: None) -> None:  # type: ignore[unused-ignore]
    """Test querying environmental data with specific metrics."""
    result = query_env_data("2025-01-13", "2025-01-13", metrics=["temp_c"])

    assert result["total_readings"] == 24
    # Each reading should only have temp_c (plus day, ts_min, timestamp)
    for reading in result["readings"]:
        assert "temp_c" in reading
        assert "humidity_pct" not in reading
        assert "pressure_hpa" not in reading


def test_query_env_data_no_data(aws_moto: None) -> None:  # type: ignore[unused-ignore]
    """Test querying environmental data when no data exists."""
    result = query_env_data("2025-01-01", "2025-01-02")

    assert result["total_readings"] == 0
    assert result["readings"] == []


def test_get_sleep_summary_stats_success(sample_sleep_data: None) -> None:  # type: ignore[unused-ignore]
    """Test calculating sleep summary statistics."""
    result = get_sleep_summary_stats("2025-01-13", "2025-01-15")

    assert "total_sleep_hours" in result
    assert "avg_sleep_hours" in result
    assert "total_nights" in result

    # Total sleep: 7.5 + 8.0 + 7.0 = 22.5 hours
    assert result["total_sleep_hours"] == 22.5
    assert result["avg_sleep_hours"] == 7.5  # 22.5 / 3
    assert result["total_nights"] == 3

    # Deep sleep average: (90 + 100 + 85) / 3 ≈ 91.67
    assert 91.0 <= result["avg_deep_min"] <= 92.0

    # Check min/max nights
    assert result["min_sleep_night"]["hours"] == 7.0
    assert result["min_sleep_night"]["date"] == "2025-01-15"
    assert result["max_sleep_night"]["hours"] == 8.0
    assert result["max_sleep_night"]["date"] == "2025-01-14"

    # Consistency score should be calculated (standard deviation)
    assert result["consistency_score"] > 0


def test_get_sleep_summary_stats_no_data(aws_moto: None) -> None:  # type: ignore[unused-ignore]
    """Test calculating sleep summary stats when no data exists."""
    result = get_sleep_summary_stats("2025-01-01", "2025-01-02")

    assert "error" in result


def test_correlate_env_with_sleep_success(sample_sleep_data: None, sample_env_data: None) -> None:  # type: ignore[unused-ignore]
    """Test correlating environmental data with sleep hours."""
    result = correlate_env_with_sleep("2025-01-13")

    assert "date" in result
    assert result["date"] == "2025-01-13"

    assert "sleep_window" in result
    assert "bedtime" in result["sleep_window"]
    assert "risetime" in result["sleep_window"]
    assert "duration_hours" in result["sleep_window"]

    assert "env_conditions" in result
    env = result["env_conditions"]

    # Should have temperature and humidity averages
    assert "temp_avg_c" in env
    assert "humidity_avg_pct" in env
    assert "light_avg_lux" in env
    assert "readings_count" in env

    # Temperature should be within expected range (18-24°C)
    assert 18.0 <= env["temp_avg_c"] <= 24.0


def test_correlate_env_with_sleep_no_sleep_data(aws_moto: None) -> None:  # type: ignore[unused-ignore]
    """Test correlating when no sleep data exists."""
    result = correlate_env_with_sleep("2025-01-01")

    assert "error" in result


def test_correlate_env_with_sleep_no_env_data(sample_sleep_data: None) -> None:  # type: ignore[unused-ignore]
    """Test correlating when no environmental data exists during sleep."""
    # Clear all environmental data by scanning and deleting
    ddb = boto3.resource("dynamodb")
    table = ddb.Table("env_readings")

    # Scan and delete all items
    scan = table.scan()
    with table.batch_writer() as batch:
        for item in scan.get('Items', []):
            batch.delete_item(Key={'day': item['day'], 'ts_min': item['ts_min']})

    result = correlate_env_with_sleep("2025-01-13")

    assert "env_conditions" in result
    # Should return error message in env_conditions or no readings
    assert "error" in result["env_conditions"] or result["env_conditions"]["readings_count"] == 0


def test_get_week_over_week_comparison_success(sample_sleep_data: None) -> None:  # type: ignore[unused-ignore]
    """Test week-over-week comparison."""
    # Add data for previous week (2025-01-06 to 2025-01-08)
    ddb = boto3.resource("dynamodb")
    table = ddb.Table("sleep_sessions")

    previous_week_data = [
        {
            "sleepDate": "2025-01-06",
            "segmentStart": "SUMMARY",
            "total_min": 420,
            "deep_min": 80,
            "rem_min": 100,
            "light_min": 210,
            "efficiency": 75,
            "score": 70,
        },
        {
            "sleepDate": "2025-01-07",
            "segmentStart": "SUMMARY",
            "total_min": 430,
            "deep_min": 85,
            "rem_min": 105,
            "light_min": 210,
            "efficiency": 78,
            "score": 72,
        },
        {
            "sleepDate": "2025-01-08",
            "segmentStart": "SUMMARY",
            "total_min": 410,
            "deep_min": 75,
            "rem_min": 95,
            "light_min": 210,
            "efficiency": 73,
            "score": 68,
        },
    ]

    for item in previous_week_data:
        table.put_item(Item=item)

    result = get_week_over_week_comparison("2025-01-13", "2025-01-06")

    assert "current_week" in result
    assert "previous_week" in result
    assert "deltas" in result

    deltas = result["deltas"]
    assert "sleep_hours_delta" in deltas
    assert "efficiency_delta" in deltas
    assert "score_delta" in deltas

    # Current week total: 22.5 hours, Previous week total: 21.0 hours
    # Delta should be positive
    assert deltas["sleep_hours_delta"] > 0


def test_get_week_over_week_comparison_missing_data(sample_sleep_data: None) -> None:  # type: ignore[unused-ignore]
    """Test week-over-week comparison when previous week has no data."""
    result = get_week_over_week_comparison("2025-01-13", "2025-01-06")

    assert "deltas" in result
    assert "error" in result["deltas"]


def test_lambda_handler(aws_moto: None) -> None:  # type: ignore[unused-ignore]
    """Test Lambda handler entrypoint."""
    event = {"body": json.dumps({})}
    context = FakeLambdaContext()

    result = lambda_handler(event, context)

    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert body["server"] == "sleep-data-mcp-server"
    assert "tools" in body
    assert len(body["tools"]) == 5  # 5 MCP tools
