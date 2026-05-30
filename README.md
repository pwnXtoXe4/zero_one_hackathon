# Carbon Backend API

## Install

Install dependencies:
```sh
pip install -r requirements.txt
```

## Environment

Create `.env` using template in `.env.example`
```sh
mv .env.example .env
```

Paste your `Sybilion API Key` and (optional) your `OpenAI API Key` into the required fields in `.env`.

## Run
uvicorn src.api.main:app --reload

## API Docs
http://localhost:8000/docs

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /health | Health check |
| GET | /companies | All companies |
| GET | /companies/{id} | Single company |
| GET | /companies/{id}/position | Long/short position |
| GET | /market/eua-prices | EUA price history (chart format) |
| GET | /market/futures?limit=500 | Carbon futures data |
| GET | /market/sell-offers | Mock seller offers |
| GET | /market/auctions | Mock auction calendar |
| GET | /market/auctions/next | Next upcoming auction |
| GET | /forecasts/request-template | Sybilion request template |
| POST | /forecasts/sybilion | Submit forecast to Sybilion |
| POST | /decisions/run | Run decision engine (stub) |
| POST | /decisions/scenario | Run scenario simulation (stub) |

## Notes
- Decision engine expects: from src.engine.agent import CarbonEdgeAgent
- Sybilion API: https://api.sybilion.dev (NOT mcp.sybilion.dev)
- No database needed — all data from JSON/CSV files
