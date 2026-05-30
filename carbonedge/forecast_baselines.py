"""
Out-of-sample forecast baselines for honest backtesting.

The Sybilion API can't be replayed historically, so the backtest needs a
stand-in forecast that uses ONLY information available at evaluation time.
Random-walk-with-drift on log-returns is the canonical financial benchmark
and is what we use here.

References
----------
- Diebold (2008) "Elements of Forecasting" §3 — random walk with drift as
  the natural null model for asset prices.
- Sybilion's own bands map to ~10/90 quantiles per the forecast artifact's
  quantile_forecast field, so the bands we emit are matched to that level.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

import numpy as np

from .sybilion_client import ForecastResult

logger = logging.getLogger(__name__)

# 80% prediction bands -> z = 1.282 (matches Sybilion's 0.10 / 0.90 quantiles).
_Z_80 = 1.2816
# Minimum trailing window for drift / vol estimates.
_MIN_TRAILING = 6
# Default trailing window length in months.
_DEFAULT_TRAILING = 24


def make_random_walk_forecast(
    historical_prices: List[float],
    spot: float,
    horizons: List[int],
    *,
    trailing_months: int = _DEFAULT_TRAILING,
    target_name: str = "rw_drift_forecast",
) -> ForecastResult:
    """Random-walk-with-drift forecast using only past prices.

    log(P_{t+h}) ~ N(log(P_t) + h * drift, h * vol^2)
    -> E[P_{t+h}] = P_t * exp(h * drift)  (approx, ignoring 0.5*h*vol^2)
    -> 10/90 bands at P_t * exp(h*drift ± 1.282 * sqrt(h) * vol)

    Parameters
    ----------
    historical_prices : monthly prices up to and INCLUDING the evaluation date.
        The last element is treated as the spot.
    spot : the current price (caller is responsible for ensuring this matches
        historical_prices[-1]).
    horizons : month offsets to produce forecast points for, e.g. [1, 3, 6].
    trailing_months : how many monthly log-returns to use for drift/vol.

    Returns
    -------
    ForecastResult with forecast_points[h] = {"value", "low", "high"}.
    """
    if spot <= 0:
        raise ValueError(f"spot price must be positive, got {spot}")

    prices = np.asarray(historical_prices, dtype=float)
    prices = prices[prices > 0]
    if len(prices) < 2:
        # No history -> flat forecast at spot with default volatility.
        drift = 0.0
        vol = 0.058  # ~20% annual vol, monthly = 20/sqrt(12)
        logger.debug(
            "make_random_walk_forecast: %d positive prices, using defaults drift=0, vol=%.3f",
            len(prices), vol,
        )
    else:
        log_rets = np.diff(np.log(prices))
        sample = log_rets[-trailing_months:] if len(log_rets) >= _MIN_TRAILING else log_rets
        drift = float(np.mean(sample))
        # Floor vol to avoid degenerate certainty when the trailing window is
        # unusually quiet (e.g. early-stage market with thin trading).
        vol = float(max(np.std(sample, ddof=1) if len(sample) > 1 else 0.0, 0.02))
        logger.debug(
            "make_random_walk_forecast: %d log-rets (using last %d), drift=%.4f, vol=%.4f",
            len(log_rets), len(sample), drift, vol,
        )

    result = ForecastResult(target_name=target_name)
    result.current_value = float(spot)
    for h in sorted(horizons):
        mean = spot * float(np.exp(h * drift))
        spread = _Z_80 * float(np.sqrt(h)) * vol
        low = mean * float(np.exp(-spread))
        high = mean * float(np.exp(+spread))
        result.forecast_points[h] = {
            "value": round(mean, 4),
            "low": round(low, 4),
            "high": round(high, 4),
        }
    # Conservative MAPE placeholder — caller may override.
    result.backtest_accuracy = 10.0
    return result


def baseline_cost_spot(spot: float, total_tons: int) -> float:
    """Cost of buying all tons at the spot price at t=0."""
    return float(spot) * int(total_tons)


def baseline_cost_equal_thirds(
    realized_prices_by_horizon: Dict[int, float],
    total_tons: int,
    horizons: List[int] = (1, 3, 6),
) -> Optional[float]:
    """Cost of splitting tons evenly across the given horizons at REALIZED prices.

    Returns None if any horizon's realized price is missing.
    """
    if any(h not in realized_prices_by_horizon for h in horizons):
        return None
    n = len(horizons)
    per_window_tons = int(total_tons) // n
    leftover = int(total_tons) - per_window_tons * n
    total = 0.0
    for i, h in enumerate(horizons):
        tons = per_window_tons + (leftover if i == 0 else 0)
        total += tons * float(realized_prices_by_horizon[h])
    return total
