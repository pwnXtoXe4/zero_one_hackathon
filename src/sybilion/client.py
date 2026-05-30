"""Sybilion API wrapper with mock fallback for offline/demo use."""

import json
import os
import time
from pathlib import Path
from typing import Optional

import pandas as pd

from src.sybilion.keywords import select_keywords

# Try importing the real SDK; fall back to mock if unavailable
try:
    from sybilion import Client as _SybilionClient
    HAS_SDK = True
except ImportError:
    HAS_SDK = False


class ForecastArtifacts:
    """Typed container for all artifacts from a completed forecast job."""

    def __init__(self, forecast: dict, signals: dict, backtest: Optional[dict] = None):
        self.forecast = forecast
        self.signals = signals
        self.backtest = backtest

    @property
    def forecast_series(self) -> dict:
        return self.forecast.get("data", {}).get("forecast_series", {})

    @property
    def drivers(self) -> dict:
        return self.signals.get("data", {})


class SybilionWrapper:
    """Wrapper around the Sybilion SDK with caching and mock fallback."""

    def __init__(
        self,
        api_token: Optional[str] = None,
        cache_dir: str = "data/prepared",
        use_mock: bool = False,
    ):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        if use_mock or not HAS_SDK or not api_token:
            self._client = MockSybilionClient()
            self._mode = "mock"
        else:
            self._client = _SybilionClient(token=api_token)
            self._mode = "live"

    @property
    def mode(self) -> str:
        return self._mode

    def submit_and_wait(
        self,
        series: pd.Series,
        keywords: Optional[list[str]] = None,
        horizon: int = 6,
        title: str = "Carbon Forecast",
        description: str = "Monthly carbon market time series",
        max_wait: int = 600,
        poll_interval: int = 10,
    ) -> ForecastArtifacts:
        """Submit a forecast job, poll until settled, return artifacts."""
        if keywords is None:
            keywords = select_keywords(focus="carbon_market", horizon=horizon)

        # Check cache first
        cache_key = self._cache_key(series, keywords, horizon)
        cached = self._load_cache(cache_key)
        if cached:
            return cached

        # Build request body
        timeseries = {
            pd.Timestamp(k).strftime("%Y-%m-%d"): float(v)
            for k, v in series.items()
        }

        body = {
            "pipeline_version": "v1",
            "frequency": "monthly",
            "soft_horizon": horizon,
            "recency_factor": 0.6,
            "backtest": True,
            "timeseries_metadata": {
                "title": title,
                "description": description,
                "keywords": keywords,
            },
            "timeseries": timeseries,
        }

        if self._mode == "mock":
            artifacts = self._client.submit_and_wait(body)
        else:
            artifacts = self._submit_live(body, max_wait, poll_interval)

        self._save_cache(cache_key, artifacts)
        return artifacts

    def get_drivers_sync(
        self,
        series: pd.Series,
        keywords: Optional[list[str]] = None,
    ) -> dict:
        """Synchronous driver recommendations (no polling needed)."""
        if keywords is None:
            keywords = select_keywords(focus="carbon_market")
        # For simplicity, this uses the same submit flow in mock mode
        # In live mode, would call POST /api/v1/drivers directly
        return {}

    # ─── Internal ─────────────────────────────────────────────────

    def _submit_live(self, body: dict, max_wait: int, poll_interval: int) -> ForecastArtifacts:
        """Submit to live API and poll."""
        submit = self._client.submit_forecast(body)
        job_id = submit.job_id
        print(f"  [Sybilion] Job submitted: {job_id}")
        print(f"  [Sybilion] Polling (max {max_wait}s, every {poll_interval}s)...")

        job = self._client.wait_forecast(job_id, poll_s=poll_interval, timeout_s=max_wait)
        print(f"  [Sybilion] Job completed. Cost: {job.eur_cents_final} cents")

        # Fetch artifacts
        forecast_data = json.loads(self._client.get_forecast_artifact(job_id, "forecast.json"))
        signals_data = json.loads(self._client.get_forecast_artifact(job_id, "external_signals.json"))
        backtest_data = None
        try:
            backtest_data = json.loads(self._client.get_forecast_artifact(job_id, "backtest_metrics.json"))
        except Exception:
            pass

        return ForecastArtifacts(forecast_data, signals_data, backtest_data)

    def _cache_key(self, series: pd.Series, keywords: list[str], horizon: int) -> str:
        """Generate a deterministic cache key from input data."""
        import hashlib
        content = f"{series.to_dict()}|{sorted(keywords)}|{horizon}"
        return hashlib.md5(content.encode()).hexdigest()[:12]

    def _save_cache(self, key: str, artifacts: ForecastArtifacts):
        """Cache artifacts to disk."""
        path = self.cache_dir / f"cache_{key}.json"
        data = {
            "forecast": artifacts.forecast,
            "signals": artifacts.signals,
            "backtest": artifacts.backtest,
        }
        with open(path, "w") as f:
            json.dump(data, f)

    def _load_cache(self, key: str) -> Optional[ForecastArtifacts]:
        """Load cached artifacts if available."""
        import glob
        matches = glob.glob(str(self.cache_dir / f"cache_{key}.json"))
        if not matches:
            return None
        with open(matches[0]) as f:
            data = json.load(f)
        return ForecastArtifacts(data["forecast"], data["signals"], data.get("backtest"))


