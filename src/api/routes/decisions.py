"""Decision engine integration endpoints (stubs until src/engine/ exists)."""

from pydantic import BaseModel

from fastapi import APIRouter

from src.api.services import decision_adapter

router = APIRouter(prefix="/decisions", tags=["decisions"])


class DecisionRunRequest(BaseModel):
    company_id: str
    forecast_source: str = "cache"  # "cache" | "sybilion" | "mock"


class ScenarioRequest(BaseModel):
    company_id: str
    event: str
    forecast_source: str = "cache"


@router.post("/run")
def run_decision(req: DecisionRunRequest) -> dict:
    return decision_adapter.run_decision(req.company_id, req.forecast_source)


@router.post("/scenario")
def run_scenario(req: ScenarioRequest) -> dict:
    return decision_adapter.run_scenario(
        req.company_id, req.event, req.forecast_source
    )
