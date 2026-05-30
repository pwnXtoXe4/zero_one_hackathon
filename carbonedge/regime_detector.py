"""
Regime Detection Layer for CarbonEdge.

Two complementary online detectors that flag structural breaks
and forecast degradation -- enabling CarbonEdge to stop trusting
Sybilion forecasts when the world has changed underneath them.

  Layer 1: FOCuS (Functional Online CUSUM) on raw price data
    - O(log n) per tick, distribution-free (NPFocus variant)
    - Signals "structural break detected in ETS price series"

  Layer 2: CUSUM on Sybilion forecast residuals
    - O(1) per tick, Page's CUSUM applied to standardized errors
    - Signals "forecast has become systematically biased"

  Combined: when BOTH fire, issue a "regime change" alert
    that tells CarbonEdge to pause, recalculate, and flag for review.

References
----------
  FOCuS: Romano, Eckley, Fearnhead, Rigaill (2023), JMLR 24(81)
    arXiv 2302.04743 -- "A Constant-per-Iteration Likelihood Ratio Test
    for Online Changepoint Detection for Exponential Family Models"
  CUSUM: Grundy, Killick, Svetunkov (2025), arXiv 2502.14173
    "Changepoint Detection in the Wild: Monitoring Forecast Performance"
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Layer 1: FOCuS -- online changepoint detection on raw data
# ---------------------------------------------------------------------------


@dataclass
class FocusConfig:
    """Configuration for the FOCuS changepoint detector."""
    threshold: float = 5.0
    min_observations: int = 12
    cooldown_ticks: int = 6
    quantiles: List[float] = field(default_factory=lambda: [0.25, 0.5, 0.75])
    return_window: int = 3  # months for log-return; 3 amplifies regime-changes over noise


class FocusDetector:
    """Wraps the changepoint_online.NPFocus detector for ETS price returns.

    ETS prices are non-stationary (trend from ~EUR5 to EUR80+ over 11 years).
    FOCuS detects mean-shift changes, which requires stationary segments.
    We apply FOCuS to N-month log-returns (relative price changes), which
    are approximately stationary with zero mean between structural breaks.
    Using 3-month returns amplifies regime-change signals over monthly noise.
    """

    def __init__(self, config: FocusConfig = None):
        self.config = config or FocusConfig()
        self._ticks_since_change: int = 0
        self._np_focus = None
        self._init_detector()
        self._last_statistic: float = 0.0
        self._history: List[float] = []
        self._change_points: List[int] = []
        self._price_buffer: List[float] = []  # for N-month return calculation

    def _init_detector(self):
        """Re-initialize the NPFocus detector after a changepoint."""
        try:
            from changepoint_online import NPFocus
            self._np_focus = NPFocus(
                quantiles=self.config.quantiles,
                side="both",
            )
        except ImportError:
            if self._np_focus is None and not getattr(FocusDetector, "_warned_no_changepoint", False):
                logger.warning(
                    "FocusDetector: 'changepoint_online' not installed; FOCuS layer disabled. "
                    "Install with: pip install changepoint_online"
                )
                FocusDetector._warned_no_changepoint = True
            self._np_focus = None

    def _to_log_return(self, price: float) -> Optional[float]:
        """Convert price to N-month log-return using the price buffer."""
        w = self.config.return_window
        self._price_buffer.append(price)
        if len(self._price_buffer) < w + 1:
            return None
        # Keep only last w+1 prices
        if len(self._price_buffer) > w + 1:
            self._price_buffer = self._price_buffer[-(w + 1):]
        old_price = self._price_buffer[0]
        if old_price <= 0 or price <= 0:
            return None
        return float(np.log(price / old_price))

    def update(self, value: float) -> bool:
        """Feed one raw price observation. Returns True if a changepoint is detected."""
        self._history.append(value)
        self._ticks_since_change += 1
        self._last_statistic = 0.0

        if self._np_focus is None:
            return False

        log_ret = self._to_log_return(value)
        if log_ret is None:
            return False

        if len(self._history) < self.config.min_observations + self.config.return_window:
            self._np_focus.update(log_ret)
            return False

        if self._ticks_since_change < self.config.cooldown_ticks:
            self._np_focus.update(log_ret)
            return False

        self._np_focus.update(log_ret)
        stat_list = self._np_focus.statistic()
        stat = max(stat_list) if stat_list else 0.0
        self._last_statistic = float(stat)

        if stat >= self.config.threshold:
            self._ticks_since_change = 0
            cp = self._np_focus.changepoint()
            cp_idx = cp.get("changepoint", len(self._history)) if isinstance(cp, dict) else len(self._history)
            self._change_points.append(cp_idx + self.config.return_window)
            logger.info(
                "FOCuS changepoint #%d at idx=%d (stat=%.2f >= %.2f), reinitializing",
                len(self._change_points), cp_idx, stat, self.config.threshold,
            )
            self._init_detector()
            return True

        return False

    def reset(self):
        self._init_detector()
        self._ticks_since_change = 0
        self._last_statistic = 0.0
        self._history = []
        self._change_points = []
        self._price_buffer = []

    @property
    def statistic(self) -> float:
        return self._last_statistic

    @property
    def change_points(self) -> List[int]:
        return list(self._change_points)


# ---------------------------------------------------------------------------
# Layer 2: CUSUM on forecast residuals
# ---------------------------------------------------------------------------

@dataclass
class CusumConfig:
    """Configuration for Page's CUSUM on standardized forecast residuals."""
    k: float = 0.3          # reference value (magnitude of shift to detect)
    h: float = 3.0          # control limit (false alarm vs detection delay)
    burn_in: int = 12       # observations before first alert allowed
    ewma_alpha: float = 0.2  # smoothing for residual std estimate


