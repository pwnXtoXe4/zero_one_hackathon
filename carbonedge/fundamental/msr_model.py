"""
Market Stability Reserve (MSR) Model.

Rules from Decision (EU) 2015/1814 as amended by Directive (EU) 2023/959:

  INTAKE: 24% of TNAC placed in MSR each year when TNAC > 833M
    (Reduced to 12% from 2024 when TNAC between 833M and 1096M, but
     the 24% threshold was confirmed Sep 2024: TNAC 2023 = 1,282M > 1,096M)

  RELEASE: 100M allowances released from MSR when TNAC < 400M

  INVALIDATION: From 2023, MSR holdings exceeding auction volume of
    previous year are permanently invalidated. Invalidated at 400M floor
    from 2024.

Ref: EC C/2025/3180 — TNAC communication (May 2025)
     https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:52025XC03180
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

MSR_INTAKE_RATE_HIGH = 0.24       # 24% when TNAC > 1,096M
MSR_INTAKE_RATE_LOW = 0.12        # 12% when 833M < TNAC <= 1,096M
MSR_INTAKE_UPPER_THRESHOLD = 1_096_000_000   # above this, 24% rate applies
MSR_INTAKE_LOWER_THRESHOLD = 833_000_000     # above this, 12% rate applies
MSR_RELEASE_THRESHOLD = 400_000_000          # below this, release 100M
MSR_RELEASE_AMOUNT = 100_000_000
MSR_INVALIDATION_FLOOR = 400_000_000

_M = 1_000_000  # Million


@dataclass
class MSRState:
    """State of the Market Stability Reserve at a point in time."""
    year: int
    msr_holdings: float  # allowances held in MSR
    tnac: float           # Total Number of Allowances in Circulation
    intake: float         # allowances absorbed this year
    release: float        # allowances released this year
    invalidated: float    # allowances permanently invalidated this year

    @property
    def net_effect(self) -> float:
        """Net MSR effect on market supply (negative = tightening)."""
        return self.release - self.intake - self.invalidated


@dataclass
class MSRModel:
    """
    Simulates MSR intake/release over a time horizon.
    Stateful — must call step() sequentially for correct TNAC accumulation.

    Example
    -------
    >>> model = MSRModel(tnac=1_148_049_585, msr_holdings=1_895_500_000)
    >>> state = model.step(2025, cap_2025, ems_2025)
    >>> state.intake / 1e6  # ~275 Mt expected
    """
    tnac: float
    msr_holdings: float
    initial_tnac: float = field(init=False)
    initial_msr_holdings: float = field(init=False)
    initial_year: int = 2024
    history: List[MSRState] = field(default_factory=list)

    def __post_init__(self):
        self.initial_tnac = self.tnac
        self.initial_msr_holdings = self.msr_holdings

    def reset(self):
        """Reset MSR state to initial values (for backtesting from a different year)."""
        self.tnac = self.initial_tnac
        self.msr_holdings = self.initial_msr_holdings
        self.history = []

    def step(self, year: int, cap: float, verified_emissions: float) -> MSRState:
        """
        Advance MSR by one year.

        Parameters
        ----------
        year : forecast year (must be called sequentially)
        cap : total cap for that year (in allowances)
        verified_emissions : verified emissions for that year (in allowances)
        """
        # Validate sequential calling
        if self.history:
            last_year = self.history[-1].year
            if year != last_year + 1:
                raise ValueError(
                    f"MSRModel.step() must be called sequentially. "
                    f"Last step: {last_year}, requested: {year}. "
                    "Use reset() to restart from initial year."
                )

        # Net surplus/deficit this year
        net_change = cap - verified_emissions

        # Tiered intake rate (Decision (EU) 2023/959):
        #   TNAC > 1,096M -> 24%
        #   833M < TNAC <= 1,096M -> 12%
        #   TNAC <= 833M -> 0%
        intake = 0.0
        if self.tnac > MSR_INTAKE_UPPER_THRESHOLD:
            intake = MSR_INTAKE_RATE_HIGH * self.tnac
        elif self.tnac > MSR_INTAKE_LOWER_THRESHOLD:
            intake = MSR_INTAKE_RATE_LOW * self.tnac

        # Compute release
        release = 0.0
        if self.tnac < MSR_RELEASE_THRESHOLD:
            release = min(MSR_RELEASE_AMOUNT, self.msr_holdings)

        # Apply intake and release
        self.msr_holdings += intake - release

        # Invalidation: holdings above the floor are invalidated
        invalidated = 0.0
        if self.msr_holdings > MSR_INVALIDATION_FLOOR:
            invalidated = self.msr_holdings - MSR_INVALIDATION_FLOOR
            self.msr_holdings = MSR_INVALIDATION_FLOOR

        # Update TNAC
        self.tnac = self.tnac + net_change - intake + release
        self.tnac = max(0.0, self.tnac)

        state = MSRState(
            year=year,
            msr_holdings=self.msr_holdings,
            tnac=self.tnac,
            intake=intake,
            release=release,
            invalidated=invalidated,
        )
        self.history.append(state)
        return state

    def project(
        self,
        start_year: int,
        end_year: int,
        cap_schedule: Dict[int, float],
        emissions_schedule: Dict[int, float],
    ) -> List[MSRState]:
        """Project MSR states over a multi-year horizon."""
        results = []
        for y in range(start_year, end_year + 1):
            cap = cap_schedule.get(y)
            ems = emissions_schedule.get(y)
            if cap is None:
                raise KeyError(f"Cap schedule missing year {y}")
            if ems is None:
                raise KeyError(f"Emissions schedule missing year {y}")
            state = self.step(y, cap * _M, ems * _M)
            results.append(state)
        return results

    def summary(self) -> Dict:
        """Return a human-readable summary of MSR status."""
        if not self.history:
            return {"error": "No simulation history"}

        last = self.history[-1]
        return {
            "current_year": last.year,
            "tnac_million": round(last.tnac / _M, 1),
            "msr_holdings_million": round(last.msr_holdings / _M, 1),
            "last_intake_million": round(last.intake / _M, 1),
            "last_release_million": round(last.release / _M, 1),
            "last_invalidated_million": round(last.invalidated / _M, 1),
            "in_intake_zone_24pct": last.tnac > MSR_INTAKE_UPPER_THRESHOLD,
            "in_intake_zone_12pct": MSR_INTAKE_LOWER_THRESHOLD < last.tnac <= MSR_INTAKE_UPPER_THRESHOLD,
            "in_release_zone": last.tnac < MSR_RELEASE_THRESHOLD,
        }
