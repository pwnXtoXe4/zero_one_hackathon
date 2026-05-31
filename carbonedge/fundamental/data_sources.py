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
    """Parsed EU ETS data for the fundamental model.

    Only verified_emissions is consumed downstream (by the balance model).
    Allocations / auctions / surrenders / sector breakdowns are intentionally
    not loaded — add them back if the downstream model starts using them.
    """
    # verified_emissions[year] = total verified emissions in tonnes
    verified_emissions: Dict[int, float]


def load_ets_csv() -> EtsData:
    """
    Load and parse the full EU-ETS CSV from datahub.io.

    Uses main_activity_code="20-99" (All stationary installations)
    to avoid double-counting sub-sectors. Sums across real countries only.
    """
    path = DATA_DIR / "eu-ets.csv"
    if not path.exists():
        logger.warning("load_ets_csv: file %s not found, returning empty data", path)
        return EtsData({})
    logger.debug("load_ets_csv: reading %s", path)

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    verified: Dict[int, float] = {}
    skipped_rows: int = 0

    for row in rows:
        country = row.get("country_code", "").strip()
        activity_code = row.get("main_activity_code", "").strip()
        metric = row.get("citl_information", "").strip()
        year_str = row.get("year", "").strip()
        value_str = row.get("value", "0").strip()

        if country not in REAL_COUNTRIES:
            continue
        if not year_str.isdigit():
            continue
        if activity_code != "20-99":
            continue

        year = int(year_str)
        if value_str == "":
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

        # The dataset also publishes a "2.1b ... (expected, gap-filled for
        # latest year)" metric whose value is added on top of the reported
        # metric for the most recent year and would double-count the totals.
        # Match the reported "2.1 EU-ETS Verified Emission" only.
        if metric.startswith("2.1 EU-ETS Verified Emission"):
            verified[year] = verified.get(year, 0) + value

    if skipped_rows > 0:
        warnings.warn(
            f"load_ets_csv: {skipped_rows} rows had non-numeric values "
            "and were skipped. Check CSV for format changes."
        )
    logger.info("load_ets_csv: parsed %d verified-emission years", len(verified))

    return EtsData(verified_emissions=dict(sorted(verified.items())))


def get_annual_emissions(ets_data: EtsData) -> Dict[int, float]:
    """
    Returns verified emissions in megatons (Mt CO2) per year.

    The CSV value is in tonnes. Convert to Mt.
    """
    return {
        year: round(tons / 1_000_000, 3)
        for year, tons in ets_data.verified_emissions.items()
    }
