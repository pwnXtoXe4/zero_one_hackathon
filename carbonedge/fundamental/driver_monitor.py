"""
Real-Time Driver Monitor.

Based on Maciejowski & Leonelli (2025) "Drivers of EU Carbon Futures via
Bayesian Networks" (arXiv:2505.10384). Their 20-variable BN proves:
  - Coal (#1 driver): 43% prob of high EUA vs 25% baseline (18pp swing)
  - MSCI Europe Energy Index (#2): 40% prob vs 27% baseline (13pp swing)
  - 95%+ of EUA-relevant information is contemporaneous (same-day)
  - Oil has a modest next-day lead (1 day)
  - Currencies, VIX, gold = noise for EUA trading
  - The gas-to-coal fuel-switch ratio modulates the correlation direction

Ren et al. (2025) "Hybrid DL Carbon Price Forecasting" (arXiv:2511.04988)
confirms the same feature set: coal, TTF gas, German power, Euro Stoxx,
EUR/USD, policy indicator are the key exogenous features.

Implementation
--------------
Monitors 3 key drivers (Maciejowski & Leonelli, 2025, §4):
  1. Coal price (ARA API-2, front-year) — monthly return
  2. MSCI Europe Energy Index — monthly return
  3. Gas-to-coal ratio (TTF/coal) — fuel-switch indicator

Signal logic (from BN conditional probabilities in Maciejowski §4.2):
  coal_up & energy_up  → BULLISH  (both key drivers point to high EUA)
  coal_down & energy_down → BEARISH
  gas/coal_ratio > 1.5× median → BEARISH (utilities switch coal→gas, fewer allowances needed)
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import warnings

import numpy as np

logger = logging.getLogger(__name__)

# Maciejowski & Leonelli (2025) BN-derived heuristics — configurable
FUEL_SWITCH_BEARISH_RATIO = 1.5   # gas/coal > 1.5x median -> bearish
FUEL_SWITCH_BULLISH_RATIO = 0.5   # gas/coal < 0.5x median -> bullish


@dataclass
class DriverState:
    """Snapshot of the 3-key driver monitor at a point in time."""
    date: str
    coal_monthly_return: float          # 22-day (1-month) log return
    energy_sector_monthly_return: float # MSCI Europe Energy 1-month return
    gas_to_coal_ratio: float           # TTF / coal ratio
    gas_to_coal_ratio_median: float    # historical median of the ratio

    @property
    def direction_signal(self) -> int:
        """
        Maciejowski & Leonelli (2025) BN logic:
          +1 = bullish (both coal and energy sector rising)
          -1 = bearish (both falling; or gas/coal ratio extreme)
          0  = neutral
        """
        signal = 0
        if self.coal_monthly_return > 0 and self.energy_sector_monthly_return > 0:
            signal += 1
        elif self.coal_monthly_return < 0 and self.energy_sector_monthly_return < 0:
            signal -= 1

        # Gas-to-coal fuel switch: high ratio → power gen switches to gas →
        # fewer coal allowances needed → bearish for EUA
        if self.gas_to_coal_ratio_median > 0:
            ratio = self.gas_to_coal_ratio / self.gas_to_coal_ratio_median
            if ratio > FUEL_SWITCH_BEARISH_RATIO:
                signal -= 1
            elif ratio < FUEL_SWITCH_BULLISH_RATIO:
                signal += 1

        return max(-1, min(1, signal))

    @property
    def signal_label(self) -> str:
        s = self.direction_signal
        if s > 0:
            return "BULLISH"
        if s < 0:
            return "BEARISH"
        return "NEUTRAL"


@dataclass
class DriverMonitor:
    """
    Monitors the 3 key EUA price drivers identified by
    Maciejowski & Leonelli (2025) from a 20-variable Bayesian Network.

    Parameters
    ----------
    lookback : rolling window (months) for computing returns and medians
    """
    lookback: int = 22  # trading days ≈ 1 month
    _coal_history: List[float] = field(default_factory=list)
    _energy_history: List[float] = field(default_factory=list)
    _gas_history: List[float] = field(default_factory=list)
    _ratio_history: List[float] = field(default_factory=list)
    _states: List[DriverState] = field(default_factory=list)

    def update(
        self,
        date: str,
        coal_price: float,
        energy_index: float,
        gas_price: float,
    ) -> DriverState:
        """
        Feed one day of driver data. Returns the current DriverState.

        Parameters
        ----------
        date : YYYY-MM-DD
        coal_price : ARA API-2 coal front-year (or proxy)
        energy_index : MSCI Europe Energy Index (MXEU0EN)
        gas_price : TTF natural gas front-month
        """
        self._coal_history.append(coal_price)
        self._energy_history.append(energy_index)
        self._gas_history.append(gas_price)

        # Trim history to lookback
        if len(self._coal_history) > self.lookback + 1:
            self._coal_history = self._coal_history[-(self.lookback + 1):]
        if len(self._energy_history) > self.lookback + 1:
            self._energy_history = self._energy_history[-(self.lookback + 1):]
        if len(self._gas_history) > self.lookback + 1:
            self._gas_history = self._gas_history[-(self.lookback + 1):]

        coal_ret = 0.0
        if len(self._coal_history) >= self.lookback + 1:
            coal_ret = np.log(self._coal_history[-1] / self._coal_history[0])

        energy_ret = 0.0
        if len(self._energy_history) >= self.lookback + 1:
            energy_ret = np.log(self._energy_history[-1] / self._energy_history[0])

        # Gas-to-coal ratio
        if coal_price <= 0:
            gcr = float("inf")
            msg = (
                f"DriverMonitor.update: coal_price={coal_price} <= 0, "
                "gas-to-coal ratio set to inf. Fuel-switch signal unreliable."
            )
            warnings.warn(msg)
            logger.warning(msg)
        else:
            gcr = gas_price / coal_price
        self._ratio_history.append(gcr)

        # Historical median of the ratio
        gcr_median = np.median(self._ratio_history) if self._ratio_history else 0.0

        state = DriverState(
            date=date,
            coal_monthly_return=round(coal_ret, 6),
            energy_sector_monthly_return=round(energy_ret, 6),
            gas_to_coal_ratio=round(gcr, 4),
            gas_to_coal_ratio_median=round(gcr_median, 4),
        )
        self._states.append(state)
        return state

    def update_monthly(
        self,
        date: str,
        coal_price: float,
        energy_index: float,
        gas_price: float,
    ) -> DriverState:
        """
        Convenience wrapper that computes 1-month returns directly
        assuming the caller provides monthly data.
        """
        self._coal_history.append(coal_price)
        self._energy_history.append(energy_index)
        self._gas_history.append(gas_price)

        coal_ret = 0.0
        if len(self._coal_history) >= 2:
            coal_ret = np.log(self._coal_history[-1] / self._coal_history[-2])

        energy_ret = 0.0
        if len(self._energy_history) >= 2:
            energy_ret = np.log(self._energy_history[-1] / self._energy_history[-2])

        if coal_price <= 0:
            gcr = float("inf")
            msg = (
                f"DriverMonitor.update_monthly: coal_price={coal_price} <= 0, "
                "gas-to-coal ratio set to inf. Fuel-switch signal unreliable."
            )
            warnings.warn(msg)
            logger.warning(msg)
        else:
            gcr = gas_price / coal_price
        self._ratio_history.append(gcr)
        gcr_median = np.median(self._ratio_history) if self._ratio_history else 0.0

        state = DriverState(
            date=date,
            coal_monthly_return=round(coal_ret, 6),
            energy_sector_monthly_return=round(energy_ret, 6),
            gas_to_coal_ratio=round(gcr, 4),
            gas_to_coal_ratio_median=round(gcr_median, 4),
        )
        self._states.append(state)
        return state

    @property
    def latest(self) -> Optional[DriverState]:
        return self._states[-1] if self._states else None

    @property
    def history(self) -> List[DriverState]:
        return list(self._states)

    def reset(self):
        self._coal_history = []
        self._energy_history = []
        self._gas_history = []
        self._ratio_history = []
        self._states = []
