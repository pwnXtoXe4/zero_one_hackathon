"""
Regime Enhancer

Wraps existing FOCuS + CUSUM detectors and adds Friedrich et al. (2019)
bubble detection logic via the PSY (Phillips-Shi-Yu) recursive right-tailed
ADF test.

  Friedrich et al. (2019) "Understanding the explosive trend in EU ETS
  prices -- fundamentals or speculation?" (arXiv:1906.10572) found:
  - 2018 price run-up was speculation, not fundamentals
  - PSY bubble test detects explosive price behaviour
  - Time-varying coefficient regression: structural instability
  - Crash odds prediction from log-periodic power law (LPPL)

The enhancer outputs a confidence_multiplier for Sybilion's bands:
  GREEN  -> multiplier = 1.0  (trust Sybilion)
  YELLOW -> multiplier = 1.5  (widen bands 50%)
  RED    -> multiplier = 3.0  (bands 3x wide, freeze advisory)
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional

from ..regime_detector import RegimeStatus
from .psy_bubble import psy_test, BubbleResult

logger = logging.getLogger(__name__)

CONFIDENCE_GREEN = 1.0
CONFIDENCE_YELLOW = 1.5
CONFIDENCE_RED = 3.0


@dataclass
class RegimeBand:
    """Regime-adjusted confidence state."""
    level: str          # GREEN / YELLOW / RED
    multiplier: float   # applied to Sybilion sigma
    focus_triggered: bool
    cusum_triggered: bool
    bubble_risk: bool   # Friedrich PSY explosive behaviour flag
    advisory: str
    psy_result: Optional[BubbleResult] = None


def get_confidence_multiplier(
    regime_status: Optional[RegimeStatus],
    historical_prices: Optional[List[float]] = None,
) -> RegimeBand:
    """
    Compute regime-adjusted confidence multiplier for Sybilion bands.

    Priority: PSY bubble test (RED) > FOCuS/CUSUM (YELLOW) > GREEN.
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

    # ---- PSY bubble test (Friedrich et al. 2019) ----
    psy_result: Optional[BubbleResult] = None
    bubble = False
    if historical_prices and len(historical_prices) >= 36:
        try:
            psy_result = psy_test(historical_prices)
            bubble = psy_result.bubble_detected
            bubble_risk = psy_result.bubble_risk
            logger.info(
                "PSY bubble test: detected=%s risk=%s bsadf=%.2f critical=%.2f",
                bubble, bubble_risk,
                psy_result.last_bsadf, psy_result.last_critical,
            )
        except Exception as e:
            logger.warning("PSY bubble test failed: %s", e)
            bubble_risk = False
    else:
        bubble_risk = False

    # ---- Level determination ----
    # PSY bubble detection takes precedence — it directly overrides to RED.
    if bubble and psy_result is not None:
        level = "RED"
        multiplier = CONFIDENCE_RED
        advisory = psy_result.advisory
    elif focus or cusum:
        level = "YELLOW"
        multiplier = CONFIDENCE_YELLOW
        parts = []
        if focus:
            parts.append(f"FOCuS triggered (stat={regime_status.focus_statistic:.1f}). ")
        if cusum:
            parts.append(f"CUSUM triggered ({regime_status.cusum_message[:60]}). ")
        if bubble_risk:
            parts.append(f"PSY bubble risk: BSADF={psy_result.last_bsadf:.2f} (recent). ")
        parts.append("Widen risk assessment. Monitor closely.")
        advisory = "".join(parts)
    else:
        level = "GREEN"
        multiplier = CONFIDENCE_GREEN
        if bubble_risk and psy_result is not None:
            advisory = (
                f"FOCuS/CUSUM clear, but PSY bubble risk elevated: "
                f"BSADF={psy_result.last_bsadf:.2f}. "
                f"Sybilion forecast trustworthy with caution."
            )
        else:
            advisory = "No structural breaks detected. Sybilion forecast trustworthy."

    return RegimeBand(
        level=level,
        multiplier=multiplier,
        focus_triggered=focus,
        cusum_triggered=cusum,
        bubble_risk=bubble,
        advisory=advisory,
        psy_result=psy_result,
    )
