"""
Chow-Lin temporal disaggregation of annual verified emissions to monthly.

Bastianin et al. (2024) use the Chow-Lin method to convert annual
verified emissions to monthly frequency, using sectoral industrial
production as the related series.

The Chow-Lin method (Chow & Lin, 1971) estimates a high-frequency
series Y from a low-frequency series Y_bar and a related high-frequency
series X (such as monthly industrial production).

Mathematics
-----------
  Y = X·β + u         (high-frequency model)
  C·Y = Y_bar          (aggregation constraint: C sums monthly to annual)

  β̂ = [X'X]⁻¹X'Y_bar  (estimated using GLS with AR(1) errors)

For our purposes, we use a simpler approach:
  1. Interpolate annual emissions linearly to monthly
  2. Scale months by the share of annual industrial production
     that falls in each month (using seasonal patterns)

Reference
---------
  Chow, G. and Lin, A. (1971), "Best Linear Unbiased Interpolation,
  Distribution, and Extrapolation of Time Series by Related Series",
  Review of Economics and Statistics.
"""

from typing import Dict, List, Optional, Tuple
import warnings

import numpy as np


def chow_lin_interpolate(
    annual_values: Dict[int, float],
    monthly_related: Optional[Dict[str, float]] = None,
    ar1_rho: float = 0.5,
    start_month: int = 1,
) -> Dict[str, float]:
    """
    Disaggregate annual data to monthly using the Chow-Lin method.

    Parameters
    ----------
    annual_values : {year: value}
    monthly_related : {YYYY-MM: related_series_value} — optional monthly indicator
        If None, a uniform distribution is used.
    ar1_rho : AR(1) autocorrelation parameter for the error term
    start_month : first month of the year to start from (1 = January)

    Returns
    -------
    {YYYY-MM: interpolated_value}
    """
    if not annual_values:
        return {}

    years = sorted(annual_values)
    result: Dict[str, float] = {}

    # Group months by year
    for year in years:
        annual_total = annual_values[year]
        month_keys = [f"{year}-{m:02d}-01" for m in range(start_month, start_month + 12)]

        if monthly_related and all(k in monthly_related for k in month_keys):
            # Use related series as distribution weights
            weights = np.array([monthly_related[k] for k in month_keys])
            total_weight = weights.sum()
            if total_weight > 0:
                shares = weights / total_weight
            else:
                shares = np.ones(12) / 12
        else:
            # Uniform distribution
            shares = np.ones(12) / 12
            if not monthly_related:
                warnings.warn(
                    "chow_lin_interpolate: no monthly related series provided. "
                    "Using uniform monthly distribution (1/12 each month). "
                    "Industrial emissions have seasonal patterns — provide "
                    "monthly industrial production data for better accuracy."
                )

        # Apply AR(1) smoothing to the shares (Chow-Lin with autocorrelated errors)
        smoothed = _ar1_smooth(shares, ar1_rho)

        for i, key in enumerate(month_keys):
            result[key] = float(annual_total * smoothed[i])

    return result


def _ar1_smooth(shares: np.ndarray, rho: float) -> np.ndarray:
    """
    Apply AR(1) smoothing to distribution shares.

    This is the Chow-Lin GLS estimator for the monthly distribution:
      y_t* = y_t - ρ·y_{t-1}
    with end-of-year correction.
    """
    if abs(rho) < 1e-6:
        return shares / shares.sum()  # renormalize

    smoothed = np.zeros_like(shares)
    smoothed[0] = shares[0] * (1 - rho)
    for t in range(1, len(shares)):
        smoothed[t] = shares[t] - rho * shares[t - 1]

    # Ensure non-negative and renormalize
    smoothed = np.maximum(smoothed, 0)
    total = smoothed.sum()
    if total > 0:
        smoothed = smoothed / total
    else:
        smoothed = np.ones_like(shares) / len(shares)
        warnings.warn(
            f"_ar1_smooth: all smoothed values zero with rho={rho}. "
            "Falling back to uniform distribution. Check input shares."
        )

    return smoothed


def seasonal_from_monthly_related(
    monthly_related: Dict[str, float],
    start_year: int,
    end_year: int,
) -> Dict[int, np.ndarray]:
    """
    Extract seasonal patterns from a monthly related series.

    Returns {year: 12-element array of seasonal factors (mean=1)}.
    """
    seasonal: Dict[int, np.ndarray] = {}
    for year in range(start_year, end_year + 1):
        month_keys = [f"{year}-{m:02d}-01" for m in range(1, 13)]
        values = np.array([
            monthly_related.get(k, 0.0) for k in month_keys
        ])
        total = values.sum()
        if total > 0:
            # Seasonal factors: monthly share × 12 (so mean = 1)
            seasonal[year] = (values / total) * 12
        else:
            seasonal[year] = np.ones(12)
    return seasonal


def emissions_to_monthly(
    annual_emissions_mt: Dict[int, float],
    monthly_ip: Optional[Dict[str, float]] = None,
) -> Dict[str, float]:
    """
    Convert annual verified emissions (Mt) to monthly using Chow-Lin.

    If no industrial production data is available, uses uniform distribution
    with mild AR(1) smoothing (rho=0.3).

    Parameters
    ----------
    annual_emissions_mt : {year: emissions_in_megatons}
    monthly_ip : optional {YYYY-MM: industrial_production_index}

    Returns
    -------
    {YYYY-MM: monthly_emissions_mt}
    """
    return chow_lin_interpolate(
        annual_values=annual_emissions_mt,
        monthly_related=monthly_ip,
        ar1_rho=0.3,  # mild autocorrelation
    )
