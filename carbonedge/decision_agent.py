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

from .config import (
    CARBON_EXPOSURE,
    COMPANY_PROFILE,
    DECISION_THRESHOLDS,
    EMISSION_SOURCES,
    ReductionOption,
)
from .enhancement.driver_filter import DriverBias, DriverFilter
from .enhancement.epu_modulator import EpuModulator, EpuState
from .enhancement.regime_enhancer import RegimeBand, get_confidence_multiplier
from .enhancement.structural_context import StructuralBackdrop, StructuralContext
from .fundamental.balance_model import FundamentalModel
from .fundamental.cap_schedule import build_cap_schedule
from .fundamental.data_sources import load_ets_csv
from .fundamental.driver_monitor import DriverMonitor, DriverState
from .mac_curve import MACCurve
from .budget_allocator import allocate_budget, AllocationPlan
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

    # Legacy fields for compatibility
    stream_a: Optional = None   # MarketTimingDecision (keep for now)
    stream_b: Optional[List] = None
    stream_c: Optional[List] = None
    cbam: Optional = None
    mac_curve: Optional[MACCurve] = None
    budget_summary: Optional[Dict] = None
    budget_allocation: Optional = None   # AllocationPlan
    alert_triggers: List[str] = field(default_factory=list)
    regime_status: Optional[RegimeStatus] = None
    regime_backtest: Optional[Dict] = None


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
    front_load = driver_bias.bias
    logger.debug(
        "front_load init from driver_bias: %+.3f (signal=%s)",
        front_load, driver_bias.signal,
    )

    # Structural BUY/DEFER signal (Bastianin et al. 2024):
    #   BUY  (market entering shortage) → tilt purchases forward
    #   DEFER (structural surplus)       → defer purchases
    # max/min override: the strongest directional signal wins. In a market with
    # a confident short-horizon Sybilion forecast, the trend signal often beats
    # the structural fundamentals on a 1-6 month window.
    if structural is not None:
        if structural.signal == "BUY":
            structural_tilt = 0.15 + 0.25 * max(0.0, structural.tightening_score)
            new_fl = max(front_load, structural_tilt)
            if new_fl != front_load:
                logger.info(
                    "Structural BUY tilt: front_load %+.2f -> %+.2f (tightening=%.2f)",
                    front_load, new_fl, structural.tightening_score,
                )
            front_load = new_fl
        elif structural.signal == "DEFER":
            structural_tilt = -0.15 - 0.15 * max(0.0, -structural.tightening_score)
            new_fl = min(front_load, structural_tilt)
            if new_fl != front_load:
                logger.info(
                    "Structural DEFER tilt: front_load %+.2f -> %+.2f (tightening=%.2f)",
                    front_load, new_fl, structural.tightening_score,
                )
            front_load = new_fl

    # Trend-aware tilt: GREEN regime + clear trend → act decisively.
    # Confidence is weighted by the NEAR-TERM (h=1) band — short-horizon
    # forecast accuracy is what makes procurement timing actionable. The
    # average band is dragged up by wide h=6+ bands and underweights confident
    # short-horizon signals.
    if regime.level == "GREEN" and forecast.current_value > 0 and forecast.forecast_points:
        last_h = max(forecast.forecast_points.keys())
        first_h = min(forecast.forecast_points.keys())
        ratio = forecast.forecast_points[last_h]["value"] / forecast.current_value
        first_fp = forecast.forecast_points[first_h]
        first_value = first_fp.get("value", forecast.current_value)
        if first_value > 0:
            first_band = (first_fp.get("high", first_value) - first_fp.get("low", first_value)) / first_value
        else:
            first_band = 1.0
        confidence = max(0.30, 1.0 - first_band / 0.30)
        if forecast.trend == "UP":
            # 5% rise -> 0.20, 20% -> 0.55, 40%+ -> ~1.0 (clipped)
            raw_magnitude = min(1.0, 0.10 + (ratio - 1.0) * 2.5)
            trend_tilt = raw_magnitude * confidence
            new_fl = max(front_load, trend_tilt)
            if new_fl != front_load:
                logger.info(
                    "GREEN+UP trend tilt: front_load %+.2f -> %+.2f (ratio=%.3f h1_band=%.3f conf=%.2f)",
                    front_load, new_fl, ratio, first_band, confidence,
                )
            front_load = new_fl
        elif forecast.trend == "DOWN":
            raw_magnitude = max(-1.0, -0.10 - (1.0 - ratio) * 2.5)
            trend_tilt = raw_magnitude * confidence
            new_fl = min(front_load, trend_tilt)
            if new_fl != front_load:
                logger.info(
                    "GREEN+DOWN trend tilt: front_load %+.2f -> %+.2f (ratio=%.3f h1_band=%.3f conf=%.2f)",
                    front_load, new_fl, ratio, first_band, confidence,
                )
            front_load = new_fl

    # EPU spike: accelerate purchases (Dai et al. 2020 — EPU -> volatility).
    # Runs AFTER trend, so a CRISIS-level spike can override a DOWN trend.
    if epu and epu.spike and front_load < 0.2:
        logger.info(
            "EPU spike override: front_load %+.2f -> 0.20 (z=%.2f)",
            front_load, epu.z_score,
        )
        front_load = max(front_load, 0.2)

    # EPU CRISIS: bands already widened via volatility_mult; cap at 0.50 (not 0.35)
    # so a confident UP forecast can still drive heavy front-loading.
    if epu and epu.level == "CRISIS":
        if front_load > 0.50:
            logger.info("EPU CRISIS cap: front_load %+.2f -> 0.50", front_load)
        front_load = min(front_load, 0.50)
    if regime.level == "RED":
        logger.warning(
            "Regime RED override: FREEZE (front_load %+.2f -> 0, 25%% lump at spot)",
            front_load,
        )
        front_load = 0.0
        if regime.level == "RED":
            # Minimal buy only
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

    # High-conviction LUMP_SUM shortcut.
    # When the agent's combined signal is strongly directional with reasonable
    # confidence, the CVaR optimizer's fixed-fraction allocation under-reacts.
    # Bypass it and lump-sum at the favorable end.
    #   front_load >= +0.55 → buy all at NOW (price expected to rise sharply)
    #   front_load <= -0.40 → buy all at the latest window (price expected to fall)
    # Conditions: GREEN regime only; RED is handled above with FREEZE.
    if regime.level == "GREEN" and front_load >= 0.55:
        logger.info(
            "LUMP_SUM shortcut: front_load=%+.2f -> 100%% at NOW (forecast %s, band=%.3f)",
            front_load, forecast.trend, forecast.band_width_ratio,
        )
        latest = max(forecast.forecast_points.keys())
        future_mu = forecast_mean.get(latest, current_price)
        sigma_now = forecast_sigma.get(min(forecast_mean), current_price * 0.1)
        return ProcurementPlan(
            total_tons=allowances_needed,
            windows=[PurchaseWindow(
                horizon=1, label="NOW", tons=allowances_needed,
                expected_price=current_price,
                price_low=max(1.0, current_price - 2 * sigma_now),
                price_high=current_price + 2 * sigma_now,
                cost_expected=allowances_needed * current_price,
                cost_worst_case=allowances_needed * (current_price + 2 * sigma_now),
            )],
            total_cost_expected=allowances_needed * current_price,
            total_cost_worst_case=allowances_needed * (current_price + 2 * sigma_now),
            cost_if_all_now=allowances_needed * current_price,
            expected_savings=allowances_needed * (future_mu - current_price),
            worst_case_savings=0.0,
            strategy="LUMP_SUM",
            reasoning=(
                f"High-conviction UP: forecast {forecast.trend}, "
                f"front_load={front_load:+.2f}, band={forecast.band_width_ratio:.2f}. "
                f"Lump-sum at spot EUR{current_price:.0f} avoids paying forward EUR{future_mu:.0f}."
            ),
        )
    if regime.level == "GREEN" and front_load <= -0.40:
        latest = max(forecast.forecast_points.keys())
        future_mu = forecast_mean.get(latest, current_price)
        sigma_h = forecast_sigma.get(latest, current_price * 0.1)
        logger.info(
            "LUMP_SUM shortcut: front_load=%+.2f -> 100%% at h=%d (forecast %s, band=%.3f)",
            front_load, latest, forecast.trend, forecast.band_width_ratio,
        )
        label = {3: "M3", 6: "M6", 9: "M9", 12: "M12"}.get(latest, f"M{latest}")
        return ProcurementPlan(
            total_tons=allowances_needed,
            windows=[PurchaseWindow(
                horizon=latest, label=label, tons=allowances_needed,
                expected_price=future_mu,
                price_low=max(1.0, future_mu - 2 * sigma_h),
                price_high=future_mu + 2 * sigma_h,
                cost_expected=allowances_needed * future_mu,
                cost_worst_case=allowances_needed * (future_mu + 2 * sigma_h),
            )],
            total_cost_expected=allowances_needed * future_mu,
            total_cost_worst_case=allowances_needed * (future_mu + 2 * sigma_h),
            cost_if_all_now=allowances_needed * current_price,
            expected_savings=allowances_needed * (current_price - future_mu),
            worst_case_savings=allowances_needed * (current_price - (future_mu + 2 * sigma_h)),
            strategy="LUMP_BACK",
            reasoning=(
                f"High-conviction DOWN: forecast {forecast.trend}, "
                f"front_load={front_load:+.2f}, band={forecast.band_width_ratio:.2f}. "
                f"Defer all to h={latest} at forecast EUR{future_mu:.0f} vs spot EUR{current_price:.0f}."
            ),
        )

    # Run CVaR optimizer
    logger.info(
        "Running CVaR optimizer: windows=%s, conf=%.2fx, vol=%.2fx, front_load=%+.2f",
        purchase_windows, confidence_mult, volatility_mult, front_load,
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
    cbam_tons: int,
    allowances_needed: int,
    grid_carbon_forecast: Optional[Dict[int, float]] = None,
    production_demand_forecast: Optional[Dict[int, float]] = None,
    regime_monitor: Optional[RegimeMonitor] = None,
    historical_prices: Optional[List[float]] = None,
    historical_forecasts: Optional[List[float]] = None,
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
        budget_allocation=reduction_plan,
        alert_triggers=alerts,
        budget_summary={
            "total_budget": budget,
            "allocated_now": procurement.windows[0].cost_expected if procurement.windows else 0,
            "reduction_tons": reduction_plan.total_tons_reduced,
            "reserve": reduction_plan.reserve_budget,
        },
    )
