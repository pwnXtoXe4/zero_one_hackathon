"""Integration point for the decision engine (src/engine/).

This module owns NO decision logic. It loads the company position and a
forecast, then attempts to hand off to ``CarbonEdgeAgent``. Until the engine
teammate adds ``src/engine/agent.py``, every endpoint returns a structured
mock response so the frontend has a stable contract.
"""

import glob
import json
from typing import Any, Optional

from fastapi import HTTPException

from src.api.services import PREPARED_DIR, company_service, forecast_service

SCENARIO_EVENTS = [
    "msr_auction_cut",
    "ets_cap_accelerated",
    "ets_cap_loosened",
    "gas_price_spike",
    "industrial_demand_drop",
    "cbam_accelerated",
    "renewable_energy_boom",
]

_MARKET_DATA_LINKS = {
    "auctions": "/market/auctions",
    "sell_offers": "/market/sell-offers",
    "prices": "/market/eua-prices",
    "next_auction": "/market/auctions/next",
}

_ENGINE_HINT = (
    "Expected: from src.engine.agent import CarbonEdgeAgent"
)


def _require_company(company_id: str) -> dict:
    company = company_service.get_company(company_id)
    if company is None:
        raise HTTPException(status_code=404, detail=f"Company '{company_id}' not found")
    return company


def _load_forecast(forecast_source: str) -> Optional[dict]:
    """Best-effort forecast load for the requested source.

    Returns None rather than raising, so a missing forecast never blocks the
    integration stub from returning a useful response.
    """
    if forecast_source == "sybilion":
        try:
            body = forecast_service.get_request_template()
            return forecast_service.submit_to_sybilion(body)
        except Exception:
            return None

    if forecast_source in ("cache", "mock"):
        # Prefer the named, known-good EUA price artifact, then the raw live
        # Sybilion dump, then any globbed cache_*.json. The engine expects the
        # Sybilion body under a top-level "forecast" key, so a raw dump
        # (data.forecast_series at the root) is wrapped before returning.
        named = PREPARED_DIR / "eua_price_forecast.json"
        live = PREPARED_DIR / "live_forecast.json"
        candidates = []
        if named.exists():
            candidates.append(str(named))
        if live.exists():
            candidates.append(str(live))
        if not candidates:
            candidates = sorted(glob.glob(str(PREPARED_DIR / "cache_*.json")))

        for path in candidates:
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
            except (OSError, json.JSONDecodeError):
                continue

            # Raw live_forecast.json dump → wrap so the engine can parse it.
            if "forecast" not in data and "forecast_series" in data.get("data", {}):
                return {"status": "ok", "forecast": data}
            return data
        return None

    return None


def run_decision(company_id: str, forecast_source: str = "cache") -> dict:
    """Load position + forecast, then delegate to the engine if available."""
    company = _require_company(company_id)
    position = company_service.compute_position(company)
    forecast = _load_forecast(forecast_source)

    try:
        from src.engine.agent import CarbonEdgeAgent  # type: ignore

        agent = CarbonEdgeAgent()
        decision = agent.run(
            company=company,
            position=position,
            forecast=forecast,
            forecast_source=forecast_source,
        )
        return {
            "status": "ok",
            "company_id": company_id,
            "forecast_source": forecast_source,
            "position": _position_payload(position),
            "decision": decision,
            "engine": {"connected": True},
        }
    except (ImportError, AttributeError):
        return {
            "status": "mock_engine_not_connected",
            "message": f"Decision engine not connected yet. {_ENGINE_HINT}",
            "company_id": company_id,
            "forecast_source": forecast_source,
            "position": _position_payload(position),
            "available_market_data": _MARKET_DATA_LINKS,
            "engine": {"connected": False},
        }


def run_scenario(
    company_id: str, event: str, forecast_source: str = "cache"
) -> dict:
    """Run a baseline -> event -> diff scenario via the engine if available."""
    company = _require_company(company_id)
    position = company_service.compute_position(company)
    forecast = _load_forecast(forecast_source)

    try:
        from src.engine.agent import CarbonEdgeAgent  # type: ignore
        from src.engine.agent import ScenarioManager  # type: ignore

        agent = CarbonEdgeAgent()
        manager = ScenarioManager(agent)
        result = manager.run_scenario(
            company=company,
            position=position,
            forecast=forecast,
            event=event,
            forecast_source=forecast_source,
        )
        return {
            "status": "ok",
            "company_id": company_id,
            "event": event,
            "forecast_source": forecast_source,
            "position": _position_payload(position),
            "scenario": result,
            "engine": {"connected": True},
        }
    except (ImportError, AttributeError):
        return {
            "status": "mock_engine_not_connected",
            "company_id": company_id,
            "event": event,
            "message": (
                "Scenario engine not available. Expected: from src.engine.agent "
                "import CarbonEdgeAgent with ScenarioManager"
            ),
            "engine": {"connected": False},
            "available_events": SCENARIO_EVENTS,
        }


def _position_payload(position: dict[str, Any]) -> dict:
    """Trim the full position summary to the fields the engine contract expects."""
    return {
        "required_allowances": position["required_allowances"],
        "available_allowances": position["available_allowances"],
        "net_position": position["net_position"],
        "status": position["status"],
    }
