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
from .enhancement.demand_signal import DemandSignal, DemandState
from .enhancement.company_risk import CompanyRiskLayer, CompanyRiskProfile
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
    AllocationConstraints,
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

    # Enhancement layers 5 & 6 (added without altering existing fields)
    demand: Optional[DemandState] = None
    risk_profile: Optional[CompanyRiskProfile] = None


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
) -> Tuple[RegimeBand, Optional[EpuState], DriverBias, Optional[StructuralBackdrop], Optional[DemandState]]:
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

    # 5. Industrial demand signal
    demand = None
    try:
        demand_signal = DemandSignal()
        demand = demand_signal.evaluate()
        logger.info("Demand layer: composite=%.1f YoY=%+.1f%% pressure=%.2f divergence=%.2f",
            demand.composite_index, demand.composite_yoy_change_pct,
            demand.demand_pressure, demand.sector_divergence)
    except Exception as e:
        logger.warning("Demand signal evaluation failed: %s", e)

    return regime, epu, driver_bias, structural, demand


# ---------------------------------------------------------------------------
# Layer-driven allocation constraints
# ---------------------------------------------------------------------------

def compute_layer_composite(
    structural: Optional[StructuralBackdrop],
    driver_bias: DriverBias,
    epu: Optional[EpuState],
    demand: Optional[DemandState],
) -> float:
    """Aggregate enhancement-layer signals into a single signed composite
    confidence score in [-1, +1].

    Positive  -> BULLISH (forwards expensive, lock in now / front-load).
    Negative  -> BEARISH (forwards cheaper, defer / back-load).

    Weights reflect each layer's empirical reliability per the cited papers:
      structural (Bastianin 2024) 40%, driver (Maciejowski-Leonelli 2025) 30%,
      demand (Bastianin 2024 §5.3) 20%, EPU (Dai 2020) 10%. The weights are
      paper-priority -- not fit to this dataset -- but they do reflect a
      bias toward the slower-moving fundamental signal over the noisier
      sentiment ones.

    The compound effect: when 3-4 layers agree, composite saturates near
    +/-1 and downstream rules can take a high-conviction directional bet.
    When layers disagree, composite stays near 0 and the agent falls back
    to the plain CVaR optimum (i.e. behaves like the no-layer baseline).
    """
    parts: List[Tuple[float, float]] = []  # (value, weight)
    if structural is not None:
        parts.append((float(structural.tightening_score), 0.40))
    parts.append((float(driver_bias.bias), 0.30))
    if epu is not None and epu.spike:
        parts.append((+0.7, 0.10))  # EPU spike -> bullish lock-in
    if demand is not None:
        parts.append((float(demand.demand_pressure), 0.20))
    if not parts:
        return 0.0
    total_w = sum(w for _, w in parts)
    if total_w <= 0:
        return 0.0
    composite = sum(v * w for v, w in parts) / total_w
    return max(-1.0, min(1.0, composite))


def apply_composite_override(
    composite: float,
    cons: AllocationConstraints,
    trend_guard_active: bool,
) -> AllocationConstraints:
    """Tighten the allocation constraints based on the composite confidence.

    Behaviour by composite range:
      composite > +0.50  -- HIGH-CONVICTION BULL   -> require >=70% at spot
                            (+ trend guard: +80%)
      0.25 < composite < +0.50 -- MEDIUM BULL      -> require >=40% at spot
      -0.25 < composite < +0.25 -- LOW CONVICTION  -> no change (CVaR free)
      -0.50 < composite < -0.25 -- MEDIUM BEAR     -> cap spot at 30%
      composite < -0.50  -- HIGH-CONVICTION BEAR   -> cap spot at 10%
                            (trend guard overrides bear signals upstream)
    """
    if composite > 0.50:
        floor = 0.80 if trend_guard_active else 0.70
        if floor > cons.min_spot_fraction:
            cons.min_spot_fraction = floor
            cons.binding_reasons.append(
                f"composite={composite:+.2f} HIGH-CONVICTION BULL -> require {int(floor*100)}% at spot"
            )
    elif composite > 0.25:
        if 0.40 > cons.min_spot_fraction:
            cons.min_spot_fraction = 0.40
            cons.binding_reasons.append(
                f"composite={composite:+.2f} MEDIUM BULL -> require 40% at spot"
            )
    elif composite < -0.50 and not trend_guard_active:
        if 0.10 < cons.max_spot_fraction:
            cons.max_spot_fraction = 0.10
            cons.binding_reasons.append(
                f"composite={composite:+.2f} HIGH-CONVICTION BEAR -> cap spot at 10%"
            )
    elif composite < -0.25 and not trend_guard_active:
        if 0.30 < cons.max_spot_fraction:
            cons.max_spot_fraction = 0.30
            cons.binding_reasons.append(
                f"composite={composite:+.2f} MEDIUM BEAR -> cap spot at 30%"
            )
    return cons


