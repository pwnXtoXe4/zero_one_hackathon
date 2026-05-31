"""
Company-Specific Risk Profile (MICRO layer)

For a given company archetype (sector + size), this layer characterises the
emission behaviour of its peer group across ~30,864 Climate TRACE companies
and translates that into a CVaR risk-aversion lambda.

  - Stable, predictable emitters  -> low lambda  (trust the forecast, hedge less)
  - Volatile, erratic emitters     -> high lambda (hedge with spot certainty)

Flat-emission companies (max == min) carry zero volatility information and
would bias the peer averages, so they are skipped from the CV/trend math
(but still counted as peers).

The 62 MB source JSON is parsed ONCE on first use; only a handful of
per-bucket profiles survive.
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from ..config import DATA_DIR

logger = logging.getLogger(__name__)

_DATA_FILE = DATA_DIR / "prepared" / "all_companies_co2_timeseries.json"

_BASE_LAMBDA = 0.30
_LAMBDA_FLOOR = 0.15
_LAMBDA_CEIL = 0.50
_SEASONAL_LAG = 12

# Module-level cache: 62 MB parse -> a few KB of bucket profiles.
_PROFILES: Optional[Dict[str, "CompanyRiskProfile"]] = None


@dataclass
class CompanyRiskProfile:
    sector: str
    size: str
    emission_volatility_cv: float
    emission_trend_yoy_pct: float
    seasonality_score: float
    predictability_score: float
    risk_adjusted_lambda: float
    peer_count: int
    reasoning: str


@dataclass
class CompanyRiskLayer:
    _profiles: Dict[str, CompanyRiskProfile] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self._profiles:
            self._profiles = _get_profiles()

    def get_profile(self, sector: str, size: str) -> Optional[CompanyRiskProfile]:
        return self._profiles.get(f"{sector}_{size}")


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


def _autocorr(series: np.ndarray, lag: int) -> float:
    """Autocorrelation at a given lag, clipped to [0, 1] as a seasonality proxy."""
    if series.size <= lag:
        return 0.0
    centered = series - series.mean()
    denom = float(np.sum(centered * centered))
    if denom == 0:
        return 0.0
    num = float(np.sum(centered[lag:] * centered[:-lag]))
    return float(np.clip(num / denom, 0.0, 1.0))


def _risk_lambda(predictability: float) -> float:
    """High predictability -> low lambda; low predictability -> high lambda."""
    return float(np.clip(_LAMBDA_CEIL - 0.35 * predictability, _LAMBDA_FLOOR, _LAMBDA_CEIL))


def _build_profiles(data_path: Path) -> Dict[str, CompanyRiskProfile]:
    if not data_path.exists():
        raise FileNotFoundError(f"Company risk source not found: {data_path}")

    logger.info("Company risk: parsing %s (one-time)", data_path.name)
    with data_path.open(encoding="utf-8") as f:
        payload = json.load(f)
    companies = payload.get("companies", {})

    buckets: Dict[str, Dict[str, List[float]]] = {}
    counts: Dict[str, int] = {}
    skipped: Dict[str, int] = {}

    for company in companies.values():
        sector = company.get("sector", "other")
        size = company.get("size", "small")
        key = f"{sector}_{size}"

        ts = company.get("timeseries", {})
        if not ts:
            continue
        values = np.array(
            [ts[d] for d in sorted(ts.keys())], dtype=float
        )

        counts[key] = counts.get(key, 0) + 1
        agg = buckets.setdefault(key, {"cv": [], "trend": [], "seasonality": []})

        # Flat timeseries: zero volatility, would distort averages -> skip.
        if values.size == 0 or float(values.max()) == float(values.min()):
            skipped[key] = skipped.get(key, 0) + 1
            continue

        mean = float(values.mean())
        if mean != 0:
            agg["cv"].append(float(values.std()) / abs(mean))
        agg["trend"].append(_yoy_pct(values))
        agg["seasonality"].append(_autocorr(values, _SEASONAL_LAG))

    # Release the 62 MB raw dict before building the small profiles.
    del payload, companies

    profiles: Dict[str, CompanyRiskProfile] = {}
    for key, agg in buckets.items():
        sector, _, size = key.partition("_")
        avg_cv = float(np.mean(agg["cv"])) if agg["cv"] else 0.0
        avg_trend = float(np.mean(agg["trend"])) if agg["trend"] else 0.0
        avg_seasonality = float(np.mean(agg["seasonality"])) if agg["seasonality"] else 0.0
        predictability = 1.0 / (1.0 + avg_cv)
        lam = _risk_lambda(predictability)
        peer_count = counts.get(key, 0)
        n_skipped = skipped.get(key, 0)

        reasoning = (
            f"{peer_count} peers in {sector}/{size} ({n_skipped} flat-emission skipped). "
            f"CV={avg_cv:.2f}, predictability={predictability:.2f} -> lambda={lam:.2f}. "
            f"Trend {avg_trend:+.1f}% YoY, seasonality {avg_seasonality:.2f}."
        )

        profiles[key] = CompanyRiskProfile(
            sector=sector,
            size=size,
            emission_volatility_cv=round(avg_cv, 4),
            emission_trend_yoy_pct=round(avg_trend, 2),
            seasonality_score=round(avg_seasonality, 3),
            predictability_score=round(predictability, 3),
            risk_adjusted_lambda=round(lam, 3),
            peer_count=peer_count,
            reasoning=reasoning,
        )

    logger.info("Company risk: built %d sector/size profiles", len(profiles))
    return profiles


def _get_profiles(data_path: Optional[Path] = None) -> Dict[str, CompanyRiskProfile]:
    global _PROFILES
    if _PROFILES is None:
        _PROFILES = _build_profiles(data_path or _DATA_FILE)
    return _PROFILES
