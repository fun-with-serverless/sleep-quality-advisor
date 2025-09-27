from __future__ import annotations

import json
from typing import Any

from aws_lambda_powertools import Logger
from botocore.exceptions import ClientError

from common.ddb import get_dynamodb, put_env_reading
from common.models import EnvReadingModel
from common.timeutil import day_from_epoch_minutes

logger = Logger()

ddb = get_dynamodb()


@logger.inject_lambda_context
def lambda_handler(event: dict[str, Any], context: object) -> dict[str, Any]:
    failures: list[dict[str, str]] = []

    for record in event.get("Records", []):
        receipt = record.get("receiptHandle")
        body = record.get("body") or "{}"
        try:
            raw = json.loads(body)
            ts_min = int(raw["ts_min"])  # raises if missing
            day = raw.get("day") or day_from_epoch_minutes(ts_min)
            model = EnvReadingModel(
                day=day,
                ts_min=ts_min,
                **{k: v for k, v in raw.items() if k not in {"day", "ts_min"}},
            )
            put_env_reading(ddb, model.model_dump(exclude_none=True))
        except ClientError as ce:
            code = ce.response.get("Error", {}).get("Code", "")
            if code == "ConditionalCheckFailedException":
                logger.info("Duplicate item; treating as success")
            else:
                logger.exception("DynamoDB error; marking failure")
                if receipt:
                    failures.append({"itemIdentifier": receipt})
        except Exception:
            logger.exception("Failed processing record; marking failure")
            if receipt:
                failures.append({"itemIdentifier": receipt})

    # SQS batch response format
    return {"batchItemFailures": failures}
