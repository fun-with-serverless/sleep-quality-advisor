from datetime import UTC, datetime


def day_from_epoch_minutes(ts_min: int) -> str:
    dt = datetime.fromtimestamp(ts_min * 60, tz=UTC)
    return dt.strftime("%Y-%m-%d")
