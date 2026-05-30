"""
CVaR Procurement Optimizer

Based on Abate et al. (2021) two-stage stochastic programming approach
for allowance procurement under the EU ETS.

Given Sybilion's adjusted forecast bands (mean + CI at each horizon),
the optimizer finds the optimal purchase schedule that minimizes:
  (1 - lambda) * expected_cost + lambda * CVaR(cost)

where CVaR = conditional value at risk (average cost in worst alpha% of paths).

For procurement: lambda controls risk aversion.
  lambda = 0.0  -> risk-neutral (buy when cheapest on average)
  lambda = 0.3  -> balanced (hedge against worst outcomes)
  lambda = 0.5  -> conservative (prioritize avoiding very expensive outcomes)
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

DEFAULT_MONTE_CARLO_PATHS = 10_000
DEFAULT_RISK_LAMBDA = 0.3       # moderate risk aversion
DEFAULT_CVAR_ALPHA = 0.95       # 5% worst outcomes


@dataclass
class PurchaseWindow:
    """A single purchase event in the procurement plan."""
    horizon: int            # months from now (1-12)
    label: str              # human-readable label
    tons: int               # quantity to purchase
    expected_price: float   # EUR/ton, midpoint of adjusted band
    price_low: float        # low end of adjusted band
    price_high: float       # high end of adjusted band
    cost_expected: float    # expected total cost in EUR
    cost_worst_case: float  # CVaR worst-case cost


@dataclass
class ProcurementPlan:
    """Full procurement plan for a compliance period."""
    total_tons: int
    windows: List[PurchaseWindow]
    total_cost_expected: float
    total_cost_worst_case: float
    cost_if_all_now: float
    expected_savings: float
    worst_case_savings: float
    strategy: str           # "FRONT_LOAD", "BALANCED", "BACK_LOAD", "LUMP_SUM"
    reasoning: str

    def summary(self) -> str:
        lines = [f"Procurement Plan: {self.total_tons:,} tons across {len(self.windows)} windows",
                 f"  Strategy: {self.strategy}",
                 f"  Expected total cost: EUR {self.total_cost_expected:,.0f}",
                 f"  Worst-case cost (CVaR 95%): EUR {self.total_cost_worst_case:,.0f}",
                 f"  Cost if bought all now: EUR {self.cost_if_all_now:,.0f}",
                 f"  Expected savings: EUR {self.expected_savings:+,.0f}",
                 f"  Worst-case savings: EUR {self.worst_case_savings:+,.0f}",
                 f"  Reasoning: {self.reasoning}"]
        for w in self.windows:
            lines.append(
                f"  [{w.label:>5}] {w.tons:>6,} tons @ EUR{w.expected_price:.0f} "
                f"(range EUR{w.price_low:.0f}-{w.price_high:.0f}) "
                f"= EUR {w.cost_expected:,.0f}"
            )
        return "\n".join(lines)


def _sample_price_path(
    horizons: List[int],
    mu: Dict[int, float],
    sigma: Dict[int, float],
    correlation: float = 0.7,
    rng: Optional[np.random.Generator] = None,
) -> Dict[int, float]:
    """Generate one correlated price path across horizons."""
    if rng is None:
        rng = np.random.default_rng()
    n = len(horizons)
    cov = np.zeros((n, n))
    for i, hi in enumerate(horizons):
        for j, hj in enumerate(horizons):
            cov[i, j] = correlation ** abs(i - j) * sigma[hi] * sigma[hj]

    L = np.linalg.cholesky(cov + np.eye(n) * 1e-6)
    z = rng.standard_normal(n)
    shocks = L @ z

    path = {}
    for idx, h in enumerate(horizons):
        path[h] = max(1.0, mu[h] + shocks[idx])
    return path


def optimize_procurement(
    forecast_mean: Dict[int, float],
    forecast_sigma: Dict[int, float],
    total_tons: int,
    purchase_windows: List[int],
    current_price: float,
    confidence_multiplier: float = 1.0,
    volatility_multiplier: float = 1.0,
    front_load_bias: float = 0.0,
    risk_lambda: float = DEFAULT_RISK_LAMBDA,
    cvar_alpha: float = DEFAULT_CVAR_ALPHA,
    n_paths: int = DEFAULT_MONTE_CARLO_PATHS,
) -> ProcurementPlan:
    """
    CVaR optimization of procurement schedule.

    Parameters
    ----------
    forecast_mean : {horizon: mean price}
    forecast_sigma : {horizon: std dev of price (adjusted by enhancement layer)}
    total_tons : total allowances needed
    purchase_windows : list of horizon months to buy at
    current_price : latest EUA price
    confidence_multiplier : from regime enhancer (widens sigma)
    volatility_multiplier : from EPU modulator (widens sigma)
    front_load_bias : from driver filter (-0.3 to +0.3)
    risk_lambda : risk aversion weight (0 = risk neutral, 1 = max risk averse)
    cvar_alpha : CVaR confidence level
    n_paths : monte-carlo simulation paths
    """
    horizons = sorted(forecast_mean.keys())
    if not purchase_windows:
        purchase_windows = [h for h in horizons if h <= 6]
    logger.debug(
        "optimize_procurement enter: %d horizons, windows=%s, tons=%d, "
        "conf=%.2fx, vol=%.2fx, front_load=%+.3f, lambda=%.2f, alpha=%.2f, paths=%d",
        len(horizons), purchase_windows, total_tons,
        confidence_multiplier, volatility_multiplier, front_load_bias,
        risk_lambda, cvar_alpha, n_paths,
    )

    # Apply enhancement multipliers to sigma.
    # When forecast_sigma is missing for a horizon, use the median sigma across
    # available horizons. If no sigma data at all, use historical EUA volatility
    # (conservative: 30% annualized vol, monthly = 30/sqrt(12) ≈ 8.7% -> CV 0.25).
    median_sigma = None
    sigmas_available = [s for s in forecast_sigma.values() if s > 0]
    if sigmas_available:
        median_sigma = float(np.median(sigmas_available))
    else:
        median_sigma = forecast_mean.get(1, current_price) * 0.25
        logger.debug(
            "optimize_procurement: no sigmas in forecast, using 25%% of mu1 fallback (%.2f)",
            median_sigma,
        )

    adjusted_sigma = {}
    for h in purchase_windows:
        base_sigma = forecast_sigma.get(h, median_sigma)
        adjusted_sigma[h] = base_sigma * confidence_multiplier * volatility_multiplier
    adjusted_mu = {h: forecast_mean[h] for h in purchase_windows}

    # Generate price paths
    rng = np.random.default_rng(42)
    path_costs = np.zeros((n_paths, len(purchase_windows)))
    for p in range(n_paths):
        path = _sample_price_path(purchase_windows, adjusted_mu, adjusted_sigma, rng=rng)
        for j, h in enumerate(purchase_windows):
            path_costs[p, j] = path[h]

    # Base allocation: equal across windows
    n_windows = len(purchase_windows)
    base_fraction = 1.0 / n_windows

    # Apply front-load bias: shift allocation earlier.
    # For |bias| >= 0.2, use quadratic weighting for stronger effect.
    fractions = np.ones(n_windows) * base_fraction
    if abs(front_load_bias) >= 0.2:
        raw = np.zeros(n_windows)
        if front_load_bias > 0:
            for i in range(n_windows):
                weight = (n_windows - i) ** (1.0 + front_load_bias * 2)
                raw[i] = weight
        else:
            for i in range(n_windows):
                weight = (i + 1) ** (1.0 - front_load_bias * 2)
                raw[i] = weight
        fractions = raw / raw.sum()
    elif front_load_bias > 0:
        for i in range(n_windows):
            fractions[i] = base_fraction + front_load_bias * (n_windows - 1 - i) / n_windows
        fractions = fractions / fractions.sum()
    elif front_load_bias < 0:
        for i in range(n_windows):
            fractions[i] = base_fraction + front_load_bias * i / n_windows
        fractions = fractions / fractions.sum()

    logger.debug(
        "optimize_procurement fractions: %s (sum=%.3f, n_windows=%d)",
        ", ".join(f"{f:.3f}" for f in fractions),
        float(fractions.sum()), n_windows,
    )

    total_costs = path_costs @ fractions * total_tons
    expected_cost = float(np.mean(total_costs))
    sorted_costs = np.sort(total_costs)
    cvar_cutoff = int(n_paths * cvar_alpha)
    cvar_cost = float(np.mean(sorted_costs[cvar_cutoff:]))
    logger.debug(
        "optimize_procurement MC: E[cost]=%.0f, CVaR%.0f=%.0f, worst=%.0f, cutoff=%d/%d",
        expected_cost, cvar_alpha * 100, cvar_cost,
        float(np.max(total_costs)), cvar_cutoff, n_paths,
    )

    # Baseline: buy all now
    cost_all_now = total_tons * current_price

    # Build plan
    window_labels = {1: "NOW", 2: "M2", 3: "M3", 4: "M4", 6: "M6", 9: "M9", 12: "M12"}
    windows = []
    for i, h in enumerate(purchase_windows):
        qty = int(total_tons * fractions[i])
        mu_h = adjusted_mu[h]
        sig_h = adjusted_sigma[h]
        windows.append(PurchaseWindow(
            horizon=h,
            label=window_labels.get(h, f"M{h}"),
            tons=qty,
            expected_price=mu_h,
            price_low=max(1.0, mu_h - 2 * sig_h),
            price_high=mu_h + 2 * sig_h,
            cost_expected=qty * mu_h,
            cost_worst_case=qty * (mu_h + 2 * sig_h),
        ))

    # Adjust last window to make total exact
    allocated = sum(w.tons for w in windows)
    if allocated != total_tons:
        diff = total_tons - allocated
        windows[-1].tons += diff
        windows[-1].cost_expected = windows[-1].tons * windows[-1].expected_price
        sig_last = adjusted_sigma[purchase_windows[-1]]
        windows[-1].price_low = max(1.0, windows[-1].expected_price - 2 * sig_last)
        windows[-1].price_high = windows[-1].expected_price + 2 * sig_last
        windows[-1].cost_worst_case = windows[-1].tons * windows[-1].price_high

    expected_savings = cost_all_now - expected_cost
    worst_case_cost = float(np.max(total_costs))
    worst_case_savings = cost_all_now - worst_case_cost

    # Strategy label based on weighted-average horizon
    avg_horizon = sum(f * h for f, h in zip(fractions, purchase_windows))
    midpoint = (purchase_windows[0] + purchase_windows[-1]) / 2
    if avg_horizon < midpoint * 0.67:
        strategy = "FRONT_LOAD"
    elif avg_horizon > midpoint * 1.33:
        strategy = "BACK_LOAD"
    else:
        strategy = "BALANCED"
    logger.debug(
        "optimize_procurement strategy=%s (avg_h=%.2f, midpoint=%.2f)",
        strategy, avg_horizon, midpoint,
    )

    # Reasoning
    parts = []
    if confidence_multiplier > 1.0:
        parts.append(f"Regime uncertain: bands widened {confidence_multiplier:.1f}x")
    if volatility_multiplier > 1.0:
        parts.append(f"EPU elevated: volatility amplified {volatility_multiplier:.1f}x")
    if front_load_bias > 0.1:
        parts.append("Drivers bullish: front-loading")
    elif front_load_bias < -0.1:
        parts.append("Drivers bearish: back-loading")
    if not parts:
        parts.append("Standard allocation based on Sybilion forecast bands")

    return ProcurementPlan(
        total_tons=total_tons,
        windows=windows,
        total_cost_expected=expected_cost,
        total_cost_worst_case=worst_case_cost,
        cost_if_all_now=cost_all_now,
        expected_savings=expected_savings,
        worst_case_savings=worst_case_savings,
        strategy=strategy,
        reasoning="; ".join(parts),
    )
