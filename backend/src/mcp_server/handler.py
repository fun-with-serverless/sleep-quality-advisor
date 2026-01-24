"""
MCP Server for DynamoDB Sleep & Environmental Data Access

Provides MCP tools for querying sleep sessions and environmental readings
from DynamoDB tables. Used by the Strands agent for weekly report generation.
"""

import json
import os
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, cast

import boto3
from boto3.dynamodb.conditions import Key
from mcp.server.fastmcp import FastMCP


def get_dynamodb_tables() -> tuple[Any, Any]:
    """
    Get DynamoDB table resources.

    Creates resources fresh each time to support moto mocking in tests.
    In production, Lambda container reuse will minimize the overhead.
    """
    dynamodb = boto3.resource('dynamodb')
    env_readings_table = dynamodb.Table(os.environ['ENV_READINGS_TABLE'])
    sleep_sessions_table = dynamodb.Table(os.environ['SLEEP_SESSIONS_TABLE'])
    return env_readings_table, sleep_sessions_table


# Initialize FastMCP server
mcp = FastMCP(name="sleep-data-mcp-server")


def decimal_to_float(obj: Any) -> Any:
    """Convert DynamoDB Decimal objects to float for JSON serialization."""
    if isinstance(obj, list):
        return [decimal_to_float(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: decimal_to_float(v) for k, v in obj.items()}
    elif isinstance(obj, Decimal):
        return float(obj)
    return obj


@mcp.tool()
def query_sleep_data(start_date: str, end_date: str) -> dict:
    """
    Fetch sleep sessions from DynamoDB for a date range.

    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format (inclusive)

    Returns:
        Dictionary containing:
        - nights: List of nightly sleep data with stages and summary
        - total_nights: Count of nights with data
    """
    try:
        _, sleep_sessions_table = get_dynamodb_tables()
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")

        nights = []
        current_date = start

        while current_date <= end:
            date_str = current_date.strftime("%Y-%m-%d")

            # Query all items for this date
            response = sleep_sessions_table.query(KeyConditionExpression=Key('sleepDate').eq(date_str))

            items = response.get('Items', [])

            if items:
                # Find summary and stages
                summary = None
                stages = []

                for item in items:
                    if item.get('segmentStart') == 'SUMMARY':
                        summary = item
                    else:
                        stages.append(item)

                if summary:
                    night_data = {
                        'date': date_str,
                        'summary': {
                            'total_min': summary.get('total_min'),
                            'deep_min': summary.get('deep_min'),
                            'rem_min': summary.get('rem_min'),
                            'light_min': summary.get('light_min'),
                            'efficiency': summary.get('efficiency'),
                            'score': summary.get('score'),
                            'bedtime': summary.get('bedtime'),
                            'risetime': summary.get('risetime'),
                        },
                        'stages': [
                            {'stage': s.get('stage'), 'start': s.get('segmentStart'), 'duration_s': s.get('duration_s')}
                            for s in sorted(stages, key=lambda x: x.get('segmentStart', ''))
                        ],
                    }
                    nights.append(night_data)

            current_date += timedelta(days=1)

        return cast(dict[Any, Any], decimal_to_float({'nights': nights, 'total_nights': len(nights)}))

    except Exception as e:
        return {'error': str(e), 'nights': [], 'total_nights': 0}


@mcp.tool()
def query_env_data(start_date: str, end_date: str, metrics: list[str] | None = None) -> dict:
    """
    Fetch environmental readings from DynamoDB for a date range.

    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format (inclusive)
        metrics: Optional list of metrics to include (e.g., ['temp_c', 'humidity_pct'])
                If None, returns all available metrics

    Returns:
        Dictionary containing:
        - readings: List of environmental readings
        - total_readings: Count of readings
        - metrics_available: List of metrics found in the data
    """
    try:
        env_readings_table, _ = get_dynamodb_tables()
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")

        readings = []
        metrics_found = set()
        current_date = start

        while current_date <= end:
            date_str = current_date.strftime("%Y-%m-%d")

            # Query all readings for this day
            response = env_readings_table.query(KeyConditionExpression=Key('day').eq(date_str))

            items = response.get('Items', [])

            for item in items:
                ts_min = float(item.get('ts_min', 0))  # Convert Decimal to float
                reading = {
                    'day': item.get('day'),
                    'ts_min': item.get('ts_min'),
                    'timestamp': datetime.fromtimestamp(ts_min * 60).isoformat(),
                }

                # Add requested metrics or all if not specified
                available_metrics = ['temp_c', 'humidity_pct', 'pressure_hpa', 'ambient_lux', 'iaq', 'noise_db']
                for metric in available_metrics:
                    if metric in item and (metrics is None or metric in metrics):
                        reading[metric] = item[metric]
                        metrics_found.add(metric)

                if len(reading) > 3:  # Has at least one metric beyond day/ts_min/timestamp
                    readings.append(reading)

            current_date += timedelta(days=1)

        result = {
            'readings': readings,
            'total_readings': len(readings),
            'metrics_available': sorted(list(metrics_found)),
        }
        return cast(dict[Any, Any], decimal_to_float(result))

    except Exception as e:
        return {'error': str(e), 'readings': [], 'total_readings': 0, 'metrics_available': []}


@mcp.tool()
def get_sleep_summary_stats(start_date: str, end_date: str) -> dict:
    """
    Calculate aggregate sleep statistics for a date range.

    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format (inclusive)

    Returns:
        Dictionary containing:
        - total_sleep_hours: Total hours slept across all nights
        - avg_sleep_hours: Average hours per night
        - avg_deep_min: Average deep sleep minutes
        - avg_rem_min: Average REM sleep minutes
        - avg_light_min: Average light sleep minutes
        - avg_efficiency: Average sleep efficiency
        - avg_score: Average sleep score
        - min_sleep_night: Date and hours of shortest sleep
        - max_sleep_night: Date and hours of longest sleep
        - consistency_score: Standard deviation of sleep duration (lower is better)
        - total_nights: Number of nights with data
    """
    try:
        # Get sleep data
        sleep_data = query_sleep_data(start_date, end_date)
        nights = sleep_data.get('nights', [])

        if not nights:
            return {'error': 'No sleep data found for the date range'}

        # Calculate statistics
        total_min = sum(n['summary']['total_min'] for n in nights if n['summary']['total_min'])
        deep_mins = [n['summary']['deep_min'] for n in nights if n['summary'].get('deep_min')]
        rem_mins = [n['summary']['rem_min'] for n in nights if n['summary'].get('rem_min')]
        light_mins = [n['summary']['light_min'] for n in nights if n['summary'].get('light_min')]
        efficiencies = [n['summary']['efficiency'] for n in nights if n['summary'].get('efficiency')]
        scores = [n['summary']['score'] for n in nights if n['summary'].get('score')]

        sleep_hours = [(n['date'], n['summary']['total_min'] / 60.0) for n in nights if n['summary']['total_min']]

        # Find min/max
        min_sleep = min(sleep_hours, key=lambda x: x[1]) if sleep_hours else (None, 0)
        max_sleep = max(sleep_hours, key=lambda x: x[1]) if sleep_hours else (None, 0)

        # Calculate consistency (standard deviation)
        if len(sleep_hours) > 1:
            mean_hours = sum(h for _, h in sleep_hours) / len(sleep_hours)
            variance = sum((h - mean_hours) ** 2 for _, h in sleep_hours) / len(sleep_hours)
            consistency_score = variance**0.5
        else:
            consistency_score = 0

        return {
            'total_sleep_hours': round(total_min / 60.0, 2),
            'avg_sleep_hours': round(total_min / 60.0 / len(nights), 2) if nights else 0,
            'avg_deep_min': round(sum(deep_mins) / len(deep_mins), 2) if deep_mins else 0,
            'avg_rem_min': round(sum(rem_mins) / len(rem_mins), 2) if rem_mins else 0,
            'avg_light_min': round(sum(light_mins) / len(light_mins), 2) if light_mins else 0,
            'avg_efficiency': round(sum(efficiencies) / len(efficiencies), 2) if efficiencies else 0,
            'avg_score': round(sum(scores) / len(scores), 2) if scores else 0,
            'min_sleep_night': {'date': min_sleep[0], 'hours': round(min_sleep[1], 2)},
            'max_sleep_night': {'date': max_sleep[0], 'hours': round(max_sleep[1], 2)},
            'consistency_score': round(consistency_score, 2),
            'total_nights': len(nights),
        }

    except Exception as e:
        return {'error': str(e)}


@mcp.tool()
def correlate_env_with_sleep(sleep_date: str) -> dict:
    """
    Join environmental data during sleep hours for a specific night.

    Args:
        sleep_date: Date in YYYY-MM-DD format

    Returns:
        Dictionary containing:
        - date: Sleep date
        - sleep_window: Bedtime and wake time
        - env_conditions: Average environmental conditions during sleep
    """
    try:
        env_readings_table, _ = get_dynamodb_tables()
        # Get sleep data for this date
        sleep_data = query_sleep_data(sleep_date, sleep_date)
        nights = sleep_data.get('nights', [])

        if not nights:
            return {'error': f'No sleep data found for {sleep_date}'}

        night = nights[0]
        summary = night['summary']

        bedtime = summary.get('bedtime')
        risetime = summary.get('risetime')

        if not bedtime or not risetime:
            return {'error': 'Missing bedtime or risetime data'}

        # Convert timestamps to minute precision
        bedtime_min = int(bedtime / 60)
        risetime_min = int(risetime / 60)

        # Query environmental data during sleep window
        # Handle overnight sleep (bedtime on one day, wake on next)
        bedtime_date = datetime.fromtimestamp(bedtime).strftime("%Y-%m-%d")
        risetime_date = datetime.fromtimestamp(risetime).strftime("%Y-%m-%d")

        readings = []

        # Get readings from bedtime day
        response1 = env_readings_table.query(
            KeyConditionExpression=Key('day').eq(bedtime_date) & Key('ts_min').gte(bedtime_min)
        )
        readings.extend(response1.get('Items', []))

        # If overnight, get readings from wake day
        if bedtime_date != risetime_date:
            response2 = env_readings_table.query(
                KeyConditionExpression=Key('day').eq(risetime_date) & Key('ts_min').lte(risetime_min)
            )
            readings.extend(response2.get('Items', []))
        else:
            # Same day, just filter by risetime
            readings = [r for r in readings if r['ts_min'] <= risetime_min]

        if not readings:
            return {
                'date': sleep_date,
                'sleep_window': {
                    'bedtime': datetime.fromtimestamp(bedtime).isoformat(),
                    'risetime': datetime.fromtimestamp(risetime).isoformat(),
                },
                'env_conditions': {'error': 'No environmental data during sleep window'},
            }

        # Calculate averages
        temps = [r['temp_c'] for r in readings if 'temp_c' in r]
        humidities = [r['humidity_pct'] for r in readings if 'humidity_pct' in r]
        pressures = [r['pressure_hpa'] for r in readings if 'pressure_hpa' in r]
        lights = [r['ambient_lux'] for r in readings if 'ambient_lux' in r]
        iaqs = [r['iaq'] for r in readings if 'iaq' in r]
        noises = [r['noise_db'] for r in readings if 'noise_db' in r]

        env_conditions = {
            'temp_avg_c': round(sum(temps) / len(temps), 2) if temps else None,
            'temp_min_c': round(min(temps), 2) if temps else None,
            'temp_max_c': round(max(temps), 2) if temps else None,
            'humidity_avg_pct': round(sum(humidities) / len(humidities), 2) if humidities else None,
            'humidity_min_pct': round(min(humidities), 2) if humidities else None,
            'humidity_max_pct': round(max(humidities), 2) if humidities else None,
            'pressure_avg_hpa': round(sum(pressures) / len(pressures), 2) if pressures else None,
            'light_avg_lux': round(sum(lights) / len(lights), 2) if lights else None,
            'light_max_lux': round(max(lights), 2) if lights else None,
            'iaq_avg': round(sum(iaqs) / len(iaqs), 2) if iaqs else None,
            'noise_avg_db': round(sum(noises) / len(noises), 2) if noises else None,
            'noise_max_db': round(max(noises), 2) if noises else None,
            'readings_count': len(readings),
        }

        return cast(
            dict[Any, Any],
            decimal_to_float(
                {
                    'date': sleep_date,
                    'sleep_window': {
                        'bedtime': datetime.fromtimestamp(bedtime).isoformat(),
                        'risetime': datetime.fromtimestamp(risetime).isoformat(),
                        'duration_hours': round((risetime - bedtime) / 3600, 2),
                    },
                    'env_conditions': env_conditions,
                }
            ),
        )

    except Exception as e:
        return {'error': str(e)}


@mcp.tool()
def get_week_over_week_comparison(current_week_start: str, previous_week_start: str) -> dict:
    """
    Compare current week metrics to previous week.

    Args:
        current_week_start: Start date of current week (YYYY-MM-DD, should be Monday)
        previous_week_start: Start date of previous week (YYYY-MM-DD, should be Monday)

    Returns:
        Dictionary containing:
        - current_week: Summary stats for current week
        - previous_week: Summary stats for previous week
        - deltas: Differences between weeks
    """
    try:
        # Calculate end dates (7 days from start)
        current_start = datetime.strptime(current_week_start, "%Y-%m-%d")
        current_end = current_start + timedelta(days=6)

        previous_start = datetime.strptime(previous_week_start, "%Y-%m-%d")
        previous_end = previous_start + timedelta(days=6)

        # Get stats for both weeks
        current_stats = get_sleep_summary_stats(current_week_start, current_end.strftime("%Y-%m-%d"))

        previous_stats = get_sleep_summary_stats(previous_week_start, previous_end.strftime("%Y-%m-%d"))

        if 'error' in current_stats or 'error' in previous_stats:
            return {
                'current_week': current_stats,
                'previous_week': previous_stats,
                'deltas': {'error': 'Missing data for one or both weeks'},
            }

        # Calculate deltas
        deltas = {
            'sleep_hours_delta': round(current_stats['total_sleep_hours'] - previous_stats['total_sleep_hours'], 2),
            'avg_sleep_delta': round(current_stats['avg_sleep_hours'] - previous_stats['avg_sleep_hours'], 2),
            'efficiency_delta': round(current_stats['avg_efficiency'] - previous_stats['avg_efficiency'], 2),
            'score_delta': round(current_stats['avg_score'] - previous_stats['avg_score'], 2),
            'deep_sleep_delta': round(current_stats['avg_deep_min'] - previous_stats['avg_deep_min'], 2),
            'rem_sleep_delta': round(current_stats['avg_rem_min'] - previous_stats['avg_rem_min'], 2),
            'consistency_delta': round(current_stats['consistency_score'] - previous_stats['consistency_score'], 2),
        }

        return {'current_week': current_stats, 'previous_week': previous_stats, 'deltas': deltas}

    except Exception as e:
        return {'error': str(e)}


def lambda_handler(event: Any, context: Any) -> dict[str, Any]:
    """
    Lambda handler for MCP server.

    This Lambda is invoked by the Strands agent via function URL.
    It processes MCP protocol requests and returns responses.
    """
    try:
        # Parse the MCP request from the event body
        json.loads(event.get('body', '{}'))

        # For now, return server info
        # The actual MCP protocol handling will be done by FastMCP
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps(
                {
                    'server': 'sleep-data-mcp-server',
                    'version': '1.0.0',
                    'tools': [
                        'query_sleep_data',
                        'query_env_data',
                        'get_sleep_summary_stats',
                        'correlate_env_with_sleep',
                        'get_week_over_week_comparison',
                    ],
                }
            ),
        }

    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': str(e)}),
        }


# For local testing
if __name__ == "__main__":
    # Set environment variables for testing
    os.environ['ENV_READINGS_TABLE'] = 'EnvReadingsTable'
    os.environ['SLEEP_SESSIONS_TABLE'] = 'SleepSessionsTable'

    # Run the MCP server
    mcp.run(transport="stdio")
