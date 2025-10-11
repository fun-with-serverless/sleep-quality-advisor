import os
from datetime import UTC, datetime
from typing import Any

from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities import parameters
from aws_lambda_powertools.utilities.data_classes import EventBridgeEvent, event_source

from common.ddb import get_dynamodb, put_sleep_stage_segment
from common.fitbit_client import FitbitClient
from common.models import SleepStageSegmentModel

logger = Logger()
ddb = get_dynamodb()

refresh_secret_name = os.environ.get("FITBIT_REFRESH_SECRET_NAME", "fitbit/refresh/token")
client_secret_name = os.environ.get("FITBIT_CLIENT_SECRET_NAME", "fitbit/client/secret")
client_id_param_name = os.environ.get("FITBIT_CLIENT_ID_PARAM_NAME", "fitbit/client/id")

LEVEL_TO_STAGE: dict[str, str] = {"wake": "Awake", "light": "Light", "deep": "Deep", "rem": "REM"}


@event_source(data_class=EventBridgeEvent)
@logger.inject_lambda_context
def lambda_handler(event: EventBridgeEvent, context: object) -> dict[str, Any]:
    # Initialize client
    client = FitbitClient(client_id_param_name=client_id_param_name, client_secret_name=client_secret_name)

    try:
        # Read refresh token and exchange for access token
        refresh_token = parameters.get_secret(refresh_secret_name)
        access_token, new_refresh_token = client.refresh_access_token(refresh_token)
        if new_refresh_token and new_refresh_token != refresh_token:
            parameters.set_secret(refresh_secret_name, new_refresh_token)

        # Determine current UTC date
        date_str = datetime.now(UTC).strftime("%Y-%m-%d")

        # Fetch sleep logs for current day
        payload = client.get_sleep_by_date(date_str, access_token)

        # Process only stages logs

        written_segments = 0
        for item in payload.get("sleep", []):
            if item.get("type") != "stages":
                continue
            date_of_sleep = str(item.get("dateOfSleep"))
            levels = item.get("levels") or {}
            for d in levels.get("data", []):
                level = str(d.get("level"))
                mapped = LEVEL_TO_STAGE.get(level)
                if not mapped:
                    logger.warning("unmapped sleep stage level", value=level)
                    continue
                dt_raw = str(d.get("dateTime"))
                # Fitbit returns ISO like 2020-02-20T23:21:30.000; treat as UTC
                try:
                    dt = datetime.fromisoformat(dt_raw.replace("Z", "").rstrip("Z"))
                except Exception:  # noqa: BLE001
                    logger.warning("invalid datetime", value=dt_raw)
                    continue
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=UTC)
                segment_start = int(dt.timestamp() // 60)
                seconds = int(d.get("seconds", 0))
                model = SleepStageSegmentModel(
                    sleepDate=date_of_sleep,
                    segmentStart=segment_start,
                    stage=mapped,  # type: ignore[arg-type]
                    duration_s=seconds,
                )
                put_sleep_stage_segment(ddb, model.model_dump())
                written_segments += 1

        return {"ok": True, "segments": written_segments}
    except Exception as exc:
        logger.exception("fitbit_fetch_failed")
        raise exc
