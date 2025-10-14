import contextlib
import os
from enum import StrEnum
from typing import Final

from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError


class LogLevel(StrEnum):
    CRITICAL = "CRITICAL"
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"
    DEBUG = "DEBUG"


class Settings(BaseModel):
    endpoint_url: str = Field(validation_alias="ENDPOINT_URL")
    post_secret: str = Field(validation_alias="POST_SECRET")
    user_agent: str = Field(default="sleep-quality-sensors/1.0", validation_alias="USER_AGENT")

    sample_interval_secs: int = Field(default=10, validation_alias="SAMPLE_INTERVAL_SECS")
    warmup_duration_secs: int = Field(default=300, validation_alias="WARMUP_DURATION_SECS")

    i2c_bus: int = Field(default=1, validation_alias="I2C_BUS")
    i2c_address: int = Field(default=0x76, validation_alias="I2C_ADDRESS")

    log_level: LogLevel = Field(default=LogLevel.INFO, validation_alias="LOG_LEVEL")


ENV_KEYS: Final[tuple[str, ...]] = (
    "ENDPOINT_URL",
    "POST_SECRET",
    "USER_AGENT",
    "SAMPLE_INTERVAL_SECS",
    "WARMUP_DURATION_SECS",
    "I2C_BUS",
    "I2C_ADDRESS",
    "LOG_LEVEL",
)


def load_settings() -> Settings:
    # Load .env if present (does nothing if file missing)
    load_dotenv()
    # Load directly from environment; also picks up values from .env above
    data: dict[str, str] = {}
    for key in ENV_KEYS:
        if key in os.environ:
            data[key] = os.environ[key]

    # Handle hex I2C address if provided
    if "I2C_ADDRESS" in data:
        val = data["I2C_ADDRESS"]
        with contextlib.suppress(Exception):
            data["I2C_ADDRESS"] = str(int(val, 0))

    try:
        return Settings.model_validate(data)
    except ValidationError as e:
        missing = [k for k in ("ENDPOINT_URL", "POST_SECRET") if k not in data]
        if missing:
            raise RuntimeError(f"Missing required configuration: {', '.join(missing)}") from e
        raise
