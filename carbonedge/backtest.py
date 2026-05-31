"""
CarbonEdge -- End-to-End Procurement Backtest

Validates the decision agent against historical data:
  1. Slices historical ETS prices into rolling evaluation windows
  2. Runs the full decision agent on each window (regime + EPU + procurement)
  3. Compares procurement cost vs "buy all at spot" baseline
  4. Reports win rate, aggregate EUR savings, and regret analysis

References
----------
  Abate et al. (2021) arXiv:2104.15062 — CVaR stochastic programming for
    allowance procurement, backtesting methodology
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from .config import CARBON_EXPOSURE, COMPANY_PROFILE

try:
    from scipy.stats import norm as _norm
    _HAS_SCIPY = True
except ImportError:
    _HAS_SCIPY = False

logger = logging.getLogger(__name__)
from .decision_agent import run_decision_agent
from .enhancement.driver_filter import DriverBias
from .enhancement.regime_enhancer import RegimeBand
from .fundamental.balance_model import FundamentalModel
from .fundamental.cap_schedule import build_cap_schedule
from .fundamental.data_sources import load_ets_csv
from .fundamental.driver_monitor import DriverMonitor
from .mac_curve import build_mac_curve
from .regime_detector import RegimeMonitor
from .sybilion_client import ForecastResult

BACKTEST_WINDOW_MONTHS = 60
BACKTEST_MIN_WINDOWS = 12
BACKTEST_STEP_MONTHS = 3
FORECAST_HORIZONS = [1, 3, 6]

_SYBILION_CALIBRATION: Optional[Dict] = None


def _load_sybilion_calibration() -> Dict:
    """Load calibration constants from a real Sybilion forecast artifact.
    Cached after first load. Falls back to conservative defaults if file missing."""
    global _SYBILION_CALIBRATION
    if _SYBILION_CALIBRATION is not None:
        return _SYBILION_CALIBRATION

    import json
    cal_path = Path(__file__).resolve().parents[1] / "data" / "sybilion_forecast_eu_ets.json"
    if cal_path.exists():
        with open(cal_path) as f:
            raw = json.load(f)
        mape = raw.get("backtest_mape", 8.0) / 100.0   # fractional
        bands = raw.get("forecast", {})
        if bands:
            first = list(bands.values())[0]
            last = list(bands.values())[-1]
            band1 = (first["high"] - first["low"]) / first["value"] if first["value"] else 0.13
            band6 = (last["high"] - last["low"]) / last["value"] if last["value"] else 0.50
        else:
            band1, band6 = 0.13, 0.50
    else:
        mape, band1, band6 = 0.08, 0.13, 0.50

    _SYBILION_CALIBRATION = {
        "mape": mape,
        "band_base": band1,
        "band_slope": (band6 - band1) / 5.0,  # linear interpolation: band = base + slope * (h-1)
    }
    return _SYBILION_CALIBRATION


def _build_forecast_from_actuals(
    sorted_dates: List[str],
    prices: Dict[str, float],
    eval_idx: int,
    rng: np.random.Generator,
) -> ForecastResult:
    """
    Build a realistic forecast at an evaluation point using:
      - Actual future prices as the 'perfect-foresight mean'
      - Sybilion-calibrated MAPE noise to simulate forecast error
      - Sybilion-observed band widening pattern for confidence bands

    No mock/fabrication — the mean is real data; only the noise and bands
    are calibrated from actual Sybilion forecast artifacts.
    """
    cal = _load_sybilion_calibration()
    spot_price = prices[sorted_dates[eval_idx]]

    result = ForecastResult(target_name="walk_forward_ets")
    result.current_value = spot_price

    for h in FORECAST_HORIZONS:
        future_idx = eval_idx + h
        if future_idx >= len(sorted_dates):
            continue

        actual_future = prices[sorted_dates[future_idx]]
        cal_noise = spot_price * cal["mape"]
        noise = rng.normal(0, cal_noise)
        forecast_value = actual_future + noise

        band = cal["band_base"] + cal["band_slope"] * (h - 1)
        half_band = forecast_value * band / 2.0

        result.forecast_points[h] = {
            "value": round(forecast_value, 2),
            "low": round(forecast_value - half_band, 2),
            "high": round(forecast_value + half_band, 2),
        }

    result.backtest_accuracy = cal["mape"] * 100
    result.driver_importance = _load_driver_importance()
    return result


def _load_driver_importance() -> Dict[str, List[float]]:
    """Load top Sybilion drivers from the real external_signals artifact."""
    import json
    sig_path = Path(__file__).resolve().parents[1] / "data" / "sybilion_forecast_eu_ets.json"
    drivers = getattr(_load_driver_importance, "_cache", None)
    if drivers is not None:
        return drivers

    try:
        with open(sig_path) as f:
            raw = json.load(f)
        driver_data = raw.get("top_drivers", {})
        if driver_data:
            drivers = driver_data
        else:
            drivers = {
                "EU trade indices": [94.0, 94.0, 94.0, 94.0, 94.0, 94.0],
                "Global risk": [94.0, 94.0, 94.0, 94.0, 94.0, 94.0],
                "Energy (USA)": [94.0, 94.0, 94.0, 94.0, 94.0, 94.0],
                "Commodities (World)": [81.0, 81.0, 81.0, 81.0, 81.0, 81.0],
                "Energy (Finland)": [93.0, 93.0, 93.0, 93.0, 93.0, 93.0],
            }
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        drivers = {
            "Energy (USA)": [94.0, 94.0, 94.0, 94.0, 94.0, 94.0],
            "Global risk": [94.0, 94.0, 94.0, 94.0, 94.0, 94.0],
            "Commodities (World)": [81.0, 81.0, 81.0, 81.0, 81.0, 81.0],
        }

    _load_driver_importance._cache = drivers
    return drivers


@dataclass
class DecisionTrace:
    """Structured per-window snapshot of every layer's state and the
    constraints / shifts they produced. Lets us audit whether layers fire
    for sensible reasons (or chaotically), and whether the trend guard
    kicks in when expected."""
    eval_date: str
    spot_price: float
    trailing_6mo_log_return: Optional[float]
    trend_guard_active: bool
    # Layer signals
    regime_level: str
    regime_multiplier: float
    epu_level: str
    epu_value: float
    epu_spike: bool
    epu_volatility_multiplier: float
    driver_signal: str
    driver_bias: float
    structural_signal: str
    structural_tightening_score: float
    structural_inflection_year: int
    demand_pressure: float
    # Mean shifts applied
    driver_shift: float
    structural_shift: float
    demand_shift: float
    total_mean_shift: float
    # Allocation constraints
    min_spot: float
    max_spot: float
    max_back: float
    max_single: float
    constraint_reasons: List[str] = field(default_factory=list)
    composite_score: float = 0.0
    # Decision output
    strategy: str = ""
    allocation: Dict[str, int] = field(default_factory=dict)


@dataclass
class BacktestWindow:
    """Result of one backtest window — all costs are REALIZED (using actual
    future prices at each window's horizon), not forecast-implied."""
    evaluation_date: str           # YYYY-MM-DD
    spot_price: float
    allowances_needed: int
    procurement_strategy: str

    # Forecast-implied figures (what the agent thought it would pay)
    total_cost_expected: float

    # Realized figures (what the agent and baselines actually paid given the
    # actual prices that materialized at each horizon)
    realized_cost_agent: float
    realized_cost_spot: float
    realized_cost_equal_thirds: Optional[float]
    realized_cost_random_walk: Optional[float]
    realized_cost_mean_reversion: Optional[float]
    realized_cost_always_6: Optional[float]

    # Convenience savings vs each baseline (positive = agent paid less)
    savings_vs_spot: float
    savings_vs_equal_thirds: Optional[float]
    savings_vs_random_walk: Optional[float]
    savings_vs_mean_reversion: Optional[float]
    savings_vs_always_6: Optional[float]

    regime_level: str
    epu_level: str
    epu_value: float
    forecast_months: int
    band_width_ratio: float
    windows_detail: List[Dict] = field(default_factory=list)
    trace: Optional[DecisionTrace] = None


@dataclass
class StatisticalSummary:
    """Paired t-test + DM test + 95% CI on per-window savings against one baseline.

    The Diebold-Mariano (DM) test replaces the naive paired t-test by using
    Newey-West HAC standard errors that are robust to autocorrelation in the
    loss-differential series — the standard in forecast evaluation literature.
    Under H₀ the DM statistic is asymptotically N(0,1).
    """
    baseline_name: str
    n: int
    mean_savings: float
    std_savings: float
    se_savings: float              # naive SE = std / sqrt(n)
    t_statistic: float              # naive paired-t (SciPy ttest_rel)
    p_value: float                  # naive p-value (SciPy or NaN)
    ci95_low: float                 # 95% CI using naive SE
    ci95_high: float
    # --- Diebold-Mariano extensions ---
    dm_se_hac: float = float("nan")       # Newey-West HAC standard error
    dm_statistic: float = float("nan")    # DM = mean / SE_HAC ~ N(0,1)
    dm_p_value: float = float("nan")      # two-sided p from N(0,1)
    dm_bandwidth: int = 0                 # Newey-West automatic bandwidth
    dm_significant: bool = False          # True if dm_p_value < 0.05


@dataclass
class BacktestResult:
    """Aggregate backtest results across all windows."""
    windows: List[BacktestWindow] = field(default_factory=list)
    total_windows: int = 0

    # Spot-baseline metrics (legacy)
    windows_won: int = 0            # procurement cheaper than spot
    windows_lost: int = 0           # procurement more expensive than spot
    win_rate: float = 0.0
    total_savings_eur: float = 0.0
    avg_savings_eur: float = 0.0
    max_savings_eur: float = 0.0
    max_loss_eur: float = 0.0
    strategy_counts: Dict[str, int] = field(default_factory=dict)
    regime_breakdown: Dict[str, int] = field(default_factory=dict)

    # Statistical comparison vs each baseline (paired t + Diebold-Mariano)
    stats_vs_spot: Optional[StatisticalSummary] = None
    stats_vs_equal_thirds: Optional[StatisticalSummary] = None
    stats_vs_random_walk: Optional[StatisticalSummary] = None
    stats_vs_mean_reversion: Optional[StatisticalSummary] = None
    stats_vs_always_6: Optional[StatisticalSummary] = None
    forecast_mode: str = "naive"    # 'naive' (out-of-sample) or 'oracle'
    step_months: int = 3            # BACKTEST_STEP_MONTHS used for this run


def _determine_trend(prices: List[float], months: int = 6) -> str:
    """Simple trend classification from trailing price history."""
    if len(prices) < months + 1:
        return "FLAT"
    recent = prices[-months:]
    change = (recent[-1] - recent[0]) / recent[0]
    if change > 0.02:
        return "UP"
    if change < -0.02:
        return "DOWN"
    return "FLAT"


def _build_regime_monitor(prices: List[float]) -> RegimeMonitor:
    """Seed a regime monitor from historical prices."""
    monitor = RegimeMonitor()
    naive_forecasts = [prices[0]] + prices[:-1]
    for actual, naive in zip(prices, naive_forecasts):
        monitor.update(actual, naive)
    return monitor


def _realized_prices_by_horizon(
    sorted_dates: List[str],
    prices: Dict[str, float],
    eval_idx: int,
    horizons: List[int],
) -> Dict[int, float]:
    """Return {h: realized price at t+h} for the given horizons.

    Missing horizons (beyond the dataset) are omitted from the dict.
    """
    out: Dict[int, float] = {}
    for h in horizons:
        target_idx = eval_idx + h
        if target_idx < len(sorted_dates):
            out[h] = float(prices[sorted_dates[target_idx]])
    return out


def _realized_cost_for_plan(
    plan: "ProcurementPlan",
    spot_price: float,
    realized_by_h: Dict[int, float],
) -> float:
    """Compute what the agent actually paid using realized prices.

    Each PurchaseWindow knows its horizon; a "SPOT" window is paid at the
    spot price (today, no horizon shift). Other windows pay the realized
    price at their horizon. When a horizon is beyond available data the
    nearest-available realized price is used; this only matters near the
    end of the price series and is logged.
    """
    total = 0.0
    available_h = sorted(realized_by_h)
    for w in plan.windows:
        if w.label == "SPOT":
            actual = float(spot_price)
        elif w.horizon in realized_by_h:
            actual = float(realized_by_h[w.horizon])
        elif available_h:
            nearest = min(available_h, key=lambda h: abs(h - w.horizon))
            actual = float(realized_by_h[nearest])
            logger.debug(
                "_realized_cost_for_plan: h=%d not in realized; using nearest h=%d (price=%.2f)",
                w.horizon, nearest, actual,
            )
        else:
            actual = float(spot_price)  # absolute fallback
        total += int(w.tons) * actual
    return total


def _newey_west_hac(d: np.ndarray, max_lag: Optional[int] = None) -> float:
    """Newey-West (1987, 1994) HAC long-run variance estimator for mean(d).

    Uses Bartlett kernel w(j) = 1 - j/(h+1) with automatic bandwidth
    h = floor(4 * (T/100)^{2/9}) per Newey-West (1994).

    Returns
    -------
    float : long-run variance estimate (scalar, not scaled by T).
    """
    T = len(d)
    if T < 2:
        return float(np.var(d, ddof=0)) if T > 0 else 0.0

    if max_lag is None:
        max_lag = max(1, int(np.floor(4.0 * (T / 100.0) ** (2.0 / 9.0))))
    max_lag = min(max_lag, T - 1)

    d_demean = d - np.mean(d)
    gamma0 = np.mean(d_demean * d_demean)
    hac_var = gamma0
    for j in range(1, max_lag + 1):
        gamma_j = np.mean(d_demean[j:] * d_demean[:-j])
        weight = 1.0 - float(j) / float(max_lag + 1)
        hac_var += 2.0 * weight * float(gamma_j)

    return max(hac_var, 1e-12)


def _diebold_mariano(agent_costs: List[float], baseline_costs: List[float]) -> Dict:
    """Diebold-Mariano test with Newey-West HAC standard errors.

    d_t = cost(agent, t) - cost(baseline, t).
    H₀: E[d_t] = 0  (agent and baseline have equal expected cost).
    DM = sqrt(T) * mean(d) / sqrt(HAC_var) ~ N(0,1) asymptotically.

    References
    ----------
    Diebold & Mariano (1995) "Comparing Predictive Accuracy," JBES 13:253-263.
    Newey & West (1994) "Automatic Lag Selection in Covariance Matrix Estimation."

    Returns
    -------
    dict with keys: n, mean, se_hac, dm_statistic, dm_p_value, bandwidth.
    """
    a = np.asarray(agent_costs, dtype=float)
    b = np.asarray(baseline_costs, dtype=float)
    d = a - b  # positive = agent was MORE expensive (worse)
    n = len(d)
    mean_d = float(np.mean(d))
    hac_var = _newey_west_hac(d)
    bandwidth = max(1, int(np.floor(4.0 * (n / 100.0) ** (2.0 / 9.0))))
    se_hac = float(np.sqrt(hac_var / float(n)))

    if se_hac > 0:
        dm_stat = mean_d / se_hac
        if _HAS_SCIPY:
            dm_p = 2.0 * float(_norm.cdf(-abs(dm_stat)))
        else:
            dm_p = float("nan")
    else:
        dm_stat = 0.0
        dm_p = 1.0

    return {
        "n": n,
        "mean": mean_d,
        "se_hac": se_hac,
        "dm_statistic": dm_stat,
        "dm_p_value": dm_p,
        "bandwidth": bandwidth,
    }


def _paired_stats(
    agent_costs: List[float],
    baseline_costs: List[float],
    baseline_name: str,
) -> StatisticalSummary:
    """Paired t-test + Diebold-Mariano + 95% CI (baseline - agent savings).

    Reports BOTH the classic paired t-test (for backward compatibility)
    AND the Diebold-Mariano test with Newey-West HAC standard errors
    (the literature standard for forecast evaluation from Diebold & Mariano 1995).
    """
    a = np.asarray(agent_costs, dtype=float)
    b = np.asarray(baseline_costs, dtype=float)
    savings = b - a
    n = int(len(savings))
    mean = float(np.mean(savings))
    if n > 1:
        std = float(np.std(savings, ddof=1))
        se = std / float(np.sqrt(n))
    else:
        std = 0.0
        se = 0.0

    try:
        from scipy.stats import ttest_rel
        t_stat, p_value = ttest_rel(b, a)
        t_stat = float(t_stat)
        p_value = float(p_value)
    except ImportError:
        if se > 0:
            t_stat = mean / se
            p_value = float("nan")
        else:
            t_stat = 0.0
            p_value = float("nan")

    try:
        from scipy.stats import t as t_dist
        crit = float(t_dist.ppf(0.975, df=max(1, n - 1))) if n > 1 else 1.96
    except ImportError:
        crit = 1.96

    dm_result = _diebold_mariano(agent_costs, baseline_costs)

    return StatisticalSummary(
        baseline_name=baseline_name,
        n=n,
        mean_savings=mean,
        std_savings=std,
        se_savings=se,
        t_statistic=t_stat,
        p_value=p_value,
        ci95_low=mean - crit * se,
        ci95_high=mean + crit * se,
        dm_se_hac=dm_result["se_hac"],
        dm_statistic=dm_result["dm_statistic"],
        dm_p_value=dm_result["dm_p_value"],
        dm_bandwidth=dm_result["bandwidth"],
        dm_significant=dm_result["dm_p_value"] < 0.05,
    )


def _seed_driver_monitor(prices: Dict[str, float], sorted_dates: List[str], lookback: int = 22) -> DriverMonitor:
    """
    Seed a DriverMonitor from ETS price history as a proxy for missing coal/gas data.

    Coal, gas, and energy sector indices are highly correlated with EUA prices
    (Maciejowski & Leonelli 2025: coal #1 driver, energy sector #2 driver).
    When real driver data is unavailable, we use the ETS series itself as a
    directional proxy — if EUAs are rising, coal and energy are likely rising too.
    This is a honest approximation, not fabrication:
      - Coal ≈ 10% of EUA (ARA API-2 ~$100/t when EUA ~EUR 90)
      - Gas (TTF) ≈ 3× coal price
      - MSCI Europe Energy ≈ 0.015× EUA (stock index proxy)
    """
    monitor = DriverMonitor(lookback=lookback)
    for date in sorted_dates:
        eua_price = prices[date]
        coal = eua_price * 0.10 + np.random.default_rng(hash(date) % 2**31).normal(0, 0.01 * eua_price)
        gas = coal * 3.0 + np.random.default_rng(hash(date + "g") % 2**31).normal(0, 0.05 * coal)
        energy_idx = eua_price * 0.015 + np.random.default_rng(hash(date + "e") % 2**31).normal(0, 0.002 * eua_price)
        monitor.update(date, max(1.0, coal), max(0.1, energy_idx), max(1.0, gas))
    return monitor


def run_backtest(
    prices: Dict[str, float],
    fundamental_model: Optional[FundamentalModel] = None,
    driver_monitor: Optional[DriverMonitor] = None,
    start_date: Optional[str] = None,
    allowances_needed: Optional[int] = None,
    seed: int = 42,
    forecast_mode: str = "naive",
    warmup_months: Optional[int] = None,
    step_months: Optional[int] = None,
    min_windows: Optional[int] = None,
    cadence_ticks_per_month: float = 1.0,
    warmup_ticks: Optional[int] = None,
    step_ticks: Optional[int] = None,
    use_asymptotic_psy: bool = False,
    psy_n_simulations: Optional[int] = None,
) -> BacktestResult:
    """
    Run end-to-end procurement backtest over rolling historical windows.

    Parameters
    ----------
    prices : {YYYY-MM-DD: float} chronological monthly ETS prices
    fundamental_model : pre-built FundamentalModel
    driver_monitor : pre-built DriverMonitor
    start_date : YYYY-MM-DD first evaluation date (default: after warmup)
    allowances_needed : tons per year (default: from config)
    seed : random seed for reproducible backtests
    forecast_mode :
        - "naive" (default): out-of-sample random-walk-with-drift forecast
          built from prices STRICTLY before the evaluation date. No future
          leakage. This is the honest test.
        - "oracle": legacy behaviour — uses (actual future + noise) as the
          forecast. Upper bound; do NOT report as evidence of agent skill.

    Returns
    -------
    BacktestResult with per-window REALIZED costs, paired t-tests vs spot
    and equal-thirds baselines, and 95% CIs on savings.
    """
    if allowances_needed is None:
        allowances_needed = CARBON_EXPOSURE["eu_ets_allowances_needed_annually"]

    # Per-run config (kwargs override module defaults; no global mutation).
    # Convert month-scoped sizes to *ticks* using cadence_ticks_per_month so
    # the same code can run on monthly (c=1.0), weekly (c~4.33) or daily
    # (c~22) input series.
    c = float(cadence_ticks_per_month)
    if c <= 0:
        raise ValueError(f"cadence_ticks_per_month must be > 0, got {c}")
    eff_warmup_months = BACKTEST_WINDOW_MONTHS if warmup_months is None else int(warmup_months)
    eff_step_months = BACKTEST_STEP_MONTHS if step_months is None else int(step_months)
    eff_min = BACKTEST_MIN_WINDOWS if min_windows is None else int(min_windows)
    # warmup_ticks / step_ticks (if provided) override the *_months convention
    # so weekly / daily callers can express cadence directly.
    eff_warmup = (
        int(warmup_ticks)
        if warmup_ticks is not None
        else max(1, int(round(eff_warmup_months * c)))
    )
    eff_step = (
        int(step_ticks)
        if step_ticks is not None
        else max(1, int(round(eff_step_months * c)))
    )

    sorted_dates = sorted(prices.keys())
    if len(sorted_dates) < eff_warmup + eff_min:
        raise ValueError(
            f"Need at least {eff_warmup + eff_min} "
            f"months of price data for a valid backtest. Have {len(sorted_dates)}."
        )
    logger.info(
        "Backtest: %d prices (%s -> %s), allowances=%d, seed=%d",
        len(sorted_dates), sorted_dates[0], sorted_dates[-1],
        allowances_needed, seed,
    )

    # Auto-build fundamental model if none provided
    if fundamental_model is None:
        try:
            caps = build_cap_schedule()
            emissions_data = load_ets_csv()
            if emissions_data.verified_emissions:
                fundamental_model = FundamentalModel(
                    cap_schedule=caps,
                    emissions_data=emissions_data,
                )
                logger.info(
                    "Backtest: auto-built fundamental model (latest year=%s)",
                    fundamental_model.latest_verified_year,
                )
        except (FileNotFoundError, ValueError, KeyError, TypeError) as exc:
            logger.warning("Backtest: could not auto-build fundamental model: %s", exc)

    # Determine evaluation windows
    if start_date:
        eval_indices = [i for i, d in enumerate(sorted_dates) if d >= start_date]
        if not eval_indices:
            raise ValueError(f"start_date {start_date} not found in price data")
        start_idx = eval_indices[0]
    else:
        start_idx = eff_warmup

    eval_indices = list(range(start_idx, len(sorted_dates) - 1, eff_step))
    logger.info(
        "Backtest: %d evaluation windows (start_idx=%d, step=%d ticks, cadence=%.2f ticks/month)",
        len(eval_indices), start_idx, eff_step, c,
    )

    # ---- Pre-compute PSY critical values for all window sizes ----
    if not use_asymptotic_psy:
        from .enhancement.psy_bubble import precompute_critical_values, PSY_N_SIMULATIONS
        try:
            T_values = [idx + 1 for idx in eval_indices]
            min_win_psy = None  # let psy_test() default it
            n_sim = psy_n_simulations or PSY_N_SIMULATIONS
            logger.info(
                "Backtest: pre-computing PSY critical values for %d T values "
                "(n_sim=%d) — this may take a while on first run",
                len(set(T_values)), n_sim,
            )
            precompute_critical_values(
                T_values=T_values,
                min_window=24,
                n_simulations=n_sim,
                seed=seed,
            )
        except Exception as exc:
            logger.warning(
                "PSY precompute failed (%s), falling back to asymptotic critical values. "
                "Bubble detection will be approximate (~5%% size distortion vs bootstrap).",
                exc,
            )

    if forecast_mode not in ("naive", "oracle"):
        raise ValueError(f"forecast_mode must be 'naive' or 'oracle', got {forecast_mode!r}")
    result = BacktestResult(forecast_mode=forecast_mode, step_months=eff_step_months)
    rng = np.random.default_rng(seed)
    from .forecast_baselines import (
        make_random_walk_forecast,
        baseline_cost_spot,
        baseline_cost_equal_thirds,
        baseline_cost_random_walk,
        baseline_cost_mean_reversion,
        baseline_cost_always_horizon_6,
    )

    # Agent thinks in MONTHS. Translate to tick offsets for forecasts/realized
    # lookups. For monthly cadence (c=1) this is identity; for weekly (c~4.33)
    # h=1mo -> 4 ticks, h=3mo -> 13 ticks, h=6mo -> 26 ticks.
    eval_horizons = [1, 3, 6]
    month_to_tick = {h: max(1, int(round(h * c))) for h in eval_horizons}
    tick_horizons = [month_to_tick[h] for h in eval_horizons]

    for window_num, eval_idx in enumerate(eval_indices, 1):
        eval_date = sorted_dates[eval_idx]
        spot_price = prices[eval_date]
        logger.info(
            "Backtest window %d/%d: %s (spot=EUR%.2f)",
            window_num, len(eval_indices), eval_date, spot_price,
        )

        # Historical context for this window
        hist_start = max(0, eval_idx - eff_warmup)
        # Full history for PSY bubble detection (Friedrich et al. 2019 needs long lookback)
        hist_prices = [prices[d] for d in sorted_dates[:eval_idx + 1]]

        # Trend from trailing data
        trend = _determine_trend(hist_prices)

        # Build regime monitor from historical data
        regime_monitor = _build_regime_monitor([prices[d] for d in sorted_dates[hist_start:eval_idx + 1]])

        # ---- Forecast: out-of-sample by default, oracle for sanity checks ----
        # The honest forecast uses ONLY prices up to and including eval_date.
        # The oracle uses actual future + noise (legacy, biased upward).
        if forecast_mode == "naive":
            past_only = [prices[d] for d in sorted_dates[:eval_idx + 1]]
            # Build forecast at tick offsets, then re-label by month for the agent.
            fc_tick = make_random_walk_forecast(
                historical_prices=past_only,
                spot=spot_price,
                horizons=tick_horizons,
                target_name=f"naive_{eval_date}",
            )
            forecast = ForecastResult(target_name=fc_tick.target_name)
            forecast.current_value = fc_tick.current_value
            forecast.backtest_accuracy = fc_tick.backtest_accuracy
            for h_month in eval_horizons:
                h_tick = month_to_tick[h_month]
                if h_tick in fc_tick.forecast_points:
                    forecast.forecast_points[h_month] = fc_tick.forecast_points[h_tick]
        else:
            # Oracle mode is calibrated against monthly Sybilion artifacts; only
            # supported at monthly cadence.
            if c != 1.0:
                raise ValueError(
                    "forecast_mode='oracle' is only supported at monthly cadence "
                    "(cadence_ticks_per_month=1.0)."
                )
            forecast = _build_forecast_from_actuals(sorted_dates, prices, eval_idx, rng)

        # Build MAC curve
        mac = build_mac_curve(current_ets_price=spot_price)

        # Build episodic driver monitor from historical data up to this window
        if driver_monitor is None:
            window_prices = {d: prices[d] for d in sorted_dates[:eval_idx + 1]}
            window_dates = sorted_dates[:eval_idx + 1]
            window_driver = _seed_driver_monitor(window_prices, window_dates)
        else:
            window_driver = driver_monitor

        # Run decision agent with evaluation_date for reproducibility
        try:
            decision = run_decision_agent(
                ets_forecast=forecast,
                mac_curve=mac,
                budget=COMPANY_PROFILE["annual_reduction_budget_eur"],
                current_ets_price=spot_price,
                allowances_needed=allowances_needed,
                regime_monitor=regime_monitor,
                historical_prices=hist_prices,
                fundamental_model=fundamental_model,
                driver_monitor=window_driver,
                evaluation_date=eval_date,
            )
        except Exception as exc:
            import warnings
            warnings.warn(f"Backtest window {eval_date} failed: {exc}")
            logger.exception("Backtest window %s failed", eval_date)
            continue

        procurement = decision.procurement

        # ---- Realized costs: what actually got paid given future prices ----
        # Look up at TICK offsets, then re-key by month so the agent's plan
        # (which thinks in months) lines up with realized prices.
        realized_by_tick = _realized_prices_by_horizon(
            sorted_dates, prices, eval_idx, tick_horizons,
        )
        realized_by_h = {
            h_month: realized_by_tick[month_to_tick[h_month]]
            for h_month in eval_horizons if month_to_tick[h_month] in realized_by_tick
        }
        realized_agent = _realized_cost_for_plan(procurement, spot_price, realized_by_h)
        realized_spot = baseline_cost_spot(spot_price, allowances_needed)
        realized_equal_thirds = baseline_cost_equal_thirds(
            realized_by_h, allowances_needed, horizons=eval_horizons,
        )
        past_prices_for_rw = [prices[d] for d in sorted_dates[:eval_idx + 1]]
        realized_random_walk = baseline_cost_random_walk(
            past_prices_for_rw, spot_price, realized_by_h, allowances_needed, eval_horizons,
        )
        realized_mr = baseline_cost_mean_reversion(
            past_prices_for_rw, spot_price, realized_by_h, allowances_needed, eval_horizons,
        )
        realized_always_6 = baseline_cost_always_horizon_6(realized_by_h, allowances_needed)

        savings_spot = realized_spot - realized_agent
        savings_equal_thirds = (realized_equal_thirds - realized_agent) if realized_equal_thirds is not None else None
        savings_rw = (realized_random_walk - realized_agent) if realized_random_walk is not None else None
        savings_mr = (realized_mr - realized_agent) if realized_mr is not None else None
        savings_a6 = (realized_always_6 - realized_agent) if realized_always_6 is not None else None

        logger.info(
            "Backtest window %s: strategy=%s realized=EUR%.0f "
            "(vs spot=EUR%.0f -> %+.0f, vs 1/3s=EUR%s -> %s, "
            "vs RW=%s, vs MR=%s, vs A6=%s)",
            eval_date, procurement.strategy,
            realized_agent, realized_spot, savings_spot,
            "n/a" if realized_equal_thirds is None else f"{realized_equal_thirds:.0f}",
            "n/a" if savings_equal_thirds is None else f"{savings_equal_thirds:+.0f}",
            "n/a" if savings_rw is None else f"{savings_rw:+.0f}",
            "n/a" if savings_mr is None else f"{savings_mr:+.0f}",
            "n/a" if savings_a6 is None else f"{savings_a6:+.0f}",
        )

        # Build a structured trace from the decision and the plan's diagnostics
        diag = procurement.diagnostics or {}
        alloc_breakdown: Dict[str, int] = {}
        for w in procurement.windows:
            key = "SPOT" if w.label == "SPOT" else f"h{w.horizon}"
            alloc_breakdown[key] = alloc_breakdown.get(key, 0) + int(w.tons)
        trace = DecisionTrace(
            eval_date=eval_date,
            spot_price=float(spot_price),
            trailing_6mo_log_return=diag.get("trend_log_return"),
            trend_guard_active=bool(diag.get("trend_guard_active", False)),
            regime_level=decision.regime.level,
            regime_multiplier=decision.regime.multiplier,
            epu_level=decision.epu.level if decision.epu else "N/A",
            epu_value=decision.epu.epu_value if decision.epu else float("nan"),
            epu_spike=bool(decision.epu.spike) if decision.epu else False,
            epu_volatility_multiplier=decision.epu.volatility_multiplier if decision.epu else 1.0,
            driver_signal=decision.driver_bias.signal,
            driver_bias=decision.driver_bias.bias,
            structural_signal=decision.structural.signal if decision.structural else "N/A",
            structural_tightening_score=decision.structural.tightening_score if decision.structural else float("nan"),
            structural_inflection_year=decision.structural.surplus_to_shortage_year if decision.structural else 0,
            demand_pressure=decision.demand.demand_pressure if decision.demand else float("nan"),
            driver_shift=float(diag.get("driver_shift", 0.0)),
            structural_shift=float(diag.get("structural_shift", 0.0)),
            demand_shift=float(diag.get("demand_shift", 0.0)),
            total_mean_shift=float(diag.get("total_mean_shift", 0.0)),
            min_spot=float(diag.get("min_spot", 0.0)),
            max_spot=float(diag.get("max_spot", 1.0)),
            max_back=float(diag.get("max_back", 1.0)),
            max_single=float(diag.get("max_single", 1.0)),
            constraint_reasons=list(diag.get("constraint_reasons", [])),
            composite_score=float(diag.get("composite_score", 0.0)),
            strategy=procurement.strategy,
            allocation=alloc_breakdown,
        )

        window = BacktestWindow(
            evaluation_date=eval_date,
            spot_price=spot_price,
            allowances_needed=allowances_needed,
            procurement_strategy=procurement.strategy,
            total_cost_expected=procurement.total_cost_expected,
            realized_cost_agent=realized_agent,
            realized_cost_spot=realized_spot,
            realized_cost_equal_thirds=realized_equal_thirds,
            realized_cost_random_walk=realized_random_walk,
            realized_cost_mean_reversion=realized_mr,
            realized_cost_always_6=realized_always_6,
            savings_vs_spot=savings_spot,
            savings_vs_equal_thirds=savings_equal_thirds,
            savings_vs_random_walk=savings_rw,
            savings_vs_mean_reversion=savings_mr,
            savings_vs_always_6=savings_a6,
            regime_level=decision.regime.level,
            epu_level=decision.epu.level if decision.epu else "N/A",
            epu_value=decision.epu.epu_value if decision.epu else float("nan"),
            forecast_months=len(forecast.forecast_points),
            band_width_ratio=forecast.band_width_ratio,
            windows_detail=[
                {"label": w.label, "tons": w.tons, "price": w.expected_price}
                for w in procurement.windows
            ],
            trace=trace,
        )

        result.windows.append(window)

    # ---- Aggregate ----
    result.total_windows = len(result.windows)
    if result.total_windows == 0:
        return result

    result.windows_won = sum(1 for w in result.windows if w.savings_vs_spot > 0)
    result.windows_lost = sum(1 for w in result.windows if w.savings_vs_spot < 0)  # ties (==0) excluded
    result.win_rate = result.windows_won / result.total_windows

    savings_list = [w.savings_vs_spot for w in result.windows]
    result.total_savings_eur = sum(savings_list)
    result.avg_savings_eur = result.total_savings_eur / result.total_windows
    result.max_savings_eur = max(savings_list)
    result.max_loss_eur = min(savings_list)

    for w in result.windows:
        result.strategy_counts[w.procurement_strategy] = result.strategy_counts.get(w.procurement_strategy, 0) + 1
        result.regime_breakdown[w.regime_level] = result.regime_breakdown.get(w.regime_level, 0) + 1

    # ---- Statistical tests against baselines (paired t + Diebold-Mariano) ----
    agent_costs = [w.realized_cost_agent for w in result.windows]
    spot_costs = [w.realized_cost_spot for w in result.windows]
    result.stats_vs_spot = _paired_stats(agent_costs, spot_costs, "buy_all_at_spot")

    equal_thirds_pairs = [
        (w.realized_cost_agent, w.realized_cost_equal_thirds)
        for w in result.windows if w.realized_cost_equal_thirds is not None
    ]
    if equal_thirds_pairs:
        a_costs = [p[0] for p in equal_thirds_pairs]
        e_costs = [p[1] for p in equal_thirds_pairs]
        result.stats_vs_equal_thirds = _paired_stats(a_costs, e_costs, "equal_thirds_1_3_6")

    rw_pairs = [
        (w.realized_cost_agent, w.realized_cost_random_walk)
        for w in result.windows if w.realized_cost_random_walk is not None
    ]
    if rw_pairs:
        result.stats_vs_random_walk = _paired_stats(
            [p[0] for p in rw_pairs], [p[1] for p in rw_pairs], "random_walk_forecast",
        )

    mr_pairs = [
        (w.realized_cost_agent, w.realized_cost_mean_reversion)
        for w in result.windows if w.realized_cost_mean_reversion is not None
    ]
    if mr_pairs:
        result.stats_vs_mean_reversion = _paired_stats(
            [p[0] for p in mr_pairs], [p[1] for p in mr_pairs], "mean_reversion_vs_MA",
        )

    a6_pairs = [
        (w.realized_cost_agent, w.realized_cost_always_6)
        for w in result.windows if w.realized_cost_always_6 is not None
    ]
    if a6_pairs:
        result.stats_vs_always_6 = _paired_stats(
            [p[0] for p in a6_pairs], [p[1] for p in a6_pairs], "always_horizon_6",
        )

    return result


def format_trace_report(bt: BacktestResult, max_rows: Optional[int] = None) -> str:
    """Per-window audit trace: for each evaluation window, dump exactly which
    layers fired, what signals/shifts they produced, whether the trend guard
    was active, and what the agent decided.

    The intent is to make every decision inspectable: a reader should be able
    to verify that layers are responding sensibly to the data (e.g. trend
    guard fires when 6m return is high; structural BUY fires when tightening
    score is positive) and aren't decorating chaotic behaviour.
    """
    rows = bt.windows if max_rows is None else bt.windows[:max_rows]
    if not rows:
        return "(no windows)"

    lines = [
        "=" * 130,
        "  CARBONEDGE -- PER-WINDOW DECISION TRACE",
        "=" * 130,
        "  Each row = one backtest evaluation. Columns show layer signals, mean shifts, constraints, and the resulting strategy.",
        "",
        f"  {'Date':<11} {'Spot':>6} {'6mRet':>6} {'TG':>3}  "
        f"{'Reg':<3} {'EPU':<6}{'S':<2} {'Drv':<7}{'bias':>5}  "
        f"{'Struc':<6}{'tscore':>7}  "
        f"{'comp':>5}  "
        f"{'mShift':>7} {'minS':>5} {'maxS':>5} {'maxB':>5}  "
        f"{'Strategy':<10} {'Alloc':<28} {'vs_spot EUR':>12}",
        f"  {'-'*130}",
    ]
    for w in rows:
        t = w.trace
        if t is None:
            continue
        tg = "Y" if t.trend_guard_active else " "
        spike = "*" if t.epu_spike else " "
        ret6 = f"{t.trailing_6mo_log_return*100:+5.1f}%" if t.trailing_6mo_log_return is not None else "  n/a "
        alloc_str = " ".join(f"{k}={v//1000}k" for k, v in t.allocation.items())[:28]
        sav_spot = w.savings_vs_spot
        lines.append(
            f"  {t.eval_date:<11} {t.spot_price:>6.2f} {ret6:>6} {tg:>3}  "
            f"{t.regime_level:<3} {t.epu_level:<6}{spike:<2} {t.driver_signal:<7}{t.driver_bias:>+5.2f}  "
            f"{t.structural_signal:<6}{t.structural_tightening_score:>+7.2f}  "
            f"{t.composite_score:>+5.2f}  "
            f"{t.total_mean_shift*100:>+6.1f}% {t.min_spot:>5.2f} {t.max_spot:>5.2f} {t.max_back:>5.2f}  "
            f"{t.strategy:<10} {alloc_str:<28} {sav_spot:>+12,.0f}"
        )

    # Summary stats: layer-firing rates and trend guard frequency
    n = len(rows)
    n_with_trace = sum(1 for w in rows if w.trace is not None)
    if n_with_trace:
        n_tg = sum(1 for w in rows if w.trace and w.trace.trend_guard_active)
        n_buy_str = sum(1 for w in rows if w.trace and w.trace.structural_signal == "BUY")
        n_def_str = sum(1 for w in rows if w.trace and w.trace.structural_signal == "DEFER")
        n_hold_str = sum(1 for w in rows if w.trace and w.trace.structural_signal == "HOLD")
        n_epu_crisis = sum(1 for w in rows if w.trace and w.trace.epu_level == "CRISIS")
        n_epu_spike = sum(1 for w in rows if w.trace and w.trace.epu_spike)
        n_regime_y = sum(1 for w in rows if w.trace and w.trace.regime_level == "YELLOW")
        n_regime_r = sum(1 for w in rows if w.trace and w.trace.regime_level == "RED")
        lines.extend([
            "",
            f"  --- LAYER FIRING SUMMARY (n={n_with_trace} windows) ---",
            f"    Trend guard active:          {n_tg:>4} ({n_tg/n_with_trace:.0%})",
            f"    Structural BUY:              {n_buy_str:>4} ({n_buy_str/n_with_trace:.0%})",
            f"    Structural DEFER:            {n_def_str:>4} ({n_def_str/n_with_trace:.0%})",
            f"    Structural HOLD:             {n_hold_str:>4} ({n_hold_str/n_with_trace:.0%})",
            f"    EPU CRISIS level:            {n_epu_crisis:>4} ({n_epu_crisis/n_with_trace:.0%})",
            f"    EPU spike (z>2):             {n_epu_spike:>4} ({n_epu_spike/n_with_trace:.0%})",
            f"    Regime YELLOW:               {n_regime_y:>4} ({n_regime_y/n_with_trace:.0%})",
            f"    Regime RED:                  {n_regime_r:>4} ({n_regime_r/n_with_trace:.0%})",
        ])
    lines.append("=" * 130)
    return "\n".join(lines)


def format_backtest_report(bt: BacktestResult, prices: Dict[str, float]) -> str:
    """Generate a human-readable backtest summary."""
    sorted_dates = sorted(prices.keys())
    price_start = min(bt.windows[0].evaluation_date, sorted_dates[0]) if bt.windows else sorted_dates[0]
    price_end = sorted_dates[-1]

    mode_label = {
        "naive": "OUT-OF-SAMPLE (random-walk-with-drift forecast, no future leakage)",
        "oracle": "ORACLE (actual future + noise; upper bound, not honest)",
    }.get(bt.forecast_mode, bt.forecast_mode.upper())

    lines = [
        "=" * 72,
        "  CARBONEDGE -- PROCUREMENT BACKTEST REPORT",
        "=" * 72,
        f"  Forecast mode: {mode_label}",
        f"  Period: {price_start} to {price_end}",
        f"  Windows evaluated: {bt.total_windows}",
        f"  Step size: {bt.step_months} months",
        f"  Allowances per window: {bt.windows[0].allowances_needed:,} tons" if bt.windows else "",
        "",
        f"  --- REALIZED PERFORMANCE vs SPOT BASELINE ---",
        f"  Windows beat spot:           {bt.windows_won}/{bt.total_windows}",
        f"  Windows lost to spot:        {bt.windows_lost}/{bt.total_windows}",
        f"  Windows tied (LUMP at spot): {bt.total_windows - bt.windows_won - bt.windows_lost}/{bt.total_windows}",
        f"  Total realized savings:      EUR {bt.total_savings_eur:>+14,.0f}",
        f"  Avg per-window savings:      EUR {bt.avg_savings_eur:>+14,.0f}",
        f"  Best window:                 EUR {bt.max_savings_eur:>+14,.0f}",
        f"  Worst window:                EUR {bt.max_loss_eur:>+14,.0f}",
    ]

    def _fmt_stats(stats: Optional[StatisticalSummary]) -> List[str]:
        if stats is None:
            return ["  (no data)"]
        sig = "**" if stats.p_value < 0.05 else "  "
        dm_sig = "**" if stats.dm_p_value < 0.05 else "  "
        dm_mark = " (SIGNIFICANT at 5%)" if stats.dm_significant else ""
        return [
            f"  n = {stats.n} paired windows",
            f"  Mean savings:   EUR {stats.mean_savings:>+14,.0f}",
            f"  Std deviation:  EUR {stats.std_savings:>+14,.0f}",
            f"  --- Classic paired t-test ---",
            f"  SE (naive):     EUR {stats.se_savings:>+14,.0f}",
            f"  t-statistic:     {stats.t_statistic:>+8.3f}",
            f"  p-value:         {stats.p_value:>8.4f}  {sig}",
            f"  95% CI:         [EUR {stats.ci95_low:>+12,.0f}, EUR {stats.ci95_high:>+12,.0f}]",
            f"  --- Diebold-Mariano (Newey-West HAC, h={stats.dm_bandwidth}) ---",
            f"  SE (HAC):       EUR {stats.dm_se_hac:>+14,.0f}",
            f"  DM statistic:    {stats.dm_statistic:>+8.3f}",
            f"  DM p-value:      {stats.dm_p_value:>8.4f}  {dm_sig}{dm_mark}",
        ]

    lines.extend([
        "",
        "  --- STATS: agent vs BUY-ALL-AT-SPOT (paired t-test + Diebold-Mariano) ---",
    ])
    lines.extend(_fmt_stats(bt.stats_vs_spot))

    lines.extend([
        "",
        "  --- STATS: agent vs EQUAL THIRDS (paired t-test + Diebold-Mariano) ---",
    ])
    lines.extend(_fmt_stats(bt.stats_vs_equal_thirds))

    lines.extend([
        "",
        "  --- STATS: agent vs RANDOM WALK FORECAST (naive benchmark) ---",
    ])
    lines.extend(_fmt_stats(bt.stats_vs_random_walk))

    lines.extend([
        "",
        "  --- STATS: agent vs MEAN-REVERSION (trailing 6-month MA anchor) ---",
    ])
    lines.extend(_fmt_stats(bt.stats_vs_mean_reversion))

    lines.extend([
        "",
        "  --- STATS: agent vs ALWAYS HORIZON-6 (extreme back-load) ---",
    ])
    lines.extend(_fmt_stats(bt.stats_vs_always_6))

    lines.extend([
        "",
        f"  --- STRATEGY BREAKDOWN ---",
    ])
    for strategy, count in sorted(bt.strategy_counts.items(), key=lambda x: -x[1]):
        pct = count / bt.total_windows * 100
        lines.append(f"  {strategy:<12} {count:>4} windows ({pct:.0f}%)")

    lines.extend([
        "",
        f"  --- REGIME BREAKDOWN ---",
    ])
    for regime, count in sorted(bt.regime_breakdown.items(), key=lambda x: -x[1]):
        pct = count / bt.total_windows * 100
        lines.append(f"  {regime:<8} {count:>4} windows ({pct:.0f}%)")

    lines.extend([
        "",
        f"  --- WINDOW DETAILS (last 10, realized costs) ---",
        f"  {'Date':<12} {'Spot':>6} {'Strategy':<10} {'Agent EUR':>11} {'vs Spot':>10} {'vs 1/3s':>10} {'vs RW':>10} {'vs A6':>10} {'Regime':<8}",
        f"  {'-' * 105}",
    ])
    for w in bt.windows[-10:]:
        eq = "    n/a" if w.savings_vs_equal_thirds is None else f"{w.savings_vs_equal_thirds:>+10,.0f}"
        rw = "    n/a" if w.savings_vs_random_walk is None else f"{w.savings_vs_random_walk:>+10,.0f}"
        a6 = "    n/a" if w.savings_vs_always_6 is None else f"{w.savings_vs_always_6:>+10,.0f}"
        lines.append(
            f"  {w.evaluation_date:<12} EUR{w.spot_price:>3.0f} "
            f"{w.procurement_strategy:<10} {w.realized_cost_agent:>11,.0f} "
            f"{w.savings_vs_spot:>+10,.0f} {eq} {rw} {a6} {w.regime_level:<8}"
        )

    # ---- Baseline summary (Diebold-Mariano significance) ----
    lines.extend([
        "",
        f"  --- BASELINE COMPARISON SUMMARY (Diebold-Mariano) ---",
        f"  {'Baseline':<25} {'n':>4} {'Mean':>12} {'DM stat':>9} {'DM p-value':>11} {'Signif':>7}",
        f"  {'-' * 75}",
    ])
    for stats in [bt.stats_vs_spot, bt.stats_vs_equal_thirds, bt.stats_vs_random_walk,
                  bt.stats_vs_mean_reversion, bt.stats_vs_always_6]:
        if stats is None:
            continue
        sig = "YES" if stats.dm_significant else " no"
        lines.append(
            f"  {stats.baseline_name:<25} {stats.n:>4} {stats.mean_savings:>+12,.0f} "
            f"{stats.dm_statistic:>+9.3f} {stats.dm_p_value:>11.4f} {sig:>7}"
        )

    lines.append("")
    lines.append("=" * 72)
    return "\n".join(lines)
