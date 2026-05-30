"""
CarbonEdge -- Formatted Decision Output v2

Shows the enhanced decision pipeline: regime, EPU, drivers, structural
context, and the final procurement plan with EUR savings.
"""

from typing import Dict, Optional, Tuple

from .config import COMPANY_PROFILE
from .decision_agent import EnhancedDecision
from .enhancement.driver_filter import DriverBias
from .enhancement.epu_modulator import EpuState
from .enhancement.regime_enhancer import RegimeBand
from .enhancement.structural_context import StructuralBackdrop
from .procurement.optimizer import ProcurementPlan
from .sybilion_client import ForecastResult

SEPARATOR = "=" * 64
SECTION_SEP = "-" * 62


def format_full_decision(
    decision: EnhancedDecision,
    ets_forecast: ForecastResult,
    original_ets_price: float,
) -> str:
    """Generate the full CarbonEdge strategy report v2."""
    profile = COMPANY_PROFILE
    parts = []

    # Header
    parts.append(SEPARATOR)
    parts.append("  CARBONEDGE -- PROCUREMENT DECISION AGENT")
    parts.append(f"  Company: {profile['name']}")
    parts.append(f"  EU ETS Price: EUR{original_ets_price:.0f}/ton")
    parts.append(f"  Allowances needed: {decision.procurement.total_tons:,}/year")
    parts.append(SEPARATOR)

    # Key Finding
    if decision.regime.level == "GREEN":
        parts.append(f"\n  REGIME: GREEN -- Sybilion forecast trustworthy.")
    elif decision.regime.level == "YELLOW":
        parts.append(f"\n  REGIME: YELLOW -- Caution advised, bands widened {decision.regime.multiplier:.1f}x.")
    else:
        parts.append(f"\n  REGIME: RED -- FREEZE. {decision.regime.advisory}")

    # Procurement Plan
    parts.append("")
    parts.append(f"  {SECTION_SEP}")
    parts.append("  PROCUREMENT PLAN")
    parts.append(f"  {SECTION_SEP}")
    parts.append(format_procurement(decision.procurement))

    # Enhancement stack
    parts.append("")
    parts.append(f"  {SECTION_SEP}")
    parts.append("  ENHANCEMENT STACK (visible reasoning)")
    parts.append(f"  {SECTION_SEP}")

    parts.append(format_regime_enhancement(decision.regime))
    parts.append(format_epu_enhancement(decision.epu))
    parts.append(format_driver_enhancement(decision.driver_bias))
    parts.append(format_structural_enhancement(decision.structural))
    parts.append(format_sybilion_drivers(ets_forecast))
    parts.append(format_band_comparison(ets_forecast, decision.procurement))

    # Alerts
    parts.append("")
    parts.append(f"  {SECTION_SEP}")
    parts.append("  MONITORING TRIGGERS")
    parts.append(f"  {SECTION_SEP}")
    for alert in decision.alert_triggers:
        parts.append(f"  [*] {alert}")

    parts.append("")
    parts.append(SEPARATOR)
    return "\n".join(parts)


def format_procurement(plan: ProcurementPlan) -> str:
    lines = [
        f"  Strategy: {plan.strategy}",
        f"  Total tons: {plan.total_tons:,}",
        f"",
        f"  Expected total cost:   EUR {plan.total_cost_expected:>12,.0f}",
        f"  Worst-case (CVaR 95%): EUR {plan.total_cost_worst_case:>12,.0f}",
        f"  Cost if bought all now: EUR {plan.cost_if_all_now:>12,.0f}",
    ]
    if plan.expected_savings > 0:
        lines.append(f"  Expected savings:       EUR {plan.expected_savings:>+12,.0f}")
    else:
        lines.append(f"  Cost premium vs spot:   EUR {-plan.expected_savings:>12,.0f} (buying now cheaper)")
    for w in plan.windows:
        lines.append(
            f"  {w.label:<8} {w.tons:>8,} {w.expected_price:>10.0f} "
            f"EUR{w.price_low:.0f}-{w.price_high:.0f} {w.cost_expected:>14,.0f}"
        )
    lines.append(f"  {'-' * 60}")
    lines.append(f"  Reason: {plan.reasoning}")
    return "\n".join(lines)


