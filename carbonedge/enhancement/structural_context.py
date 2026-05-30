"""
Structural Context

Bastianin et al. (2024) "What drives the European carbon market?" (arXiv:2402.04828).

Provides the structural backdrop for decision reasoning — NOT a timing signal.
The cap-emissions-MSR balance explains WHY the procurement optimizer front-loads
or back-loads, but does not override the optimizer.

  - Market balance: cap - emissions - MSR intake + MSR release
  - Tightening rate: annual cap decline (93 Mt/yr)
  - Price pressure (PP+/PP-): Bastianin et al. eq. 7-8
  - Surplus-to-shortage inflection point
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

from ..fundamental.balance_model import FundamentalModel

logger = logging.getLogger(__name__)


@dataclass
class StructuralBackdrop:
    """Structural context for the procurement decision."""
    balance_mt: float
    cap_mt: float
    emissions_mt: float
    msr_intake_mt: float
    msr_release_mt: float
    annual_cap_decline_mt_per_year: float
    surplus_to_shortage_year: int   # estimated year balance flips negative
    signal: str                     # BUY / DEFER / HOLD (structural only)
    tightening_score: float         # -1 (loosening) to +1 (tightening)
    narrative: str


@dataclass
class StructuralContext:
    """
    Wraps the FundamentalModel and produces structural backdrop text.
    Does NOT produce a competing forecast — only explanatory context.
    """
    model: FundamentalModel

    def evaluate(self, year: Optional[int] = None, month: int = 1) -> StructuralBackdrop:
        """Evaluate structural backdrop at a given point in time."""
        if year is None:
            year = self.model.current_year

        signal = self.model.evaluate(year, month)
        cap_decline = self.model.cap_schedule.annual_reduction_mt()
        caps = self.model.cap_schedule.years

        # Find surplus-to-shortage inflection: year where cap falls below last known emissions
        last_ems = signal.verified_emissions_mt
        inflection_year = year
        for y in sorted(caps):
            if caps[y] < last_ems:
                inflection_year = y
                break

        # Tightening score: how close are we to shortage, scaled -1 to +1
        max_surplus = max(caps.values()) - last_ems
        min_surplus = min(caps.values()) - last_ems if last_ems > 0 else -500
        range_surplus = max(max_surplus - min_surplus, 1.0)
        tightening_score = 1.0 - 2.0 * (signal.market_balance_mt - min_surplus) / range_surplus
        tightening_score = max(-1.0, min(1.0, tightening_score))

        # Build narrative
        balance_sign = "surplus" if signal.market_balance_mt > 0 else "shortage"
        narrative_parts = [
            f"EU ETS cap {year}: {signal.cap_mt:,.0f} Mt. "
            f"Latest verified emissions ({signal.verified_emissions_mt:,.0f} Mt "
            f"from {self.model.latest_verified_year}). "
            f"Market balance: {signal.market_balance_mt:+,.0f} Mt ({balance_sign}).",
            f"Cap declining at {cap_decline:.0f} Mt/year. "
            f"Structural inflection (cap < last known emissions) expected by {inflection_year}.",
        ]
        if signal.msr_intake_mt > 0:
            narrative_parts.append(
                f"MSR absorbing {signal.msr_intake_mt:.0f} Mt ("
                f"TNAC={signal.tnac_million:,.0f}M, holdings={signal.msr_holdings_million:,.0f}M). "
                f"Effective tightening: {signal.msr_intake_mt:.0f} Mt removed from market."
            )
        if signal.market_balance_mt < -50:
            narrative_parts.append(
                "Structural SHORTAGE: cap + MSR absorption below emissions. "
                "Expect upward price pressure over 6-12 month horizon."
            )
        elif signal.market_balance_mt > 50:
            narrative_parts.append(
                "Structural SURPLUS: cap still above emissions despite MSR. "
                "Price direction will be driven by expectations and energy markets."
            )

        return StructuralBackdrop(
            balance_mt=signal.market_balance_mt,
            cap_mt=signal.cap_mt,
            emissions_mt=signal.verified_emissions_mt,
            msr_intake_mt=signal.msr_intake_mt,
            msr_release_mt=signal.msr_release_mt,
            annual_cap_decline_mt_per_year=cap_decline,
            surplus_to_shortage_year=inflection_year,
            signal=signal.signal,
            tightening_score=tightening_score,
            narrative=" ".join(narrative_parts),
        )
