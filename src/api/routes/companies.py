"""Company profile and position endpoints. Routes only call the service."""

from fastapi import APIRouter, HTTPException

from src.api.services import company_service, emissions_service

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("")
def list_companies() -> list[dict]:
    return company_service.load_companies()


@router.get("/{company_id}")
def get_company(company_id: str) -> dict:
    company = company_service.get_company(company_id)
    if company is None:
        raise HTTPException(status_code=404, detail=f"Company '{company_id}' not found")
    return company


@router.get("/{company_id}/position")
def get_company_position(company_id: str) -> dict:
    company = company_service.get_company(company_id)
    if company is None:
        raise HTTPException(status_code=404, detail=f"Company '{company_id}' not found")
    return company_service.compute_position(company)


@router.get("/{company_id}/emissions-outlook")
def get_company_emissions_outlook(company_id: str) -> dict:
    outlook = emissions_service.emissions_outlook(company_id)
    if outlook is None:
        raise HTTPException(status_code=404, detail=f"Company '{company_id}' not found")
    return outlook
