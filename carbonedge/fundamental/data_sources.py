"""
Data loading and processing for the fundamental model.

Sources:
  - eu-ets.csv (datahub.io): country × activity × metric × year
    Metrics: verified emissions, allocated allowances, auctioned allowances, surrendered
  - eu_ets_monthly_prices.json: monthly closing prices Apr 2015 - May 2026
  - EC publications: cap schedule (see cap_schedule.py), MSR rules (see msr_model.py)
"""

import csv
import json
import logging
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

_HERE = Path(__file__).resolve()
# Prefer the project-root data/ directory; fall back to carbonedge/data/ if present.
_PROJECT_DATA = _HERE.parents[2] / "data"
_CARBONEDGE_DATA = _HERE.parents[1] / "data"
DATA_DIR = _PROJECT_DATA if _PROJECT_DATA.exists() else _CARBONEDGE_DATA

# Real country codes in the EU-ETS dataset (excludes aggregate labels)
REAL_COUNTRIES = {
    "AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "ES", "FI",
    "FR", "GB", "GR", "HR", "HU", "IE", "IS", "IT", "LI", "LT",
    "LU", "LV", "MT", "NL", "NO", "PL", "PT", "RO", "SE", "SI",
    "SK", "XI",  # XI = Northern Ireland (post-Brexit, replaces GB for ETS)
}


@dataclass
class EtsData:
    """Parsed EU ETS data for the fundamental model."""
    # verified_emissions[year] = total verified emissions in tonnes
    verified_emissions: Dict[int, float]
    # allocated_allowances[year] = free allocation in tonnes
    allocated_allowances: Dict[int, float]
    # auctioned_allowances[year] = auctioned/sold in tonnes
    auctioned_allowances: Dict[int, float]
    # surrendered_units[year] = total surrendered in tonnes
    surrendered_units: Dict[int, float]
    # sector_emissions[sector][year] = tonnes (for breakout analysis)
    sector_emissions: Dict[str, Dict[int, float]]


def load_ets_csv() -> EtsData:
    """
    Load and parse the full EU-ETS CSV from datahub.io.

    Uses main_activity_code="20-99" (All stationary installations)
    to avoid double-counting sub-sectors. Sums across real countries only.
    """
    path = DATA_DIR / "eu-ets.csv"
    if not path.exists():
        logger.warning("load_ets_csv: file %s not found, returning empty data", path)
        return EtsData({}, {}, {}, {}, {})
    logger.debug("load_ets_csv: reading %s", path)

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # Pivot: (metric, year) → total tonnes
    verified: Dict[int, float] = {}
    allocated: Dict[int, float] = {}
    auctioned: Dict[int, float] = {}
    surrendered: Dict[int, float] = {}
    sector_data: Dict[str, Dict[int, float]] = {}
    skipped_rows: int = 0

    for row in rows:
        country = row.get("country_code", "").strip()
        activity_code = row.get("main_activity_code", "").strip()
        activity_name = row.get("main_activity_name", "").strip()
        metric = row.get("citl_information", "").strip()
        year_str = row.get("year", "").strip()
        value_str = row.get("value", "0").strip()

        # Skip aggregate rows
        if country not in REAL_COUNTRIES:
            continue

        if not year_str.isdigit():
            continue

        year = int(year_str)
        if value_str == "":
            # Empty cells in the datahub.io dump represent "not reported"
            # (e.g. GB auctions post-Brexit). Skipping silently keeps the
            # totals correct without warning about every empty row.
            continue
        try:
            value = float(value_str)
        except ValueError:
            skipped_rows += 1
            continue

        # UK left EU ETS on 2021-01-01. Exclude GB rows post-2020.
        # Northern Ireland (XI) remains in EU ETS under the Protocol.
        if country == "GB" and year > 2020:
            continue

        # Reported verified emissions only. The dataset also publishes a
        # "2.1b ... (expected, gap-filled for latest year)" metric whose value
        # is added on top of the reported metric for the most recent year and
        # would double-count the totals. Exclude it.
        is_verified_reported = metric.startswith("2.1 EU-ETS Verified Emission")

        # Aggregate verified emissions across countries (use 20-99 to avoid double counting)
        if activity_code == "20-99":
            if is_verified_reported:
                verified[year] = verified.get(year, 0) + value
            if metric == "1.1 Freely allocated allowances":
                allocated[year] = allocated.get(year, 0) + value
            if "Allowances auctioned" in metric:
                auctioned[year] = auctioned.get(year, 0) + value
            if "Total surrendered" in metric:
                surrendered[year] = surrendered.get(year, 0) + value

        # Sector-level: use specific activity codes (not the 20-99 aggregate)
        if activity_code != "20-99":
            sector_key = activity_name if activity_name else activity_code
            if is_verified_reported:
                if sector_key not in sector_data:
                    sector_data[sector_key] = {}
                sector_data[sector_key][year] = sector_data[sector_key].get(year, 0) + value

    if skipped_rows > 0:
        warnings.warn(
            f"load_ets_csv: {skipped_rows} rows had non-numeric values "
            "and were skipped. Check CSV for format changes."
        )
    logger.info(
        "load_ets_csv: parsed %d verified-emission years (%d sectors), %d allocation years, %d auction years",
        len(verified), len(sector_data), len(allocated), len(auctioned),
    )

    return EtsData(
        verified_emissions=dict(sorted(verified.items())),
        allocated_allowances=dict(sorted(allocated.items())),
        auctioned_allowances=dict(sorted(auctioned.items())),
        surrendered_units=dict(sorted(surrendered.items())),
        sector_emissions={k: dict(sorted(v.items())) for k, v in sector_data.items()},
    )


def load_monthly_prices() -> Dict[str, float]:
    """Load the monthly ETS price JSON from the centralized data directory."""
    path = DATA_DIR / "eu_ets_monthly_prices.json"
    if path.exists():
        with open(path) as f:
            data = json.load(f)
        logger.debug("load_monthly_prices: %d points from %s", len(data), path)
        return data
    warnings.warn(
        f"load_monthly_prices: No price file found at {path}. "
        "PP+/PP- price pressure analysis will be unavailable."
    )
    logger.warning("load_monthly_prices: %s not found", path)
    return {}


def load_sector_emissions() -> List[Dict]:
    """Load sector emissions from the datahub.io CSV (if available)."""
    path = DATA_DIR / "eu-ets-sector-emissions.csv"
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def get_annual_emissions(ets_data: EtsData) -> Dict[int, float]:
    """
    Returns verified emissions in megatons (Mt CO2) per year.

    The CSV value is in tonnes. Convert to Mt.
    """
    return {
        year: round(tons / 1_000_000, 3)
        for year, tons in ets_data.verified_emissions.items()
    }


def get_annual_shortage(
    ets_data: EtsData,
    cap_schedule_mt: Dict[int, float],
) -> Dict[int, float]:
    """
    Compute annual market shortage (Mt):
      shortage = cap - verified_emissions (+ positive = surplus, - = deficit)

    Returns {year: shortage_mt}. Positive = surplus (bearish), negative = shortage (bullish).
    """
    emissions_mt = get_annual_emissions(ets_data)
    shortage: Dict[int, float] = {}
    for year in sorted(set(emissions_mt) & set(cap_schedule_mt)):
        shortage[year] = round(cap_schedule_mt[year] - emissions_mt[year], 3)
    return shortage
