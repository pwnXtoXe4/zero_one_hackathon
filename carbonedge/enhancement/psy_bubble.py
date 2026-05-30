"""
PSY Bubble Detection (Phillips, Shi & Yu 2015)

Implements the right-tailed recursive ADF test for explosive price behaviour
as applied to EU ETS allowance prices by Friedrich et al. (2019).

Algorithm
---------
1. For each end-point r2 (≥ min_window), compute ADF on every sub-window y[r1:r2].
2. BSADF(r2) = max over r1 of ADF_{r1}^{r2}.
3. Bubble at time r2 if BSADF(r2) > critical_value(r2).

Critical values are bootstrapped via Monte Carlo on a random walk null.

Friedrich et al. (2019) used a 36-month minimum window on 134 months of
EU ETS prices and found the bubble starting March 2018 (MSR reform adoption).

References
----------
Phillips, Shi & Yu (2015) "Testing for Multiple Bubbles"
  International Economic Review 56(4), 1043-1078.

Friedrich, Fries, Pahle & Edenhofer (2019) "Understanding the explosive
  trend in EU ETS prices -- fundamentals or speculation?" arXiv:1906.10572.
"""

import json
import os
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np


PSY_SIGNIFICANCE = 0.05
LPPL_OSCILLATION_MIN = 3.0
LPPL_CRASH_WINDOW = 3


@dataclass
class BubbleResult:
    """Output of PSY bubble detection test."""
    bubble_detected: bool
    bubble_risk: bool
    bsadf_sequence: List[float]
    critical_values: List[float]
    last_bsadf: float
    last_critical: float
    significance: float
    min_window: int
    advisory: str


# ---------------------------------------------------------------------------
# OLS helper
# ---------------------------------------------------------------------------

