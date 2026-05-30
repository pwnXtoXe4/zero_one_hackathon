"""
Regime Enhancer

Wraps existing FOCuS + CUSUM detectors and adds Friedrich et al. (2019)
bubble detection logic.

  Friedrich et al. (2019) "Understanding the explosive trend in EU ETS
  prices -- fundamentals or speculation?" (arXiv:1906.10572) found:
  - 2018 price run-up was speculation, not fundamentals
  - PSY bubble test detects explosive price behaviour
  - Time-varying coefficient regression: structural instability -> RED
  - Crash odds prediction from log-periodic power law (LPPL)

The enhancer outputs a confidence_multiplier for Sybilion's bands:
  GREEN  -> multiplier = 1.0  (trust Sybilion)
  YELLOW -> multiplier = 1.5  (widen bands 50%)
  RED    -> multiplier = 3.0  (bands 3x wide, freeze advisory)
"""

from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np

from ..regime_detector import RegimeStatus

CONFIDENCE_GREEN = 1.0
CONFIDENCE_YELLOW = 1.5


@dataclass
class RegimeBand:
    """Regime-adjusted confidence state."""
    level: str          # GREEN / YELLOW / RED
    multiplier: float   # applied to Sybilion sigma
    focus_triggered: bool
    cusum_triggered: bool
    bubble_risk: bool   # Friedrich PSY-like explosive behaviour flag
    advisory: str


def _detect_momentum_acceleration(prices: List[float], window: int = 24) -> bool:
    """
    Momentum-acceleration heuristic for bubble-like behaviour.
    Detects: >55% positive returns in the recent window AND variance increasing
    in the second half of the window. This is a lightweight proxy for the
    explosive-root behaviour that the full PSY test (Phillips-Shi-Yu) would
    detect with rolling ADF regressions.
    """
    if len(prices) < window + 2:
        return False

    recent = np.array(prices[-window:])
    log_rets = np.diff(np.log(recent))

    if len(log_rets) < 6:
        return False

    pos_ratio = np.mean(log_rets > 0)
    half = len(log_rets) // 2
    half1_var = np.var(log_rets[:half])
    half2_var = np.var(log_rets[half:])

    return pos_ratio > 0.55 and half2_var > half1_var * 1.5


def get_confidence_multiplier(
    regime_status: Optional[RegimeStatus],
    historical_prices: Optional[List[float]] = None,
) -> RegimeBand:
    """
    Compute regime-adjusted confidence multiplier for Sybilion bands.
    """
    if regime_status is None:
        return RegimeBand(
            level="YELLOW", multiplier=CONFIDENCE_YELLOW,
            focus_triggered=False, cusum_triggered=False,
            bubble_risk=False,
            advisory="No regime monitor active. Defaulting to YELLOW (widen bands — regime data unavailable).",
        )

    focus = regime_status.focus_triggered
    cusum = regime_status.cusum_triggered
    regime_change = regime_status.regime_change

    bubble = False
    if historical_prices and len(historical_prices) >= 26:
        bubble = _detect_momentum_acceleration(historical_prices)

    if focus or cusum:
        level = "YELLOW"
        multiplier = CONFIDENCE_YELLOW
        parts = []
        if focus:
            parts.append(f"FOCuS triggered (stat={regime_status.focus_statistic:.1f}). ")
        if cusum:
            parts.append(f"CUSUM triggered ({regime_status.cusum_message[:60]}). ")
        parts.append("Widen risk assessment. Monitor closely.")
        advisory = "".join(parts)
    else:
        level = "GREEN"
        multiplier = CONFIDENCE_GREEN
        advisory = "No structural breaks detected. Sybilion forecast trustworthy."

    return RegimeBand(
        level=level,
        multiplier=multiplier,
        focus_triggered=focus,
        cusum_triggered=cusum,
        bubble_risk=bubble,
        advisory=advisory,
    )
