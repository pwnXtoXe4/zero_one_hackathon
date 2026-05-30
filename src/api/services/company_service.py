"""Company data loading and pure-arithmetic position calculations.

No decision logic lives here — only file IO and position math.
"""

import json
from typing import Optional

from src.api.services import MOCK_DIR

_COMPANIES_FILE = MOCK_DIR / "companies.json"


def load_companies() -> list[dict]:
    """Load all companies from data/mock/companies.json."""
    if not _COMPANIES_FILE.exists():
        raise FileNotFoundError(f"Mock companies file not found: {_COMPANIES_FILE}")
    with _COMPANIES_FILE.open(encoding="utf-8") as f:
        return json.load(f)


def get_company(company_id: str) -> Optional[dict]:
    """Return a single company by id, or None if not found."""
    for company in load_companies():
        if company.get("id") == company_id:
            return company
    return None


def compute_position(company: dict) -> dict:
    """Pure arithmetic position summary (LONG/SHORT). Not decision logic."""
    available = company["free_allocation"] + company["current_allowances"]
    required = company["forecast_emissions"]
    net_position = available - required
    return {
        "company_id": company["id"],
        "company": company["name"],
        "required_allowances": required,
        "available_allowances": available,
        "net_position": net_position,
        "status": "LONG" if net_position >= 0 else "SHORT",
    }
