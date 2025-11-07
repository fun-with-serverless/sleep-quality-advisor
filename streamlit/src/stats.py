from enum import Enum
from typing import Dict, List

import numpy as np
import pandas as pd
from datetime import tzinfo


class BucketSize(Enum):
    FIVE_MINUTES = 5
    ONE_HOUR = 60


class Percentile(Enum):
    P50 = 50
    P90 = 90
    P99 = 99
    MAX = 1000  # sentinel for max


def _bucket_minute(minute_of_day: pd.Series, bucket: BucketSize) -> pd.Series:
    size = int(bucket.value)
    return (minute_of_day // size) * size


def _nan_percentile(values: np.ndarray, p: int) -> float | None:
    try:
        return float(np.nanpercentile(values, p))
    except Exception:
        return None


def _nan_mean(values: np.ndarray) -> float | None:
    try:
        return float(np.nanmean(values))
    except Exception:
        return None


def _nan_max(values: np.ndarray) -> float | None:
    try:
        return float(np.nanmax(values))
    except Exception:
        return None


def aggregate_buckets(df: pd.DataFrame, bucket: BucketSize, local_tz: tzinfo | None = None) -> pd.DataFrame:
    """Aggregate readings into continuous time buckets using local timezone.

    Returns a DataFrame with columns:
      bucket_time (tz-aware), temp_avg, temp_p50, temp_p90, temp_p99, temp_max,
      humidity_avg, humidity_p50, humidity_p90, humidity_p99, humidity_max
    """
    if df is None or df.empty:
        return pd.DataFrame(
            columns=[
                "bucket_time",
                "temp_avg",
                "temp_p50",
                "temp_p90",
                "temp_p99",
                "temp_max",
                "humidity_avg",
                "humidity_p50",
                "humidity_p90",
                "humidity_p99",
                "humidity_max",
            ]
        )

    work = df.copy()
    # Convert epoch minutes to timezone-aware datetime in local timezone
    ts = pd.to_datetime(work["ts_min"] * 60, unit="s", utc=True)
    if local_tz is not None:
        ts = ts.dt.tz_convert(local_tz)
    work["local_dt"] = ts

    bucket_minutes = int(bucket.value)
    work["bucket_time"] = work["local_dt"].dt.floor(f"{bucket_minutes}min")

    results: List[Dict[str, float | int | None]] = []
    for bkt, g in work.groupby("bucket_time"):
        temps = g.get("temp_c")
        hums = g.get("humidity_pct")
        t_arr = temps.to_numpy(dtype=float) if temps is not None else np.array([], dtype=float)
        h_arr = hums.to_numpy(dtype=float) if hums is not None else np.array([], dtype=float)

        row = {
            "bucket_time": bkt,
            # temperature
            "temp_avg": _nan_mean(t_arr),
            "temp_p50": _nan_percentile(t_arr, 50),
            "temp_p90": _nan_percentile(t_arr, 90),
            "temp_p99": _nan_percentile(t_arr, 99),
            "temp_max": _nan_max(t_arr),
            # humidity
            "humidity_avg": _nan_mean(h_arr),
            "humidity_p50": _nan_percentile(h_arr, 50),
            "humidity_p90": _nan_percentile(h_arr, 90),
            "humidity_p99": _nan_percentile(h_arr, 99),
            "humidity_max": _nan_max(h_arr),
        }
        results.append(row)

    out = pd.DataFrame(results).sort_values("bucket_time").reset_index(drop=True)
    return out


def summarize_timeframe(df: pd.DataFrame) -> Dict[str, Dict[str, float | None]]:
    """Compute min, max, std across the full timeframe for temp and humidity."""
    if df is None or df.empty:
        return {
            "temperature": {"min": None, "max": None, "std": None},
            "humidity": {"min": None, "max": None, "std": None},
        }

    t = df.get("temp_c").to_numpy(dtype=float)
    h = df.get("humidity_pct").to_numpy(dtype=float)

    def _nan_std(values: np.ndarray) -> float | None:
        try:
            return float(np.nanstd(values, ddof=0))
        except Exception:
            return None

    def _nan_min(values: np.ndarray) -> float | None:
        try:
            return float(np.nanmin(values))
        except Exception:
            return None

    return {
        "temperature": {"min": _nan_min(t), "max": _nan_max(t), "std": _nan_std(t)},
        "humidity": {"min": _nan_min(h), "max": _nan_max(h), "std": _nan_std(h)},
    }