def derive_constraints(
    regime: RegimeBand,
    epu: Optional[EpuState],
    driver_bias: DriverBias,
    structural: Optional[StructuralBackdrop],
    demand: Optional[DemandState] = None,
) -> AllocationConstraints:
    """Translate enhancement-layer state into hard allocation bounds.

    Grounded in the cited papers — each bound has a single paper citation as
    rationale so the constraint is traceable. The optimizer enforces these
    via SLSQP; the rationale strings show up in the procurement plan reason.

    Directionality convention:
      - "BUY" / spike  -> require some near-term lock-in (raise min_spot)
      - "DEFER"        -> cap near-term, force forward allocation (lower max_spot,
                          lower max_back so we don't dump everything at 6mo either)
      - Wide bands /
        regime unrest  -> force spreading (cap any single window)
    """
    c = AllocationConstraints()

    # --- Structural (Bastianin et al. 2024 -- shortage premium) ---
    if structural is not None:
        if structural.signal == "BUY" and structural.tightening_score > 0.3:
            c.min_spot_fraction = max(c.min_spot_fraction, 0.30)
            c.binding_reasons.append(
                f"Bastianin 2024 structural BUY (tighten={structural.tightening_score:+.2f}) "
                f"-> min 30% at spot"
            )
        elif structural.signal == "DEFER" and structural.tightening_score < -0.3:
            c.max_spot_fraction = min(c.max_spot_fraction, 0.40)
            c.max_back_fraction = min(c.max_back_fraction, 0.50)
            c.binding_reasons.append(
                f"Bastianin 2024 structural DEFER (tighten={structural.tightening_score:+.2f}) "
                f"-> cap spot @40%, cap back-load @50%"
            )

    # --- EPU (Dai et al. 2020 -- spike accelerates purchases) ---
    if epu is not None:
        if epu.spike:
            c.min_spot_fraction = max(c.min_spot_fraction, 0.30)
            c.binding_reasons.append(
                f"Dai 2020 EPU spike (z={epu.z_score:+.2f}) "
                f"-> min 30% at spot (lock in before vol surge)"
            )
        if epu.level == "CRISIS" and not epu.spike:
            c.max_single_fraction = min(c.max_single_fraction, 0.60)
            c.binding_reasons.append(
                f"Dai 2020 EPU CRISIS (level={epu.level}) without spike "
                f"-> cap any single window @60% (force spread)"
            )

    # --- Drivers (Maciejowski & Leonelli 2025 -- coal/energy) ---
    if driver_bias.signal == "BUY" and driver_bias.bias > 0.30:
        c.max_back_fraction = min(c.max_back_fraction, 0.30)
        c.binding_reasons.append(
            f"Maciejowski-Leonelli 2025 drivers bullish (bias={driver_bias.bias:+.2f}) "
            f"-> cap back-load @30%"
        )
    elif driver_bias.signal == "DEFER" and driver_bias.bias < -0.30:
        c.max_spot_fraction = min(c.max_spot_fraction, 0.50)
        c.binding_reasons.append(
            f"Maciejowski-Leonelli 2025 drivers bearish (bias={driver_bias.bias:+.2f}) "
            f"-> cap spot @50%"
        )

    # --- Regime / structural break (Friedrich 2019) ---
    if regime.level == "YELLOW":
        c.max_single_fraction = min(c.max_single_fraction, 0.70)
        c.binding_reasons.append(
            "Friedrich 2019 regime YELLOW (FOCuS/CUSUM/PSY soft) "
            "-> cap any single window @70%"
        )

    return c


# ---------------------------------------------------------------------------
# Procurement decision
# ---------------------------------------------------------------------------

def _trailing_return(historical_prices: Optional[List[float]], months: int = 6) -> Optional[float]:
    """Compute trailing N-month log-return from a price series. Returns None
    if insufficient data."""
    if not historical_prices or len(historical_prices) < months + 1:
        return None
    p_then = historical_prices[-(months + 1)]
    p_now = historical_prices[-1]
    if p_then <= 0 or p_now <= 0:
        return None
    return float(np.log(p_now / p_then))


