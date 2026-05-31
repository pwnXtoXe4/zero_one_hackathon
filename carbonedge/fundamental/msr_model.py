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