class ForecastHealthMonitor:
    """
    Monitors a forecast stream's residuals using Page's CUSUM.

    When the forecast becomes systematically biased (the CUSUM
    crosses the control limit), this signals that the underlying
    data-generating process has changed -- i.e. the forecast
    is no longer trustworthy.
    """

    def __init__(self, config: CusumConfig = None):
        self.config = config or CusumConfig()
        self._n: int = 0
        self._s_pos: float = 0.0
        self._s_neg: float = 0.0
        self._running_std: float = 0.0
        self._running_mean: float = 0.0
        self._alerts: List[Dict] = []

    def update(self, actual: float, forecast: float) -> Tuple[bool, str]:
        """
        Feed one (actual, forecast) pair.
        Returns (alert_triggered, message).
        """
        residual = actual - forecast
        self._n += 1

        # Exponential moving estimates of residual mean and std
        if self._n == 1:
            self._running_mean = residual
            self._running_std = abs(residual) + 1e-8
        else:
            alpha = self.config.ewma_alpha
            self._running_mean = alpha * residual + (1 - alpha) * self._running_mean
            sq_diff = (residual - self._running_mean) ** 2
            self._running_std = np.sqrt(
                alpha * sq_diff
                + (1 - alpha) * self._running_std ** 2
            ) + 1e-8

        # Standardize
        z = (residual - self._running_mean) / self._running_std

        # Page's CUSUM
        k = self.config.k
        self._s_pos = max(0.0, self._s_pos + z - k)
        self._s_neg = max(0.0, self._s_neg - z - k)

        if self._n < self.config.burn_in:
            return False, ""

        h = self.config.h
        if self._s_pos > h:
            cusum_val = self._s_pos
            self._s_pos = 0.0
            logger.info(
                "CUSUM+ alert at tick %d: stat=%.2f > h=%.2f, residual=%.3f",
                self._n, cusum_val, h, residual,
            )
            self._alerts.append({
                "tick": self._n,
                "direction": "UPWARD_BIAS",
                "magnitude": round(residual, 4),
                "message": (
                    f"Forecast systematically UNDER-estimating. "
                    f"CUSUM+ = {cusum_val:.2f} > h={h}. "
                    f"Last residual = {residual:.2f}. "
                    f"Likely regime change: prices rising faster than model expects."
                ),
            })
            return True, self._alerts[-1]["message"]

        if self._s_neg > h:
            cusum_val = self._s_neg
            self._s_neg = 0.0
            logger.info(
                "CUSUM- alert at tick %d: stat=%.2f > h=%.2f, residual=%.3f",
                self._n, cusum_val, h, residual,
            )
            self._alerts.append({
                "tick": self._n,
                "direction": "DOWNWARD_BIAS",
                "magnitude": round(residual, 4),
                "message": (
                    f"Forecast systematically OVER-estimating. "
                    f"CUSUM- = {cusum_val:.2f} > h={h}. "
                    f"Last residual = {residual:.2f}. "
                    f"Likely regime change: prices falling faster than model expects."
                ),
            })
            return True, self._alerts[-1]["message"]

        return False, ""

    def reset(self):
        self._n = 0
        self._s_pos = 0.0
        self._s_neg = 0.0
        self._running_std = 0.0
        self._running_mean = 0.0
        self._alerts = []

    @property
    def s_positive(self) -> float:
        return self._s_pos

    @property
    def s_negative(self) -> float:
        return self._s_neg

    @property
    def alerts(self) -> List[Dict]:
        return list(self._alerts)


