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

        # ---- Tightening score (raw) -------------------------------------
        # How close are we to shortage, scaled -1 to +1 (positive = tightening).
        max_surplus = max(caps.values()) - last_ems
        min_surplus = min(caps.values()) - last_ems if last_ems > 0 else -500
        range_surplus = max(max_surplus - min_surplus, 1.0)
        raw_score = 1.0 - 2.0 * (signal.market_balance_mt - min_surplus) / range_surplus
        raw_score = max(-1.0, min(1.0, raw_score))

        # ---- Adjustment 1: time-to-inflection dampening -----------------
        # A DEFER/BUY signal driven by fundamentals 10+ years out is too
        # weak to act on -- markets already discount distant tightening into
        # current price. Phase 3 (2013-2017) had inflection ~2026, and the
        # naive structural model recommended STRONG DEFER even though prices
        # were creeping up on forward expectations. We dampen the signal
        # linearly with years-to-inflection (full strength at/past inflection,
        # 30% strength when >=8 years out).
        years_to_inflection = inflection_year - year
        if years_to_inflection <= 0:
            temporal_weight = 1.0
        else:
            temporal_weight = max(0.3, 1.0 - years_to_inflection / 8.0)

        # ---- Adjustment 2: TNAC carryover dampening (BUY direction only) -
        # MSR intake threshold (EU Decision 2015/1814) is 833M allowances --
        # above that the market is officially "surplus". A nominal shortage
        # signal (cap < emissions this year) is misleading if TNAC carryover
        # is still above the MSR intake floor, because supply is being
        # absorbed but not destroyed. We only dampen the BUY side; surplus
        # signal stays as-is because excess TNAC reinforces it.
        TNAC_INTAKE_FLOOR_M = 833.0
        TNAC_RELEASE_FLOOR_M = 400.0
        tnac_weight = 1.0
        if raw_score > 0 and signal.tnac_million > 0:
            if signal.tnac_million > TNAC_INTAKE_FLOOR_M:
                # Overhung -- dampen BUY proportionally to how far above floor
                overhang = signal.tnac_million - TNAC_INTAKE_FLOOR_M
                tnac_weight = max(0.3, 1.0 - overhang / 2000.0)  # 2.8B -> 0.3
            elif signal.tnac_million < TNAC_RELEASE_FLOOR_M:
                # Below MSR release floor -- amplify BUY
                tnac_weight = 1.2

        tightening_score = raw_score * temporal_weight * tnac_weight
        tightening_score = max(-1.0, min(1.0, tightening_score))

        # Re-classify signal in light of dampened score so the agent sees a
        # consistent (signal, score) pair. The strict cutoff at 0.3 matches
        # derive_constraints() in decision_agent.py.
        if tightening_score > 0.3:
            structural_signal = "BUY"
        elif tightening_score < -0.3:
            structural_signal = "DEFER"
        else:
            structural_signal = "HOLD"
        logger.debug(
            "tightening_score: raw=%+.2f temporal_w=%.2f (yti=%d) tnac_w=%.2f -> %+.2f "
            "[signal: %s -> %s]",
            raw_score, temporal_weight, years_to_inflection,
            tnac_weight, tightening_score, signal.signal, structural_signal,
        )

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
            signal=structural_signal,
            tightening_score=tightening_score,
            narrative=" ".join(narrative_parts),
        )
