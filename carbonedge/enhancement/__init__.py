"""
Forecast Enhancement Layer

The 9 arXiv papers feed this layer — it adjusts Sybilion's output,
does NOT compete with it. Each module produces a multiplier or bias
that the procurement optimizer consumes.

  epu_modulator     : EPU index -> volatility multiplier (Dai et al. 2020)
  regime_enhancer   : FOCuS + CUSUM + bubble test -> confidence multiplier (Friedrich 2019)
  driver_filter     : coal, MSCI Energy, gas/coal -> front/back-load bias (Maciejowski & Leonelli 2025)
  structural_context: cap-emissions-MSR -> reasoning text (Bastianin et al. 2024)
"""

from .epu_modulator import EpuModulator, EpuState
from .regime_enhancer import RegimeBand, get_confidence_multiplier
from .driver_filter import DriverFilter, DriverBias
from .structural_context import StructuralContext, StructuralBackdrop