def _ols(X: np.ndarray, y: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Ordinary least squares regression.

    Returns (coefficients, residuals, t_statistics).
    """
    n, k = X.shape
    XtX = X.T @ X
    try:
        XtX_inv = np.linalg.inv(XtX)
    except np.linalg.LinAlgError:
        XtX_inv = np.linalg.pinv(XtX)
    beta = XtX_inv @ X.T @ y
    fitted = X @ beta
    residuals = y - fitted
    df = max(1, n - k)
    sigma2 = (residuals @ residuals) / df
    if sigma2 <= 0:
        sigma2 = 1e-10
    var_beta = np.diag(XtX_inv) * sigma2
    se = np.sqrt(np.maximum(var_beta, 1e-15))
    t_stats = beta / se
    return beta, residuals, t_stats


# ---------------------------------------------------------------------------
# Right-tailed ADF test
# ---------------------------------------------------------------------------

def _right_tailed_adf(series: np.ndarray, max_lags: int = 0) -> float:
    """
    Augmented Dickey-Fuller test on a single sub-window.

    Regression:
        Δy_t = α + β·y_{t-1} + Σ γ_i·Δy_{t-i} + ε_t

    H₀: β = 0  (unit root)
      vs
    H₁: β > 0  (explosive / bubble)  ← right-tailed

    Returns the t-statistic on β̂.
    """
    y = series.astype(np.float64)
    dy = np.diff(y)
    if len(dy) < 4:
        return -999.0

    y_lag = y[:-1 - max_lags] if max_lags > 0 else y[:-1]
    T_eff = len(y_lag)

    if T_eff < 3:
        return -999.0

    if max_lags == 0:
        X = np.column_stack([np.ones(T_eff), y_lag])
        dy_eff = dy[:T_eff]
    else:
        cols = [np.ones(T_eff), y_lag]
        for lag in range(1, max_lags + 1):
            dy_lag = dy[max_lags - lag:len(dy) - lag]
            cols.append(dy_lag[:T_eff])
        X = np.column_stack(cols)
        dy_eff = dy[max_lags:T_eff + max_lags]

    if X.shape[0] < 3 or np.isnan(X).any() or np.isnan(dy_eff).any():
        return -999.0

    _, _, t_stats = _ols(X, dy_eff)
    return float(t_stats[1])


# ---------------------------------------------------------------------------
# BSADF sequence
# ---------------------------------------------------------------------------

def _bsadf_sequence(
    log_prices: np.ndarray,
    min_window: int,
    max_lags: int = 0,
) -> np.ndarray:
    """
    Compute the Backward Sup ADF sequence.

    For each end-point r2 ∈ [min_window, T]:
        BSADF(r2) = max_{r1 ∈ [1, r2-min_window+1]} ADF(y[r1:r2])

    Returns array of length (T - min_window + 1) where index i corresponds to
    time point min_window + i.
    """
    T = len(log_prices)
    n_out = T - min_window + 1
    bsadf = np.full(n_out, np.nan)

    for r2 in range(min_window, T + 1):
        n_sub = r2 - min_window + 1
        adfs = np.empty(n_sub)
        for r1 in range(1, r2 - min_window + 2):
            sub_series = log_prices[r1 - 1:r2]
            adfs[r1 - 1] = _right_tailed_adf(sub_series, max_lags)
        bsadf[r2 - min_window] = np.max(adfs)

    return bsadf


# ---------------------------------------------------------------------------
# Bootstrap critical values
# ---------------------------------------------------------------------------

def _bootstrap_critical_values(
    T: int,
    min_window: int,
    n_simulations: int = 2000,
    significance: float = 0.05,
    seed: int = 42,
    max_lags: int = 0,
) -> np.ndarray:
    """
    Monte Carlo critical values under the unit-root null.

    Simulates n_simulations independent random walks of length T,
    computes BSADF sequences for each, and returns the (1 - significance)
    quantile at each time point.

    Returns array of critical values indexed [min_window, T].
    """
    rng = np.random.RandomState(seed)
    n_out = T - min_window + 1
    all_sim = np.zeros((n_simulations, n_out))

    for sim in range(n_simulations):
        rw = np.cumsum(rng.randn(T))  # random walk (unit root)
        bsadf = _bsadf_sequence(rw, min_window, max_lags)
        all_sim[sim, :] = bsadf

    critical = np.percentile(all_sim, 100 * (1 - significance), axis=0)
    return critical


# ---------------------------------------------------------------------------
# Critical value caching
# ---------------------------------------------------------------------------

def _cache_dir() -> str:
    """Return the cache directory, creating it if needed."""
    d = os.path.join(os.path.dirname(__file__), "..", "..", "data", "psy_critical_cache")
    os.makedirs(d, exist_ok=True)
    return d


def _cache_key(T: int, min_window: int, significance: float, n_sim: int, seed: int) -> str:
    return f"T{T}_w{min_window}_sig{significance:.4f}_nsim{n_sim}_seed{seed}.json"


def _load_or_bootstrap_critical(
    T: int,
    min_window: int,
    n_simulations: int,
    significance: float,
    seed: int,
) -> np.ndarray:
    """
    Load cached critical values or bootstrap compute them.

    Cached to disk so 2000 × O(T²) bootstrap runs only once per parameter set.
    """
    key = _cache_key(T, min_window, significance, n_simulations, seed)
    path = os.path.join(_cache_dir(), key)

    if os.path.exists(path):
        with open(path, "r") as f:
            data = json.load(f)
            critical = np.array(data["critical_values"])
            if len(critical) == T - min_window + 1:
                return critical

    critical = _bootstrap_critical_values(T, min_window, n_simulations, significance, seed)

    with open(path, "w") as f:
        json.dump({
            "T": T, "min_window": min_window,
            "significance": significance, "n_simulations": n_simulations,
            "seed": seed,
            "critical_values": [float(v) for v in critical],
        }, f)

    return critical


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def psy_test(
    prices: List[float],
    min_window: Optional[int] = None,
    significance: float = PSY_SIGNIFICANCE,
    n_simulations: int = 100,
    seed: int = 42,
) -> BubbleResult:
    """
    Run the PSY bubble detection test on a price series.

    Parameters
    ----------
    prices : list of float
        Monthly price observations, chronological order.
    min_window : int, optional
        Minimum sub-sample window size in months.
        Defaults to T * (0.01 + 1.8/√T) per Phillips et al. (2015),
        or 36 months for EU ETS (~25% of 134) per Friedrich et al. (2019),
        whichever is larger.
    significance : float
        Significance level for bubble detection (default 0.05).
    n_simulations : int
        Number of Monte Carlo simulations for critical values.

    Returns
    -------
    BubbleResult with detection status and diagnostic statistics.
    """
    T = len(prices)

    if min_window is None:
        # Friedrich et al. (2019) used 36 months for EU ETS analysis.
        # The Phillips et al. (2015) formula: T * (0.01 + 1.8/sqrt(T))
        min_window = max(24, int(T * (0.01 + 1.8 / np.sqrt(T))))

    if T < min_window + 4:
        return BubbleResult(
            bubble_detected=False,
            bubble_risk=False,
            bsadf_sequence=[],
            critical_values=[],
            last_bsadf=float("nan"),
            last_critical=float("nan"),
            significance=significance,
            min_window=min_window,
            advisory=f"Insufficient data for PSY test ({T} months < min window {min_window}).",
        )

    log_prices = np.log(prices)

    bsadf = _bsadf_sequence(log_prices, min_window)
    critical = _load_or_bootstrap_critical(T, min_window, n_simulations, significance, seed)

    n_points = len(bsadf)
    is_bubble = np.zeros(n_points, dtype=bool)
    for i in range(n_points):
        is_bubble[i] = bsadf[i] > critical[i]

    current_bubble = bool(is_bubble[-1])
    any_recent_bubble = bool(np.any(is_bubble[-6:])) if n_points >= 6 else bool(np.any(is_bubble))

    last_bsadf = float(bsadf[-1])
    last_critical = float(critical[-1])

    if current_bubble:
        advisory = (
            f"PSY bubble test POSITIVE: BSADF={last_bsadf:.2f} > critical={last_critical:.2f} "
            f"(significance={significance}). Explosive price behaviour detected — "
            f"consistent with Friedrich et al. (2019) speculation regime. "
            f"Recommend FREEZE procurement."
        )
    elif any_recent_bubble:
        advisory = (
            f"PSY bubble test: recent explosive episode resolved. BSADF={last_bsadf:.2f} "
            f"vs critical={last_critical:.2f}. Bubble active within last 6 months — "
            f"monitor closely. Consider YELLOW regime with caution."
        )
    else:
        advisory = (
            f"PSY bubble test NEGATIVE: BSADF={last_bsadf:.2f} < critical={last_critical:.2f}. "
            f"No explosive price behaviour detected."
        )

    return BubbleResult(
        bubble_detected=current_bubble,
        bubble_risk=any_recent_bubble,
        bsadf_sequence=[float(v) for v in bsadf],
        critical_values=[float(v) for v in critical],
        last_bsadf=last_bsadf,
        last_critical=last_critical,
        significance=significance,
        min_window=min_window,
        advisory=advisory,
    )
