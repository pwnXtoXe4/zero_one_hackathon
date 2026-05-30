"""
Ladder Rules — Heuristic Fallback

When the full CVaR optimizer is too heavy or input data is insufficient,
this provides rule-based laddering.

Based on Abate et al. (2021) and the decision logic documented in GAME_PLAN.md.
"""

import logging
from dataclasses import dataclass
from typing import Dict, List

logger = logging.getLogger(__name__)

# Allocation fractions (see GAME_PLAN.md §"Laddering Heuristic")
RED_MINIMAL = 0.25          # RED regime: minimal buy, freeze rest
WIDE_BAND_NOW = 0.40        # Wide bands (>30% CV): ladder evenly
WIDE_BAND_MID = 0.30
NARROW_UP_NOW = 0.70        # Narrow bands + UP trend: front-load
NARROW_UP_MID = 0.20
NARROW_DOWN_NOW = 0.20      # Narrow bands + DOWN trend: back-load
NARROW_DOWN_MID = 0.30
DEFAULT_NOW = 0.40          # Default moderate ladder
DEFAULT_MID = 0.30


@dataclass
class LadderInput:
    """Simplified input for heuristic laddering."""
    trend: str
    band_width_ratio: float
    regime_level: str
    total_tons: int
    current_price: float


def ladder_fallback(inp: LadderInput) -> Dict[str, int]:
    """
    Heuristic ladder allocation.

    When bands WIDE (CV > 0.3): ladder evenly
    When bands NARROW (CV < 0.15): follow trend aggressively
    When REGIME RED: minimal buy, freeze rest
    """
    cv = inp.band_width_ratio
    logger.debug(
        "ladder_fallback: trend=%s, band_cv=%.3f, regime=%s, tons=%d, spot=%.2f",
        inp.trend, cv, inp.regime_level, inp.total_tons, inp.current_price,
    )

    if inp.regime_level == "RED":
        now = int(inp.total_tons * RED_MINIMAL)
        return {
            "NOW": now,
            "M6": 0,
            "M12": 0,
            "FREEZE": inp.total_tons - now,
        }

    if cv > 0.3:
        now = int(inp.total_tons * WIDE_BAND_NOW)
        mid = int(inp.total_tons * WIDE_BAND_MID)
        return {
            "NOW": now,
            "M4": mid,
            "M8": inp.total_tons - now - mid,
        }

    if cv < 0.15:
        if inp.trend == "UP":
            now = int(inp.total_tons * NARROW_UP_NOW)
            mid = int(inp.total_tons * NARROW_UP_MID)
            return {"NOW": now, "M4": mid, "M8": inp.total_tons - now - mid}
        elif inp.trend == "DOWN":
            now = int(inp.total_tons * NARROW_DOWN_NOW)
            mid = int(inp.total_tons * NARROW_DOWN_MID)
            return {"NOW": now, "M4": mid, "M8": inp.total_tons - now - mid}

    now = int(inp.total_tons * DEFAULT_NOW)
    mid = int(inp.total_tons * DEFAULT_MID)
    return {"NOW": now, "M4": mid, "M8": inp.total_tons - now - mid}
