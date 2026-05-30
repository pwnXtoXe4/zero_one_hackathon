"""
CarbonEdge -- Confidence-Aware Budget Allocator

Splits a fixed reduction budget across time horizons and reduction options,
using forecast confidence bands to determine how much to allocate now vs. later.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .config import ALLOCATOR_CONFIG
from .mac_curve import MACCurve, RankedOption

logger = logging.getLogger(__name__)


@dataclass
class AllocationBucket:
    """Budget allocation at a specific time horizon."""
    horizon: str          # NOW / MONTH_3 / MONTH_6 / RESERVE
    budget_eur: float
    reductions: List[Tuple[str, float, float]] = field(default_factory=list)
    # [(option_name, tons_reduced, cost_eur), ...]

    @property
    def total_tons(self) -> float:
        return sum(r[1] for r in self.reductions)

    @property
    def blended_cost(self) -> float:
        total = sum(r[2] for r in self.reductions)
        tons = self.total_tons
        return total / tons if tons > 0 else 0


@dataclass
class AllocationPlan:
    """Full budget allocation plan."""
    budget: float
    buckets: List[AllocationBucket] = field(default_factory=list)
    total_tons_reduced: float = 0
    blended_cost_per_ton: float = 0
    reserve_budget: float = 0

    def summary(self) -> str:
        lines = [
            f"Budget Allocation Plan (EUR{self.budget:,.0f} total)",
            f"{'=' * 60}",
        ]
        for b in self.buckets:
            lines.append(
                f"\n  {b.horizon:<12} EUR{b.budget_eur:,.0f} "
                f"({b.budget_eur / self.budget * 100:.0f}%)"
            )
            for opt_name, tons, cost in b.reductions:
                lines.append(f"    * {opt_name:<35} {tons:<8.0f} tons  EUR{cost:,.0f}")
            if b.total_tons > 0:
                lines.append(
                    f"    Blended: {b.total_tons:,.0f} tons @ EUR{b.blended_cost:.0f}/ton"
                )
        lines.append(f"\n  TOTAL: {self.total_tons_reduced:,.0f} tons CO2e reduced")
        lines.append(f"  Blended cost: EUR{self.blended_cost_per_ton:.1f}/ton")
        lines.append(f"  Reserve held: EUR{self.reserve_budget:,.0f}")
        return "\n".join(lines)


def allocate_budget(
    mac_curve: MACCurve,
    budget: float,
    uncertainty_factors: Optional[Dict[str, float]] = None,
    ets_price: float = 80.0,
) -> AllocationPlan:
    """
    Allocate budget across reduction options and time horizons.

    Strategy:
      1. Reserve 10% for year-end offsets.
      2. From remaining 90%, allocate to NOW first (up to 30% cap),
         then spread remainder based on option timing and cost-effectiveness.

    Parameters
    ----------
    mac_curve : ranked reduction options
    budget : total annual reduction budget in EUR
    uncertainty_factors : {option_name: uncertainty_pct} -- wider band = defer
    ets_price : current carbon price for ROI calculation
    """
    reserve_pct = ALLOCATOR_CONFIG["reserve_pct"]
    max_upfront_pct = ALLOCATOR_CONFIG["max_upfront_pct"]

    reserve = budget * reserve_pct
    allocatable = budget - reserve

    # Separate options by timing
    now_options: List[RankedOption] = []
    later_options: List[RankedOption] = []
    defer_options: List[RankedOption] = []

    for ro in mac_curve.options:
        if not ro.viability:
            defer_options.append(ro)
        elif ro.timing == "NOW":
            now_options.append(ro)
        else:
            later_options.append(ro)

    # Phase 1: Allocate to NOW (capped at 30% of total budget)
    now_budget = min(allocatable * max_upfront_pct, allocatable)
    now_bucket = _fill_bucket(now_options, now_budget)

    # Phase 2: Distribute remainder to later phases
    remaining = allocatable - now_bucket.budget_eur
    later_bucket = _fill_bucket(later_options, remaining)

    # Phase 3: Reserve
    reserve_bucket = AllocationBucket(horizon="RESERVE", budget_eur=reserve)
    reserve_bucket.reductions = [
        ("Offset purchase (if off-target)", 0, reserve),
    ]

    plan = AllocationPlan(
        budget=budget,
        buckets=[now_bucket, later_bucket, reserve_bucket],
        reserve_budget=reserve,
    )

    # Compute totals
    plan.total_tons_reduced = sum(b.total_tons for b in plan.buckets)
    total_cost = sum(
        sum(r[2] for r in b.reductions)
        for b in plan.buckets
        if b.horizon != "RESERVE"
    )
    plan.blended_cost_per_ton = (
        total_cost / plan.total_tons_reduced if plan.total_tons_reduced > 0 else 0
    )

    return plan


def _fill_bucket(
    options: List[RankedOption],
    available_budget: float,
) -> AllocationBucket:
    """
    Fill a budget bucket with the cheapest-available reduction options.

    Uses a greedy approach: sort by cost-per-ton, allocate until budget exhausted.
    For production use, this could be a knapsack solver, but greedy is optimal
    for independent options with additive costs and no selection constraints.
    """
    bucket = AllocationBucket(
        horizon=options[0].timing if options else "UNALLOCATED",
        budget_eur=0,
    )

    remaining = available_budget
    for ro in options:
        if remaining <= 0:
            break

        max_cost = ro.adjusted_cost_per_ton * ro.max_reduction_tons
        if max_cost <= remaining:
            allocate_cost = max_cost
            allocate_tons = ro.max_reduction_tons
        else:
            allocate_tons = remaining / ro.adjusted_cost_per_ton
            allocate_cost = remaining

        bucket.reductions.append((ro.option.name, allocate_tons, allocate_cost))
        bucket.budget_eur += allocate_cost
        remaining -= allocate_cost

    return bucket


def reallocate_after_shift(
    plan: AllocationPlan,
    new_ets_price: float,
    mac_curve: Optional[MACCurve] = None,
    delta_budget: float = 0,
) -> AllocationPlan:
    """
    Reallocate budget after a regulatory or market shift.

    A higher carbon price makes all reductions more valuable,
    so the plan should front-load more investments. Uses the
    updated MAC curve to recompute allocation.
    """
    new_budget = plan.budget + delta_budget

    if mac_curve is None:
        return plan

    reserve_pct = ALLOCATOR_CONFIG["reserve_pct"]
    max_upfront_pct = ALLOCATOR_CONFIG["max_upfront_pct"]

    reserve = new_budget * reserve_pct
    allocatable = new_budget - reserve

    now_options = [ro for ro in mac_curve.options if ro.viability and ro.timing == "NOW"]
    later_options = [ro for ro in mac_curve.options if ro.viability and ro.timing != "NOW"]

    now_budget = min(allocatable * max_upfront_pct, allocatable)
    now_bucket = _fill_bucket(now_options, now_budget)

    remaining = allocatable - now_budget
    later_bucket = _fill_bucket(later_options, remaining)

    reserve_bucket = AllocationBucket(horizon="RESERVE", budget_eur=reserve)
    reserve_bucket.reductions = [("Offset purchase (if off-target)", 0, reserve)]

    result = AllocationPlan(
        budget=new_budget,
        buckets=[now_bucket, later_bucket, reserve_bucket],
        reserve_budget=reserve,
    )
    result.total_tons_reduced = sum(b.total_tons for b in result.buckets)
    total_cost = sum(
        sum(r[2] for r in b.reductions)
        for b in result.buckets
        if b.horizon != "RESERVE"
    )
    result.blended_cost_per_ton = (
        total_cost / result.total_tons_reduced if result.total_tons_reduced > 0 else 0
    )
    return result
