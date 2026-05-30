"""Market data endpoints: prices, futures, sell offers, auctions."""

from fastapi import APIRouter, Query

from src.api.services import market_service

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/eua-prices")
def eua_prices() -> dict:
    return market_service.get_eua_prices()


@router.get("/futures")
def futures(limit: int = Query(500, ge=0)) -> dict:
    return market_service.get_futures(limit=limit)


@router.get("/sell-offers")
def sell_offers() -> list[dict]:
    return market_service.get_sell_offers()


@router.get("/auctions")
def auctions() -> list[dict]:
    return market_service.get_auctions()


@router.get("/auctions/next")
def next_auction() -> dict:
    return market_service.get_next_auction()
