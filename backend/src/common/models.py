from typing import Literal

from pydantic import BaseModel, Field

SleepStage = Literal["Awake", "Light", "Deep", "REM"]


class EnvReadingModel(BaseModel):
    day: str
    ts_min: int
    temp_c: float | None = None
    humidity_pct: float | None = None
    pressure_hpa: float | None = None
    iaq: float | None = None
    noise_db: float | None = None
    deviceId: str | None = None


class SleepStageSegmentModel(BaseModel):
    sleepDate: str
    segmentStart: int
    stage: SleepStage
    duration_s: int


class DailySummaryModel(BaseModel):
    sleepDate: str
    segmentStart: Literal["SUMMARY"] = Field(default="SUMMARY")
    score: int
    efficiency: float
    rem_min: int
    deep_min: int
    light_min: int
    total_min: int
    bedtime: int
    risetime: int
