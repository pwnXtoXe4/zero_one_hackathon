"""CarbonEdge engine package.

Thin bridge exposing the real ``carbonedge`` 5-layer decision pipeline through
the class interface the API's decision_adapter expects.
"""

from src.engine.agent import CarbonEdgeAgent

__all__ = ["CarbonEdgeAgent"]
