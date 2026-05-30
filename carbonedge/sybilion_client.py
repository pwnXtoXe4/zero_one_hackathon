"""
CarbonEdge -- Sybilion API Integration Layer

Wraps the Sybilion MCP forecasting API.
In hackathon context, forecasts come from the MCP tool calls.
This module provides helpers to structure requests and parse responses.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ForecastResult:
    """Parsed forecast output from Sybilion."""
    target_name: str
    current_value: float = 0.0
    forecast_points: Dict[int, Dict[str, float]] = field(default_factory=dict)
    driver_importance: Dict[str, List[float]] = field(default_factory=dict)
    backtest_accuracy: Optional[float] = None
    raw_response: Optional[Dict[str, Any]] = None

    @property
    def confidence_bands(self) -> Dict[int, Tuple[float, float]]:
        return {
            m: (d.get("low", d["value"]), d.get("high", d["value"]))
            for m, d in self.forecast_points.items()
        }

    @property
    def band_width_ratio(self) -> float:
        """Average confidence band width / mean value."""
        ratios = []
        for m, d in self.forecast_points.items():
            low = d.get("low", d["value"])
            high = d.get("high", d["value"])
            if d["value"] > 0:
                ratios.append((high - low) / d["value"])
        return sum(ratios) / len(ratios) if ratios else 1.0

    @property
    def trend(self) -> str:
        """Is the forecast trending UP, DOWN, or FLAT?"""
        if not self.forecast_points or self.current_value <= 0:
            return "FLAT"
        last = max(self.forecast_points.keys())
        ratio = self.forecast_points[last]["value"] / self.current_value
        if ratio > 1.05:
            return "UP"
        if ratio < 0.95:
            return "DOWN"
        return "FLAT"

    def confidence_level(self, horizon: int) -> str:
        """NARROW / MEDIUM / WIDE for a specific horizon."""
        if horizon not in self.forecast_points:
            return "WIDE"
        d = self.forecast_points[horizon]
        low = d.get("low", d["value"])
        high = d.get("high", d["value"])
        ratio = (high - low) / d["value"] if d["value"] > 0 else 1.0
        if ratio < 0.15:
            return "NARROW"
        if ratio < 0.40:
            return "MEDIUM"
        return "WIDE"


def build_forecast_request(
    timeseries: Dict[str, float],
    title: str,
    description: str,
    keywords: Optional[List[str]] = None,
    soft_horizon: int = 6,
    backtest: bool = True,
    hard_horizon: Optional[int] = None,
    recency_factor: float = 0.5,
    categories: Optional[List[int]] = None,
    regions: Optional[List[int]] = None,
    driver_limit: int = 1000,
) -> Dict[str, Any]:
    """
    Build a Sybilion forecast request payload.

    Parameters
    ----------
    timeseries : {YYYY-MM-DD: value}
    title : human-readable name (20-511 chars)
    description : context for the forecast pipeline (<=2048 chars)
    keywords : topic hints for driver selection (<=20, each <=255 chars)
    soft_horizon : ideal forecast horizon (1-12 months)
    backtest : whether to request backtest artifacts
    hard_horizon : minimum acceptable horizon for fallback ladder
    recency_factor : 0.0-1.0, controls news recency weight
    categories : integer category IDs to filter driver search
    regions : integer region IDs to filter driver search
    driver_limit : max candidate drivers (0-1000)
    """
    sorted_series = dict(sorted(timeseries.items()))

    request = {
        "pipeline_version": "v1",
        "soft_horizon": soft_horizon,
        "frequency": "monthly",
        "backtest": backtest,
        "recency_factor": recency_factor,
        "timeseries_metadata": {
            "title": title[:511],
            "description": description[:2048],
            "keywords": (keywords or [])[:20],
        },
        "timeseries": sorted_series,
    }

    if hard_horizon is not None:
        request["hard_horizon"] = hard_horizon

    if categories or regions:
        request["filters"] = {"limit": driver_limit}
        if categories:
            request["filters"]["categories"] = categories
        if regions:
            request["filters"]["regions"] = regions

    return request


def validate_timeseries(ts: Dict[str, float], soft_horizon: int = 6) -> Tuple[bool, str]:
    """Basic validation before submitting to Sybilion.

    Parameters
    ----------
    ts : monthly time series {YYYY-MM-DD: value}
    soft_horizon : forecast horizon, determines minimum data points required:
        1-3 months -> 40, 4-6 months -> 60, 7-12 months -> 120
    """
    if not ts:
        return False, "Timeseries is empty"

    # Determine minimum points based on soft_horizon
    if soft_horizon <= 3:
        min_points = 40
    elif soft_horizon <= 6:
        min_points = 60
    else:
        min_points = 120
    for k in ts:
        try:
            dt = datetime.strptime(k, "%Y-%m-%d")
            if dt.day != 1:
                return False, f"Date {k} is not month-aligned (use YYYY-MM-01)"
        except ValueError:
            return False, f"Invalid date format: {k}"

    # Check chronological order and no gaps
    dates = sorted(ts.keys())
    for i in range(1, len(dates)):
        d1 = datetime.strptime(dates[i - 1], "%Y-%m-%d")
        d2 = datetime.strptime(dates[i], "%Y-%m-%d")
        gap = (d2.year - d1.year) * 12 + (d2.month - d1.month)
        if gap != 1:
            return False, f"Gap between {dates[i-1]} and {dates[i]} ({gap} months)"

    # Check all values are finite
    for k, v in ts.items():
        if not isinstance(v, (int, float)) or v != v:  # NaN check
            return False, f"Non-finite value at {k}: {v}"

    # Check minimum length
    if len(ts) < min_points:
        return False, f"Need >= {min_points} data points, have {len(ts)}"

    return True, "OK"


def parse_forecast_response(
    response: Dict[str, Any],
    target_name: str,
    external_signals: Optional[Dict[str, Any]] = None,
    backtest_metrics: Optional[Dict[str, Any]] = None,
    reference_date: Optional[datetime] = None,
) -> ForecastResult:
    """
    Parse a Sybilion forecast response into CarbonEdge's ForecastResult.

    Handles the real Sybilion format:
      forecast.json -> data.forecast_series[date].forecast / .quantile_forecast
      external_signals.json -> data[driver_uuid].driver_name / .importance / .direction
      backtest_metrics.json -> data[horizon].metrics.MAPE

    Also supports simplified test/mock format.
    """
    result = ForecastResult(target_name=target_name)

    # ---- Extract forecast series ----
    # Real format: response has "data" wrapper
    if "data" in response and "forecast_series" in response["data"]:
        fs = response["data"]["forecast_series"]
        logger.debug("parse_forecast_response: detected real Sybilion format (data.forecast_series)")
    elif "forecast_series" in response:
        fs = response["forecast_series"]
        logger.debug("parse_forecast_response: detected forecast_series top-level format")
    else:
        fs = None
        logger.debug("parse_forecast_response: falling back to simplified 'forecast' branch")

    if fs:
        forecast_series = {}
        skipped = 0
        for date_str, point in fs.items():
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                month_offset = _months_from_now(dt, reference_date)

                median = point.get("forecast", 0)
                qf = point.get("quantile_forecast", {})

                forecast_series[month_offset] = {
                    "value": median,
                    "low": float(qf.get("0.10", qf.get("0.05", median * 0.85))),
                    "high": float(qf.get("0.90", qf.get("0.95", median * 1.15))),
                }
            except (ValueError, TypeError) as exc:
                logger.debug("Skipped forecast point %r: %s", date_str, exc)
                skipped += 1
                continue
        if skipped:
            logger.warning("parse_forecast_response: skipped %d malformed forecast points", skipped)
        result.forecast_points = forecast_series

    elif "forecast" in response:
        # Simplified/mock format
        forecast_series = {}
        for horizon_key, point in response["forecast"].items():
            month_offset: Optional[int] = None
            if isinstance(horizon_key, int):
                month_offset = horizon_key
            elif isinstance(horizon_key, str):
                if horizon_key.startswith("month_"):
                    try:
                        month_offset = int(horizon_key.split("_")[1])
                    except (IndexError, ValueError):
                        month_offset = None
                else:
                    # Try date format first (YYYY-MM-DD)
                    try:
                        dt = datetime.strptime(horizon_key, "%Y-%m-%d")
                        month_offset = _months_from_now(dt, reference_date)
                    except ValueError:
                        try:
                            month_offset = int(horizon_key)
                        except ValueError:
                            month_offset = None
            if month_offset is None:
                continue
            value = point.get("value", 0)
            if "confidence_band" in point:
                low = point["confidence_band"][0]
                high = point["confidence_band"][1]
            else:
                low = point.get("low", value * 0.85)
                high = point.get("high", value * 1.15)
            forecast_series[month_offset] = {
                "value": value,
                "low": low,
                "high": high,
            }
        result.forecast_points = forecast_series

    logger.info(
        "Parsed %d forecast points for target '%s' from %s",
        len(result.forecast_points),
        target_name,
        "real Sybilion format" if fs else "simplified format",
    )

    # ---- Extract driver importance from external_signals ----
    if external_signals and "data" in external_signals:
        for uuid, entry in external_signals["data"].items():
            name = entry.get("driver_name", uuid[:12])
            imp = entry.get("importance", {})
            overall = imp.get("overall", {})
            scores = [
                overall.get("min", 0),
                overall.get("mean", 0),
                overall.get("max", 0),
            ]
            result.driver_importance[name] = scores
    elif "drivers" in response:
        for driver in response["drivers"]:
            name = driver.get("name", "unknown")
            scores = []
            for key in sorted([k for k in driver if k.startswith("importance_")]):
                scores.append(driver[key])
            result.driver_importance[name] = scores
    elif "top_drivers" in response:
        # Sybilion v1 simplified artifact: { driver_name: [imp_h1, imp_h2, ...] }
        for name, scores in response["top_drivers"].items():
            if isinstance(scores, list):
                result.driver_importance[name] = [float(s) for s in scores]
            elif isinstance(scores, (int, float)):
                result.driver_importance[name] = [float(scores)]

    # ---- Extract backtest accuracy ----
    if backtest_metrics and "data" in backtest_metrics:
        best_mape = None
        for horizon_key in ["6m", "12m", "24m", "60m"]:
            hdata = backtest_metrics["data"].get(horizon_key, {})
            mape = hdata.get("metrics", {}).get("MAPE")
            if mape is not None and (best_mape is None or mape < best_mape):
                best_mape = mape
        result.backtest_accuracy = best_mape
    elif "backtest" in response:
        result.backtest_accuracy = response["backtest"].get(
            "historical_accuracy",
            response["backtest"].get("accuracy"),
        )
    elif "backtest_mape" in response:
        # Simplified artifact: MAPE is reported directly as percentage.
        try:
            result.backtest_accuracy = float(response["backtest_mape"])
        except (TypeError, ValueError) as exc:
            logger.debug("Ignored non-numeric backtest_mape=%r (%s)", response["backtest_mape"], exc)

    if result.driver_importance:
        logger.debug("Parsed %d driver importance entries", len(result.driver_importance))
    if result.backtest_accuracy is not None:
        logger.debug("Backtest MAPE = %.3f%%", result.backtest_accuracy)

    result.raw_response = response
    return result


def _months_from_now(dt: datetime, reference_date: Optional[datetime] = None) -> int:
    now = reference_date or datetime.now()
    return max(1, (dt.year - now.year) * 12 + (dt.month - now.month))


# ---------------------------------------------------------------------------
# Mock forecast generator (for testing without live Sybilion API)
# ---------------------------------------------------------------------------

def generate_mock_forecast(
    current_price: float,
    trend: str = "UP",
    noise_std: float = 0.05,
    horizons: List[int] = None,
) -> ForecastResult:
    """
    Generate a mock Sybilion forecast for testing the decision agent.

    This avoids live API calls during development and testing.
    """
    if horizons is None:
        horizons = [1, 3, 6, 12]

    result = ForecastResult(target_name="mock_ets_price")
    result.current_value = current_price

    rng = np.random.default_rng(42)  # deterministic for testing
    drift = {"UP": 0.03, "DOWN": -0.02, "FLAT": 0.005}

    for h in horizons:
        trend_drift = drift.get(trend, 0.005) * h
        noise = rng.normal(0, noise_std)
        value = current_price * (1 + trend_drift + noise)
        band = value * (0.1 + 0.02 * h)  # confidence band widens with horizon
        result.forecast_points[h] = {
            "value": round(value, 2),
            "low": round(value - band, 2),
            "high": round(value + band, 2),
        }

    result.driver_importance = {
        "EU ETS reform": [0.25, 0.40, 0.45, 0.55],
        "Natural gas price": [0.30, 0.20, 0.10, 0.05],
        "CBAM phase-in": [0.10, 0.15, 0.25, 0.35],
        "Renewable energy auction": [0.15, 0.22, 0.18, 0.12],
    }
    result.backtest_accuracy = 0.65
    return result
