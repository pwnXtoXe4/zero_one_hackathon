"""
Procurement Optimizer

Converts adjusted Sybilion forecast bands into a concrete procurement plan.

Abate et al. (2021) "Contracts in Electricity Markets under EU ETS:
A Stochastic Programming Approach" (arXiv:2104.15062) provides the
CVaR framework for optimizing allowance purchases under uncertainty.
"""

from .optimizer import (
    ProcurementPlan,
    PurchaseWindow,
    optimize_procurement,
)
from .ladder_rules import ladder_fallback, LadderInput
