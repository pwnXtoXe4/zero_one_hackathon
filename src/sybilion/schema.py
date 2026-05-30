"""Pydantic models for Sybilion API request/response shapes."""

from pydantic import BaseModel, Field
from typing import Optional


# ─── Forecast Request ───────────────────────────────────────────────

class TimeseriesMetadata(BaseModel):
    title: str
    description: str
    keywords: list[str]


class ForecastRequest(BaseModel):
    pipeline_version: str = "v1"
    frequency: str = "monthly"
    soft_horizon: int = 6
    recency_factor: float = 0.6
    backtest: bool = True
    timeseries_metadata: TimeseriesMetadata
    timeseries: dict[str, float]


# ─── Forecast Response (forecast.json) ─────────────────────────────

class QuantileForecast(BaseModel):
    p10: float = Field(alias="0.1")
    p50: float = Field(alias="0.5")
    p90: float = Field(alias="0.9")

    class Config:
        populate_by_name = True


class ForecastPoint(BaseModel):
    forecast: float
    quantile_forecast: Optional[QuantileForecast] = None


class ForecastData(BaseModel):
    forecast_horizon: int
    forecast_start: str
    forecast_end: str
    forecast_series: dict[str, ForecastPoint]


class ForecastArtifact(BaseModel):
    version: str
    data: ForecastData


# ─── External Signals (external_signals.json) ──────────────────────

class DriverImportance(BaseModel):
    importance: float
    direction: float = 0.0  # -1 to 1


class ExternalDriver(BaseModel):
    name: str
    importance: dict[str, DriverImportance]  # keyed by month label
    direction: dict[str, float] = Field(default_factory=dict)
    correlation: dict[str, float] = Field(default_factory=dict)


class ExternalSignalsArtifact(BaseModel):
    version: str
    data: dict[str, ExternalDriver]


# ─── Backtest Metrics ──────────────────────────────────────────────

class BacktestWindow(BaseModel):
    window: str
    mape: float
    rmse: float


class BacktestMetricsArtifact(BaseModel):
    version: str
    data: dict[str, list[BacktestWindow]]


# ─── Job Status ────────────────────────────────────────────────────

class JobArtifact(BaseModel):
    name: str
    href: str
    content_type: str = "application/json"
    size: int = 0


class JobStatus(BaseModel):
    job_id: str
    status: str
    settled: bool
    eur_cents_final: Optional[int] = None
    artifacts: list[JobArtifact] = Field(default_factory=list)
