"""Forecast endpoints: request template + Sybilion submission."""

from typing import Any

from fastapi import APIRouter, Body

from src.api.services import forecast_service

router = APIRouter(prefix="/forecasts", tags=["forecasts"])


@router.get("/request-template")
def request_template() -> dict:
    return forecast_service.get_request_template()


@router.post("/sybilion")
def submit_sybilion(body: dict[str, Any] = Body(...)) -> dict:
    return forecast_service.submit_to_sybilion(body)
