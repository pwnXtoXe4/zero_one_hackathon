"""
CarbonEdge -- Decision Agent v2

The agent consumes Sybilion's forecast, enhances it through 4 layers
(regime, EPU, drivers, structural context), then produces a concrete
procurement plan via CVaR optimization or ladder heuristics.

ARCHITECTURE:
  Sybilion forecast
       |
       v
  Enhancement Layer  -> adjusted_bands + context
       |
       v
  Procurement Optimizer -> buy_plan (tons, EUR, windows)

The fundamental model provides STRUCTURAL CONTEXT only — it does NOT
produce a competing forecast. All signals enhance Sybilion's bands.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import numpy as np

from .config import CARBON_EXPOSURE, COMPANY_PROFILE
from .enhancement.driver_filter import DriverBias, DriverFilter
from .enhancement.epu_modulator import EpuModulator, EpuState
from .enhancement.regime_enhancer import RegimeBand, get_confidence_multiplier
from .enhancement.structural_context import StructuralBackdrop, StructuralContext
from .fundamental.balance_model import FundamentalModel
from .fundamental.driver_monitor import DriverMonitor
from .mac_curve import MACCurve
from .budget_allocator import allocate_budget
from .procurement.ladder_rules import ladder_fallback, LadderInput
from .procurement.optimizer import (
    ProcurementPlan,
    PurchaseWindow,
    optimize_procurement,
)
from .regime_detector import RegimeMonitor, RegimeStatus
from .sybilion_client import ForecastResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enhanced decision output
# ---------------------------------------------------------------------------

@dataclass
class EnhancedDecision:
    """Full decision output with enhancement layer visible."""
    # Sybilion forecast summary
    trend: str
    band_width_ratio: float
    current_price: float

    # Enhancement state (all visible for reasoning transparency)
    regime: RegimeBand
    epu: Optional[EpuState]
    driver_bias: DriverBias
    structural: Optional[StructuralBackdrop]

    # Procurement plan
    procurement: ProcurementPlan

    # Auxiliary state used by output formatter
    mac_curve: Optional[MACCurve] = None
    budget_summary: Optional[Dict] = None
    alert_triggers: List[str] = field(default_factory=list)
    regime_status: Optional[RegimeStatus] = None


# ---------------------------------------------------------------------------
# Enhancement pipeline
# ---------------------------------------------------------------------------

def build_enhancement_pipeline(
    forecast: ForecastResult,
    current_price: float,
    regime_monitor: Optional[RegimeMonitor],
    historical_prices: Optional[List[float]],
    fundamental_model: Optional[FundamentalModel],
    driver_monitor: Optional[DriverMonitor],
    evaluation_date: str = "",
) -> Tuple[RegimeBand, Optional[EpuState], DriverBias, Optional[StructuralBackdrop]]:
    """
    Run all 4 enhancement modules and return their state.
    None of these produce a competing forecast — they adjust bands.
    evaluation_date: YYYY-MM-DD for backtest reproducibility. Falls back to current month.
    """

    logger.debug(
        "build_enhancement_pipeline: regime_monitor=%s history=%d, hist_prices=%d, "
        "fundamental_model=%s, driver_monitor=%s, eval_date=%s",
        "yes" if regime_monitor else "no",
        len(regime_monitor._status_history) if regime_monitor else 0,
        len(historical_prices) if historical_prices else 0,
        "yes" if fundamental_model else "no",
        "yes" if driver_monitor else "no",
        evaluation_date or "(now)",
    )

    # 1. Regime detection
    regime_status = None
    if regime_monitor is not None and regime_monitor._status_history:
        regime_status = regime_monitor._status_history[-1]
    regime = get_confidence_multiplier(regime_status, historical_prices)
    logger.info(
        "Regime layer: level=%s mult=%.2fx focus=%s cusum=%s bubble=%s",
        regime.level, regime.multiplier,
        regime.focus_triggered, regime.cusum_triggered, regime.bubble_risk,
    )

    # 2. EPU volatility
    epu = None
    try:
        epu_mod = EpuModulator()
        if evaluation_date:
            date_key = evaluation_date
        else:
            date_key = f"{datetime.now().year}-{datetime.now().month:02d}-01"
        epu = epu_mod.evaluate(date_key)
        logger.info(
            "EPU layer: date=%s value=%.0f level=%s mult=%.2fx z=%.2f spike=%s",
            date_key, epu.epu_value, epu.level,
            epu.volatility_multiplier, epu.z_score, epu.spike,
        )
    except (KeyError, ValueError, FileNotFoundError) as e:
        logger.warning("EPU modulator evaluation failed: %s", e)
        import warnings
        warnings.warn(f"EPU modulator evaluation failed: {e}")

    # 3. Driver filter
    if driver_monitor and driver_monitor.latest:
        driver_filter = DriverFilter(driver_monitor)
        driver_bias = driver_filter.evaluate()
        logger.info(
            "Driver layer: signal=%s bias=%+.2f coal_up=%s energy_up=%s fuel_switch_bearish=%s",
            driver_bias.signal, driver_bias.bias,
            driver_bias.coal_rising, driver_bias.energy_rising,
            driver_bias.fuel_switch_bearish,
        )
    else:
        driver_bias = DriverBias(
            bias=0.0, signal="NEUTRAL",
            coal_rising=False, energy_rising=False,
            fuel_switch_bearish=False,
            reasoning="Driver monitor inactive. Using neutral allocation.",
        )
        logger.warning(
            "Driver layer inactive: monitor=%s, latest=%s -> NEUTRAL bias",
            "present" if driver_monitor else "missing",
            "yes" if driver_monitor and driver_monitor.latest else "no",
        )

    # 4. Structural context
    structural = None
    if fundamental_model:
        try:
            ctx = StructuralContext(fundamental_model)
            if evaluation_date:
                eval_year = int(evaluation_date[:4])
            else:
                eval_year = datetime.now().year
            structural = ctx.evaluate(year=eval_year)
            logger.info(
                "Structural layer: year=%d signal=%s cap=%.0fMt ems=%.0fMt balance=%+.0fMt inflection=%s",
                eval_year, structural.signal,
                structural.cap_mt, structural.emissions_mt,
                structural.balance_mt, structural.surplus_to_shortage_year,
            )
        except (ValueError, KeyError) as e:
            logger.warning("Structural context evaluation failed: %s", e)
            import warnings
            warnings.warn(f"Structural context evaluation failed: {e}")
    else:
        logger.debug("Structural layer skipped: no fundamental model provided.")

    return regime, epu, driver_bias, structural


# ---------------------------------------------------------------------------
# Procurement decision
# ---------------------------------------------------------------------------

def make_procurement_decision(
    forecast: ForecastResult,
    current_price: float,
    allowances_needed: int,
    regime: RegimeBand,
    epu: Optional[EpuState],
    driver_bias: DriverBias,
    structural: Optional[StructuralBackdrop] = None,
) -> ProcurementPlan:
    """
    Convert enhanced forecast bands into a procurement plan.
    Uses CVaR optimizer; falls back to ladder heuristics if insufficient data.
    """
    logger.debug(
        "make_procurement_decision: %d forecast horizons, allowances=%d, "
        "regime.mult=%.2fx, epu_mult=%.2fx, driver_bias=%+.2f",
        len(forecast.forecast_points),
        allowances_needed,
        regime.multiplier,
        epu.volatility_multiplier if epu else 1.0,
        driver_bias.bias,
    )

    if not forecast.forecast_points:
        # No forecast at all — buy all now as emergency fallback
        logger.warning(
            "No forecast points available -> emergency LUMP_SUM at spot price EUR%.2f",
            current_price,
        )
        return ProcurementPlan(
            total_tons=allowances_needed,
            windows=[PurchaseWindow(
                horizon=1, label="NOW", tons=allowances_needed,
                expected_price=current_price,
                price_low=current_price * 0.9,
                price_high=current_price * 1.1,
                cost_expected=allowances_needed * current_price,
                cost_worst_case=allowances_needed * current_price * 1.1,
            )],
            total_cost_expected=allowances_needed * current_price,
            total_cost_worst_case=allowances_needed * current_price * 1.1,
            cost_if_all_now=allowances_needed * current_price,
            expected_savings=0,
            worst_case_savings=-allowances_needed * current_price * 0.1,
            strategy="LUMP_SUM",
            reasoning="No forecast available. Buying all now at spot as emergency measure.",
        )

    # Extract mean and sigma from Sybilion forecast
    forecast_mean: Dict[int, float] = {}
    forecast_sigma: Dict[int, float] = {}
    for h, fp in forecast.forecast_points.items():
        value = fp.get("value", current_price)
        low = fp.get("low", value * 0.85)
        high = fp.get("high", value * 1.15)
        forecast_mean[h] = value
        forecast_sigma[h] = max(1.0, (high - low) / 4.0)  # approx sigma from CI

    purchase_windows = [1, 3, 6]
    available_horizons = sorted(forecast_mean.keys())
    purchase_windows = [h for h in purchase_windows if h in available_horizons]
    if not purchase_windows:
        # At minimum, buy at the nearest horizon
        purchase_windows = [min(available_horizons)]

    confidence_mult = regime.multiplier
    volatility_mult = epu.volatility_multiplier if epu else 1.0

    # ---- Forecast adjustment from enhancement layers ----
    # Each layer's signal is folded into the inputs the CVaR optimizer sees,
    # instead of fighting over a single scalar `front_load_bias` via min/max.
    #
    #   regime.multiplier      → sigma scaling (uncertainty up = wider bands)
    #   epu.volatility_mult    → sigma scaling (EPU up = wider bands)
    #   driver_bias.bias       → mean shift   (BULLISH = forecast biased up)
    #   structural.signal      → mean shift   (BUY = structural shortage premium)
    #
    # The mean shifts are intentionally small — the Sybilion forecast is the
    # primary signal; enhancement layers nudge it. Larger nudges in the same
    # direction compound; opposing nudges partially cancel. The CVaR optimizer
    # then chooses the allocation by minimising (1−λ)·E[cost] + λ·CVaR.
    driver_shift = driver_bias.bias * 0.05   # ±0.30 driver bias → ±1.5% mean shift
    structural_shift = 0.0
    if structural is not None:
        if structural.signal == "BUY":
            structural_shift = 0.02 + 0.03 * max(0.0, structural.tightening_score)
        elif structural.signal == "DEFER":
            structural_shift = -0.02 - 0.03 * max(0.0, -structural.tightening_score)
    mean_shift = driver_shift + structural_shift
    logger.info(
        "Forecast mean shift: driver=%+.3f + structural=%+.3f -> %+.3f (applied as multiplier 1+shift)",
        driver_shift, structural_shift, mean_shift,
    )

    # Apply the mean shift to the forecast going into the optimizer
    shifted_mean = {h: v * (1.0 + mean_shift) for h, v in forecast_mean.items()}

    # Use the driver bias as a soft prior for the optimizer's initial guess.
    # This shortens search time and helps in flat-forecast cases where the
    # CVaR objective has multiple near-optimal solutions.
    front_load = float(np.clip(driver_bias.bias + 0.5 * structural_shift, -0.5, 0.5))

    # EPU spike: nudge mean upward (lock in before vol surge) per Dai et al.
    if epu and epu.spike:
        logger.info("EPU spike: shifting forecast mean +2%% (z=%.2f)", epu.z_score)
        shifted_mean = {h: v * 1.02 for h, v in shifted_mean.items()}

    # Regime RED: structural break → emergency freeze, skip optimization.
    if regime.level == "RED":
        logger.warning("Regime RED -> FREEZE (25%% lump at spot)")
        return ProcurementPlan(
            total_tons=allowances_needed,
            windows=[PurchaseWindow(
                horizon=1, label="NOW", tons=int(allowances_needed * 0.25),
                expected_price=current_price,
                price_low=current_price * 0.8,
                price_high=current_price * 1.5,
                cost_expected=int(allowances_needed * 0.25) * current_price,
                cost_worst_case=int(allowances_needed * 0.25) * current_price * 1.5,
            )],
            total_cost_expected=int(allowances_needed * 0.25) * current_price,
            total_cost_worst_case=int(allowances_needed * 0.25) * current_price * 1.5,
            cost_if_all_now=allowances_needed * current_price,
            expected_savings=allowances_needed * current_price - int(allowances_needed * 0.25) * current_price,
            worst_case_savings=allowances_needed * current_price - int(allowances_needed * 0.25) * current_price * 1.5,
            strategy="FREEZE",
            reasoning="REGIME RED: Minimal purchase to cover compliance. Freeze remaining until regime clears.",
        )

    # Adaptive risk aversion: λ scales with forecast uncertainty.
    # Narrow bands -> trust the forecast direction (low λ).
    # Wide bands -> hedge with spot certainty (high λ).
    risk_lambda = float(np.clip(0.05 + 0.30 * forecast.band_width_ratio / 0.5, 0.05, 0.50))

    # Run CVaR optimizer (scipy SLSQP over allocation fractions).
    forecast_mean = shifted_mean
    logger.info(
        "Running CVaR optimizer: windows=%s, conf=%.2fx, vol=%.2fx, prior_bias=%+.2f, "
        "mean_shift=%+.2f%%, lambda=%.2f (band=%.3f)",
        purchase_windows, confidence_mult, volatility_mult, front_load, mean_shift * 100,
        risk_lambda, forecast.band_width_ratio,
    )
    try:
        plan = optimize_procurement(
            forecast_mean=forecast_mean,
            forecast_sigma=forecast_sigma,
            total_tons=allowances_needed,
            purchase_windows=purchase_windows,
            current_price=current_price,
            confidence_multiplier=confidence_mult,
            volatility_multiplier=volatility_mult,
            front_load_bias=front_load,
            risk_lambda=risk_lambda,
        )
        logger.info(
            "Procurement plan: %s, %d tons, EUR%.0f expected, EUR%+.0f vs spot",
            plan.strategy, plan.total_tons,
            plan.total_cost_expected, plan.expected_savings,
        )
    except (ValueError, KeyError) as exc:
        logger.warning(
            "CVaR optimizer failed (%s) -> ladder fallback (trend=%s band=%.3f regime=%s)",
            exc, forecast.trend, forecast.band_width_ratio, regime.level,
        )
        # Fallback to ladder heuristic
        inp = LadderInput(
            trend=forecast.trend,
            band_width_ratio=forecast.band_width_ratio,
            regime_level=regime.level,
            total_tons=allowances_needed,
            current_price=current_price,
        )
        ladder = ladder_fallback(inp)
        windows = []
        for label, qty in ladder.items():
            if label == "FREEZE":
                continue
            h = {"NOW": 1, "M3": 3, "M4": 4, "M6": 6, "M8": 8, "M12": 12}.get(label, 1)
            windows.append(PurchaseWindow(
                horizon=h, label=label, tons=qty,
                expected_price=forecast_mean.get(h, current_price),
                price_low=forecast_mean.get(h, current_price) - forecast_sigma.get(h, current_price * 0.1),
                price_high=forecast_mean.get(h, current_price) + forecast_sigma.get(h, current_price * 0.1),
                cost_expected=qty * forecast_mean.get(h, current_price),
                cost_worst_case=qty * (forecast_mean.get(h, current_price) + forecast_sigma.get(h, current_price * 0.1)),
            ))
        plan = ProcurementPlan(
            total_tons=allowances_needed,
            windows=windows,
            total_cost_expected=sum(w.cost_expected for w in windows),
            total_cost_worst_case=sum(w.cost_worst_case for w in windows),
            cost_if_all_now=allowances_needed * current_price,
            expected_savings=allowances_needed * current_price - sum(w.cost_expected for w in windows),
            worst_case_savings=allowances_needed * current_price - sum(w.cost_worst_case for w in windows),
            strategy="LADDER",
            reasoning="Heuristic ladder (CVaR optimization data insufficient).",
        )
        logger.info(
            "Ladder fallback: %s, %d tons, EUR%.0f expected, EUR%+.0f vs spot",
            plan.strategy, plan.total_tons,
            plan.total_cost_expected, plan.expected_savings,
        )

    return plan


# ---------------------------------------------------------------------------
# Aggregator: run enhanced decision pipeline
# ---------------------------------------------------------------------------

def run_decision_agent(
    ets_forecast: ForecastResult,
    mac_curve: MACCurve,
    budget: float,
    current_ets_price: float,
    allowances_needed: int,
    regime_monitor: Optional[RegimeMonitor] = None,
    historical_prices: Optional[List[float]] = None,
    fundamental_model: Optional[FundamentalModel] = None,
    driver_monitor: Optional[DriverMonitor] = None,
    evaluation_date: str = "",
) -> EnhancedDecision:
    """
    Run the enhanced decision pipeline:
    1. Enhance Sybilion forecast bands
    2. Compute procurement plan
    3. Return full decision with all context visible
    """

    # ---- Enhancement Pipeline ----
    regime, epu, driver_bias, structural = build_enhancement_pipeline(
        ets_forecast, current_ets_price,
        regime_monitor, historical_prices,
        fundamental_model, driver_monitor,
        evaluation_date=evaluation_date,
    )

    # ---- Procurement Decision ----
    procurement = make_procurement_decision(
        ets_forecast, current_ets_price, allowances_needed,
        regime, epu, driver_bias, structural,
    )

    # ---- Alerts ----
    alerts: List[str] = []

    # Regime alerts
    if regime.level != "GREEN":
        alerts.append(f"[REGIME] {regime.level}: {regime.advisory}")
    if regime.focus_triggered:
        alerts.append("[FOCuS] Structural break detected in ETS price volatility.")
    if regime.cusum_triggered:
        alerts.append("[CUSUM] Forecast residuals show systematic bias.")
    if regime.bubble_risk:
        alerts.append("[BUBBLE] Explosive price behaviour detected (Friedrich et al. 2019).")

    # EPU alerts
    if epu:
        epu_advisory = (
            f"EPU: {epu.epu_value:.0f} ({epu.level}), "
            f"z-score: {epu.z_score:+.1f} vs 12m mean {epu.epu_12m_mean:.0f}"
        )
        if epu.spike:
            epu_advisory += " | SPIKE: >2 sigma above mean"
        if epu.level == "CRISIS":
            epu_advisory += " | CRISIS: strongly consider freezing purchases"
        alerts.append(f"[EPU] {epu_advisory}")
        if epu.spike:
            alerts.append("[EPU SPIKE] Consider accelerating purchases before volatility surge.")

    # Driver alerts
    alerts.append(f"[DRIVERS] {driver_bias.reasoning}")

    # Structural alerts
    if structural:
        alerts.append(f"[STRUCTURAL] {structural.narrative}")
        if structural.signal == "BUY":
            alerts.append(
                f"[STRUCTURAL] Market entering shortage from {structural.surplus_to_shortage_year}. "
                f"Cap declining {structural.annual_cap_decline_mt_per_year:.0f} Mt/year."
            )

    # Procurement alerts
    alerts.append(
        f"[PROCUREMENT] {procurement.strategy}: {procurement.total_tons:,} tons, "
        f"expected cost EUR{procurement.total_cost_expected:,.0f}, "
        f"savings EUR{procurement.expected_savings:+,.0f} vs spot."
    )

    # ---- Budget Allocation ----
    reduction_plan = allocate_budget(
        mac_curve=mac_curve,
        budget=budget,
        ets_price=current_ets_price,
    )
    alerts.append(
        f"[BUDGET] EUR{budget:,.0f} allocated: "
        f"{reduction_plan.total_tons_reduced:,.0f} tons reduced "
        f"@ EUR{reduction_plan.blended_cost_per_ton:.0f}/ton. "
        f"EUR{reduction_plan.reserve_budget:,.0f} held in reserve."
    )

    return EnhancedDecision(
        trend=ets_forecast.trend,
        band_width_ratio=ets_forecast.band_width_ratio,
        current_price=current_ets_price,
        regime=regime,
        epu=epu,
        driver_bias=driver_bias,
        structural=structural,
        procurement=procurement,
        alert_triggers=alerts,
        budget_summary={
            "total_budget": budget,
            "allocated_now": procurement.windows[0].cost_expected if procurement.windows else 0,
            "reduction_tons": reduction_plan.total_tons_reduced,
            "reserve": reduction_plan.reserve_budget,
        },
    )
