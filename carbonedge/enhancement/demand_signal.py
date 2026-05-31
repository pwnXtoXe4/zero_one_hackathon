"""
Industrial Carbon Demand Index (MACRO layer)

Aggregates ~30,864 Climate TRACE manufacturing companies into a single
size-weighted composite index that proxies real-economy carbon demand.
Rising industrial output -> more emissions -> more allowance demand ->
upward structural bias on the forecast. Falling output -> the reverse.

This layer does NOT produce a competing forecast. It emits a small
``demand_pressure`` scalar that nudges the optimizer's mean shift.

The 62 MB source JSON is parsed ONCE on first use; only a few KB of
numpy aggregates survive (the raw dict is released afterwards).
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from ..config import DATA_DIR

logger = logging.getLogger(__name__)

_DATA_FILE = DATA_DIR / "prepared" / "all_companies_co2_timeseries.json"

_SIZE_WEIGHTS = {"large": 3.0, "medium": 2.0, "small": 1.0}
_YOY_FULL_PCT = 5.0          # +/-5% YoY maps to +/-1.0 demand pressure
_ACTIVE_TREND_PCT = 1.0      # |sector momentum| above this counts as a clear trend

# Module-level cache: 62 MB parse -> a few KB of aggregates.
_INDEX: Optional["_DemandIndex"] = None


@dataclass
class DemandState:
    date: str
    composite_index: float
    composite_yoy_change_pct: float
    sector_momentum: Dict[str, float]
    sector_divergence: float
    demand_pressure: float
    signal: str
    active_sectors: int
    reasoning: str


@dataclass
class _DemandIndex:
    """Pre-computed monthly aggregates (the only thing kept in memory)."""
    dates: List[str]
    composite_monthly: np.ndarray
    sector_monthly_totals: Dict[str, np.ndarray]


def _yoy_pct(series: np.ndarray) -> float:
    """Latest 3-month average vs the same 3 months one year earlier."""
    if series.size < 15:
        if series.size < 2 or series[0] == 0:
            return 0.0
        return float((series[-1] / series[0] - 1.0) * 100.0)
    recent = float(series[-3:].mean())
    prior = float(series[-15:-12].mean())
    if prior == 0:
        return 0.0
    return (recent / prior - 1.0) * 100.0


def _build_index(data_path: Path) -> _DemandIndex:
    if not data_path.exists():
        raise FileNotFoundError(f"Demand index source not found: {data_path}")

    logger.info("Demand index: parsing %s (one-time)", data_path.name)
    with data_path.open(encoding="utf-8") as f:
        payload = json.load(f)
    companies = payload.get("companies", {})

    all_dates: set[str] = set()
    sector_buckets: Dict[str, Dict[str, float]] = {}
    for company in companies.values():
        sector = company.get("sector", "other")
        weight = _SIZE_WEIGHTS.get(company.get("size", "small"), 1.0)
        bucket = sector_buckets.setdefault(sector, {})
        for date_key, value in company.get("timeseries", {}).items():
            bucket[date_key] = bucket.get(date_key, 0.0) + value * weight
            all_dates.add(date_key)

    # Release the 62 MB raw dict before building the small arrays.
    del payload, companies

    dates = sorted(all_dates)
    index_of = {d: i for i, d in enumerate(dates)}
    n = len(dates)

    sector_monthly_totals: Dict[str, np.ndarray] = {}
    for sector, bucket in sector_buckets.items():
        arr = np.zeros(n, dtype=float)
        for date_key, total in bucket.items():
            arr[index_of[date_key]] = total
        sector_monthly_totals[sector] = arr

    composite_monthly = np.sum(
        np.vstack(list(sector_monthly_totals.values())), axis=0
    ) if sector_monthly_totals else np.zeros(n, dtype=float)

    logger.info(
        "Demand index built: %d months, %d sectors, latest composite=%.0f",
        n, len(sector_monthly_totals),
        composite_monthly[-1] if n else 0.0,
    )
    return _DemandIndex(dates, composite_monthly, sector_monthly_totals)


def _get_index(data_path: Optional[Path] = None) -> _DemandIndex:
    global _INDEX
    if _INDEX is None:
        _INDEX = _build_index(data_path or _DATA_FILE)
    return _INDEX


class DemandSignal:
    """Builds (once) and evaluates the composite industrial demand index."""

    def __init__(self, data_path: Optional[Path] = None):
        self._index = _get_index(data_path)

    def evaluate(self) -> DemandState:
        idx = self._index
        composite_yoy = _yoy_pct(idx.composite_monthly)

        sector_momentum = {
            sector: round(_yoy_pct(arr), 2)
            for sector, arr in sorted(idx.sector_monthly_totals.items())
        }

        momentums = np.array(list(sector_momentum.values()), dtype=float)
        mean_abs = float(np.mean(np.abs(momentums))) if momentums.size else 0.0
        divergence = float(np.std(momentums) / mean_abs) if mean_abs > 0 else 0.0
        divergence = float(np.clip(divergence, 0.0, 1.0))

        demand_pressure = float(np.clip(composite_yoy / _YOY_FULL_PCT, -1.0, 1.0))
        if demand_pressure > 0.3:
            signal = "BULLISH"
        elif demand_pressure < -0.3:
            signal = "BEARISH"
        else:
            signal = "NEUTRAL"

        active_sectors = int(np.sum(np.abs(momentums) >= _ACTIVE_TREND_PCT))

        return DemandState(
            date=idx.dates[-1] if idx.dates else "",
            composite_index=float(idx.composite_monthly[-1]) if idx.dates else 0.0,
            composite_yoy_change_pct=round(composite_yoy, 2),
            sector_momentum=sector_momentum,
            sector_divergence=round(divergence, 3),
            demand_pressure=round(demand_pressure, 3),
            signal=signal,
            active_sectors=active_sectors,
            reasoning=self._reasoning(composite_yoy, sector_momentum, divergence),
        )

    @staticmethod
    def _reasoning(
        composite_yoy: float,
        sector_momentum: Dict[str, float],
        divergence: float,
    ) -> str:
        ordered = sorted(
            sector_momentum.items(), key=lambda kv: abs(kv[1]), reverse=True
        )
        movers = [
            f"{sector.capitalize()} {mom:+.1f}%"
            for sector, mom in ordered
            if abs(mom) >= _ACTIVE_TREND_PCT
        ]
        stable = [
            sector.capitalize() for sector, mom in ordered
            if abs(mom) < _ACTIVE_TREND_PCT
        ]
        if divergence < 0.3:
            div_label = "Low"
        elif divergence <= 0.5:
            div_label = "Moderate"
        else:
            div_label = "High"

        parts = [f"Composite {composite_yoy:+.1f}% YoY."]
        if movers:
            parts.append(", ".join(movers) + ".")
        parts.append(f"{div_label} divergence ({divergence:.2f}).")
        if stable:
            parts.append(f"{', '.join(stable)} stable.")
        return " ".join(parts)
