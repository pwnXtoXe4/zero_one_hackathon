"""
Fundamental supply-demand model for EU ETS carbon price direction.

Based on Bastianin et al. (2024) and Maciejowski & Leonelli (2025):
  Layer 1: cap schedule, verified emissions, MSR → BUY/DEFER direction
  Layer 2: real-time driver monitor (coal, MSCI Energy, gas/coal ratio)
  Layer 3: ensemble decision matrix (fundamental × real-time × regime)
"""
