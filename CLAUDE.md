# CarbonEdge — Project Context for Claude Code

## What This Project Is

CarbonEdge is a 36h hackathon project (Zero One Hackathon). A CO2/EUA procurement intelligence platform that uses the **Sybilion probabilistic forecasting API** to help EU-ETS companies decide when and how to buy carbon certificates.

## Team Roles

| Role | Owner | Status |
|------|-------|--------|
| Backend Infrastructure | Florian Zainzinger | ✅ DONE |
| Decision Engine Logic | Another teammate | ❌ `src/engine/` not built yet |
| Frontend | Another teammate | ❌ Waiting for APIs |

## Current Repo State (updated 30.05.2026)

### ✅ Done

| What | Where |
|------|-------|
| FastAPI backend (CORS open, 13 endpoints) | `src/api/` |
| Health, companies, position routes | `src/api/routes/health.py`, `companies.py` |
| Market data routes (prices, futures, offers, auctions) | `src/api/routes/market.py` |
| Forecast routes (template + Sybilion submission) | `src/api/routes/forecasts.py` |
| Decision adapter stubs (engine integration points) | `src/api/routes/decisions.py` |
| Service layer (file loading, CSV parsing, position calc) | `src/api/services/` |
| Sybilion API wrapper (caching + mock fallback) | `src/sybilion/client.py` |
| Pydantic schemas (ForecastRequest, ExternalDriver, etc.) | `src/sybilion/schema.py` |
| Keyword sets (4 layers: Regulatory, Market, Technology, Macro) | `src/sybilion/keywords.py` |
| 3 synthetic companies | `data/mock/companies.json` |
| 4 synthetic seller offers | `data/mock/sell_offers.json` |
| 5 synthetic auction entries | `data/mock/auction_calendar.json` |
| Real EUA carbon prices (Jan 2021 – May 2026, 67 points) | `data/raw/eua_prices_monthly.json` |
| Daily carbon futures 2015-2026 (2849 rows, UTF-8 BOM fixed) | `data/raw/carbon_emission_futures_data.csv` |
| Ready-to-submit Sybilion forecast request | `data/prepared/eua_forecast_request.json` |
| Design document (656 lines) | `IDEA_CARBON_REDUCTION.md` |
| Frontend API contract | `FRONTEND_API_CONTRACT.md` |
| Submission templates (unfilled) | `submission/` |
| README with install + endpoint table | `README.md` |

### ❌ Not yet built

- Decision engine (`src/engine/agent.py` — teammate's scope)
- Frontend
- Submission report (template only)

## All API Endpoints

| Method | Path | Status |
|--------|------|--------|
| GET | `/` | Service info |
| GET | `/health` | `{"status":"ok"}` |
| GET | `/companies` | 3 mock companies |
| GET | `/companies/{id}` | Single company + 404 |
| GET | `/companies/{id}/position` | LONG/SHORT calculation |
| GET | `/market/eua-prices` | 65 months, chart-ready array |
| GET | `/market/futures?limit=500` | 2849 rows, CSV → JSON |
| GET | `/market/sell-offers` | 4 mock sellers |
| GET | `/market/auctions` | 5 mock auctions |
| GET | `/market/auctions/next` | Nearest future auction |
| GET | `/forecasts/request-template` | Sybilion request JSON |
| POST | `/forecasts/sybilion` | Submit to Sybilion or mock fallback |
| POST | `/decisions/run` | Engine stub → mock_engine_not_connected |
| POST | `/decisions/scenario` | Scenario stub → mock_engine_not_connected |

All endpoints verified working (`python -m compileall src/api` clean, live server tested).

## Decision Engine Integration

The backend is ready for the decision teammate. They must create:

```
src/engine/
├── __init__.py
├── agent.py          # CarbonEdgeAgent class with run() method
└── scenario_manager.py  # ScenarioManager with run_scenario() method
```

The adapter in `src/api/services/decision_adapter.py` tries:
```python
from src.engine.agent import CarbonEdgeAgent
```

If import fails → returns `"status": "mock_engine_not_connected"` with available market data URLs.
If import succeeds → calls the engine and returns real decision output.

## Tech Stack

- **Language:** Python 3.11+
- **Backend:** FastAPI + Uvicorn
- **Data:** JSON files + CSV (NO database)
- **Forecasting:** Sybilion API (api.sybilion.dev)
- **No Docker, no ORM, no auth**

## Sybilion Integration (Critical)

- **Correct API endpoint:** `https://api.sybilion.dev`
- **Auth header:** `Authorization: Bearer <token>`
- **Token env var:** `SYBILION_API_TOKEN`
- **SDK package:** `sybilion` (in requirements.txt)
- **DO NOT use:** `mcp.sybilion.dev` — MCP proxy has user-mapping bugs
- **Account:** `e909b765`, Tier 4, hackathon grant ~€10,000 (expires June 1 2026)
- The existing `src/sybilion/client.py` uses the `sybilion` SDK which connects correctly
- **Current limitation:** venv lacks `pandas` → Sybilion wrapper falls back to mock. Install with: `pip install pandas`

## Known Issues & Fixes

1. **CSV BOM encoding** — `carbon_emission_futures_data.csv` has UTF-8 BOM. Fixed in `market_service.py` by using `encoding="utf-8-sig"`.
2. **Sybilion mock fallback** — `POST /forecasts/sybilion` returns mock because venv lacks `pandas`. Install `pandas` + set `SYBILION_API_TOKEN` for live calls.
3. **Decision endpoints mock** — Both `/decisions/run` and `/decisions/scenario` return `mock_engine_not_connected` until teammate implements `src/engine/agent.py`.

## How to Run

```bash
pip install -r requirements.txt
uvicorn src.api.main:app --reload
# Docs at http://localhost:8000/docs
```

## Requirements (current)

```
sybilion
scipy>=1.10.0
pytest>=8.0.0
fastapi
uvicorn
```
