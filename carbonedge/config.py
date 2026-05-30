"""
CarbonEdge -- Company Configuration & Reduction Options

Defines the company profile, emission sources, reduction options,
and carbon market exposure for decision-making.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Base paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"

# ---------------------------------------------------------------------------
# Company profile (synthetic mid-sized European manufacturer)
# Mirroring a typical CDP-disclosing industrial company
# ---------------------------------------------------------------------------

COMPANY_PROFILE = {
    "name": "European Manufacturing Corp",
    "baseline_emissions_tons_co2e": 500_000,
    "reduction_target_pct": 15,
    "target_year": 2027,
    "annual_reduction_budget_eur": 2_000_000,
}

# ---------------------------------------------------------------------------
# Emission sources with reduction options
# Each option has: name, cost_per_ton (EUR), max_reduction_pct,
#   capex_fixed (optional upfront cost), lead_time_months (implementation delay)
# ---------------------------------------------------------------------------

@dataclass
class ReductionOption:
    name: str
    cost_per_ton: float          # EUR / ton CO2e
    max_reduction_pct: float     # % of source emissions reducible
    capex_fixed: float = 0.0     # fixed upfront investment
    lead_time_months: int = 0    # months before benefit starts
    category: str = "efficiency"


@dataclass
class EmissionSource:
    id: str
    tons_co2e_per_year: int
    reduction_options: List[ReductionOption] = field(default_factory=list)


# Pre-built emission sources matching the IDEA_CARBON_REDUCTION.md spec
EMISSION_SOURCES: Dict[str, EmissionSource] = {
    "SCOPE_1_COMBUSTION": EmissionSource(
        id="SCOPE_1_COMBUSTION",
        tons_co2e_per_year=180_000,
        reduction_options=[
            ReductionOption("Boiler efficiency upgrade", 25, 0.08),
            ReductionOption("Natural gas -> H2 blend", 65, 0.15, lead_time_months=6),
            ReductionOption("Process electrification", 45, 0.12, lead_time_months=4),
        ],
    ),
    "SCOPE_2_ELECTRICITY": EmissionSource(
        id="SCOPE_2_ELECTRICITY",
        tons_co2e_per_year=200_000,
        reduction_options=[
            ReductionOption("Solar PPA", 30, 0.25, lead_time_months=2),
            ReductionOption("Wind PPA", 28, 0.20, lead_time_months=2),
            ReductionOption("Energy efficiency program", 15, 0.10),
        ],
    ),
    "SCOPE_3_SUPPLIERS": EmissionSource(
        id="SCOPE_3_SUPPLIERS",
        tons_co2e_per_year=120_000,
        reduction_options=[
            ReductionOption("Supplier engagement program", 40, 0.05, lead_time_months=3),
            ReductionOption("Alternative low-carbon materials", 55, 0.08, lead_time_months=4),
        ],
    ),
}

# ---------------------------------------------------------------------------
# Carbon market exposure
# ---------------------------------------------------------------------------

CARBON_EXPOSURE = {
    "eu_ets_allowances_needed_annually": 80_000,
    "cbam_exposed_imports_tons_co2e": 30_000,
    "voluntary_offset_purchases_annually": 10_000,
}

# ---------------------------------------------------------------------------
# Sybilion forecast configuration
# Each forecast target mapped to its input file + keywords
# ---------------------------------------------------------------------------

FORECAST_TARGETS = {
    "eu_ets_price": {
        "input_file": "eu_ets_monthly_prices.json",
        "title": "EU ETS Carbon Allowance Monthly Price",
        "description": (
            "Monthly closing price of EU ETS carbon allowances (EUA) traded on ICE, "
            "in EUR per metric ton CO2. Reflects regulatory tightening, energy market "
            "dynamics, and industrial activity in the European Union."
        ),
        "keywords": [
            "EU ETS reform",
            "Fit for 55",
            "carbon border tax",
            "energy crisis",
            "industrial production",
        ],
    },
    "company_emissions": {
        "input_file": None,  # synthetic, built from profile
        "title": "Company Monthly CO2 Emissions Trajectory",
        "description": (
            "Synthetic monthly CO2e emissions for European Manufacturing Corp, "
            "spanning Scope 1 (combustion), Scope 2 (electricity), and Scope 3 "
            "(suppliers). Includes seasonal production patterns."
        ),
        "keywords": [
            "industrial production index",
            "energy efficiency investment",
            "renewable energy auction",
            "natural gas price forecast",
        ],
    },
    "grid_carbon_intensity": {
        "input_file": None,  # synthetic
        "title": "Grid Carbon Intensity Monthly Average",
        "description": (
            "Monthly average grid carbon intensity in gCO2/kWh for the "
            "EU interconnected system, reflecting renewable penetration and "
            "fossil fuel dispatch."
        ),
        "keywords": [
            "renewable capacity expansion",
            "solar deployment",
            "wind deployment",
            "natural gas price",
            "coal phase-out",
        ],
    },
}

# ---------------------------------------------------------------------------
# MAC curve configuration
# ---------------------------------------------------------------------------

MAC_CONFIG = {
    # Thresholds for re-evaluating reduction options under new carbon prices
    "viability_threshold_ratio": 0.8,  # cost/ETS_price < 0.8 -> viable
    "max_options_to_consider": 7,
}

# ---------------------------------------------------------------------------
# Budget allocator configuration
# ---------------------------------------------------------------------------

ALLOCATOR_CONFIG = {
    "reserve_pct": 0.10,         # 10% held in reserve for offsets
    "max_upfront_pct": 0.30,     # max 30% allocated to "immediate" bucket
    "emission_trigger_ratio": 0.85,  # deploy reserve if emissions > 85% of target
}

# ---------------------------------------------------------------------------
# Decision thresholds
# ---------------------------------------------------------------------------

DECISION_THRESHOLDS = {
    "buy_confidence_threshold": 0.8,   # confidence band width / mean < 0.8 -> narrow
    "ladder_boundary": 0.3,            # band width / mean > 0.3 -> ladder
    "price_trend_up_threshold": 1.02,  # forecast/current > 1.02 -> UP
    "price_trend_down_threshold": 0.98,# forecast/current < 0.98 -> DOWN
}

# ---------------------------------------------------------------------------
# Helper: load a JSON time series
# ---------------------------------------------------------------------------

def load_timeseries(file_name: str) -> Dict[str, float]:
    """Load a JSON time series file from the data directory."""
    path = DATA_DIR / file_name
    if not path.exists():
        raise FileNotFoundError(f"Time series file not found: {path}")
    with open(path) as f:
        return json.load(f)
