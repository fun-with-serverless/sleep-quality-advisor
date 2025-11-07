from typing import Any

from src.offline_queue import OfflineQueue


def _make_payload(device_id: str, ts_min: int, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    base = {"deviceId": device_id, "ts_min": ts_min, "day": ts_min // 1440}
    if extra:
        base.update(extra)
    return base


def test_enqueue_dedupe_and_prune(tmp_path) -> None:  # type: ignore[no-untyped-def]
    db_path = tmp_path / "spool.db"
    q = OfflineQueue(str(db_path), max_rows=3)

    # Enqueue 5 items, capped to 3 rows → only last 3 remain
    for i in range(5):
        q.enqueue(_make_payload("dev1", 100 + i))

    assert q.count() == 3
    rows = q.dequeue_batch(10)
    # Remaining should be ts_min 102,103,104
    assert [p[1]["ts_min"] for p in rows] == [102, 103, 104]

    # Dedupe on (deviceId, ts_min)
    q.enqueue(_make_payload("dev1", 104))
    assert q.count() == 3


def test_flush_once_stops_on_failure_and_deletes_success(tmp_path) -> None:  # type: ignore[no-untyped-def]
    db_path = tmp_path / "spool.db"
    q = OfflineQueue(str(db_path), max_rows=10)

    for i in range(3):
        q.enqueue(_make_payload("dev1", 200 + i))

    calls: list[int] = []

    def send_func(payload: dict[str, Any]) -> int:
        calls.append(payload["ts_min"])  # type: ignore[index]
        # First two succeed, third fails
        if payload["ts_min"] < 202:  # type: ignore[index]
            return 200
        raise RuntimeError("network down")

    flushed = q.flush_once(max_batch=10, send_func=send_func)
    assert flushed == 2
    assert q.count() == 1
    remaining = q.dequeue_batch(10)
    assert [p[1]["ts_min"] for p in remaining] == [202]

    # Now recovery: all sends succeed
    flushed2 = q.flush_once(max_batch=10, send_func=lambda _p: 201)
    assert flushed2 == 1
    assert q.count() == 0
