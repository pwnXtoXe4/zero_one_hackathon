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

try:
    from scipy.optimize import minimize
    _HAVE_SCIPY = True
except ImportError:  # pragma: no cover - exercised only when scipy missing
    _HAVE_SCIPY = False

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

    # ---- Generate correlated MC price paths for the purchase horizons ----
    rng = np.random.default_rng(42)
    horizon_prices = np.zeros((n_paths, len(purchase_windows)))
    for p in range(n_paths):
        path = _sample_price_path(purchase_windows, adjusted_mu, adjusted_sigma, rng=rng)
        for j, h in enumerate(purchase_windows):
            horizon_prices[p, j] = path[h]

    # ---- Add spot-at-NOW as an additional choice with no uncertainty ----
    # This lets the optimizer naturally pick "buy all now" when the expected
    # forward cost exceeds the spot, rather than forcing it to spread.
    spot_column = np.full((n_paths, 1), float(current_price))
    all_prices = np.hstack([spot_column, horizon_prices])
    all_horizons = [0] + purchase_windows  # 0 == buy now
    n_choices = len(all_horizons)

    # ---- CVaR objective ----
    cvar_cutoff = int(n_paths * cvar_alpha)
    def objective(fractions: np.ndarray) -> float:
        costs = all_prices @ fractions * total_tons
        e_cost = float(np.mean(costs))
        sorted_c = np.sort(costs)
        cvar = float(np.mean(sorted_c[cvar_cutoff:]))
        return (1.0 - risk_lambda) * e_cost + risk_lambda * cvar

    # ---- Initial guess + soft bias toward front_load preference ----
    # The bias comes from the enhancement layer; it's a prior, not a hard rule.
    # An exponential weighting on horizon distance, signed by the bias, gives
    # the optimizer a sensible starting point in a high-dim search space.
    horizon_array = np.array(all_horizons, dtype=float)
    if abs(front_load_bias) > 1e-6:
        weights = np.exp(-front_load_bias * horizon_array / max(horizon_array.max(), 1.0))
        x0 = weights / weights.sum()
    else:
        x0 = np.ones(n_choices) / n_choices

    # ---- Constrained optimization with multi-start ----
    # The CVaR objective is piecewise-linear (sorted-mean of MC paths) so
    # gradient-based methods get stuck. We evaluate a small set of structural
    # candidates (each lump-sum vertex, equal split, the front-loaded prior)
    # and use the best as the starting point for scipy.SLSQP refinement.
    candidates: List[np.ndarray] = []
    # All-vertex candidates: one-hot at each choice (LUMP_SUM at each horizon)
    for i in range(n_choices):
        v = np.zeros(n_choices)
        v[i] = 1.0
        candidates.append(v)
    # Equal-split
    candidates.append(np.ones(n_choices) / n_choices)
    # Front-loaded prior
    candidates.append(x0)

    best_obj = float("inf")
    best_sol = x0
    for c in candidates:
        val = objective(c)
        if val < best_obj:
            best_obj = val
            best_sol = c
    logger.debug(
        "Best candidate objective=%.0f at fractions=%s",
        best_obj, ", ".join(f"{f:.2f}" for f in best_sol),
    )

    solver_status = "best-candidate"
    if _HAVE_SCIPY:
        constraints = [{"type": "eq", "fun": lambda f: float(np.sum(f) - 1.0)}]
        bounds = [(0.0, 1.0)] * n_choices
        try:
            result = minimize(
                objective, best_sol, method="SLSQP",
                bounds=bounds, constraints=constraints,
                options={"ftol": 1e-7, "maxiter": 300},
            )
            if result.success and abs(result.x.sum() - 1.0) < 0.05:
                refined = np.clip(result.x, 0.0, 1.0)
                refined = refined / refined.sum()
                if objective(refined) < best_obj:
                    best_sol = refined
                    best_obj = objective(refined)
                    solver_status = "best-candidate + SLSQP refinement"
                else:
                    solver_status = "best-candidate (SLSQP did not improve)"
            else:
                solver_status = f"best-candidate (SLSQP fail: {result.message})"
        except (ValueError, RuntimeError) as exc:  # pragma: no cover
            solver_status = f"best-candidate (scipy raised {exc!r})"
    else:
        solver_status = "best-candidate (scipy unavailable)"
    solution = best_sol

    # ---- Apply the solution: spot choice + horizon fractions ----
    spot_fraction = float(solution[0])
    horizon_fractions = np.array(solution[1:], dtype=float)
    logger.debug(
        "CVaR optimizer (%s): spot=%.3f, horizons=[%s]",
        solver_status, spot_fraction,
        ", ".join(f"h{h}:{f:.3f}" for h, f in zip(purchase_windows, horizon_fractions)),
    )

    # Compute realized E[cost] and CVaR on the chosen solution
    realized_costs = all_prices @ solution * total_tons
    expected_cost = float(np.mean(realized_costs))
    sorted_costs = np.sort(realized_costs)
    cvar_cost = float(np.mean(sorted_costs[cvar_cutoff:]))
    logger.debug(
        "CVaR optimizer realized: E[cost]=%.0f, CVaR%.0f=%.0f, worst=%.0f",
        expected_cost, cvar_alpha * 100, cvar_cost,
        float(np.max(realized_costs)),
    )

    # Baseline: buy all now at spot
    cost_all_now = total_tons * current_price

    # ---- Build per-event windows including the spot choice when picked ----
    window_labels = {1: "NOW", 2: "M2", 3: "M3", 4: "M4", 6: "M6", 9: "M9", 12: "M12"}
    windows: List[PurchaseWindow] = []
    if spot_fraction > 0.005:
        qty = int(round(total_tons * spot_fraction))
        windows.append(PurchaseWindow(
            horizon=1,  # spot is "buy this month"
            label="SPOT",
            tons=qty,
            expected_price=float(current_price),
            price_low=float(current_price),
            price_high=float(current_price),
            cost_expected=qty * float(current_price),
            cost_worst_case=qty * float(current_price),
        ))
    for i, h in enumerate(purchase_windows):
        frac = float(horizon_fractions[i])
        if frac < 0.005:  # skip dust allocations
            continue
        qty = int(round(total_tons * frac))
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

    # Reconcile rounding: any leftover tons go to the largest existing window
    if not windows:
        # All allocation rounded away — emergency LUMP_SUM at spot.
        windows.append(PurchaseWindow(
            horizon=1, label="SPOT", tons=total_tons,
            expected_price=float(current_price),
            price_low=float(current_price), price_high=float(current_price),
            cost_expected=total_tons * float(current_price),
            cost_worst_case=total_tons * float(current_price),
        ))
    allocated = sum(w.tons for w in windows)
    diff = total_tons - allocated
    if diff != 0:
        anchor = max(windows, key=lambda w: w.tons)
        anchor.tons += diff
        anchor.cost_expected = anchor.tons * anchor.expected_price
        anchor.cost_worst_case = anchor.tons * anchor.price_high

    expected_savings = cost_all_now - expected_cost
    worst_case_cost = float(np.max(realized_costs))
    worst_case_savings = cost_all_now - worst_case_cost

    # ---- Strategy label from realized allocation across horizons ----
    # SPOT is treated as horizon=0 for centroid math; LUMP_SUM names extreme
    # concentration regardless of which end.
    centroid_num = spot_fraction * 0 + sum(
        f * h for f, h in zip(horizon_fractions, purchase_windows)
    )
    centroid_den = spot_fraction + float(horizon_fractions.sum())
    centroid = centroid_num / centroid_den if centroid_den > 0 else 0.0
    max_frac = max([spot_fraction] + [float(f) for f in horizon_fractions])
    midpoint = (0 + purchase_windows[-1]) / 2
    if max_frac > 0.85:
        strategy = "LUMP_SUM" if centroid <= midpoint else "LUMP_BACK"
    elif centroid < midpoint * 0.67:
        strategy = "FRONT_LOAD"
    elif centroid > midpoint * 1.33:
        strategy = "BACK_LOAD"
    else:
        strategy = "BALANCED"
    logger.debug(
        "Strategy=%s (centroid=%.2f midpoint=%.2f max_frac=%.2f)",
        strategy, centroid, midpoint, max_frac,
    )

    # Reasoning
    parts = []
    if spot_fraction > 0.3:
        parts.append(f"CVaR optimum allocates {spot_fraction*100:.0f}% at spot")
    if confidence_multiplier > 1.0:
        parts.append(f"Regime uncertain: bands widened {confidence_multiplier:.1f}x")
    if volatility_multiplier > 1.0:
        parts.append(f"EPU elevated: volatility amplified {volatility_multiplier:.1f}x")
    if front_load_bias > 0.1:
        parts.append("Drivers bullish: front-loading prior")
    elif front_load_bias < -0.1:
        parts.append("Drivers bearish: back-loading prior")
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