class MockSybilionClient:
    """Returns realistic synthetic forecast data. Used when API is unavailable."""

    @staticmethod
    def submit_and_wait(body: dict) -> ForecastArtifacts:
        """Generate realistic synthetic forecast artifacts."""
        series = body["timeseries"]
        horizon = body["soft_horizon"]
        keywords = body["timeseries_metadata"]["keywords"]

        dates = sorted(series.keys())
        values = list(series.values())

        # Compute basic stats from the input series
        recent = values[-12:]
        mean_recent = sum(recent) / len(recent)
        std_recent = (sum((x - mean_recent) ** 2 for x in recent) / len(recent)) ** 0.5
        trend = (values[-1] - values[0]) / len(values) if len(values) > 1 else 0

        # Generate forecast with upward bias (typical for carbon markets)
        forecast_series = {}
        base_value = values[-1]
        for i in range(1, horizon + 1):
            month_date = _add_months(dates[-1], i)
            point = base_value + trend * i * 0.3 + mean_recent * 0.005 * i
            noise = std_recent * 0.15
            band_width = std_recent * (0.10 + 0.04 * i)  # bands widen over time

            forecast_series[month_date] = {
                "forecast": round(point, 2),
                "quantile_forecast": {
                    "0.1": round(point - band_width, 2),
                    "0.5": round(point, 2),
                    "0.9": round(point + band_width, 2),
                },
            }

        # Generate driver importance scores
        driver_base = {
            "EU ETS reform": {"m1": 0.25, "m3": 0.40, "m6": 0.45},
            "Natural gas price forecast": {"m1": 0.30, "m3": 0.20, "m6": 0.10},
            "CBAM implementation": {"m1": 0.10, "m3": 0.15, "m6": 0.25},
            "Renewable energy auction results": {"m1": 0.15, "m3": 0.22, "m6": 0.18},
            "Industrial production index": {"m1": 0.20, "m3": 0.18, "m6": 0.12},
        }

        # Build external_signals.json shape
        signals_data = {}
        for driver_name, importance_values in driver_base.items():
            signals_data[driver_name] = {
                "importance": {
                    f"month_{k}": {"importance": v}
                    for k, v in importance_values.items()
                }
            }

        # Build forecast.json shape
        start_date = _add_months(dates[-1], 1)
        end_date = _add_months(dates[-1], horizon)

        forecast_data = {
            "version": "1.1",
            "data": {
                "forecast_horizon": horizon,
                "forecast_start": start_date,
                "forecast_end": end_date,
                "forecast_series": forecast_series,
            },
        }

        # Build backtest_metrics.json shape
        backtest_data = {
            "version": "1.1",
            "data": {
                "rolling_windows": [
                    {"window": "6m", "mape": 0.12, "rmse": std_recent * 0.5},
                    {"window": "12m", "mape": 0.15, "rmse": std_recent * 0.7},
                    {"window": "24m", "mape": 0.18, "rmse": std_recent * 0.9},
                ]
            },
        }

        return ForecastArtifacts(forecast_data, {"version": "1.1", "data": signals_data}, backtest_data)


def _add_months(date_str: str, months: int) -> str:
    """Add months to a YYYY-MM-DD date string."""
    dt = pd.Timestamp(date_str)
    return (dt + pd.DateOffset(months=months)).strftime("%Y-%m-%d")
