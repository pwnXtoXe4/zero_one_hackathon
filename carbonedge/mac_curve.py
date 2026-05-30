"""
CarbonEdge -- Marginal Abatement Cost (MAC) Curve Engine

Builds a forward-looking MAC curve: ranks reduction options by cost-per-ton,
adjusted by forecasted energy prices and regulatory trajectories.
Standard MAC curves are static; CarbonEdge makes them dynamic using Sybilion forecasts.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

from .config import (
    DECISION_THRESHOLDS,
    EMISSION_SOURCES,
    MAC_CONFIG,
    ReductionOption,
)


@dataclass
class RankedOption:
    """A single entry in the MAC curve ranking."""
    option: ReductionOption
    source_id: str
    source_tons: int
    cost_per_ton: float              # original or forecast-adjusted
    max_reduction_tons: float        # maximum reducible tons
    adjusted_cost_per_ton: float = 0.0  # after applying energy price adjustments
    roi_pct: float = 0.0             # return on investment: savings / cost
    viability: bool = True
    timing: str = "NOW"              # NOW / MONTH_X / DEFER


@dataclass
class MACCurve:
    """The full MAC curve -- ranked list of reduction options."""
    options: List[RankedOption] = field(default_factory=list)
    total_potential_tons: float = 0.0
    weighted_avg_cost: float = 0.0

    def __len__(self) -> int:
        return len(self.options)


def _adjust_cost_for_energy_price(
    baseline_cost: float,
    energy_forecast_ratio: float,
    sensitivity: float = 0.3,
) -> float:
    """
    Adjust a reduction option's cost-per-ton based on energy price forecasts.

    A higher energy price makes efficiency investments MORE valuable
    (each saved kWh avoids a higher cost), so *effective* cost decreases.

    Parameters
    ----------
    baseline_cost : original EUR/ton
    energy_forecast_ratio : forecast energy price / current energy price
    sensitivity : how strongly energy prices affect the option cost
    """
    return baseline_cost * (1.0 - sensitivity * (energy_forecast_ratio - 1.0))


def build_mac_curve(
    ets_price_forecast: Optional[Dict[int, float]] = None,
    energy_price_forecast: Optional[float] = None,
    current_ets_price: float = 80.0,
) -> MACCurve:
    """
    Build a forward-looking MAC curve.

    Parameters
    ----------
    ets_price_forecast : {month_offset: price} -- e.g. {3: 90, 6: 110}
        Sybilion's forecast of EU ETS price at future horizons.
        Used to determine if an option becomes viable when carbon price rises.
    energy_price_forecast : float
        Ratio of forecast energy price to current (e.g. 1.1 = 10% higher).
        Used to adjust costs: higher energy -> efficiency saves more -> lower effective cost.
    current_ets_price : float
        Current price for viability check.

    Returns
    -------
    MACCurve ranked from cheapest-to-most-expensive cost-per-ton.
    """
    ranked: List[RankedOption] = []

    for source_id, source in EMISSION_SOURCES.items():
        for opt in source.reduction_options:
            adjusted = opt.cost_per_ton
            if energy_price_forecast is not None:
                adjusted = _adjust_cost_for_energy_price(
                    opt.cost_per_ton, energy_price_forecast
                )

            viability = _check_viability(adjusted, current_ets_price, ets_price_forecast)

            timing = _determine_timing(
                opt, adjusted, current_ets_price, ets_price_forecast
            )

            max_tons = opt.max_reduction_pct * source.tons_co2e_per_year
            roi = ((current_ets_price - adjusted) / adjusted) * 100 if viability else 0

            ranked.append(RankedOption(
                option=opt,
                source_id=source_id,
                source_tons=source.tons_co2e_per_year,
                cost_per_ton=opt.cost_per_ton,
                max_reduction_tons=max_tons,
                adjusted_cost_per_ton=adjusted,
                roi_pct=roi,
                viability=viability,
                timing=timing,
            ))

    # Sort by adjusted cost (cheapest first)
    ranked.sort(key=lambda r: r.adjusted_cost_per_ton)

    total_tons = sum(r.max_reduction_tons for r in ranked if r.viability)
    weighted_cost = (
        sum(r.adjusted_cost_per_ton * r.max_reduction_tons for r in ranked if r.viability)
        / total_tons
        if total_tons > 0
        else 0
    )

    logger.debug(
        "build_mac_curve: %d options ranked, %d viable, %.0f total tons, EUR%.2f avg cost (spot=EUR%.2f)",
        len(ranked),
        sum(1 for r in ranked if r.viability),
        total_tons,
        weighted_cost,
        current_ets_price,
    )
    return MACCurve(
        options=ranked,
        total_potential_tons=total_tons,
        weighted_avg_cost=weighted_cost,
    )


def _check_viability(
    cost_per_ton: float,
    current_ets_price: float,
    ets_price_forecast: Optional[Dict[int, float]] = None,
) -> bool:
    """Check if a reduction option is economically viable."""
    threshold = MAC_CONFIG["viability_threshold_ratio"]

    # Check against current price
    if cost_per_ton < current_ets_price * threshold:
        return True

    # Check against forecasted prices (does it become viable later?)
    if ets_price_forecast:
        for horizon, price in ets_price_forecast.items():
            if cost_per_ton < price * threshold:
                return True

    return False


def _determine_timing(
    opt: ReductionOption,
    adjusted_cost: float,
    current_ets_price: float,
    ets_price_forecast: Optional[Dict[int, float]] = None,
) -> str:
    """Determine when an option should be executed."""
    threshold = MAC_CONFIG["viability_threshold_ratio"]

    # Already viable at current prices -> NOW (subject to lead time)
    if adjusted_cost < current_ets_price * threshold:
        if opt.lead_time_months <= 1:
            return "NOW"
        return f"MONTH_{opt.lead_time_months}"

    # Check when it becomes viable based on forecast
    if ets_price_forecast:
        for horizon, price in sorted(ets_price_forecast.items()):
            if adjusted_cost < price * threshold:
                effective_month = max(horizon, opt.lead_time_months)
                return f"MONTH_{effective_month}"

    return "DEFER"


def recalculate_mac(
    mac_curve: MACCurve,
    new_ets_price: float,
    ets_forecast: Optional[Dict[int, float]] = None,
) -> MACCurve:
    """Rebuild MAC curve after a regulatory shift (e.g. new ETS price)."""
    return build_mac_curve(
        ets_price_forecast=ets_forecast,
        current_ets_price=new_ets_price,
    )


def mac_summary(mac_curve: MACCurve) -> str:
    """Format the MAC curve as a readable table."""
    lines = [
        f"{'Rank':<5} {'Option':<35} {'EUR/ton':<8} {'Max Tons':<10} "
        f"{'ROI%':<7} {'Timing':<12} {'Viable'}",
        "-" * 90,
    ]
    for i, ro in enumerate(mac_curve.options, 1):
        lines.append(
            f"{i:<5} {ro.option.name:<35} {ro.adjusted_cost_per_ton:<8.1f} "
            f"{ro.max_reduction_tons:<10.0f} {ro.roi_pct:<7.0f} "
            f"{ro.timing:<12} {'[v]' if ro.viability else '[x]'}"
        )
    lines.append("-" * 90)
    lines.append(
        f"Total potential: {mac_curve.total_potential_tons:,.0f} tons | "
        f"Weighted avg cost: EUR{mac_curve.weighted_avg_cost:.1f}/ton"
    )
    return "\n".join(lines)
