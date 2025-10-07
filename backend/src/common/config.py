import os
from typing import Final

ENV_READINGS_TABLE: Final[str] = os.environ["ENV_READINGS_TABLE"]
SLEEP_SESSIONS_TABLE: Final[str] = os.environ["SLEEP_SESSIONS_TABLE"]
INGEST_SHARED_SECRET_NAME: Final[str] = os.environ.get("INGEST_SHARED_SECRET_NAME", "")
