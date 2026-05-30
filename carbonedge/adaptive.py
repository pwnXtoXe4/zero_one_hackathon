"""
CarbonEdge -- Adaptive Recalculator

Handles mid-run assumption shifts:
  - Regulatory tightening (ETS reform, CBAM acceleration)
  - Market shocks (gas price spike, renewable price crash)
  - Policy announcements (new carbon tax, cap reduction)

Recomputes MAC curve, re-evaluates viability, and generates before/after delta.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .config import COMPANY_PROFILE, DECISION_THRESHOLDS, CARBON_EXPOSURE

logger = logging.getLogger(__name__)
from .mac_curve import MACCurve, build_mac_curve, mac_summary
from .sybilion_client import ForecastResult
from .procurement.optimizer import ProcurementPlan
from .decision_agent import EnhancedDecision, make_procurement_decision
from .enhancement.regime_enhancer import RegimeBand
from .enhancement.epu_modulator import EpuState
from .enhancement.driver_filter import DriverBias


@dataclass
class ScenarioShift:
    """A regulatory or market assumption change."""
    name: str
    description: str
    new_ets_price: Optional[float] = None       # immediate price impact
    ets_forecast_multiplier: float = 1.0        # scale all forecast points
    confidence_band_shrink: float = 1.0          # <1 = narrower (more certain)
    new_reduction_options: Optional[List[str]] = None  # newly viable options

    def apply_to_forecast(self, forecast: ForecastResult) -> ForecastResult:
        """Create an adjusted forecast reflecting the scenario shift."""
        adjusted = ForecastResult(target_name=forecast.target_name)
        adjusted.current_value = self.new_ets_price or forecast.current_value

        for m, d in forecast.forecast_points.items():
            new_value = d["value"] * self.ets_forecast_multiplier
            band_width = (d["high"] - d["low"]) * self.confidence_band_shrink
            adjusted.forecast_points[m] = {
                "value": round(new_value, 2),
                "low": round(new_value - band_width / 2, 2),
                "high": round(new_value + band_width / 2, 2),
            }

        adjusted.driver_importance = forecast.driver_importance
        adjusted.backtest_accuracy = forecast.backtest_accuracy
        return adjusted


# Pre-built scenarios for the demo
ACCELERATED_ETS_REFORM = ScenarioShift(
    name="Accelerated ETS Reform",
    description=(
        "EU has announced an accelerated ETS reform -- the emissions cap will be cut "
        "20% faster than planned, starting next quarter. Carbon analysts project "
        "allowance prices could spike to EUR120/ton within 6 months."
    ),
    new_ets_price=95.0,    # immediate market reaction
    ets_forecast_multiplier=1.35,  # ~35% higher across all horizons
    confidence_band_shrink=0.7,     # policy certainty narrows bands
)

CBAM_ACCELERATION = ScenarioShift(
    name="CBAM Acceleration",
    description=(
        "CBAM phase-in accelerated: full implementation moved forward by 2 years. "
        "All imported goods face carbon border tax at EU ETS-equivalent price "
        "starting next fiscal year."
    ),
    ets_forecast_multiplier=1.15,
    confidence_band_shrink=0.8,
)

ENERGY_PRICE_CRASH = ScenarioShift(
    name="Renewable Energy Price Crash",
    description=(
        "Massive renewable capacity deployment has driven solar PPA prices "
        "down 30% and wind PPA prices down 25%. Grid carbon intensity is "
        "forecast to drop faster than expected."
    ),
    ets_forecast_multiplier=0.95,  # lower carbon intensity -> slightly lower ETS demand
)


# ---------------------------------------------------------------------------
# Recalculation logic
# ---------------------------------------------------------------------------

@dataclass
class AdaptiveDelta:
    """Before/after comparison for a scenario shift."""
    scenario_name: str

    # ETS Forecast changes
    old_ets_forecast: Dict[int, Dict[str, float]]
    new_ets_forecast: Dict[int, Dict[str, float]]

    # MAC Curve changes
    old_mac_summary: str
    new_mac_summary: str

    # Decision changes
    changed_decisions: List[Dict[str, str]]

    # Driver importance shifts
    driver_shifts: Dict[str, Tuple[float, float]]  # {driver: (old, new)}

    # Financial impact
    additional_savings_eur: float = 0.0
    revised_reduction_tons: float = 0.0

    # Procurement delta
    old_procurement: Optional[ProcurementPlan] = None
    new_procurement: Optional[ProcurementPlan] = None


def recalculate_after_shift(
    scenario: ScenarioShift,
    original_forecast: ForecastResult,
    original_mac: MACCurve,
    current_budget: float,
) -> AdaptiveDelta:
    """
    Run a full recalculation after a scenario shift:
      1. Adjust the forecast
      2. Rebuild the MAC curve with new prices
      3. Re-run procurement optimizer
      4. Compare before/after
    """
    logger.info(
        "Recalculating after shift: %s (mult=%.2fx, band_shrink=%.2f, new_spot=%s)",
        scenario.name,
        scenario.ets_forecast_multiplier,
        scenario.confidence_band_shrink,
        scenario.new_ets_price,
    )
    # Adjust forecast
    new_forecast = scenario.apply_to_forecast(original_forecast)

    # Rebuild MAC curve
    new_ets_price = scenario.new_ets_price or original_forecast.current_value
    new_ets_fc_dict = {
        m: d["value"] for m, d in new_forecast.forecast_points.items()
    }
    new_mac = build_mac_curve(
        ets_price_forecast=new_ets_fc_dict,
        current_ets_price=new_ets_price,
    )

    # Find changed decisions on MAC curve
    changed = _find_changed_decisions(original_mac, new_mac, new_ets_price)

    # Re-run procurement with adjusted forecast (same neutral regime/epu/bias for comparison)
    neutral_regime = RegimeBand(
        level="GREEN", multiplier=1.0,
        focus_triggered=False, cusum_triggered=False,
        bubble_risk=False, advisory="Scenario recalculation baseline",
    )
    neutral_epu = EpuState(
        date="", epu_value=100.0, epu_12m_mean=100.0, epu_12m_std=30.0,
        z_score=0.0, volatility_multiplier=1.0, level="NORMAL", spike=False,
    )
    neutral_bias = DriverBias(
        bias=0.0, signal="NEUTRAL", coal_rising=False,
        energy_rising=False, fuel_switch_bearish=False,
        reasoning="Scenario recalculation baseline",
    )
    new_forecast.current_value = new_ets_price
    new_procurement = make_procurement_decision(
        new_forecast, new_ets_price,
        CARBON_EXPOSURE["eu_ets_allowances_needed_annually"],
        neutral_regime, neutral_epu, neutral_bias,
    )

    # Driver shifts
    driver_shifts: Dict[str, Tuple[float, float]] = {}
    for driver, scores in original_forecast.driver_importance.items():
        if driver in new_forecast.driver_importance:
            old_val = scores[-1] if scores else 0
            new_val = new_forecast.driver_importance[driver][-1] if new_forecast.driver_importance.get(driver) else 0
            if abs(new_val - old_val) > 0.01:
                driver_shifts[driver] = (old_val, new_val)

    # Estimate additional savings
    old_total = original_mac.total_potential_tons
    new_total = new_mac.total_potential_tons
    additional_savings = (new_total - old_total) * new_ets_price

    return AdaptiveDelta(
        scenario_name=scenario.name,
        old_ets_forecast=original_forecast.forecast_points,
        new_ets_forecast=new_forecast.forecast_points,
        old_mac_summary=mac_summary(original_mac),
        new_mac_summary=mac_summary(new_mac),
        changed_decisions=changed,
        driver_shifts=driver_shifts,
        additional_savings_eur=additional_savings,
        revised_reduction_tons=new_total,
        old_procurement=None,
        new_procurement=new_procurement,
    )


def _find_changed_decisions(
    old_mac: MACCurve,
    new_mac: MACCurve,
    new_ets_price: float,
) -> List[Dict[str, str]]:
    """Identify which reduction options changed viability or timing."""
    changes = []

    # Map options by name for comparison
    old_map = {ro.option.name: ro for ro in old_mac.options}
    new_map = {ro.option.name: ro for ro in new_mac.options}

    for name in set(old_map) | set(new_map):
        old = old_map.get(name)
        new = new_map.get(name)

        if old and new:
            if old.viability != new.viability:
                changes.append({
                    "option": name,
                    "change": f"Became {'VIABLE' if new.viability else 'UNVIABLE'}",
                    "reason": (
                        f"New ETS price EUR{new_ets_price:.0f}/ton changes viability "
                        f"threshold (cost EUR{new.adjusted_cost_per_ton:.0f}/ton)"
                    ),
                })
            elif old.timing != new.timing:
                changes.append({
                    "option": name,
                    "change": f"Timing shifted: {old.timing} -> {new.timing}",
                    "reason": f"Forecast-adjusted feasibility changed",
                })

    return changes