def format_regime_enhancement(regime: RegimeBand) -> str:
    lines = [
        f"\n  1. REGIME DETECTION (Friedrich 2019 + FOCuS/CUSUM)",
        f"     Level: {regime.level}",
        f"     Confidence multiplier: {regime.multiplier:.1f}x (applied to Sybilion bands)",
        f"     FOCuS: {'TRIGGERED' if regime.focus_triggered else 'stable'}",
        f"     CUSUM: {'TRIGGERED' if regime.cusum_triggered else 'stable'}",
        f"     Bubble risk: {'YES' if regime.bubble_risk else 'no'}",
        f"     {regime.advisory}",
    ]
    return "\n".join(lines)


def format_epu_enhancement(epu: Optional[EpuState]) -> str:
    import math
    if epu is None:
        return "\n  2. EPU VOLATILITY (Dai et al. 2020)\n     No EPU data available."

    if epu.level == "UNKNOWN":
        return "\n  2. EPU VOLATILITY (Dai et al. 2020)\n     EPU data unavailable for current date."

    if math.isnan(epu.epu_value):
        return "\n  2. EPU VOLATILITY (Dai et al. 2020)\n     EPU index: N/A (data unavailable)"

    lines = [
        f"\n  2. EPU VOLATILITY (Dai et al. 2020)",
        f"     EPU index: {epu.epu_value:.0f} ({epu.level})",
        f"     12-month mean: {epu.epu_12m_mean:.0f} (z={epu.z_score:+.1f})",
        f"     Volatility multiplier: {epu.volatility_multiplier:.1f}x",
    ]
    if epu.level == "CRISIS":
        lines.append("     Advisory: CRISIS -- Freeze advised.")
    elif epu.spike:
        lines.append("     Advisory: SPIKE -- Consider buying now.")
    else:
        lines.append("     Advisory: Normal volatility.")
    if epu.level == "CRISIS":
        lines.append("     [!!] EPU CRISIS: strongly consider freezing purchases.")
    return "\n".join(lines)


def format_driver_enhancement(bias: DriverBias) -> str:
    lines = [
        f"\n  3. DRIVER FILTER (Maciejowski & Leonelli 2025)",
        f"     Coal trending: {'UP' if bias.coal_rising else 'DOWN/FLAT'}",
        f"     MSCI Energy: {'UP' if bias.energy_rising else 'DOWN/FLAT'}",
        f"     Fuel-switch risk: {'BEARISH' if bias.fuel_switch_bearish else 'none'}",
        f"     Front/back-load bias: {bias.bias:+.1f} ({bias.signal})",
        f"     {bias.reasoning}",
    ]
    return "\n".join(lines)


def format_structural_enhancement(structural: Optional[StructuralBackdrop]) -> str:
    if structural is None:
        return "\n  4. STRUCTURAL CONTEXT (Bastianin et al. 2024)\n     Model not active."
    lines = [
        f"\n  4. STRUCTURAL CONTEXT (Bastianin et al. 2024)",
        f"     Cap: {structural.cap_mt:,.0f} Mt | Emissions: {structural.emissions_mt:,.0f} Mt",
        f"     MSR intake: {structural.msr_intake_mt:,.0f} Mt | Release: {structural.msr_release_mt:,.0f} Mt",
        f"     Balance: {structural.balance_mt:+,.0f} Mt | Inflection: {structural.surplus_to_shortage_year}",
        f"     Cap decline rate: {structural.annual_cap_decline_mt_per_year:.0f} Mt/year",
        f"     {structural.narrative}",
    ]
    return "\n".join(lines)


def format_sybilion_drivers(forecast: ForecastResult) -> str:
    """Surface Sybilion API driver importance scores."""
    if not forecast.driver_importance:
        return "\n  5. SYBILION DRIVER SIGNALS\n     No driver importance data available."

    lines = ["\n  5. SYBILION DRIVER SIGNALS (API driver importance)"]
    for name, scores in sorted(forecast.driver_importance.items(),
                                key=lambda x: x[1][-1] if x[1] else 0, reverse=True):
        score_str = "[" + " > ".join(f"{s:.2f}" for s in scores) + "]"
        lines.append(f"     {name}: {score_str}")
    return "\n".join(lines)


