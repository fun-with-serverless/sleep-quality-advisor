from typing import Any

from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.batch import (
    BatchProcessor,
    EventType,
    process_partial_response,
)
from aws_lambda_powertools.utilities.batch.types import PartialItemFailureResponse
from aws_lambda_powertools.utilities.data_classes.sqs_event import SQSRecord
from botocore.exceptions import ClientError

from common.ddb import get_dynamodb, put_env_reading
from common.models import EnvReadingModel

logger = Logger()

ddb = get_dynamodb()
processor = BatchProcessor(event_type=EventType.SQS)


def record_handler(record: SQSRecord) -> None:
    body = record.body or "{}"
    try:
        model = EnvReadingModel.model_validate_json(body)
        put_env_reading(ddb, model.model_dump(exclude_none=True))
    except ClientError as ce:
        code = ce.response.get("Error", {}).get("Code", "")
        if code == "ConditionalCheckFailedException":
            logger.info("Duplicate item; treating as success")
            return
        logger.exception("DynamoDB client error while processing SQS record")
        raise
    except Exception:
        logger.exception("Unhandled error while processing SQS record")
        raise


@logger.inject_lambda_context
def lambda_handler(event: dict[str, Any], context: Any) -> PartialItemFailureResponse:
    return process_partial_response(
        event=event,
        record_handler=record_handler,
        processor=processor,
        context=context,  # type: ignore[arg-type]
    )
