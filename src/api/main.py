"""Carbon Backend API — FastAPI app.

Run with:
    uvicorn src.api.main:app --reload
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.routes import companies, decisions, forecasts, health, market

app = FastAPI(title="Carbon Backend API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(companies.router)
app.include_router(market.router)
app.include_router(forecasts.router)
app.include_router(decisions.router)


@app.get("/")
def root() -> dict:
    return {"service": "carbon-backend", "docs": "/docs"}


@app.exception_handler(FileNotFoundError)
def _file_not_found_handler(request: Request, exc: FileNotFoundError) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"detail": f"Required data file missing: {exc}"},
    )


@app.exception_handler(ValueError)
def _value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"detail": f"Invalid data or request: {exc}"},
    )
