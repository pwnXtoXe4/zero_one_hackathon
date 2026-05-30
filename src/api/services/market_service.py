"""Market data loading: EUA prices, futures, sell offers, auctions.

All paths are pathlib-based so the service works from the repo root.
"""

import csv
import json
from datetime import date, datetime
from typing import Optional

from src.api.services import MOCK_DIR, RAW_DIR

_EUA_PRICES_FILE = RAW_DIR / "eua_prices_monthly.json"
_FUTURES_FILE = RAW_DIR / "carbon_emission_futures_data.csv"
_SELL_OFFERS_FILE = MOCK_DIR / "sell_offers.json"
_AUCTIONS_FILE = MOCK_DIR / "auction_calendar.json"


def _load_json(path) -> object:
    if not path.exists():
        raise FileNotFoundError(f"Data file not found: {path}")
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def get_eua_prices() -> dict:
    """EUA price history as a chart-friendly, chronologically sorted array."""
    raw: dict = _load_json(_EUA_PRICES_FILE)
    data = [
        {"date": d, "price": raw[d]}
        for d in sorted(raw.keys())
    ]
    return {"data": data}


def get_futures(limit: int = 500) -> dict:
    """Carbon futures rows from CSV. limit=0 returns all rows."""
    if not _FUTURES_FILE.exists():
        raise FileNotFoundError(f"Futures CSV not found: {_FUTURES_FILE}")

    rows: list[dict] = []
    with _FUTURES_FILE.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(dict(row))

    selected = rows if limit == 0 else rows[:limit]
    return {
        "limit": limit,
        "returned": len(selected),
        "data": selected,
    }


def get_sell_offers() -> list[dict]:
    """All mock seller offers."""
    return _load_json(_SELL_OFFERS_FILE)


def get_auctions() -> list[dict]:
    """All mock auctions from the auction calendar."""
    return _load_json(_AUCTIONS_FILE)


def get_next_auction(today: Optional[date] = None) -> dict:
    """Nearest future auction relative to today.

    Falls back to the earliest mock auction (with a note) when no future
    auction exists in the mock data.
    """
    if today is None:
        today = datetime.now().date()

    auctions = get_auctions()
    if not auctions:
        raise ValueError("No auctions available in mock data.")

    def _parse(a: dict) -> date:
        return datetime.strptime(a["auction_date"], "%Y-%m-%d").date()

    future = sorted(
        (a for a in auctions if _parse(a) >= today),
        key=_parse,
    )
    if future:
        return future[0]

    earliest = min(auctions, key=_parse)
    return {
        **earliest,
        "note": "No future auction found in mock data; returning earliest available mock auction.",
    }
