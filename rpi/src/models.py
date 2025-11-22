from pydantic import BaseModel


class EnvReadingModel(BaseModel):
    day: str
    ts_min: int
    temp_c: float | None = None
    humidity_pct: float | None = None
    pressure_hpa: float | None = None
    ambient_lux: float | None = None
    iaq: float | None = None
    noise_db: float | None = None
    deviceId: str | None = None