# ---------------------------------------------------------------------------
# Combined Regime Monitor
# ---------------------------------------------------------------------------

@dataclass
class RegimeStatus:
    """Snapshot of the regime detection state at a point in time."""
    tick: int
    focus_statistic: float
    cusum_pos: float
    cusum_neg: float
    focus_triggered: bool
    cusum_triggered: bool
    regime_change: bool
    cusum_message: str = ""


class RegimeMonitor:
    """
    Combines FOCuS (raw price breaks) and CUSUM (forecast degradation)
    into a unified regime-change detection signal.

    Alert levels:
      GREEN  -- neither detector firing; forecast trustworthy
      YELLOW -- one detector firing; monitor closely
      RED    -- both detectors firing; regime change -- stop trusting forecast
    """

    def __init__(
        self,
        focus_config: FocusConfig = None,
        cusum_config: CusumConfig = None,
    ):
        self.focus = FocusDetector(focus_config)
        self.cusum = ForecastHealthMonitor(cusum_config)
        self._tick: int = 0
        self._status_history: List[RegimeStatus] = []
        self._last_focus_triggered: bool = False
        self._last_cusum_triggered: bool = False
        self._last_cusum_msg: str = ""

    def update(self, price: float, forecast: float = None) -> RegimeStatus:
        """
        Feed one observation. If `forecast` is None, only FOCuS runs (no CUSUM).

        Returns a RegimeStatus with the current alert level.
        """
        self._tick += 1
        focus_triggered = self.focus.update(price)
        cusum_triggered = False
        cusum_msg = ""

        if forecast is not None:
            cusum_triggered, cusum_msg = self.cusum.update(price, forecast)

        self._last_focus_triggered = focus_triggered
        self._last_cusum_triggered = cusum_triggered
        self._last_cusum_msg = cusum_msg

        regime_change = focus_triggered and cusum_triggered

        status = RegimeStatus(
            tick=self._tick,
            focus_statistic=self.focus.statistic,
            cusum_pos=self.cusum.s_positive,
            cusum_neg=self.cusum.s_negative,
            focus_triggered=focus_triggered,
            cusum_triggered=cusum_triggered,
            regime_change=regime_change,
            cusum_message=cusum_msg,
        )
        self._status_history.append(status)
        return status

    def reset(self):
        self.focus.reset()
        self.cusum.reset()
        self._tick = 0
        self._status_history = []

    @property
    def status_history(self) -> List[RegimeStatus]:
        return list(self._status_history)

    @property
    def alert_level(self) -> str:
        """Current alert level: GREEN, YELLOW, or RED."""
        if self._last_focus_triggered and self._last_cusum_triggered:
            return "RED"
        if self._last_focus_triggered or self._last_cusum_triggered:
            return "YELLOW"
        return "GREEN"
