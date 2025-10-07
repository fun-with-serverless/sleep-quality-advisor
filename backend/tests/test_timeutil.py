def test_day_from_epoch_minutes() -> None:
    from src.common.timeutil import day_from_epoch_minutes

    # 2025-01-01 00:00 UTC is 1735689600 seconds -> minutes = 28928160
    assert day_from_epoch_minutes(1735689600 // 60) == "2025-01-01"
