import contextlib
import json
import sqlite3
import time
from collections.abc import Callable
from typing import Any


class OfflineQueue:
    """SQLite-backed FIFO queue for payloads with a row cap and dedupe.

    Dedupe key: (deviceId, ts_min)
    Oldest-first order: (ts_min, id)
    """

    def __init__(self, db_path: str, max_rows: int) -> None:
        self.db_path = db_path
        self.max_rows = max_rows
        # check_same_thread=False because this may be called from different contexts in the future
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                deviceId TEXT NOT NULL,
                ts_min INTEGER NOT NULL,
                payload_json TEXT NOT NULL,
                created_at INTEGER NOT NULL
            )
            """
        )
        self._conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_queue_unique ON queue(deviceId, ts_min)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_queue_order ON queue(ts_min, id)")
        self._conn.commit()

    def close(self) -> None:
        with contextlib.suppress(Exception):
            self._conn.close()

    def enqueue(self, payload: dict[str, Any]) -> None:
        """Insert payload if not already present, then enforce row cap."""
        device_id = str(payload["deviceId"])  # required key
        ts_min = int(payload["ts_min"])  # required key
        payload_json = json.dumps(payload, separators=(",", ":"))
        now = int(time.time())
        cur = self._conn.cursor()
        cur.execute(
            """
            INSERT OR IGNORE INTO queue(deviceId, ts_min, payload_json, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (device_id, ts_min, payload_json, now),
        )
        self._conn.commit()
        self.prune_to_row_cap(self.max_rows)

    def dequeue_batch(self, limit: int) -> list[tuple[int, dict[str, Any]]]:
        """Return up to limit oldest entries as (id, payload) tuples."""
        cur = self._conn.cursor()
        cur.execute(
            "SELECT id, payload_json FROM queue ORDER BY ts_min ASC, id ASC LIMIT ?",
            (int(limit),),
        )
        rows = cur.fetchall()
        result: list[tuple[int, dict[str, Any]]] = []
        for row in rows:
            rid = int(row[0])
            payload = json.loads(str(row[1]))
            result.append((rid, payload))
        return result

    def delete(self, ids: list[int]) -> int:
        if not ids:
            return 0
        placeholders = ",".join(["?"] * len(ids))
        cur = self._conn.cursor()
        cur.execute(f"DELETE FROM queue WHERE id IN ({placeholders})", [int(x) for x in ids])
        self._conn.commit()
        return int(cur.rowcount or 0)

    def count(self) -> int:
        cur = self._conn.cursor()
        cur.execute("SELECT COUNT(1) FROM queue")
        row = cur.fetchone()
        return int(row[0]) if row else 0

    def prune_to_row_cap(self, max_rows: int) -> None:
        max_rows = max(0, int(max_rows))
        total = self.count()
        if total <= max_rows:
            return
        to_remove = total - max_rows
        cur = self._conn.cursor()
        cur.execute(
            "DELETE FROM queue WHERE id IN (SELECT id FROM queue ORDER BY ts_min ASC, id ASC LIMIT ?)",
            (to_remove,),
        )
        self._conn.commit()

    def flush_once(self, max_batch: int, send_func: Callable[[dict[str, Any]], int]) -> int:
        """Attempt to send up to max_batch oldest items.

        Stops at first failure (exception or non-2xx). Returns number of flushed items.
        """
        batch = self.dequeue_batch(int(max_batch))
        flushed = 0
        for rid, payload in batch:
            try:
                code = int(send_func(payload))
                if 200 <= code < 300:
                    self.delete([rid])
                    flushed += 1
                else:
                    # Stop on first non-2xx to avoid busy looping when remote is down
                    break
            except Exception:
                # Stop on first exception; assume network outage persists
                break
        return flushed