# Trend guard threshold: when trailing 6-month log-return exceeds +5%, suppress
# any DEFER-direction signals from the structural / driver / demand layers.
# Rationale: in a positively-trending market, betting against the trend is
# expected to lose under any momentum-respecting prior. Cross-asset momentum
# literature (Asness-Moskowitz-Pedersen 2013; commodity momentum studies)
# consistently find positive 6-12 month momentum premia.
TREND_GUARD_LOG_RETURN = 0.05


def make_procurement_decision(
    forecast: ForecastResult,
    current_price: float,
    allowances_needed: int,
    regime: RegimeBand,
    epu: Optional[EpuState],
    driver_bias: DriverBias,
    structural: Optional[StructuralBackdrop] = None,
    demand: Optional[DemandState] = None,
    risk_profile: Optional[CompanyRiskProfile] = None,
    historical_prices: Optional[List[float]] = None,
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
    # Magnitudes are calibrated to the cited empirical findings:
    #   Maciejowski-Leonelli 2025 -- coal/MSCI-Energy each ~+8% prob swing on EUA
    #     direction -> ~±3% mean shift at full driver bias.
    #   Bastianin et al. 2024 -- structural shortage historically 10-15% premium
    #     -> structural shift up to ±10% at full tightening_score.
    #   Demand: industrial demand pressure -> up to ±5% (literature: BVAR demand
    #     elasticity in carbon-energy nexus ~0.3-0.5 on 6-month horizon).
    driver_shift = driver_bias.bias * 0.10           # ±0.30 bias -> ±3.0% mean shift
    structural_shift = 0.0
    if structural is not None:
        if structural.signal == "BUY":
            structural_shift = 0.04 + 0.06 * max(0.0, structural.tightening_score)
        elif structural.signal == "DEFER":
            structural_shift = -0.04 - 0.06 * max(0.0, -structural.tightening_score)
    if demand is not None:
        demand_shift_val = demand.demand_pressure * 0.05  # ±5% max
        logger.info("Demand shift: pressure=%.2f -> mean_shift += %.3f", demand.demand_pressure, demand_shift_val)
    else:
        demand_shift_val = 0.0
    mean_shift = driver_shift + structural_shift + demand_shift_val
    logger.info(
        "Forecast mean shift: driver=%+.3f + structural=%+.3f + demand=%+.3f -> %+.3f (applied as multiplier 1+shift)",
        driver_shift, structural_shift, demand_shift_val, mean_shift,
    )

    # ---- Trend guard: don't fight a creeping uptrend ----
    # If trailing 6-month return is positive enough, suppress any DEFER-
    # direction nudge. We clamp the mean_shift to be non-negative and also
    # neutralise per-component DEFER bias so derive_constraints() sees
    # neutral signals further down.
    trend_log_ret = _trailing_return(historical_prices, months=6)
    trend_guard_active = (
        trend_log_ret is not None and trend_log_ret > TREND_GUARD_LOG_RETURN
    )
    if trend_guard_active:
        if mean_shift < 0:
            logger.info(
                "Trend guard active (6mo log-ret=%+.3f > %.2f): clamping mean_shift "
                "from %+.3f to 0",
                trend_log_ret, TREND_GUARD_LOG_RETURN, mean_shift,
            )
            mean_shift = 0.0
        # Also override structural/driver DEFER signals to HOLD so the
        # downstream constraint builder doesn't cap spot in an uptrend.
        if structural is not None and structural.signal == "DEFER":
            logger.info("Trend guard: overriding structural DEFER -> HOLD")
            from .enhancement.structural_context import StructuralBackdrop as _SB
            structural = _SB(
                balance_mt=structural.balance_mt,
                cap_mt=structural.cap_mt,
                emissions_mt=structural.emissions_mt,
                msr_intake_mt=structural.msr_intake_mt,
                msr_release_mt=structural.msr_release_mt,
                annual_cap_decline_mt_per_year=structural.annual_cap_decline_mt_per_year,
                surplus_to_shortage_year=structural.surplus_to_shortage_year,
                signal="HOLD",
                tightening_score=max(0.0, structural.tightening_score),
                narrative=structural.narrative + " [Trend guard active: DEFER suppressed]",
            )
        if driver_bias.signal == "DEFER":
            logger.info("Trend guard: overriding driver DEFER -> NEUTRAL")
            driver_bias = DriverBias(
                bias=max(0.0, driver_bias.bias),
                signal="NEUTRAL",
                coal_rising=driver_bias.coal_rising,
                energy_rising=driver_bias.energy_rising,
                fuel_switch_bearish=False,
                reasoning=driver_bias.reasoning + " [Trend guard: DEFER suppressed]",
            )

    # Apply the mean shift to the forecast going into the optimizer
    shifted_mean = {h: v * (1.0 + mean_shift) for h, v in forecast_mean.items()}

    # Use the driver bias as a soft prior for the optimizer's initial guess.
    # This shortens search time and helps in flat-forecast cases where the
    # CVaR objective has multiple near-optimal solutions.
    front_load = float(np.clip(driver_bias.bias + 0.5 * structural_shift, -0.5, 0.5))

    # EPU spike: nudge mean upward (lock in before vol surge) per Dai et al.
    # Magnitude: 3% reflects the empirical EPU-on-EUA effect at 1-2sigma shock
    # in the Dai 2020 GARCH-MIDAS specification.
    if epu and epu.spike:
        logger.info("EPU spike: shifting forecast mean +3%% (z=%.2f)", epu.z_score)
        shifted_mean = {h: v * 1.03 for h, v in shifted_mean.items()}

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

    # Company risk layer override: peer-group emission predictability sets the
    # CVaR risk aversion for this company type, superseding the band-width default.
    if risk_profile is not None:
        risk_lambda = risk_profile.risk_adjusted_lambda
        logger.info("Company risk layer: using risk_lambda=%.2f (sector=%s size=%s)", risk_lambda, risk_profile.sector, risk_profile.size)

    # Derive layer-driven allocation constraints (paper-cited bounds).
    alloc_constraints = derive_constraints(regime, epu, driver_bias, structural, demand)
    # Composite-confidence override: when layers AGREE strongly, force a
    # high-conviction directional bet so the layer-specific edge can show
    # above the CVaR-spreading null.
    composite_score = compute_layer_composite(structural, driver_bias, epu, demand)
    alloc_constraints = apply_composite_override(
        composite_score, alloc_constraints, trend_guard_active,
    )
    if alloc_constraints.binding_reasons:
        logger.info(
            "Allocation constraints active: %s",
            " | ".join(alloc_constraints.binding_reasons),
        )

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
            constraints=alloc_constraints,
        )
        # Populate diagnostics for backtest trace / audit logging.
        plan.diagnostics = {
            "driver_shift": driver_shift,
            "structural_shift": structural_shift,
            "demand_shift": demand_shift_val,
            "total_mean_shift": mean_shift,
            "trend_log_return": trend_log_ret,
            "trend_guard_active": trend_guard_active,
            "composite_score": composite_score,
            "min_spot": alloc_constraints.min_spot_fraction,
            "max_spot": alloc_constraints.max_spot_fraction,
            "max_back": alloc_constraints.max_back_fraction,
            "max_single": alloc_constraints.max_single_fraction,
            "constraint_reasons": list(alloc_constraints.binding_reasons),
            "risk_lambda": risk_lambda,
        }
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
    risk_profile: Optional[CompanyRiskProfile] = None,
) -> EnhancedDecision:
    """
    Run the enhanced decision pipeline:
    1. Enhance Sybilion forecast bands
    2. Compute procurement plan
    3. Return full decision with all context visible
    """

    # ---- Enhancement Pipeline ----
    regime, epu, driver_bias, structural, demand = build_enhancement_pipeline(
        ets_forecast, current_ets_price,
        regime_monitor, historical_prices,
        fundamental_model, driver_monitor,
        evaluation_date=evaluation_date,
    )

    # ---- Procurement Decision ----
    procurement = make_procurement_decision(
        ets_forecast, current_ets_price, allowances_needed,
        regime, epu, driver_bias, structural,
        demand=demand, risk_profile=risk_profile,
        historical_prices=historical_prices,
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

    # Demand & company-risk alerts
    if demand is not None:
        alerts.append(f"[DEMAND] {demand.reasoning}")
        if demand.sector_divergence > 0.5:
            alerts.append(f"[DEMAND DIVERGENCE] Sectors pulling apart ({demand.sector_divergence:.2f}). Consider sector-specific strategies.")
    if risk_profile is not None:
        alerts.append(f"[RISK] {risk_profile.reasoning}")

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
        demand=demand,
        risk_profile=risk_profile,
    )