def format_band_comparison(forecast: ForecastResult, plan: ProcurementPlan) -> str:
    """Show original Sybilion bands vs plan-adjusted bands."""
    if not forecast.forecast_points:
        return ""

    lines = ["\n  6. BAND COMPARISON (original Sybilion -> plan execution)",
             f"     {'Window':<8} {'Syb Mean':>10} {'Syb Low':>10} {'Syb High':>10}"]
    for h, fp in sorted(forecast.forecast_points.items()):
        val = fp.get("value", 0)
        low = fp.get("low", val * 0.85)
        high = fp.get("high", val * 1.15)
        window_label = {1: "NOW", 3: "M3", 4: "M4", 6: "M6", 8: "M8", 9: "M9", 12: "M12"}.get(h, f"M{h}")
        lines.append(f"     {window_label:<8} {val:>10.0f} {low:>10.0f} {high:>10.0f}")
    return "\n".join(lines)


def format_adaptive_delta(
    scenario_name: str,
    old_forecast: Dict[int, Dict[str, float]],
    new_forecast: Dict[int, Dict[str, float]],
    old_mac_summary: str,
    new_mac_summary: str,
    changed_decisions: list,
    driver_shifts: Dict[str, Tuple[float, float]],
    additional_savings: float,
    old_procurement: Optional[ProcurementPlan] = None,
    new_procurement: Optional[ProcurementPlan] = None,
) -> str:
    """Format the before/after delta for an adaptive scenario shift."""
    parts = [
        f"\n{'=' * 64}",
        f"  ADAPTIVE RECALCULATION: {scenario_name}",
        f"{'=' * 64}",
    ]

    # Forecast changes
    parts.append("\n  --- FORECAST SHIFT ---")
    parts.append(f"  {'Window':<8} {'Old':>10} {'New':>10} {'Change %':>10}")
    for h in sorted(set(list(old_forecast.keys()) + list(new_forecast.keys()))):
        old_val = old_forecast.get(h, {}).get("value", 0)
        new_val = new_forecast.get(h, {}).get("value", 0)
        pct = (new_val / old_val - 1) * 100 if old_val > 0 else 0
        window_label = {1: "NOW", 3: "M3", 4: "M4", 6: "M6", 8: "M8", 9: "M9", 12: "M12"}.get(h, f"M{h}")
        parts.append(f"  {window_label:<8} {old_val:>10.1f} {new_val:>10.1f} {pct:>+10.1f}%")

    # MAC changes
    parts.append("\n  --- MAC CURVE SHIFT ---")
    parts.append(f"  OLD MAC: {old_mac_summary}")
    parts.append(f"  NEW MAC: {new_mac_summary}")

    # Decision changes
    if changed_decisions:
        parts.append("\n  --- DECISION CHANGES ---")
        for change in changed_decisions:
            parts.append(f"  [{change['option']}] {change['change']}")
            parts.append(f"    Reason: {change.get('reason', 'N/A')}")

    # Driver shifts
    if driver_shifts:
        parts.append("\n  --- DRIVER SHIFTS ---")
        for driver, (old_val, new_val) in driver_shifts.items():
            pct = (new_val / old_val - 1) * 100 if old_val > 0 else 0
            parts.append(f"  {driver}: {old_val:.2f} -> {new_val:.2f} ({pct:+.0f}%)")

    # Financial impact
    if additional_savings != 0:
        parts.append(f"\n  Additional savings: EUR {additional_savings:+,.0f}")

    # Procurement delta
    if old_procurement and new_procurement:
        parts.append("\n  --- PROCUREMENT SHIFT ---")
        parts.append(f"  Strategy: {old_procurement.strategy} -> {new_procurement.strategy}")
        parts.append(f"  Expected cost: EUR {old_procurement.total_cost_expected:,.0f} -> EUR {new_procurement.total_cost_expected:,.0f}")
        diff_tons = new_procurement.windows[0].tons - old_procurement.windows[0].tons if old_procurement.windows and new_procurement.windows else 0
        if diff_tons != 0:
            parts.append(f"  NOW tons: {old_procurement.windows[0].tons if old_procurement.windows else 0:,} -> {new_procurement.windows[0].tons if new_procurement.windows else 0:,} ({diff_tons:+} tons front-loaded)")

    return "\n".join(parts)
