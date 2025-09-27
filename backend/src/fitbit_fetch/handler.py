from __future__ import annotations

from typing import Any

from aws_lambda_powertools import Logger

from common.ddb import get_dynamodb, put_daily_summary, put_sleep_stage_segment
from common.models import DailySummaryModel, SleepStageSegmentModel

logger = Logger()
ddb = get_dynamodb()


@logger.inject_lambda_context
def lambda_handler(event: dict[str, Any], context: object) -> dict[str, Any]:
    # For now, accept pre-fetched data via event for testing; later we will call Fitbit API.
    segments: list[dict[str, Any]] = event.get("segments") or []
    summary: dict[str, Any] | None = event.get("summary")

    written_segments = 0
    for seg in segments:
        model = SleepStageSegmentModel(**seg)
        put_sleep_stage_segment(ddb, model.model_dump())
        written_segments += 1

    if summary:
        s = DailySummaryModel(**summary)
        put_daily_summary(ddb, s.model_dump())

    return {"ok": True, "segments": written_segments, "summary": bool(summary)}
