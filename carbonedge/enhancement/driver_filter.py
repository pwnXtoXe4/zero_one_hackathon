"""
Driver Filter

Maciejowski & Leonelli (2025) "Uncovering Drivers of EU Carbon Futures
with Bayesian Networks" (arXiv:2505.10384) found:
  - Coal (#1): 43% prob high EUA vs 25% baseline (18pp swing)
  - MSCI Europe Energy (#2): 40% prob vs 27% baseline (13pp swing)
  - Gas/coal fuel-switch ratio modulates direction
  - 95%+ of EUA-relevant info is contemporaneous

The DriverFilter wraps the existing DriverMonitor and outputs a
front-load / back-load bias for the procurement optimizer.
It does NOT produce a competing forecast — it biases the optimizer
toward buying earlier or later.
"""

from dataclasses import dataclass
from typing import Optional

from ..fundamental.driver_monitor import DriverMonitor, DriverState

BIAS_FRONT_LOAD = +0.3   # pull purchases forward by 30%
BIAS_NEUTRAL = 0.0
BIAS_BACK_LOAD = -0.3    # push purchases back by 30%


@dataclass
class DriverBias:
    """Procurement bias from real-time driver state."""
    bias: float          # -0.3 to +0.3, applied to front-load allocation
    signal: str          # BULLISH / NEUTRAL / BEARISH
    coal_rising: bool
    energy_rising: bool
    fuel_switch_bearish: bool
    reasoning: str


@dataclass
class DriverFilter:
    """
    Filters which Sybilion drivers to weight and computes front/back-load bias.
    """
    monitor: DriverMonitor

    def evaluate(self) -> DriverBias:
        """Compute current procurement bias from latest driver state."""
        state = self.monitor.latest

        if state is None:
            return DriverBias(
                bias=BIAS_NEUTRAL, signal="NEUTRAL",
                coal_rising=False, energy_rising=False,
                fuel_switch_bearish=False,
                reasoning="No driver data available. Using neutral allocation.",
            )

        coal_rising = state.coal_monthly_return > 0
        energy_rising = state.energy_sector_monthly_return > 0

        # Fuel-switch check
        fuel_switch_bearish = False
        fuel_switch_bullish = False
        if state.gas_to_coal_ratio_median > 0:
            ratio = state.gas_to_coal_ratio / state.gas_to_coal_ratio_median
            if ratio > 1.5:
                fuel_switch_bearish = True
            elif ratio < 0.5:
                fuel_switch_bullish = True

        bias = BIAS_NEUTRAL
        signal = state.signal_label
        reasons = []

        if coal_rising and energy_rising:
            bias += BIAS_FRONT_LOAD
            reasons.append(
                f"Coal + MSCI Energy both rising (Maciejowski & Leonelli 2025: "
                f"coal={state.coal_monthly_return:+.1%}, energy={state.energy_sector_monthly_return:+.1%})"
            )
        elif not coal_rising and not energy_rising:
            bias += BIAS_BACK_LOAD
            reasons.append(
                f"Both key drivers declining (coal={state.coal_monthly_return:+.1%}, "
                f"energy={state.energy_sector_monthly_return:+.1%})"
            )

        if fuel_switch_bearish:
            bias += BIAS_BACK_LOAD * 0.5
            reasons.append(
                f"Gas/coal ratio {ratio:.1f}x > 1.5x median: fuel-switch bearish"
            )
        elif fuel_switch_bullish:
            bias += BIAS_FRONT_LOAD * 0.5
            reasons.append(
                f"Gas/coal ratio {ratio:.1f}x < 0.5x median: fuel-switch bullish"
            )

        if not reasons:
            reasons.append("Drivers mixed or neutral — balanced allocation.")

        return DriverBias(
            bias=max(-0.5, min(0.5, bias)),
            signal=signal,
            coal_rising=coal_rising,
            energy_rising=energy_rising,
            fuel_switch_bearish=fuel_switch_bearish,
            reasoning="; ".join(reasons),
        )
