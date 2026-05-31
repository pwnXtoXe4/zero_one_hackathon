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
import logging
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

PSY_SIGNIFICANCE = 0.05
PSY_N_SIMULATIONS = 2000


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


def _asymptotic_critical_values(T: int, min_window: int, significance: float = 0.05) -> np.ndarray:
    """
    Asymptotic GSADF/BSADF critical values from PSY (2015) Table 1,
    interpolated for the given T and min_window.

    The BSADF critical value at window size t = ⌊T·r₂⌋ is approximated
    by the GSADF critical value for sample size t with r₀ = min_window/t.

    Per PSY (2015) footnote 9, asymptotic values have ~5% size distortion
    vs bootstrap. Acceptable for rapid iteration; use bootstrap for final.
    """
    r0 = min_window / T
    # PSY (2015) Table 1: GSADF critical values at 95% for selected r₀
    # r₀:      0.190   0.137   0.100   0.074   0.055
    # T=inf:   1.89    2.02    2.19    2.34    2.56
    # We interpolate linearly on log(r₀)
    r0_ref = np.array([0.055, 0.074, 0.100, 0.137, 0.190])
    cv_ref = np.array([2.56, 2.34, 2.19, 2.02, 1.89])
    if r0 <= 0.055:
        cv = float(cv_ref[0])
    elif r0 >= 0.190:
        cv = float(cv_ref[-1])
    else:
        cv = float(np.interp(np.log(r0), np.log(r0_ref), cv_ref))

    n_out = T - min_window + 1
    # BSADF critical values grow slightly as r₂ → 1; add a gentle slope
    # calibrated to match bootstrap shape: cv ≈ c·(1 + 0.15·(r₂ - r₀))
    idx = np.arange(n_out)
    r2 = (min_window + idx) / T
    slope = 0.15 * (1.0 + min_window / T)
    critical = cv * (1.0 + slope * (r2 - max(r0, r2[0])))
    return np.maximum(critical, cv * 0.95)


def _load_or_bootstrap_critical(
    T: int,
    min_window: int,
    n_simulations: int,
    significance: float,
    seed: int,
    use_asymptotic: bool = False,
) -> np.ndarray:
    """
    Load cached critical values or bootstrap compute them.

    Cached to disk so bootstrap runs only once per parameter set.
    When use_asymptotic=True, skips bootstrap entirely and returns
    asymptotic approximations from PSY (2015) Table 1.
    """
    if use_asymptotic:
        return _asymptotic_critical_values(T, min_window, significance)

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
# Pre-compute API: compute critical values for many T in parallel
# ---------------------------------------------------------------------------

def _bootstrap_one(params: Tuple[int, int, int, float, int]) -> Tuple[int, np.ndarray]:
    """Worker for precompute: bootstrap one (T, min_window) combo."""
    T, min_window, n_sim, sig, seed = params
    critical = _bootstrap_critical_values(T, min_window, n_sim, sig, seed)
    return T, critical


def precompute_critical_values(
    T_values: List[int],
    min_window: int,
    n_simulations: int = PSY_N_SIMULATIONS,
    significance: float = PSY_SIGNIFICANCE,
    seed: int = 42,
    max_workers: Optional[int] = None,
    use_asymptotic: bool = False,
) -> Dict[int, np.ndarray]:
    """
    Pre-compute and cache PSY critical values for multiple T values in parallel.

    Runs bootstrap for each unique T using ProcessPoolExecutor and caches
    results to disk. Subsequent psy_test() calls hit the cache instantly.

    Parameters
    ----------
    T_values : list of int
        Sample sizes to pre-compute critical values for.
    min_window : int
        Minimum window size for the PSY test.
    n_simulations : int
        Bootstrap simulations per T (2000 recommended by PSY 2015).
    max_workers : int, optional
        Number of parallel workers. Defaults to cpu_count or 4, whichever is larger.
    use_asymptotic : bool
        If True, skip bootstrap and use asymptotic approximation (instant).

    Returns
    -------
    Dict mapping T to cached critical value arrays.
    """
    if use_asymptotic:
        result = {}
        for T in T_values:
            result[T] = _asymptotic_critical_values(T, min_window, significance)
        return result

    unique_T = sorted(set(T for T in T_values if T >= min_window + 4))
    if not unique_T:
        return {}

    # Check what's already cached
    to_compute = []
    cached = {}
    for T in unique_T:
        key = _cache_key(T, min_window, significance, n_simulations, seed)
        path = os.path.join(_cache_dir(), key)
        if os.path.exists(path):
            with open(path, "r") as f:
                data = json.load(f)
                critical = np.array(data["critical_values"])
                if len(critical) == T - min_window + 1:
                    cached[T] = critical
                else:
                    to_compute.append(T)
        else:
            to_compute.append(T)

    if not to_compute:
        logger.info("PSY precompute: all %d T values already cached (skip)", len(unique_T))
        return cached

    t0 = time.time()
    logger.info(
        "PSY precompute: %d T values need bootstrap (%d cached, %d to compute)",
        len(unique_T), len(cached), len(to_compute),
    )

    params = [(T, min_window, n_simulations, significance, seed) for T in to_compute]

    import multiprocessing
    workers = max_workers or max(4, multiprocessing.cpu_count() or 4)

    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_bootstrap_one, p): p[0] for p in params}
        for future in as_completed(futures):
            T_label = futures[future]
            try:
                T_result, critical = future.result()
                cache_path = os.path.join(
                    _cache_dir(),
                    _cache_key(T_result, min_window, significance, n_simulations, seed),
                )
                with open(cache_path, "w") as f:
                    json.dump({
                        "T": T_result, "min_window": min_window,
                        "significance": significance, "n_simulations": n_simulations,
                        "seed": seed,
                        "critical_values": [float(v) for v in critical],
                    }, f)
                cached[T_result] = critical
                logger.info(
                    "PSY precompute: cached T=%d (%d/%d done)",
                    T_result, len(cached), len(unique_T),
                )
            except Exception as exc:
                logger.error("PSY precompute: T=%d FAILED: %s", T_label, exc)
                # Fall back to asymptotic for this T
                cached[T_label] = _asymptotic_critical_values(T_label, min_window, significance)

    elapsed = time.time() - t0
    logger.info(
        "PSY precompute: done in %.0fs (%d T values, %d workers, %d sims each)",
        elapsed, len(to_compute), workers, n_simulations,
    )
    return cached


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def psy_test(
    prices: List[float],
    min_window: Optional[int] = None,
    significance: float = PSY_SIGNIFICANCE,
    n_simulations: int = PSY_N_SIMULATIONS,
    seed: int = 42,
    use_asymptotic: bool = False,
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
    critical = _load_or_bootstrap_critical(T, min_window, n_simulations, significance, seed, use_asymptotic)

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
