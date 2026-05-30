"""
EU ETS Cap Schedule 2024-2030.

Source: EU Directive 2023/959 (Fit for 55 reform), Umweltbundesamt (DEHSt).

Values are the EU-wide cap for stationary installations (excluding aviation
but including the EEA-EFTA states and Northern Ireland). These are rounded
from the official Commission Decisions and as published on:
https://www.dehst.de/EN/european-emissions-trading/emissions-trading-in-the-eu-/cap/cap_node.html

Two one-off cap reductions per Decision (EU) 2023/852:
  - 90 Mt in 2024 (rebasing)
  - 27 Mt in 2026 (MSR-related)
"""

from dataclasses import dataclass
from typing import Dict

CAP_SCHEDULE_MT: Dict[int, float] = {
    # Phase 3 (2013-2020): LRF 1.74% on 2,084 Mt baseline
    # Cap = 2,084 - (year-2013) * 36.27
    # Values in Mt CO2e for stationary installations
    2013: 2084.0,
    2014: 2048.0,
    2015: 2011.0,
    2016: 1975.0,
    2017: 1939.0,
    2018: 1902.0,
    2019: 1866.0,
    2020: 1830.0,
    # Phase 4 (2021-2030): LRF 2.2%->4.3%->4.4%
    # 2021-2023: LRF 2.2% on new base 1,572 Mt
    2021: 1572.0,
    2022: 1537.0,
    2023: 1504.0,
    # 2024-2030: LRF 4.3% (2024-27), 4.4% (2028-30), from Umweltbundesamt
    2024: 1386.0,
    2025: 1298.0,
    2026: 1183.0,
    2027: 1095.0,
    2028: 1005.0,
    2029: 915.0,
    2030: 825.0,
}


@dataclass
class CapSchedule:
    """Known ETS cap schedule through 2030 (Mt CO2e)."""
    years: Dict[int, float]

    def cap_mt(self, year: int) -> float:
        """Cap in megatons for a given year.
        Raises ValueError for years not in the schedule (post-2030 unknown)."""
        if year in self.years:
            return self.years[year]
        if year < min(self.years):
            raise ValueError(
                f"No cap data for year {year} (earliest: {min(self.years)}). "
                "Extend CAP_SCHEDULE_MT with historical cap values."
            )
        raise ValueError(
            f"No cap data for year {year} (latest: {max(self.years)}). "
            "Post-2030 cap not yet legislated."
        )

    def annual_reduction_mt(self) -> float:
        """Average annual cap reduction (Mt/year) over the schedule."""
        years = sorted(self.years)
        if len(years) < 2:
            return 0.0
        return (self.years[years[0]] - self.years[years[-1]]) / (years[-1] - years[0])


def build_cap_schedule() -> CapSchedule:
    """Build the EU ETS cap schedule 2024-2030 from confirmed values."""
    return CapSchedule(years=dict(CAP_SCHEDULE_MT))
